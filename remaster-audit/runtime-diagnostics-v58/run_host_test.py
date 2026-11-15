#!/usr/bin/env python3
"""Host test of the ACTUAL v58 ring/handler text extracted from new/debug_server.c, plus mutation controls
(claude-einhander). CPU only, below-normal priority, sequential, no game. Writes host-test.json."""
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import derive_phases  # noqa: E402

CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
WORK = HERE / "work"
V57_DIR = Path("C:/github/Einhander/remaster-audit/runtime-review/native-upload-stream/new")
BEGIN, END = "/* FRAME_PHASE_RING BEGIN", "/* Present-classification ring"

MUTANTS = [
    ("index: open-row write uses s_fpr_seq",
     "FramePhaseRecord *r = &s_fpr_ring[(s_fpr_seq - 1) % FRAME_PHASE_RING_CAP];",
     "FramePhaseRecord *r = &s_fpr_ring[s_fpr_seq % FRAME_PHASE_RING_CAP];"),
    ("wrap: eviction bound off by one", "s_fpr_seq - seq > FRAME_PHASE_RING_CAP", "s_fpr_seq - seq > FRAME_PHASE_RING_CAP + 1"),
    ("truncation flag dropped", "if (returned == n) { truncated = 1; break; }", "if (returned == n) { break; }"),
    ("row budget too small", "const int rowsz = 64 + n * 384;", "const int rowsz = 64 + n * 96;"),
    ("owner guard removed", "if (!s_fpr_is_owner) return;", "if (0) return;"),
    ("debug_end not first-wins", "if (!r->t[phase]) { r->t[phase] = now; r->frame = (uint32_t)s_frame_count; }",
     "{ r->t[phase] = now; r->frame = (uint32_t)s_frame_count; }"),
    ("unclosed flag dropped", ".flags |= FP_FLAG_UNCLOSED;", ".flags |= 0;"),
    ("multi-swap keeps last", "if (r->swaps++ == 0)", "if (++r->swaps)"),
    ("frame filter inverted", "r.frame > (uint32_t)to_frame", "r.frame >= (uint32_t)to_frame"),
]


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def build(tag, inc_text, cap):
    d = WORK / tag
    d.mkdir(parents=True, exist_ok=True)
    (d / "ring_extracted.inc").write_text(inc_text, encoding="utf-8")
    exe = d / "test.exe"
    args = [CLANG, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", "-I", str(d), "-I", str(HERE / "new"),
            "-I", "C:/github/Einhander/windows-x64/psxrecomp/runtime/include"]   # real psx_bss.h
    if cap:
        args.append(f"-DFRAME_PHASE_RING_CAP={cap}")
    cc = subprocess.run(args + [str(HERE / "test_frame_phase_ring.c"), "-o", str(exe)], capture_output=True, text=True,
                        timeout=300)
    return exe, cc


def run(exe, mode, env_on):
    env = {k: v for k, v in os.environ.items() if k != "PSX_FRAME_PHASE_RING"}
    if env_on:
        env["PSX_FRAME_PHASE_RING"] = "1"
    p = subprocess.run([str(exe), mode], capture_output=True, text=True, env=env, timeout=120)
    js, fails = [], []
    for line in p.stdout.splitlines():
        if line.startswith("JSON "):
            js.append(json.loads(line[5:]))
        elif line.startswith("FAIL"):
            fails.append(line)
    return p.returncode, js, fails


