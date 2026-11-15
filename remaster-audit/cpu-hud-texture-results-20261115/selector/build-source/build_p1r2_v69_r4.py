"""build_p1r2_v69_r4.py - private CPU build of v69 + P1 r2 (player AND enemy colour rows) (claude-einhander-ui). NOT RUN by its author.

r4 vs r3 (5f713865, frozen): ONE change only. The pinned main is the clean 3-way merge main.v69-plus-p1r2.cpp (fe85c7e4)
  = git merge-file(ours=v69-plus-p1 d8abf287, base=P1 r1 994af594, theirs=P1 r2 91a2bcab), rc 0, no conflicts; its delta vs d8abf287
  equals the r2 delta vs 994af594 line for line (143 changed lines). Keymap .c/.h, rsp, closure and all other pins are unchanged.
  Every r3 "d8abf287" reference below refers to the copied main; for r4 read it as fe85c7e4.

r3 header (kept for history):

build_p1_v69_r3.py - private CPU build of v69 + P1 player-color (claude-einhander-ui). NOT RUN by its author.

r3 vs r2 (8a6f3146, frozen), per root msg_a882efe0:
  - deps:main now compares CONTENT, not only paths.
    - Every shared dependency must exist and hash-equal the v69 manifest's recorded build.main.closure (pinned bytes, 1142 entries).
    - Excluded are ONLY the v69 src/main.cpp and the old upload-index-hitch host_keymap.h; those are replaced by the copied main
      (d8abf287) and the new header (ba280651), and both must hash to their pins.
    - The audio header c84258e1 must be present with that hash.
    - The v69 closure keys must also equal the pinned v69 depfile's entries.
  - Every resolved dependency must exist (a missing file fails), and every path must be strictly C: (absolute, drive C:).
  - deps:keymap records the complete C:-only closure with hashes. The old D: closure of e03f07c5 is disclosed as UNKNOWN.
  - Old-keymap reproduction is not included (optional per root; no D: reads).

r2 header (kept for history):

r2 vs r1 (59891527, preserved unchanged), per root msg_5db128ff:
  1. The v69 manifest is pinned (e6ab30e9...). Its bytes are read ONCE, hash-verified, and only those bytes are parsed for argv.
  2. Every rsp file input (155) is pinned through retained-inputs.v69.tsv (d9eb77e0...).
     - 153 of those 155 hashes also appear in the frozen v68 build.json; main and debug are v69-new and pinned by the v69 manifest.
     - Every input is re-hashed at run time.
     - The new rsp must equal the v69 rsp token for token, except exactly two objects: main.cpp.obj and host_keymap.c.obj.
  3. Depfile closures:
     - main.cpp's new dependency set must EQUAL v69's, except the copied main.cpp and the new host_keymap.h.
       The audio header (recomp_audio_drc.h c84258e1) must remain.
     - host_keymap.c's closure must contain only C: paths, resolve host_keymap.h to the private header, and is hashed and recorded.
     - Every dependency of both new depfiles is hashed into the manifest.
  4. Child processes:
     - the pid and Windows creation time are recorded (best effort);
     - each invoked compiler path is hashed against its pin before the call;
     - children run BELOW_NORMAL with CREATE_NO_WINDOW and an explicit single-thread environment;
     - after a kill, communicate() is bounded.
     The outer qualified fa5 Job envelope remains authoritative for wall time and memory.
  5. Verdict and manifest:
     - PASS requires every REQUIRED_STEPS entry to be recorded ok. A missing step or any exception means FAIL.
     - The manifest is written exclusively and fsynced.
Never: install, launch, SDL device open, GPU, D: reads.
"""
import argparse, ctypes, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1 = HERE.parent
V69 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206")
SS8C = Path("C:/github/Einhander/windows-x64/build-ss8c")
TC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")
UPLOAD_HITCH_KEYMAP_H = "C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime/include/host_keymap.h"

