"""Read-only post-restart verification of the v5 recovery sources (claude-einhander). Below normal, one CPU.
1 run-3 result.json sha == runs/INDEX.jsonl record; 2 run-3 inputs == result.json input hashes; 3 working sources vs
run-3 inputs / selftest copies; 4 every run-3 sidecar (class + RGB-only) == its recorded sha; 5 selftest build.json
file hashes; 6 any NUL byte in a text file of the scoped trees (partial zeroing), outside the damaged frozen v5."""
import hashlib, json, os, sys
from pathlib import Path
import psutil
me = psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([me.cpu_affinity()[-1]])
H = Path("C:/github/Einhander/remaster-audit/claude-backlog/class-mip/renderer-v61-classmip")
CM = H.parent
RUN = H / "runs/20261114T124104Z"
ST = H / "selftest/20261114T124348Z"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
rep = {}
idx = [json.loads(l) for l in (H / "runs/INDEX.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
rec = next(x for x in idx if x["run"] == RUN.name)
rep["1_result_sha_matches_index"] = sha(RUN / "result.json") == rec["result_sha256"]
res = json.loads((RUN / "result.json").read_text(encoding="utf-8"))
rep["1_verdict"] = res["verdict"]
bad = {n: [h, sha(RUN / "inputs" / n)] for n, h in res["inputs"].items() if sha(RUN / "inputs" / n) != h}
rep["2_inputs_mismatch"] = bad
work = {}
for n in res["inputs"]:
    w = H / n
    if n in ("class_mip.c", "class_mip.h"):
        w = CM / "frozen/class-mip-v2b-breakdown-v1/proto-v2b" / n
    work[n] = dict(working_equals_run3_input=w.exists() and sha(w) == res["inputs"][n])
rep["3_working_vs_run3_inputs"] = work
b = json.loads((ST / "build.json").read_text(encoding="utf-8"))
rep["5_selftest_build_files"] = {n: sha(ST / n) == h for n, h in b["files"].items()}
rep["3_working_vs_selftest_copies"] = {n: sha(H / n) == b["files"][n] for n in ("gl_selftest_classmips.c", "build_selftest.py", "hd_class_mips.inc") if n in b["files"]}
sc = res["steps"]["4-sidecars"]["sidecars"]
rg = res["steps"]["4b-rgbonly"]["rows"]
rep["4_class_sidecars_ok"] = sum(1 for s in sc if s.get("written") and sha(s["path"]) == s["sha256"]), sum(1 for s in sc if s.get("written"))
rep["4_rgb_sidecars_ok"] = sum(1 for r in rg if r.get("written") and sha(r["path"]) == r["sha256"]), sum(1 for r in rg if r.get("written"))
TEXT = {".py", ".c", ".h", ".inc", ".md", ".json", ".jsonl", ".txt", ".log", ".csv", ".svg", ".frag", ".vert", ".i", ".d", ".tsv"}
nul = []
for root in (CM, Path("C:/Users/Admin/.claude/projects/C--github/memory"), Path("C:/github/Einhander/.hermes3d_orchestrator/continuity")):
    for dp, dn, fn in os.walk(root):
        if "frozen/renderer-v61-classmip-v5" in dp.replace("\\", "/") and not dp.replace("\\", "/").endswith("-v5-r2"):
            if "/frozen/renderer-v61-classmip-v5" in dp.replace("\\", "/") + "/":
                continue
        for n in fn:
            p = Path(dp) / n
            if p.suffix.lower() in TEXT and p.stat().st_size and p.stat().st_size < 200 * 1024 * 1024:
                if b"\0" in p.read_bytes():
                    nul.append(str(p))
rep["6_text_files_with_nul"] = nul
for n in ("freeze_version.py", "build_selftest.py", "FAILED-RUNS.md", "DESIGN-V5.md", "census_rgb_edges.py", "ab_targets.py",
          "gl_selftest_classmips.c"):
    t = (H / n).read_bytes()
    rep.setdefault("7_working_text_sizes", {})[n] = dict(bytes=len(t), nul=t.count(b"\0"), lines=t.count(b"\n"))
print(json.dumps(rep, indent=1))
Path(sys.argv[1]).write_text(json.dumps(rep, indent=1), encoding="utf-8")
