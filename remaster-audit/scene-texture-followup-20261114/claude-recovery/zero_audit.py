"""Post-restart zero-file audit of claude-einhander's OWN scoped trees (read-only). Below normal, one CPU.
Flags files that are empty or entirely NUL. Prints groups; writes JSON to argv[1]."""
import hashlib, json, os, sys, time
from pathlib import Path
import psutil
me = psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([me.cpu_affinity()[-1]])
ROOTS = [Path("C:/github/Einhander/remaster-audit/claude-backlog/class-mip"),
         Path("C:/github/Einhander/remaster-audit/claude-backlog/95a3-k-panel"),
         Path("C:/Users/Admin/.claude/projects/C--github/memory"),
         Path("C:/github/Einhander/.hermes3d_orchestrator/continuity")]
BOOT = psutil.boot_time()
out = dict(boot_time_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(BOOT)), roots=[str(r) for r in ROOTS], zero=[], empty=[],
           checked=0, recent_after=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(BOOT - 6 * 3600)))
recent = []
for root in ROOTS:
    if not root.exists():
        continue
    for dp, dn, fn in os.walk(root):
        for n in fn:
            p = Path(dp) / n
            try:
                st = p.stat()
            except OSError as e:
                out.setdefault("errors", []).append([str(p), str(e)]); continue
            out["checked"] += 1
            if st.st_size == 0:
                out["empty"].append(str(p)); continue
            if st.st_size > 256 * 1024 * 1024:
                continue
            allzero = True
            with open(p, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    if b.count(0) != len(b):
                        allzero = False; break
            if allzero:
                out["zero"].append(dict(path=str(p), size=st.st_size, mtime=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime))))
            if st.st_mtime > BOOT - 6 * 3600:
                recent.append((st.st_mtime, str(p), st.st_size))
groups = {}
for z in out["zero"]:
    rel = z["path"].replace("\\", "/")
    key = "/".join(rel.split("/")[:9])
    groups[key] = groups.get(key, 0) + 1
out["zero_groups"] = groups
out["recent_files_count"] = len(recent)
Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("boot", out["boot_time_utc"], "checked", out["checked"], "zero", len(out["zero"]), "empty", len(out["empty"]))
for k, v in sorted(groups.items()):
    print(" ", v, k)
nonfrozen = [z for z in out["zero"] if "frozen/renderer-v61-classmip-v5" not in z["path"].replace("\\", "/")]
print("zero outside frozen v5:", len(nonfrozen))
for z in nonfrozen[:40]:
    print("   ", z)
print("empty files:", out["empty"][:30])