def check_main(js):
    """Checks on the handler replies of the 'main' mode (CAP=8 build). Returns failure strings."""
    f = []

    def need(c, msg):
        if not c:
            f.append(msg)
    need(len(js) == 7, f"expected 7 replies, got {len(js)}")
    if len(js) != 7 or not all(j.get("ok") for j in js):
        return f + ["a reply was not ok: " + str([j.get("error") for j in js if not j.get("ok")])]
    fields = js[0]["fields"]
    need(fields == ["seq", "frame", "frame_at_enter", "frame_at_swap", "flags", "swaps", "enter", "debug_end",
                    "pace_begin", "pace_end", "swap_begin", "swap_end", "alt_pace_begin", "alt_pace_end", "exit"], "fields")
    o = js[0]   # open-row query
    need(o["total"] == 6 and o["returned"] == 6 and o["last_open"] == 1 and o["truncated"] == 0, "open-row query header")
    need(o["rows"][-1][4] & 1 == 0, "newest row must be open (not CLOSED)")
    need(o["rows"][0] == [0, 6, 5, 6, 1, 1, 1000, 1010, 1020, 1050, 1070, 1075, 0, 0, 1080], f"row0 raw {o['rows'][0]}")
    need(o["enabled"] == 1 and o["owner_bound"] == 1 and o["orphans"] == 4 and o["unclosed"] == 1, "counters")
    rows, freq = derive_phases.rows_from([o])
    seg = {s["seq"]: s for s in derive_phases.derive(rows, freq)}
    us = 1e3 / freq   # 1 tick in ms
    s0 = seg[0]
    need([round(s0[k] / us) for k in ("housekeeping_ms", "pre_pace_ms", "pace_ms", "present_prep_ms", "swap_ms", "post_ms",
                                       "cycle_ms")] == [10, 10, 30, 20, 5, 5, 80] and s0["outside_ms"] is None, f"seg0 {s0}")
    need(seg[0]["precise"] and seg[0]["in_scope"], "row0 precise")
    need(not seg[1]["precise"] and round(seg[1]["outside_ms"] / us) == 920, "row1 multi-swap excluded, outside 920")
    need(not seg[2]["precise"] and seg[3]["outside_ms"] is None and seg[3]["precise"], "unclosed row excluded")
    need(round(seg[4]["outside_ms"] / us) == 920 and seg[4]["precise"], "row4 outside after foreign test")
    need(not seg[5]["precise"], "open row excluded")
    p1, p2, p3, allr, filt, big = js[1:]
    need(p1["first_seq"] == 18 and p1["retained"] == 8 and p1["capacity"] == 8, "wrap header")
    need([r[0] for r in p1["rows"]] == [18, 19, 20] and p1["truncated"] == 1 and p1["next_seq"] == 21, "page1")
    need([r[0] for r in p2["rows"]] == [21, 22, 23] and p2["truncated"] == 1 and p2["next_seq"] == 24, "page2")
    need([r[0] for r in p3["rows"]] == [24, 25] and p3["truncated"] == 0 and p3["next_seq"] == 26, "page3")
    need([r[0] for r in allr["rows"]] == list(range(18, 26)), "from_seq below first clamps to first")
    need([r[0] for r in filt["rows"]] == [20, 21, 22] and filt["truncated"] == 0, f"frame filter {[r[0] for r in filt['rows']]}")
    need(big["returned"] == 8 and all(r[1] == 4294967295 and r[4] == 13 and r[5] == 2 for r in big["rows"]), "max width")
    need(big["rows"][-1][14] == 18446744073709551079, "max stamp exact")
    return f


def suite(inc_text, tag):
    out = {}
    exe, cc = build(tag + "-cap8", inc_text, 8)
    out["compile_cap8"] = dict(exit=cc.returncode, diagnostics=cc.stderr.strip().splitlines()[-12:])
    if cc.returncode:
        return out, False
    rc, js, fails = run(exe, "main", True)
    try:
        jf = check_main(js) if js else ["no replies"]
    except Exception as ex:  # noqa: BLE001  (a malformed reply is a failure, not a crash)
        jf = [f"check raised {type(ex).__name__}: {ex}"]
    out["main"] = dict(exit=rc, c_fails=fails[:8], json_fails=jf[:8])
    ok = rc == 0 and not jf
    for mode, env_on in (("disabled", False), ("unbound", True)):
        rc, js, fails = run(exe, mode, env_on)
        good = rc == 0 and len(js) == 1 and js[0].get("ok") and js[0]["total"] == 0 and js[0]["owner_bound"] == 0 \
            and js[0]["enabled"] == (1 if env_on else 0) and js[0]["returned"] == 0
        out[mode] = dict(exit=rc, c_fails=fails[:4], ok=bool(good))
        ok = ok and good
    return out, ok


# Exact file-scope names r2 introduces. The scan must find exactly these (a fixture), so parser drift is a failure.
EXPECTED_DECLS = {"s_fpr_ring", "s_fpr_seq", "s_fpr_orphans", "s_fpr_unclosed", "s_fpr_open", "s_fpr_enabled",
                  "s_fpr_owner_bound", "s_fpr_is_owner", "debug_server_frame_phase_enabled",
                  "debug_server_frame_phase_init_owner", "debug_server_frame_phase_mark", "debug_server_frame_phase_total",
                  "debug_server_frame_phase_get", "handle_frame_phase_ring"}


