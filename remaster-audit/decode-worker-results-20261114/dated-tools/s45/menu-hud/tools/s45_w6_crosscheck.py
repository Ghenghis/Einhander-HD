#!/usr/bin/env python3
"""s45 menu/HUD: cross-check of s45 fade recovery / fade-alias candidates against the earlier w6-hud-fades v1 track.
(1) overlap of keys; (2) CLUT bytes equality on overlapping keys; (3) runtime PNG equality on overlapping keys;
(4) (304,492) phase sequence: recovered n per draw frame (does it form a coherent cycle?). Read-only; light; writes
ONLY s45/menu-hud/crosscheck-w6/<UTC>/crosscheck.json."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
W6 = RA / "comfy-authoring/w6-hud-fades/frozen/hud-fades-v1"
REC = S45 / "menu-hud/fade-recovery/20261114T150008Z"
JH = S45 / "menu-hud/fade-aliases-v1/20261114T150907Z"
RUN = Path("C:/github/Einhander/windows-x64/tools/research-runs/research-20261112-153406-11eebc24/native")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/crosscheck-w6" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    w6 = json.loads((W6 / "manifest.json").read_text(encoding="utf-8"))
    rec = json.loads((REC / "recovery.json").read_text(encoding="utf-8"))
    jh = json.loads((JH / "result.json").read_text(encoding="utf-8"))
    w6keys = {}
    for k in w6["keys"]:
        key = k["key"] if isinstance(k, dict) else k
        w6keys[key] = k if isinstance(k, dict) else {}
    mine = set(rec["files"])
    overlap = sorted(mine & set(w6keys))
    only_w6 = sorted(set(w6keys) - mine)
    only_mine = sorted(mine - set(w6keys))
    clut_eq, png_eq = {}, {}
    for key in overlap:
        # w6 CLUT file: search the frozen folder for <key>.clut.bin or *-<PAL>.clut.bin
        cands = list(W6.rglob(f"{key}.clut.bin")) + list(W6.rglob(f"*-{key[9:]}.clut.bin"))
        mb = (REC / f"{key}.clut.bin").read_bytes()
        clut_eq[key] = dict(w6_files=[str(c.relative_to(W6)) for c in cands[:2]], equal=bool(cands) and all(c.read_bytes() == mb for c in cands))
        jk = next(x for x in jh["keys"] if x["key"] == key)
        res = {}
        for size in ("2048", "1024"):
            w6p = list(W6.rglob(f"runtime-{size}/{key}.png"))
            mp = JH / jk["runtime"][size]["path"]
            res[size] = dict(w6=str(w6p[0].relative_to(W6)) if w6p else None, equal=bool(w6p) and sha(w6p[0]) == sha(mp))
        png_eq[key] = res
    # (304,492) phase sequence by frame
    rows = [json.loads(line) for line in open(RUN / "capture.jsonl", encoding="utf-8") if "source_draw_query_matched" in line]
    nbypal = {k[9:]: v["phase_n"] for k, v in rec["files"].items() if v["clut_xy"] == [304, 492]}
    seq = sorted({(r["frame"], nbypal[r["key"][9:]]) for r in rows if tuple(r["clut_xy"]) == (304, 492) and r["key"][9:] in nbypal})
    by_frame = collections.OrderedDict()
    for f, n in seq:
        by_frame.setdefault(f, set()).add(n)
    conflicts = {f: sorted(ns) for f, ns in by_frame.items() if len(ns) > 1}
    frames = list(by_frame)
    deltas = collections.Counter()
    for a, b in zip(frames, frames[1:]):
        if b - a == 1:
            deltas[min(by_frame[b]) - min(by_frame[a])] += 1
    out = dict(run=stamp, owner="claude-einhander-s45",
               inputs=dict(w6_manifest_sha256=sha(W6 / "manifest.json"), recovery_sha256=sha(REC / "recovery.json"), jh_result_sha256=sha(JH / "result.json")),
               w6_keys=len(w6keys), s45_keys=len(mine), overlap=len(overlap), only_w6=only_w6, only_s45=len(only_mine),
               combined_unique_keys=len(mine | set(w6keys)),
               clut_bytes_equal_on_overlap=sum(v["equal"] for v in clut_eq.values()), clut_detail=clut_eq,
               png_equal_on_overlap={s: sum(v[s]["equal"] for v in png_eq.values()) for s in ("2048", "1024")}, png_detail=png_eq,
               p304_492=dict(draw_frames=len(by_frame), frames_with_conflicting_n=conflicts,
                             consecutive_frame_n_deltas=dict(deltas),
                             first_80=[(f, sorted(ns)) for f, ns in list(by_frame.items())[:80]]))
    (rd / "crosscheck.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("w6", len(w6keys), "s45", len(mine), "overlap", len(overlap), "only_w6", only_w6, "combined", out["combined_unique_keys"])
    print("clut equal on overlap", out["clut_bytes_equal_on_overlap"], "/", len(overlap), "png equal", out["png_equal_on_overlap"])
    print("304,492 frames", len(by_frame), "conflicts", conflicts, "deltas", dict(deltas))
    print("first frames", out["p304_492"]["first_80"][:40])
    print("run", rd.name, sha(rd / "crosscheck.json"))


if __name__ == "__main__":
    main()
