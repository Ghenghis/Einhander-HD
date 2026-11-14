#!/usr/bin/env python3
"""Record (read-only) the restart-damaged freeze frozen/renderer-v61-classmip-v5 WITHOUT touching it (claude-einhander).
Writes frozen/DAMAGED-renderer-v61-classmip-v5.json next to it (exist_ok=False): every file's relative path, size,
sha256, all-NUL flag, mtime; group counts; the recovery source evidence. Below normal, one CPU."""
import datetime
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAMAGED = HERE / "frozen" / "renderer-v61-classmip-v5"
OUT = HERE / "frozen" / "DAMAGED-renderer-v61-classmip-v5.json"


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    files, groups = [], {}
    for p in sorted(x for x in DAMAGED.rglob("*") if x.is_file()):
        b = p.read_bytes()
        zero = len(b) > 0 and b.count(0) == len(b)
        rel = p.relative_to(DAMAGED).as_posix()
        top = rel.split("/")[0] if "/" in rel else "(root)"
        g = groups.setdefault(top, dict(files=0, all_nul=0, bytes=0))
        g["files"] += 1
        g["all_nul"] += int(zero)
        g["bytes"] += len(b)
        files.append(dict(path=rel, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), all_nul=zero,
                          mtime_utc=datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc).isoformat()))
    rec = dict(
        damaged=str(DAMAGED), recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        cause="Windows restart (boot 2026-11-14T12:49:22Z) while/just after freeze_version.py wrote this folder; data "
              "evidently not flushed. Cause not otherwise proven. Folder preserved UNCHANGED; never use it.",
        boot_time_utc=datetime.datetime.fromtimestamp(__import__("psutil").boot_time(), datetime.timezone.utc).isoformat(),
        files=len(files), all_nul_files=sum(1 for f in files if f["all_nul"]), bytes=sum(f["bytes"] for f in files),
        groups=groups, ready_json=next((f for f in files if f["path"] == "READY.json"), None),
        recovery=dict(source_run="runs/20261114T124104Z (run-3 result.json sha 53c73313...d3ee32 == runs/INDEX.jsonl; "
                                 "inputs == recorded hashes; working sources == inputs; 8 class + 136 RGB-only sidecars == "
                                 "recorded sha256)", source_selftest="selftest/20261114T124348Z (== its build.json)",
                      new_freeze="frozen/renderer-v61-classmip-v5-r2 (from a fresh replay)"),
        listing=files)
    with open(OUT, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, indent=1) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    print(json.dumps({k: rec[k] for k in ("files", "all_nul_files", "bytes", "groups", "ready_json")}, indent=1))


if __name__ == "__main__":
    main()
