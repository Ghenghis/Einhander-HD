#!/usr/bin/env python3
"""claude-einhander-ui (EIN-MENU-HUD-20261114): VERIFIED integration summary builder for v5 J-R3 runs.

Light (JSON + sha256 of written PNGs only; no image decode). For every row and variant of the given v5 result folders it
re-hashes the referenced file FROM DISK and refuses (exit 1, no summary written) if:
  * any recorded sha256 differs from the file on disk;
  * any path is referenced twice (within or across runs) or two references resolve to the same file case-insensitively;
  * a result was not produced by an accepted v5 tool hash, or a census pin differs.
It then writes integration/runtime-summary-v5-<UTC>.json (exclusive create) with every member's input pin, candidate +
noR5 paths and on-disk sha256, native words/CLUT paths and sha256 (flagging paths outside C:/github/Einhander), shape
identity per unit and cross-folder conflicts (same key + dir, different repaired alpha) computed over all members.
Usage: python -I -B ui_build_summary_v1.py --v5-tool-sha256 <hash> <result folder> [<result folder> ...]"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
CENSUS = UI_OUT / "census/failure-census-20261114T170036Z.json"
CENSUS_SHA256 = "fff7a1c811c92ed5a6999220ddad641f06712605248736a79d14adf27e80c5b0"
PROJECT = "c:/github/einhander/"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v5-tool-sha256", required=True, nargs="+")
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    assert sha(CENSUS) == CENSUS_SHA256, "census changed"
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    errors, seen, members, info = [], {}, {}, {}
    for run in a.runs:
        rd = Path(run).resolve()
        assert os.path.commonpath([str(rd).lower(), str(UI_OUT.resolve()).lower()]) == str(UI_OUT.resolve()).lower(), rd
        res = json.loads((rd / "result.json").read_text(encoding="utf-8"))
        if res["tool_sha256"] not in a.v5_tool_sha256:
            errors.append(f"{rd.name}: tool {res['tool_sha256'][:12]} is not an accepted v5 hash")
        if res.get("census_sha256") != CENSUS_SHA256:
            errors.append(f"{rd.name}: census pin differs")
        info[rd.name] = dict(result_sha256=sha(rd / "result.json"), tool_sha256=res["tool_sha256"],
                             status=res.get("status_run"), rows=len(res["rows"]), remaining=len(res.get("remaining", [])))
        for r in res["rows"]:
            key = (f"{r['lane']}/{r['folder']}", r["file"])
            if key in members:
                errors.append(f"member built twice: {key}")
            for vname, v in r["variants"].items():
                p = (rd / v["path"]).resolve()
                k = str(p).lower()
                if k in seen:
                    errors.append(f"path referenced twice: {p}")
                seen[k] = v["sha256"]
                if not p.is_file():
                    errors.append(f"missing: {p}")
                elif sha(p) != v["sha256"]:
                    errors.append(f"hash mismatch: {p}")
            members[key] = (rd, r)
    if errors:
        print("REFUSED", len(errors), "errors; first:", errors[:10])
        sys.exit(1)
    units, conflicts = [], collections.defaultdict(list)
    for u in census["units"]:
        built = [(m, members.get((u["folder"], m))) for m in u["members"]]
        if not any(b for _, b in built):
            continue
        out = []
        for m, b in built:
            if not b:
                out.append(dict(file=m, built=False))
                continue
            rd, r = b
            v, n = r["variants"]["snap-native"], r["variants"]["snap-native-noR5"]
            clut = r["native"]["clut"] or ""
            out.append(dict(file=m, built=True, input_sha256=r["input_sha256"],
                            candidate=(rd / v["path"]).relative_to(UI_OUT).as_posix(), candidate_sha256=v["sha256"],
                            primary_pass=v["after"]["primary_pass"], s2_pass=v["after"]["s2_strict_pass"],
                            noR5=(rd / n["path"]).relative_to(UI_OUT).as_posix(), noR5_sha256=n["sha256"],
                            alpha_after_sha256=r["alpha_after_sha256"], words=r["native"]["words"],
                            words_sha256=r["native"]["words_sha256"], clut=clut, clut_sha256=r["native"]["clut_sha256"],
                            native_outside_project=not clut.replace("\\", "/").lower().startswith(PROJECT)))
            conflicts[(r["native"]["words_sha256"], u["dir"], os.path.basename(m))].append((u["folder"], r["alpha_after_sha256"]))
        b = [x for x in out if x["built"]]
        units.append(dict(folder=u["folder"], dir=u["dir"], r1=u["r1"], conn=u["conn"], members=out,
                          built=len(b), shape_identical=len({x["alpha_after_sha256"] for x in b}) == 1))
    conf = [dict(key=k[2], dir=k[1], folders=sorted({f for f, _ in v})) for k, v in conflicts.items()
            if len({al for _, al in v}) > 1]
    files = [x for u in units for x in u["members"] if x["built"]]
    summ = dict(run=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), owner="claude-einhander-ui",
                task="EIN-MENU-HUD-20261114", tool_sha256=sha(Path(__file__)), census_sha256=CENSUS_SHA256, runs=info,
                verification=f"every one of {len(seen)} referenced variant files re-hashed from disk; 0 mismatches; 0 duplicate paths",
                status="PROPOSAL for main integration review; class-valid != look/live accepted",
                units=len(units), files=len(files), files_pass=sum(x["primary_pass"] for x in files),
                native_refs_outside_project=sum(x["native_outside_project"] for x in files),
                cross_folder_conflicts=dict(count=len(conf), items=conf), units_detail=units)
    fn = UI_OUT / "integration" / f"runtime-summary-v5-{summ['run']}.json"
    with open(fn, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(summ, indent=1) + "\n")
    print(fn, sha(fn), "units", summ["units"], "files", summ["files"], "pass", summ["files_pass"], "conflicts", len(conf))


if __name__ == "__main__":
    main()