def file_scope_decls(inc):
    """Names DECLARED at file scope (column 0) in the extracted block: static/global variables and function
    definitions. Indented lines (locals, calls) and comments are ignored."""
    import re
    inc = re.sub(r"/\*.*?\*/", "", inc, flags=re.S)
    names = set()
    for line in inc.split("\n"):
        if not line or line[0].isspace() or line[0] in "#}{":
            continue
        head = line.split("{")[0]
        if "(" in head:   # function definition or prototype at column 0
            m = re.match(r"\s*(?:static\s+)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\(", head)
            if m:
                names.add(m.group(1))
            continue
        decl = re.sub(r"=[^,;]*", "", head)   # drop initializers
        names.update(re.findall(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*[,;]", decl))
    return names


def symbol_scan(inc):
    """Integration guard the extracted-block test cannot give: every file-scope name the patch INTRODUCES (ring block,
    header, renderer hook, main macro) must be absent from the exact base of each TU it lands in. The full-TU compiler
    stays the authoritative gate; this is a cheap pre-check."""
    import re
    decls = file_scope_decls(inc)
    hdr = re.sub(r"/\*.*?\*/", "", (HERE / "new" / "frame_phase_ring.h").read_text(encoding="utf-8"), flags=re.S)
    hdr_names = set(re.findall(r"\b(FP_[A-Z_]+|FRAME_PHASE_RING_[A-Z_]+|FramePhaseRecord|debug_server_frame_phase_\w+|"
                               r"gl_renderer_set_swap_phase_hook)\b", hdr))
    names = decls | hdr_names
    bases = {"debug_server.c": V57_DIR / "debug_server.c", "gpu_gl_renderer.c": V57_DIR / "gpu_gl_renderer.c",
             "main.cpp": Path("C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime/src/main.cpp")}
    extra = {"gpu_gl_renderer.c": {"s_swap_phase_hook"}, "main.cpp": {"FRAME_PHASE_MARK"}}
    hits = {}
    for tu, p in bases.items():
        text = p.read_text(encoding="utf-8", errors="replace")
        for n in sorted(names | extra.get(tu, set())):
            c = len(re.findall(r"\b" + re.escape(n) + r"\b", text))
            if c:
                hits[f"{tu}:{n}"] = c
    fixture_ok = decls == EXPECTED_DECLS
    return dict(decls=sorted(decls), fixture_matches_expected=fixture_ok, header_names=len(hdr_names),
                names_checked=len(names) + 2, collisions=hits, passed=fixture_ok and not hits)


def main():
    result = dict(below_normal=below_normal())
    src = (HERE / "new" / "debug_server.c").read_text(encoding="utf-8").replace("\r\n", "\n")
    a, b = src.index(BEGIN), src.index(END)
    inc = src[a:b]
    result["extracted"] = dict(chars=len(inc), lines=inc.count("\n"))
    result["symbol_scan"] = symbol_scan(inc)
    ctrl = symbol_scan(inc.replace("s_fpr_", "s_fp_"))   # control: the r1 first-build collision must be detected
    result["symbol_scan_control_detects_s_fp_ring"] = "debug_server.c:s_fp_ring" in ctrl["collisions"]
    result["symbol_scan_control_collisions"] = ctrl["collisions"]
    res, ok = suite(inc, "actual")
    result["actual"] = dict(res, passed=ok)
    exe, cc = build("actual-defaultcap", inc, None)
    rc, js, fails = run(exe, "capacity", True) if cc.returncode == 0 else (-1, [], ["compile failed"])
    cap_ok = rc == 0 and len(js) == 1 and js[0]["capacity"] == 16384 and js[0]["first_seq"] == 5 \
        and js[0]["retained"] == 16384 and js[0]["returned"] == 2048 and js[0]["truncated"] == 1 and js[0]["next_seq"] == 2053
    result["default_capacity"] = dict(compile_exit=cc.returncode, exit=rc, c_fails=fails[:4], passed=bool(cap_ok))
    muts = []
    for name, old, new in MUTANTS:
        n = inc.count(old)
        if n != 1:
            muts.append(dict(name=name, error=f"anchor count {n}"))
            continue
        res, mok = suite(inc.replace(old, new), "mut-" + str(len(muts)))
        muts.append(dict(name=name, caught=not mok))
    result["mutants"] = muts
    result["all_mutants_caught"] = all(m.get("caught") for m in muts)
    result["passed"] = ok and cap_ok and result["all_mutants_caught"] and result["symbol_scan"]["passed"] \
        and result["symbol_scan_control_detects_s_fp_ring"]
    (HERE / "host-test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
