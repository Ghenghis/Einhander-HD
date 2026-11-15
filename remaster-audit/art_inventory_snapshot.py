#!/usr/bin/env python3
"""Exact, read-only inventory of Claude's frozen art sets plus 3090 GPU provenance (claude-einhander).

Bounded: walks only remaster-audit/comfy-authoring/<lane>/frozen/<set>/ (never the repo root). Below-normal priority.
Per set: PNG file count, unique texture keys parsed from file names (XXXXXXXX-XXXXXXXX), resolution variants,
manifest presence + sha256 + top-level fields. GPU provenance: comfy-authoring/gpu-log.jsonl slot records by owner.
It reports FACTS on disk only: 'frozen' means a frozen folder exists. It does not establish live capture, in-game
acceptance or installation. Duplicate keys across sets/versions are reported, never summed as distinct assets.
Writes art-inventory.json next to this script.
"""
import ctypes
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
KEY = re.compile(r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{8})")
RES = re.compile(r"(?:^|[_\-.x])(256|512|1024|2048|4096)(?:[_\-.x]|$)")


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def stage_of(lane):
    m = re.match(r"w7-stage(\d)", lane)
    return int(m.group(1)) if m else 1   # t*/w2-w6 lanes are stage 1 work (w6-drache = stage 1 boss)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def scan_set(d):
    pngs, keys, res = 0, set(), Counter()
    other = Counter()
    for root, _dirs, files in os.walk(d):
        for fn in files:
            low = fn.lower()
            if low.endswith(".png"):
                pngs += 1
                keys.update(k.upper() for k in KEY.findall(fn))
                r = RES.search(low)
                res[r.group(1) if r else "unlabelled"] += 1
            else:
                other[Path(fn).suffix.lower() or "(none)"] += 1
    man = d / "manifest.json"
    info = dict(png_files=pngs, unique_keys=len(keys), resolution_labels=dict(res), other_files=dict(other))
    if man.exists():
        info["manifest"] = dict(sha256=sha(man))
        try:
            j = json.loads(man.read_text(encoding="utf-8"))
            info["manifest"]["top_level_fields"] = sorted(j)[:20] if isinstance(j, dict) else type(j).__name__
        except Exception as ex:  # noqa: BLE001
            info["manifest"]["parse_error"] = str(ex)[:120]
    else:
        info["manifest"] = None
    return info, keys


def gpu_provenance():
    owners = defaultdict(lambda: dict(slots=0, minutes=0.0, first=None, last=None))
    log = CA / "gpu-log.jsonl"
    bad = 0
    import datetime as dt
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
            o = owners[r["owner"]]
            a, b = dt.datetime.fromisoformat(r["start"]), dt.datetime.fromisoformat(r["end"])
            o["slots"] += 1
            o["minutes"] += (b - a).total_seconds() / 60
            o["first"] = min(o["first"] or r["start"], r["start"])
            o["last"] = max(o["last"] or r["end"], r["end"])
        except Exception:  # noqa: BLE001
            bad += 1
    for o in owners.values():
        o["minutes"] = round(o["minutes"], 1)
    return dict(log=dict(path=log.as_posix(), sha256=sha(log)), unparsed_lines=bad, owners=dict(sorted(owners.items())))


def main():
    out = dict(below_normal=below_normal(), root=CA.as_posix(),
               scope="Facts on disk only. 'frozen' = a frozen folder exists; not live-captured, in-game accepted or "
                     "installed unless separate evidence says so. Keys are parsed from file names; duplicate keys "
                     "across sets/versions are listed, not summed as assets.", lanes={})
    key_sets = defaultdict(set)
    for lane in sorted(p for p in CA.iterdir() if p.is_dir() and (p / "frozen").is_dir()):
        sets = {}
        for s in sorted(p for p in (lane / "frozen").iterdir() if p.is_dir()):
            info, keys = scan_set(s)
            sets[s.name] = info
            for k in keys:
                key_sets[k].add(f"{lane.name}/{s.name}")
        ledgers = [f.name for f in lane.iterdir() if f.is_file() and f.suffix.lower() in (".md", ".json")]
        lane_keys = set().union(*[{k for k, v in key_sets.items() if any(x.startswith(lane.name + "/") for x in v)}])
        out["lanes"][lane.name] = dict(stage=stage_of(lane.name), frozen_sets=len(sets),
                                       png_files=sum(v["png_files"] for v in sets.values()),
                                       unique_keys_in_lane=len(lane_keys),
                                       sets_without_manifest=[n for n, v in sets.items() if v["manifest"] is None],
                                       ledger_files=sorted(ledgers), sets=sets)
    per_stage = defaultdict(lambda: dict(lanes=[], frozen_sets=0, png_files=0, unique_keys=set()))
    for name, lane in out["lanes"].items():
        st = per_stage[lane["stage"]]
        st["lanes"].append(name)
        st["frozen_sets"] += lane["frozen_sets"]
        st["png_files"] += lane["png_files"]
        st["unique_keys"] |= {k for k, v in key_sets.items() if any(x.startswith(name + "/") for x in v)}
    out["per_stage"] = {str(k): dict(v, unique_keys=len(v["unique_keys"])) for k, v in sorted(per_stage.items())}
    out["keys_in_multiple_sets"] = sum(1 for v in key_sets.values() if len(v) > 1)
    out["unique_keys_all_lanes"] = len(key_sets)
    out["gpu_provenance"] = gpu_provenance()
    (HERE / "art-inventory.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dict(per_stage=out["per_stage"], unique_keys_all_lanes=out["unique_keys_all_lanes"],
                          keys_in_multiple_sets=out["keys_in_multiple_sets"],
                          lanes={k: dict(sets=v["frozen_sets"], png=v["png_files"], keys=v["unique_keys_in_lane"],
                                         no_manifest=len(v["sets_without_manifest"])) for k, v in out["lanes"].items()},
                          gpu_owners={k: (v["slots"], v["minutes"]) for k, v in out["gpu_provenance"]["owners"].items()},
                          gpu_unparsed=out["gpu_provenance"]["unparsed_lines"]), indent=1))


if __name__ == "__main__":
    main()
