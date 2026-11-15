"""s67 PRIVATE v69 audio-integration build driver (source only; NOT run). Never installs, launches or opens a device.

v69 = the verified v68 recorder-reserve link (155 inputs) with exactly TWO objects replaced:
  main.cpp.obj        <- combined telemetry r1 main.cpp (8022b148) + header (c84258e1)
  debug_server.c.obj  <- combined telemetry r1 debug_server.c (b50aef2a)
Every other link input, the v68 renderer object, libSDL3.a and the link flags are reused byte-for-byte.

Two phases, each a SEPARATE granted job inside the qualified outer Job (wall <= 120 s, 1024 MiB, one CPU,
BelowNormal); the outer Job is authoritative and its kill/refusal receipt is FAILURE:
  --phase repro : recompile the UNMODIFIED v58 main.cpp and v67 debug_server.c with their recorded
                  arguments (only -o / -MF changed, -MD -MF added for main), in place. Both objects must be
                  byte-identical to the objects v68 links (911b117a / 1947bca3), proving this toolchain and
                  include closure still reproduce v68. Every dependency in the depfiles is hashed.
  --phase build : requires a PASS repro manifest (path + sha256). Compiles the patched copies with the same
                  arguments (+ one leading -I for the combined header, main only). Each depfile closure must
                  equal the repro closure except {source file, recomp_audio_drc.h}, with identical hashes for
                  every shared dependency. Then links with v68's response file with ONLY the two object paths
                  replaced; the other 153 recorded link inputs are re-hashed against v68 build.json.
Fails closed on any pin, closure, reproduction or link mismatch. Inner envelope 105 s per phase.
The compiler is hashed then executed by path; a swap in between is not excluded.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

try:
    import psutil  # optional: best-effort child creation time only
except ImportError:
    psutil = None

R = Path(r"C:/github/Einhander")
EV = R / "remaster-audit/dev-center-evidence/stage1-completion-20261112"
S67 = R / "remaster-audit/parallel-stages-20261114/s67/proposals"
PINS = {
    "v68_build_json": (EV / "sampling-build-v68-recorder-reserve-r1/build.json", "21944d697b27b6715edcf8a4ad67c76c2527b5bf5a3aa729b981fc34702af70e"),
    "v68_rsp": (EV / "sampling-build-v68-recorder-reserve-r1/Einhander_Recompiled.rsp", "c2b737c691b83aac0b0ab6bf6fecb853eba52f51f04827b8009ef2c9d3952130"),
    "v68_exe": (EV / "sampling-build-v68-recorder-reserve-r1/Einhander_Recompiled.exe", "5c1436ff778701d981410da61046aca60c0da60215a5f724523197b58199dfaa"),
    "v58_build_json": (EV / "sampling-build-v58-frame-phases/build.json", "7f4640f683571af20cc0430cb9fe816fbead89847800a3a73971d9110381c3c7"),
    "v67_build_json": (EV / "sampling-build-v67-decode-identity-r3/build.json", "85deaaf3f4870259b190a929675fae706897f91f1dc3e16b3d94d8f3752d6108"),
    "v58_main_cpp": (EV / "sampling-build-v58-frame-phases/main.cpp", "5c94d2dd17f52338515ac52df4f8fde04b4eb269ee49ba6bc42b6924bc6523c0"),
    "v67_debug_server_c": (EV / "sampling-build-v67-decode-identity-r3/src/debug_server.c", "10e31f8dc50cdf451776f18e4b468f95bb2c97d33f50816d9b9d193557af2eba"),
    "v58_main_obj": (EV / "sampling-build-v58-frame-phases/main.cpp.obj", "911b117aebb45d0414d54057bdde273aac43219dfafeecb08bacaf496d337dd3"),
    "v67_debug_obj": (EV / "sampling-build-v67-decode-identity-r3/debug_server.c.obj", "1947bca3cd81af078289a46a4e6d7017f1296edb4c93e650b30ec8f186ddf8b6"),
    "combined_main_cpp": (S67 / "audio-telemetry-combined-r1/main.cpp.proposed", "8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36"),
    "combined_debug_c": (S67 / "audio-telemetry-combined-r1/debug_server.c.proposed", "b50aef2a4de7ef8ceb621ffc681d072699f88cc5247357a435ebe405cebc0185"),
    "combined_header": (S67 / "audio-telemetry-combined-r1/recomp_audio_drc.h.proposed", "c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c"),
}
TOOLCHAIN_DIR = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")
TOOLCHAIN = {
    "clang.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
REPLACED = {"main": "main.cpp.obj", "debug": "debug_server.c.obj"}
CREATIONFLAGS = 0x08004000 if os.name == "nt" else 0   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
ENVELOPE_S = 105
CAPS = {"repro:main": 75, "repro:debug": 20, "build:main": 65, "build:debug": 20, "build:link": 15}
REQUIRED_RECEIPT = ("step", "argv", "cwd", "start_utc", "pid", "rc", "timed_out", "timeout_s", "elapsed_s", "stdout", "stderr")


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    return sha_bytes(Path(p).read_bytes())


def norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


class Budget:
    def __init__(self):
        self.t0 = time.monotonic()

    def left(self):
        return ENVELOPE_S - (time.monotonic() - self.t0)


def run_child(step, argv, cwd, budget, man):
    left = budget.left()
    if left < 5:
        man["reasons"].append(f"envelope exhausted before {step} ({left:.1f} s left)")
        return None
    timeout = min(CAPS[step], left)
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    rec = {"step": step, "argv": [str(x) for x in argv], "cwd": str(cwd), "start_utc": utc(), "pid": None,
           "rc": None, "timed_out": False, "timeout_s": round(timeout, 1), "creation_unix": None}
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATIONFLAGS, env=env)
    rec["pid"] = p.pid
    if psutil is None:
        rec["creation_note"] = "psutil not installed"
    else:
        try:
            rec["creation_unix"] = psutil.Process(p.pid).create_time()
        except psutil.Error as e:
            rec["creation_note"] = f"unavailable: {type(e).__name__} (process may have exited)"
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        rec["timed_out"] = True
        p.kill()
        out, err = p.communicate()   # bounded only by the outer Job
    rec["rc"] = p.returncode
    rec["elapsed_s"] = round(time.monotonic() - t0, 3)
    rec["stdout"] = out.decode("utf-8", errors="replace")
    rec["stderr"] = err.decode("utf-8", errors="replace")
    man["children"].append(rec)
    if any(k not in rec for k in REQUIRED_RECEIPT) or rec["rc"] is None:
        man["reasons"].append(f"incomplete receipt for {step}")
    return rec


def parse_depfile(path):
    """Make-style depfile from clang -MD: 'target: dep dep \\' lines, '\\ ' escapes a space."""
    text = Path(path).read_text(encoding="utf-8", errors="strict")
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    i = text.find(": ")
    if i < 0:
        raise ValueError(f"malformed depfile {path}")
    body, deps, cur, k = text[i + 2:], [], [], 0
    while k < len(body):
        c = body[k]
        if c == "\\" and k + 1 < len(body) and body[k + 1] == " ":
            cur.append(" "); k += 2; continue
        if c.isspace():
            if cur: deps.append("".join(cur)); cur = []
        else:
            cur.append(c)
        k += 1
    if cur: deps.append("".join(cur))
    return [norm(d) for d in deps]


def check_pins(man, keys):
    for k in keys:
        p, want = PINS[k]
        got = sha(p) if p.is_file() else None
        man["inputs"][k] = {"path": str(p), "sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"pin mismatch: {k}")
    tools = {}
    for n, want in TOOLCHAIN.items():
        f = TOOLCHAIN_DIR / n
        got = sha(f) if f.is_file() else None
        tools[n] = {"path": str(f), "sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"toolchain pin mismatch: {n}")
    man["inputs"]["toolchain"] = tools
    return not man["reasons"]


def recorded_args(label):
    """Exact recorded compile command: v58 build.json 'arguments' (main) / v67 build.json 'args' (debug)."""
    key, bj = ("compile-main.cpp", "v58_build_json") if label == "main" else ("compile-debug_server.c", "v67_build_json")
    b = json.loads(PINS[bj][0].read_bytes())
    cmds = [c for c in b["commands"] if c.get("label") == key]
    if len(cmds) != 1:
        raise ValueError(f"{key}: expected exactly one recorded command")
    args = list(cmds[0].get("arguments") or cmds[0].get("args"))
    return args, cmds[0].get("cwd")


def retarget(args, src_old, src_new, obj_new, dep_new):
    """Replace the -c source and -o object; set -MD -MF to dep_new (append if absent). Fail on ambiguity."""
    a = list(args)
    ci = [i for i, x in enumerate(a) if x == "-c"]
    oi = [i for i, x in enumerate(a) if x == "-o"]
    if len(ci) != 1 or len(oi) != 1 or norm(a[ci[0] + 1]) != norm(src_old):
        raise ValueError("recorded command does not have exactly one -c <expected source> and one -o")
    a[ci[0] + 1] = str(src_new)
    a[oi[0] + 1] = str(obj_new)
    mf = [i for i, x in enumerate(a) if x == "-MF"]
    if len(mf) > 1:
        raise ValueError("multiple -MF")
    if mf:
        a[mf[0] + 1] = str(dep_new)
        if "-MD" not in a:
            raise ValueError("-MF without -MD")
    else:
        a[ci[0]:ci[0]] = ["-MD", "-MF", str(dep_new)]
    return a


def compile_one(phase, label, src_old, src_new, extra_first_include, out, budget, man):
    args, cwd = recorded_args(label)
    obj = out / REPLACED[label]
    dep = out / (REPLACED[label] + ".d")
    a = retarget(args, src_old, src_new, obj, dep)
    if extra_first_include:
        a[1:1] = [f"-I{extra_first_include}"]
    if Path(a[0]).name not in ("clang.exe", "clang++.exe") or norm(Path(a[0]).parent) != norm(TOOLCHAIN_DIR):
        raise ValueError(f"{label}: recorded compiler is not the pinned toolchain: {a[0]}")
    rec = run_child(f"{phase}:{label}", a, cwd or R, budget, man)
    if rec is None or rec["timed_out"] or rec["rc"] != 0 or not obj.is_file() or not dep.is_file():
        man["reasons"].append(f"{phase}:{label} compile failed")
        return None
    deps = parse_depfile(dep)
    closure = {}
    for d in deps:
        if not Path(d).is_file():
            man["reasons"].append(f"{phase}:{label} dependency missing after compile: {d}")
            continue
        closure[d] = sha(d)
    return {"obj": str(obj), "obj_sha256": sha(obj), "depfile": str(dep), "depfile_sha256": sha(dep),
            "closure": closure, "closure_count": len(closure)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--phase", required=True, choices=("repro", "build"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--repro-manifest")
    ap.add_argument("--repro-manifest-sha256")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    try:
        out.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        print(f"refusing: {out} exists", file=sys.stderr)
        return 2
    man = {"driver": "build_v69_audio.py", "driver_sha256": sha(__file__), "phase": a.phase, "grant_id": a.grant_id,
           "out": str(out), "started_utc": utc(), "envelope_s": ENVELOPE_S, "caps_s": CAPS, "inputs": {},
           "children": [], "verdict": "FAIL", "reasons": [], "errors": [],
           "never": "no install, no launch, no SDL device open, no GPU",
           "note": "outer Job receipt is authoritative for wall/memory limits"}
    code = 1
    try:
        code = repro(out, man) if a.phase == "repro" else build(a, out, man)
    except Exception:
        man["errors"].append(traceback.format_exc())
        code = 1
    finally:
        if man["reasons"] or man["errors"]:
            man["verdict"] = "FAIL"
            code = code or 1
        man["finished_utc"] = utc()
        (out / "manifest.json").write_bytes(json.dumps(man, indent=2).encode("utf-8"))
    return code


def repro(out, man):
    budget = Budget()
    if not check_pins(man, ["v58_build_json", "v67_build_json", "v58_main_cpp", "v67_debug_server_c",
                            "v58_main_obj", "v67_debug_obj"]):
        return 2
    res = {}
    for label, src, want in (("main", PINS["v58_main_cpp"][0], PINS["v58_main_obj"][1]),
                             ("debug", PINS["v67_debug_server_c"][0], PINS["v67_debug_obj"][1])):
        r = compile_one("repro", label, src, src, None, out, budget, man)   # in place: original path kept
        if r is None:
            return 1
        r["reproduces_v68_object"] = r["obj_sha256"] == want
        r["expected_obj_sha256"] = want
        if not r["reproduces_v68_object"]:
            man["reasons"].append(f"repro:{label} object differs from the v68-linked object")
        res[label] = r
    for k in ("v58_main_cpp", "v67_debug_server_c"):   # originals untouched by the in-place compile
        if sha(PINS[k][0]) != PINS[k][1]:
            man["reasons"].append(f"{k} changed during repro")
    hdr = [d for d in res["main"]["closure"] if os.path.basename(d) == "recomp_audio_drc.h"]
    man["repro_main_audio_header"] = {d: res["main"]["closure"][d] for d in hdr}
    if len(hdr) != 1 or res["main"]["closure"][hdr[0]] != "70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29":
        man["reasons"].append("repro main.cpp did not include exactly one canonical recomp_audio_drc.h (70cb5acd)")
    if any(os.path.basename(d) == "recomp_audio_drc.h" for d in res["debug"]["closure"]):
        man["reasons"].append("debug_server.c unexpectedly includes recomp_audio_drc.h")
    man["repro"] = res
    if man["reasons"]:
        return 1
    man["verdict"] = "PASS"
    return 0


def build(a, out, man):
    budget = Budget()
    if not a.repro_manifest or not a.repro_manifest_sha256:
        man["reasons"].append("build needs --repro-manifest and --repro-manifest-sha256")
        return 2
    rm_path = Path(a.repro_manifest).resolve()
    rm_bytes = rm_path.read_bytes()
    man["inputs"]["repro_manifest"] = {"path": str(rm_path), "sha256": sha_bytes(rm_bytes), "expected": a.repro_manifest_sha256}
    if sha_bytes(rm_bytes) != a.repro_manifest_sha256:
        man["reasons"].append("pin mismatch: repro manifest")
        return 2
    rm = json.loads(rm_bytes)
    if rm.get("verdict") != "PASS" or rm.get("phase") != "repro":
        man["reasons"].append("repro manifest is not a PASS repro")
        return 2
    if not check_pins(man, list(PINS)):
        return 2

    # read-once hashed copies of the three changed sources
    copies = {}
    for key, rel in (("combined_main_cpp", "src/main.cpp"), ("combined_debug_c", "src/debug_server.c"),
                     ("combined_header", "include/recomp_audio_drc.h")):
        data = PINS[key][0].read_bytes()
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        copies[key] = dst
        ok = sha_bytes(data) == PINS[key][1] and sha(dst) == PINS[key][1]
        man["inputs"][key + "_copy"] = {"copy": str(dst), "read_sha256": sha_bytes(data), "copy_sha256": sha(dst), "ok": ok}
        if not ok:
            man["reasons"].append(f"pin mismatch: {key} copy")
    if man["reasons"]:
        return 2

    objdir = out / "obj"
    objdir.mkdir()
    built = {}
    plan = (("main", PINS["v58_main_cpp"][0], copies["combined_main_cpp"], copies["combined_header"].parent),
            ("debug", PINS["v67_debug_server_c"][0], copies["combined_debug_c"], None))
    for label, src_old, src_new, inc in plan:
        r = compile_one("build", label, src_old, src_new, inc, objdir, budget, man)
        if r is None:
            return 1
        # closure equality vs the reproduced v68 closure, except the source file and the audio header
        rc = rm["repro"][label]["closure"]
        skip_new = {norm(src_new)} | ({norm(copies["combined_header"])} if label == "main" else set())
        skip_old = {norm(src_old)} | (set(rm.get("repro_main_audio_header", {})) if label == "main" else set())
        a_set = {d: h for d, h in r["closure"].items() if d not in skip_new}
        b_set = {d: h for d, h in rc.items() if d not in skip_old}
        r["closure_equal_to_repro"] = a_set == b_set
        if not r["closure_equal_to_repro"]:
            only_new = sorted(set(a_set) - set(b_set))[:20]
            only_old = sorted(set(b_set) - set(a_set))[:20]
            changed = sorted(d for d in set(a_set) & set(b_set) if a_set[d] != b_set[d])[:20]
            r["closure_diff"] = {"only_build": only_new, "only_repro": only_old, "hash_changed": changed}
            man["reasons"].append(f"build:{label} include closure differs from the reproduced v68 closure")
        if label == "main" and norm(copies["combined_header"]) not in r["closure"]:
            man["reasons"].append("build main.cpp did not include the combined header copy")
        if label == "debug" and any(os.path.basename(d) == "recomp_audio_drc.h" for d in r["closure"]):
            man["reasons"].append("build debug_server.c unexpectedly includes recomp_audio_drc.h")
        built[label] = r
    man["build"] = built
    if man["reasons"]:
        return 1

    # link: v68 response file with exactly the two object paths replaced; other recorded inputs re-hashed
    v68 = json.loads(PINS["v68_build_json"][0].read_bytes())
    link_cmds = [c for c in v68["commands"] if c.get("label") == "link"]
    if len(link_cmds) != 1:
        man["reasons"].append("v68 build.json: expected one link command")
        return 1
    lc = link_cmds[0]
    old_main = str(PINS["v58_main_obj"][0]).replace("\\", "/")
    old_debug = str(PINS["v67_debug_obj"][0]).replace("\\", "/")
    rsp = PINS["v68_rsp"][0].read_bytes().decode("utf-8")
    for old in (old_main, old_debug):
        if rsp.count(old) != 1:
            man["reasons"].append(f"v68 rsp does not contain exactly one {old}")
            return 1
    rsp = rsp.replace(old_main, built["main"]["obj"].replace("\\", "/")).replace(old_debug, built["debug"]["obj"].replace("\\", "/"))
    new_rsp = out / "Einhander_Recompiled.v69.rsp"
    new_rsp.write_bytes(rsp.encode("utf-8"))
    retained, bad = 0, []
    for e in v68["link_inputs"]:
        p = e["path"]
        if norm(p) in (norm(PINS["v58_main_obj"][0]), norm(PINS["v67_debug_obj"][0])):
            continue
        got = sha(p) if Path(p).is_file() else None
        retained += 1
        if got != e["sha256"]:
            bad.append({"path": p, "sha256": got, "expected": e["sha256"]})
    man["link_inputs"] = {"recorded": len(v68["link_inputs"]), "retained_checked": retained, "mismatched": bad,
                          "replaced": {"main": built["main"]["obj_sha256"], "debug": built["debug"]["obj_sha256"]}}
    if retained != len(v68["link_inputs"]) - 2 or bad:
        man["reasons"].append("retained link inputs differ from v68 records")
        return 1
    exe = out / "Einhander_Recompiled.exe"
    args = list(lc["args"])
    ri = [i for i, x in enumerate(args) if x.startswith("@")]
    oi = [i for i, x in enumerate(args) if x == "-o"]
    if len(ri) != 1 or len(oi) != 1 or Path(args[0]).name != "clang++.exe":
        man["reasons"].append("v68 link command shape unexpected")
        return 1
    args[ri[0]] = "@" + str(new_rsp)
    args[oi[0] + 1] = str(exe)
    rec = run_child("build:link", args, lc["cwd"], budget, man)
    if rec is None or rec["timed_out"] or rec["rc"] != 0 or not exe.is_file():
        man["reasons"].append("link failed")
        return 1
    man["v69_executable"] = {"path": str(exe), "sha256": sha(exe), "bytes": exe.stat().st_size,
                             "v68_parent_sha256": PINS["v68_exe"][1], "installed": False, "launched": False}
    man["verdict"] = "PASS"
    return 0


if __name__ == "__main__":
    sys.exit(main())