PINS = {
    "v69_manifest": (V69 / "manifest.json", "e6ab30e9c9c03697b3c4dcd64a253d232cd0de1d1fbc9bc73d5c7880748de8b4"),
    "v69_rsp": (V69 / "Einhander_Recompiled.v69.rsp", "52342192c15c3c14f7acd556e7644b1533d1e3fedd2da32600286fffb93c8496"),
    "v69_exe": (V69 / "Einhander_Recompiled.exe", "f1ccb34dc0d06ba945fd822c9e807fe14b452b0d61584b731dcd4163f27759e5"),
    "v69_main_dep": (V69 / "obj/main.cpp.obj.d", "07d4a5769bb3a53f96fd9901ba077ed53ea6e94b5bbf4d0635c1a8878c34f3bf"),
    "v69_audio_header": (V69 / "include/recomp_audio_drc.h", "c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c"),
    "v69_main_src": (V69 / "src/main.cpp", "8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36"),
    "retained_table": (HERE / "retained-inputs.v69.tsv", "d9eb77e020cc36a45b5c533869a938b2a82839826fbe2634a408579b503de757"),
    "p1_main": (P1.parents[1] / "skin-selector-map/p1r2-enemy-channel/v69-merge/main.v69-plus-p1r2.cpp", "fe85c7e4caf7be4f76ce3a8528ba08868e9468113940ea44e716aa68a2ae6dd3"),
    "p1_keymap_c": (P1 / "proposed/host_keymap.c", "8c81f0c65100ba1aa10ac8f84f25027ff4298a56a05013fb874e1fe09345ac96"),
    "p1_keymap_h": (P1 / "proposed/host_keymap.h", "ba28065153423cc39640832ef169143794a14f9babe69adc3616923da8dcbf0f"),
    "clang.exe": (TC / "clang.exe", "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85"),
    "clang++.exe": (TC / "clang++.exe", "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85"),
    "clang-22.exe": (TC / "clang-22.exe", "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1"),
    "libclang-cpp.dll": (TC / "libclang-cpp.dll", "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e"),
    "libLLVM-22.dll": (TC / "libLLVM-22.dll", "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af"),
}
OLD_MAIN_OBJ = "C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206/obj/main.cpp.obj"
OLD_KEYMAP_OBJ = "CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/host_keymap.c.obj"
OLD_KEYMAP_OBJ_SHA = "e03f07c5eba4cc93611584f96929a0bccf98aeeb41763b4890c9460b73d3fa89"
EXPECTED_FILE_INPUTS = 155

# host_keymap.c flags provenance: build-ss8c/build.ninja lines 637-645 (DEFINES, FLAGS) for
# CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/host_keymap.c.obj. INCLUDES there name D:/Games/Einhander/...;
# they are mapped 1:1 to C:/github/Einhander/... (the same C: set v69 build:main used). D: is never read.
KEYMAP_DEFINES = [
    "-DDEFAULT_DEBUG_PORT=4370", "-DFMT_HEADER_ONLY=1", "-DLNG_SDL3=1", "-DNOMINMAX",
    '-DPSX_BUNDLED_BIOS_PATH="bios/openbios.bin"', '-DPSX_DEFAULT_BIOS_PATH="bios/SCPH1001.BIN"',
    '-DPSX_DEFAULT_GAME_CONFIG_PATH="game.toml"', "-DPSX_ENABLE_BLOCK_CYCLES=1", "-DPSX_HAS_CODEGEN_SETUP_HOST=1",
    "-DPSX_HAS_GAME_CODEGEN=1", "-DPSX_HAS_GAME_DISPATCH=1", "-DPSX_HAS_RBENGINE_SNAP=1", "-DPSX_HAS_SETUP_WIZARD=1",
    "-DPSX_HAVE_VULKAN=1", "-DPSX_MAX_PLAYERS=1", "-DPSX_NATIVE_BUILD=1", "-DPSX_SDL3=1",
    '-DPSX_WINDOW_TITLE="Einhander Recompiled"', "-DRECOMP_LAUNCHER", "-DRECOMP_UI_ENABLE_MODS=1",
    "-DRECOMP_UI_PSX_HAS_REWIND=1", "-DSDL_MAIN_HANDLED",
]
KEYMAP_FLAGS = ["-O3", "-DNDEBUG", "-fzero-initialized-in-bss"]
KEYMAP_INCLUDES = [
    "-IC:/github/Einhander/windows-x64/psxrecomp/runtime/include",
    "-IC:/github/Einhander/windows-x64/psxrecomp/recompiler/src",
    "-IC:/github/Einhander/windows-x64/psxrecomp/recompiler/include",
    "-IC:/github/Einhander/windows-x64/psxrecomp/recompiler/lib/fmt/include",
    "-IC:/github/Einhander/windows-x64/psxrecomp/recompiler/lib/toml11",
    "-IC:/github/Einhander/windows-x64/psxrecomp/lib/retcomm-rbengine/include",
    "-IC:/github/Einhander/windows-x64/recomp-ui/src",
    "-IC:/github/Einhander/windows-x64/recomp-ui/src/common",
    "-IC:/github/Einhander/windows-x64/recomp-ui/src/third_party/imgui",
    "-IC:/github/Einhander/windows-x64/recomp-ui/src/third_party/imgui/backends",
    "-IC:/VulkanSDK/1.4.363.0/Include",
    "-IC:/github/Einhander/windows-x64/build-ss8c/psx-runtime_vkgen",
    "-IC:/github/Einhander/windows-x64/psxrecomp/host",
    "-IC:/github/Einhander/windows-x64/build-ss8c/_deps/psx_libchdr-src/include",
    "-isystem", "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/deps/include",
]
CAPS = {"compile:main": 65, "compile:keymap": 20, "link": 15}
ENVELOPE_S = 110
REQUIRED_STEPS = ("pins", "retained_inputs", "copy:main", "copy:keymap_c", "copy:keymap_h", "compile:main",
                  "compile:keymap", "deps:main", "deps:keymap", "rsp", "link", "outputs")
THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
              "NUMEXPR_NUM_THREADS": "1"}
BELOW_NORMAL = 0x00004000
NO_WINDOW = 0x08000000


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm(p):
    return os.path.normcase(os.path.normpath(str(p)))


def step(man, name, ok, **info):
    man["steps"][name] = dict(ok=bool(ok), at_utc=utc(), **info)
    if not ok:
        man["reasons"].append(f"step failed: {name}")
    return bool(ok)


def creation_time(handle):
    """Windows process creation time (FILETIME as unix seconds); best effort."""
    try:
        ft = [ctypes.c_ulonglong() for _ in range(4)]
        if ctypes.windll.kernel32.GetProcessTimes(ctypes.c_void_p(int(handle)), *[ctypes.byref(x) for x in ft]):
            return ft[0].value / 1e7 - 11644473600.0
    except Exception:
        pass
    return None


def run_child(name, argv, cwd, pin_key, deadline, man):
    left = deadline - time.monotonic()
    rec = {"step": name, "argv": [str(x) for x in argv], "cwd": str(cwd), "start_utc": utc(), "pid": None,
           "creation_unix": None, "rc": None, "timed_out": False, "killed": False,
           "timeout_s": round(min(CAPS[name], max(0.0, left)), 3), "elapsed_s": None, "stdout": "", "stderr": ""}
    man["children"].append(rec)
    exe = Path(rec["argv"][0])
    rec["compiler_sha256"] = sha(exe) if exe.is_file() else None
    if norm(exe) != norm(PINS[pin_key][0]) or rec["compiler_sha256"] != PINS[pin_key][1]:
        rec["stderr"] = "compiler path/hash does not match pin"
        return rec
    if left <= 1:
        rec["stderr"] = "envelope exhausted before start"
        return rec
    env = dict(os.environ)
    env.update(THREAD_ENV)
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, creationflags=BELOW_NORMAL | NO_WINDOW)
    rec["pid"] = p.pid
    rec["creation_unix"] = creation_time(getattr(p, "_handle", 0))
    try:
        out, err = p.communicate(timeout=rec["timeout_s"])
    except subprocess.TimeoutExpired:
        rec["timed_out"] = True
        p.kill()
        rec["killed"] = True
        try:
            out, err = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = b"", b"post-kill communicate timed out"
    rec["rc"] = p.returncode
    rec["elapsed_s"] = round(time.monotonic() - t0, 3)
    rec["stdout"] = (out or b"").decode("utf-8", "replace")[-4000:]
    rec["stderr"] = (err or b"").decode("utf-8", "replace")[-4000:]
    return rec


