"""J4 (claude-einhander-s23): alpha-preserving cutout-RGB bleed-fill copies of the selected Stage 2/3 files that have
an R5 fringe. PIXEL JOB: run only inside a granted CPU slot.

  python -I j4_r5_bleed.py <out_dir> <budget_seconds>

Input list: J1 rows (runs/j1-20261114T134041Z/rows.jsonl, pinned) with np.r5_fringe_px > 0. For each file:
  * source PNG re-hashed = J1 png_sha256 (frozen input unchanged);
  * s23lib.bleed_fill: cutout pixels only; layer-1 = proto-v2b BFS winner, deeper = Euclidean-nearest visible;
  * checks: alpha byte-identical, visible RGB byte-identical, strict R1-R4 unchanged (0), R5 == 0, re-read == written;
  * sampled fringe before/after.
Copies go to <out_dir>/<stage folder>/<frozen folder>/<keys path> (NEW, private, not frozen, not for import).
Resumable (rows.jsonl). Frozen inputs are never written.
"""
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import s23lib as L  # noqa: E402

J1 = L.S23 + "/runs/j1-20261114T134041Z/rows.jsonl"
J1_SHA = "6b2000316400ba80c5bb24e90075a4ef5e0779ac31ef0add07926f3864e2124b"


def main(out, budget):
    L.below_normal()
    b = L.Budget(float(budget))
    os.makedirs(out, exist_ok=True)
    assert L.sha256_file(J1) == J1_SHA
    rows_p = out + "/rows.jsonl"
    done = {r["source"] for r in L.read_jsonl(rows_p)}
    todo = [r for r in L.read_jsonl(J1) if r["np"]["r5_fringe_px"] > 0 and r["path"] not in done]
    L.append_jsonl(out + "/sessions.jsonl", dict(start_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), todo=len(todo),
                                                 tool_sha256=L.sha256_file(os.path.abspath(__file__)),
                                                 lib_sha256=L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/s23lib.py")))
    words = {}
    n = 0
    for r in todo:
        if b.left() < 15:
            break
        p = r["path"]
        assert L.sha256_file(p) == r["png_sha256"], p
        a0 = L.load_rgba(p)
        a, written = L.bleed_fill(a0)
        vis = a0[..., 3] != 0
        rel = p.split("/comfy-authoring/")[1]
        dst = f"{out}/{rel}"
        h = L.save_png(dst, a)
        back = L.load_rgba(dst)
        # strict class check against the native class map (page words from any manifest of the same stage + key CLUT)
        tex = r["key"].split("-")[0]
        if tex not in words:
            frozen_root = p.split("/keys/")[0].rsplit("/", 1)[0]
            pg = None
            for name in sorted(os.listdir(frozen_root)):
                mp = f"{frozen_root}/{name}/manifest.json"
                if pg is None and os.path.exists(mp):
                    pgs = json.load(open(mp, encoding="utf-8")).get("pages") or {}
                    if tex in pgs and isinstance(pgs[tex].get("words"), dict):
                        pg = pgs[tex]
            idx, wsha, ok = L.load_words(pg["words"]["path"], pg["vram_rect_words"], tex)
            assert ok and wsha == r["words"]["sha256"], (tex, wsha)
            words[tex] = idx
        mf = json.load(open(p.split("/keys/")[0] + "/manifest.json", encoding="utf-8"))
        c = L.clut_words(mf["keys"][r["key"]]["clut"]["words_hex"])
        ncls = L.clut_classes(c)[words[tex]]
        v = L.validate(back, ncls, r["scale"])
        rec = dict(stage=r["stage"], key=r["key"], file=r["file"], source=p, source_sha256=r["png_sha256"], out=dst, out_sha256=h,
                   cutout_rgb_written=written, readback_equal=bool((back == a).all()),
                   alpha_identical=bool((back[..., 3] == a0[..., 3]).all()),
                   visible_rgb_identical=bool((back[..., :3][vis] == a0[..., :3][vis]).all()),
                   strict=v, strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                   r5_before=r["np"]["r5_fringe_px"], r5_after=v["r5_fringe_px"],
                   fringe_before=r["sampled_fringe"], fringe_after=L.sampled_fringe(back, n=50000),
                   utc=datetime.now(timezone.utc).isoformat())
        L.append_jsonl(rows_p, rec)
        n += 1
        print(r["key"], r["file"], "r5", rec["r5_before"], "->", rec["r5_after"], "alpha", rec["alpha_identical"], "vis", rec["visible_rgb_identical"],
              "strict", rec["strict_pass"], flush=True)
    rows = L.read_jsonl(rows_p)
    total = sum(1 for r in L.read_jsonl(J1) if r["np"]["r5_fringe_px"] > 0)
    s = dict(updated_utc=datetime.now(timezone.utc).isoformat(), rows=len(rows), expected=total, complete=len(rows) >= total,
             all_alpha_identical=all(r["alpha_identical"] for r in rows), all_visible_rgb_identical=all(r["visible_rgb_identical"] for r in rows),
             all_strict_pass=all(r["strict_pass"] for r in rows), all_r5_zero=all(r["r5_after"] == 0 for r in rows),
             status="PROPOSAL copies (private; not frozen; not for import)")
    json.dump(s, open(out + "/summary.json.tmp", "w", encoding="utf-8"), indent=1)
    os.replace(out + "/summary.json.tmp", out + "/summary.json")
    L.append_jsonl(out + "/sessions.jsonl", dict(end_utc=datetime.now(timezone.utc).isoformat(), new=n))
    print(json.dumps(s))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