def child_ok(rec):
    return rec["rc"] == 0 and not rec["timed_out"]


def parse_depfile(path):
    return parse_depfile_bytes(Path(path).read_bytes())


def hashed_deps(deps):
    """Every resolved dependency must exist; a missing one is recorded as None and fails its step."""
    return [{"path": d, "sha256": sha(d) if Path(d).is_file() else None} for d in deps]


def is_c_path(p):
    """Strict: an absolute path on drive C: only (no D:, no UNC, no relative path)."""
    s = norm(p)
    return s.startswith("c:\\") and not s.startswith("\\\\")


def rsp_tokens(text):
    return re.findall(r'"([^"]*)"', text)


def load_retained(table_bytes):
    rows = {}
    for line in table_bytes.decode("utf-8").splitlines():
        if line.strip():
            h, p = line.split("\t", 1)
            rows[p] = h
    return rows


def write_exclusive(path, data):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_pinned(man, step_name, key, dst):
    src, want = PINS[key]
    data = Path(src).read_bytes()
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    write_exclusive(dst, data)
    got, back = sha_bytes(data), sha(dst)
    return step(man, step_name, got == want == back, src=str(src), dst=str(dst), read_sha256=got, copy_sha256=back)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--out", required=True, help="new, non-existent absolute output root")
    a = ap.parse_args()
    out = Path(a.out)
    if not out.is_absolute() or out.exists():
        print(json.dumps({"verdict": "FAIL", "reason": "--out must be a new absolute path"}))
        return 2
    out.mkdir(parents=True)
    deadline = time.monotonic() + ENVELOPE_S
    man = {"driver": Path(__file__).name, "driver_sha256": sha(__file__), "grant_id": a.grant_id, "out": str(out),
           "started_utc": utc(), "inputs": {}, "steps": {}, "children": [], "checks": {}, "reasons": [],
           "never": "no install, no launch, no SDL device open, no GPU, no D: reads"}
    try:
        if sys.flags.optimize:
            man["reasons"].append("refusing to run under python -O")
        else:
            body(out, deadline, man)
    except Exception as e:
        man["reasons"].append(f"exception: {type(e).__name__}: {e}")
    missing = [s for s in REQUIRED_STEPS if not man["steps"].get(s, {}).get("ok")]
    man["missing_or_failed_steps"] = missing
    man["verdict"] = "PASS" if not man["reasons"] and not missing else "FAIL"
    man["ended_utc"] = utc()
    write_exclusive(out / "manifest.json", json.dumps(man, indent=1).encode("utf-8"))
    print(json.dumps({"verdict": man["verdict"], "reasons": man["reasons"], "missing": missing,
                      "manifest": str(out / "manifest.json")}))
    return 0 if man["verdict"] == "PASS" else 1


def body(out, deadline, man):
    # 1. pins; read-once bytes for every file whose content drives the build
    blobs, ok = {}, True
    for k, (p, want) in PINS.items():
        data = Path(p).read_bytes() if Path(p).is_file() else None
        got = sha_bytes(data) if data is not None else None
        man["inputs"][k] = {"path": str(p), "sha256": got, "expected": want}
        if got is None or (want is not None and got != want):
            ok = False
        if k in ("v69_manifest", "v69_rsp", "retained_table", "v69_main_dep"):
            blobs[k] = data
    if not step(man, "pins", ok):
        return
    v69 = json.loads(blobs["v69_manifest"].decode("utf-8"))
    rec = {c["step"]: c for c in v69.get("children", [])}
    if v69.get("verdict") != "PASS" or not all(s in rec for s in ("build:main", "build:link")):
        step(man, "pins", False, why="v69 manifest lacks PASS build:main/build:link")
        return

    # 2. retained inputs: every rsp file token pinned and re-hashed
    old_rsp = blobs["v69_rsp"].decode("utf-8")
    toks = rsp_tokens(old_rsp)
    files = [t for t in toks if not t.startswith("-")]
    table = load_retained(blobs["retained_table"])
    bad = []
    for t in files:
        p = Path(t) if Path(t).is_absolute() else SS8C / t
        got = sha(p) if p.is_file() else None
        if table.get(t) is None or got != table[t]:
            bad.append(t)
    shape = (len(files) == EXPECTED_FILE_INPUTS == len(table) and set(files) == set(table) and
             toks.count(OLD_MAIN_OBJ) == 1 and toks.count(OLD_KEYMAP_OBJ) == 1 and
             table.get(OLD_KEYMAP_OBJ) == OLD_KEYMAP_OBJ_SHA)
    if not step(man, "retained_inputs", shape and not bad, file_inputs=len(files), mismatched=bad[:20]):
        return

    inc, src, obj = out / "include", out / "src", out / "obj"
    obj.mkdir(parents=True)
    if not (copy_pinned(man, "copy:main", "p1_main", src / "main.cpp") and
            copy_pinned(man, "copy:keymap_c", "p1_keymap_c", src / "host_keymap.c") and
            copy_pinned(man, "copy:keymap_h", "p1_keymap_h", inc / "host_keymap.h")):
        return

    # 3a. compile main with v69's exact argv (read from the pinned bytes), retargeted, private include first
    margv = list(rec["build:main"]["argv"])
    olds = {norm(V69 / "src/main.cpp"): str(src / "main.cpp"), norm(V69 / "obj/main.cpp.obj"): str(obj / "main.cpp.obj"),
            norm(V69 / "obj/main.cpp.obj.d"): str(obj / "main.cpp.obj.d")}
    if any([norm(x) for x in margv].count(k) != 1 for k in olds):
        step(man, "compile:main", False, why="v69 build:main argv lacks exactly one src/obj/dep")
        return
    margv = [olds.get(norm(x), x) for x in margv]
    margv.insert(1, f"-I{inc}")
    r = run_child("compile:main", margv, Path("C:/github/Einhander"), "clang++.exe", deadline, man)
    if not step(man, "compile:main", child_ok(r)):
        return

    # 3b. compile host_keymap.c (C-only), private include first
    kargv = ([str(PINS["clang.exe"][0]), f"-I{inc}"] + KEYMAP_DEFINES + KEYMAP_FLAGS + KEYMAP_INCLUDES +
             ["-MD", "-MF", str(obj / "host_keymap.c.obj.d"), "-c", str(src / "host_keymap.c"),
              "-o", str(obj / "host_keymap.c.obj")])
    r = run_child("compile:keymap", kargv, Path("C:/github/Einhander"), "clang.exe", deadline, man)
    if not step(man, "compile:keymap", child_ok(r)):
        return

    # 3c. depfile closures (r3: content-checked, not just path sets)
    new_h = norm(inc / "host_keymap.h")
    new_main_src = norm(src / "main.cpp")
    v69_closure = {norm(k): v for k, v in v69["build"]["main"]["closure"].items()}  # path -> sha256, pinned bytes
    v69_depfile_set = {norm(d) for d in parse_depfile_bytes(blobs["v69_main_dep"])}
    excluded_old = {norm(V69 / "src/main.cpp"), norm(UPLOAD_HITCH_KEYMAP_H)}
    audio_h = norm(PINS["v69_audio_header"][0])
    main_deps = parse_depfile(obj / "main.cpp.obj.d")
    main_h = hashed_deps(main_deps)
    got = {norm(d["path"]): d["sha256"] for d in main_h}
    expect_paths = (set(v69_closure) - excluded_old) | {new_main_src, new_h}
    shared = set(got) - {new_main_src, new_h}
    changed = sorted(p for p in shared if got[p] is None or got[p] != v69_closure.get(p))
    main_ok = (set(v69_closure) == v69_depfile_set and excluded_old <= set(v69_closure) and
               set(got) == expect_paths and not changed and audio_h in got and
               v69_closure.get(audio_h) == PINS["v69_audio_header"][1] == got.get(audio_h) and
               got.get(new_main_src) == PINS["p1_main"][1] and got.get(new_h) == PINS["p1_keymap_h"][1] and
               all(is_c_path(p) for p in got))
    step(man, "deps:main", main_ok, v69_closure_entries=len(v69_closure), new_entries=len(got),
         only_in_new=sorted(set(got) - expect_paths)[:20], only_in_expected=sorted(expect_paths - set(got))[:20],
         changed_or_missing_shared=changed[:20], deps=main_h)
    k_deps = parse_depfile(obj / "host_keymap.c.obj.d")
    k_h = hashed_deps(k_deps)
    k_got = {norm(d["path"]): d["sha256"] for d in k_h}
    k_keymap_h = sorted(p for p in k_got if Path(p).name == "host_keymap.h")
    k_ok = (k_keymap_h == [new_h] and k_got.get(new_h) == PINS["p1_keymap_h"][1] and
            k_got.get(norm(src / "host_keymap.c")) == PINS["p1_keymap_c"][1] and
            all(v is not None for v in k_got.values()) and all(is_c_path(p) for p in k_got) and
            norm(UPLOAD_HITCH_KEYMAP_H) not in k_got)
    step(man, "deps:keymap", k_ok, host_keymap_h=k_keymap_h, entries=len(k_got), deps=k_h,
         note="complete C:-only closure recorded; the historical D: closure of old object e03f07c5 is UNKNOWN "
              "(D: never read); no old-keymap reproduction in this revision")
    if man["reasons"]:
        return

    # 4. rsp: exactly two object replacements, everything else token-identical
    new_main = str(obj / "main.cpp.obj").replace("\\", "/")
    new_keymap = str(obj / "host_keymap.c.obj").replace("\\", "/")
    new_rsp_text = old_rsp.replace(f'"{OLD_MAIN_OBJ}"', f'"{new_main}"').replace(f'"{OLD_KEYMAP_OBJ}"', f'"{new_keymap}"')
    nt = rsp_tokens(new_rsp_text)
    diffs = [(a_, b_) for a_, b_ in zip(toks, nt) if a_ != b_]
    rsp_ok = (len(nt) == len(toks) and sorted(diffs) == sorted([(OLD_MAIN_OBJ, new_main), (OLD_KEYMAP_OBJ, new_keymap)]))
    new_rsp = out / "Einhander_Recompiled.p1.rsp"
    if rsp_ok:
        write_exclusive(new_rsp, new_rsp_text.encode("utf-8"))
    if not step(man, "rsp", rsp_ok, replaced=diffs, sha256=sha(new_rsp) if rsp_ok else None):
        return

    # 5. link with v69's argv shape
    largv = list(rec["build:link"]["argv"])
    ri = [i for i, x in enumerate(largv) if x.startswith("@")]
    oi = [i for i, x in enumerate(largv) if x == "-o"]
    if len(ri) != 1 or len(oi) != 1:
        step(man, "link", False, why="v69 link argv shape unexpected")
        return
    largv[ri[0]] = "@" + str(new_rsp)
    largv[oi[0] + 1] = str(out / "Einhander_Recompiled.exe")
    r = run_child("link", largv, SS8C, "clang++.exe", deadline, man)
    if not step(man, "link", child_ok(r)):
        return

    outs = {k: sha(obj / k) for k in ("main.cpp.obj", "host_keymap.c.obj")}
    outs["exe"] = sha(out / "Einhander_Recompiled.exe")
    v69_ok = sha(PINS["v69_exe"][0]) == PINS["v69_exe"][1]
    step(man, "outputs", v69_ok and outs["exe"] != PINS["v69_exe"][1], hashes=outs, v69_exe_untouched=v69_ok)


def parse_depfile_bytes(data):
    """Make-style depfile. Line continuations are removed; '\\ ' is an escaped space; other backslashes are
    Windows path separators and are kept. The target ends at the first ': ' (drive colons have no space)."""
    tmp_text = data.decode("utf-8", "replace").replace("\\\r\n", " ").replace("\\\n", " ")
    i = tmp_text.find(": ")
    if i < 0:
        raise ValueError("unparseable depfile")
    deps, cur, esc = [], "", False
    for ch in tmp_text[i + 2:]:
        if esc:
            cur += ch if ch == " " else "\\" + ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch in " \t\r\n":
            if cur:
                deps.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        deps.append(cur)
    return deps


if __name__ == "__main__":
    sys.exit(main())
