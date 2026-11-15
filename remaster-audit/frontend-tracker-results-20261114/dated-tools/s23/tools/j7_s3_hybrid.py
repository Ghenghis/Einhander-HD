"""J7 (claude-einhander-s23): Stage 3 signage hybrid = J5 Scale2x base + J2-a noise cells as exact native texels.
PIXEL JOB: grant required.

  python -I j7_s3_hybrid.py <out_dir> <budget_seconds>

Why (runs/j5-20261114T154534Z/compare.json): J5 (Scale2x on indices) keeps straight structure crisp (vent slats,
mortar lines, panel borders) but joins diagonal neighbours in high-entropy stone noise into small 'worm' shapes;
J2-a (exact native texels in detected noise cells) is clean in the noise but leaves v1's rounded categorical structure
elsewhere. J7 takes J5 everywhere and J2-a's noise cells (its D masks, CLUT-free, phase-consistent) as native texels.
Inputs (pinned, read only): J5 proposals/s3-scale2x-20261114T154534Z (manifest 22370974...), J2-a
proposals/s3-dither-hybrid-a-20261114T143143Z (manifest 2775b232...: D masks), native words/CLUTs via the frozen
stage3-signage-props-v1 manifest. Scope: the 14 signage keys (E49BC3F1 / AA5DBEF2); the 25 wall keys have no D cells
and J5 stands for them unchanged.
Per key and size: replace whole D cells by native texels; island repair (J2 rule, counted); R5 bleed fill; strict
(s23lib); outside-D alpha and visible RGB must equal J5 byte for byte. Shimmer SIMULATION + gradient proxy on the J2
windows; review sheet native | J2a | J5 | J7. Resumable (rows.jsonl); manifest only when complete.
"""
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import s23lib as L  # noqa: E402
import j2_s3_dither_hybrid as J2  # noqa: E402
from PIL import Image  # noqa: E402

V1 = L.ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen/stage3-signage-props-v1"
J5D = L.S23 + "/proposals/s3-scale2x-20261114T154534Z"
J2D = L.S23 + "/proposals/s3-dither-hybrid-a-20261114T143143Z"
PINS = {V1 + "/manifest.json": "d1b212e91777310f25fa433227cfb1333d8ba838a5de1e7ed98239748b675282",
        J5D + "/manifest.json": "22370974abccc6d5868d021c48d1ccee27fa5e0eaafdce1ae9cb4eb372f9128e",
        J2D + "/manifest.json": "2775b23264569d215a809faea4ee018bc6a538fbd934393cb59e94009f9597ad"}
WINDOWS = {"E49BC3F1": [0, 64, 64, 128], "AA5DBEF2": [188, 124, 252, 188]}


def main(out, budget):
    L.below_normal()
    b = L.Budget(float(budget))
    assert not os.path.exists(out + "/manifest.json"), "refusing to overwrite a finished proposal"
    os.makedirs(out, exist_ok=True)
    for p, h in PINS.items():
        assert L.sha256_file(p) == h, ("pinned input changed", p)
    v1m = json.load(open(V1 + "/manifest.json", encoding="utf-8"))
    j5m = json.load(open(J5D + "/manifest.json", encoding="utf-8"))
    j2m = json.load(open(J2D + "/manifest.json", encoding="utf-8"))
    pages = {}
    for tex in ("E49BC3F1", "AA5DBEF2"):
        pg = v1m["pages"][tex]
        idx, wsha, ok = L.load_words(pg["words"]["path"], pg["vram_rect_words"], tex)
        assert ok and wsha == pg["words"]["sha256"]
        dm = j2m["pages"][tex]["D_mask"]
        assert L.sha256_file(f"{J2D}/{dm['path']}") == dm["sha256"]
        D = np.asarray(Image.open(f"{J2D}/{dm['path']}")) > 0
        pages[tex] = (idx, D)
    rows_p = out + "/rows.jsonl"
    done = {r["key"] for r in L.read_jsonl(rows_p)}
    L.append_jsonl(out + "/sessions.jsonl", dict(start_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
                                                 affinity=os.environ.get("S23_CPU"), resumed_keys=len(done)))
    keys = sorted(k for k, v in v1m["keys"].items() if v["tex"] in pages)
    sheet, reviewed = [], set()
    for key in keys:
        if key in done:
            continue
        if b.left() < 20:
            break
        tex = key[:8]
        idx, D = pages[tex]
        c = L.clut_words(v1m["keys"][key]["clut"]["words_hex"])
        ncls, nrgb = L.clut_classes(c)[idx], L.clut_rgb(c)[idx]
        kout = dict(files={})
        for fk in ("page2048", "page1024"):
            f5 = j5m["keys"][key]["files"][fk]
            p5 = f"{J5D}/{f5['path']}"
            assert L.sha256_file(p5) == f5["sha256"]
            a5 = L.load_rgba(p5)
            s = a5.shape[1] // idx.shape[1]
            Dh = L.up(D, s)
            a = a5.copy()
            a[Dh] = np.dstack([L.up(nrgb, s), L.up(ncls, s)])[Dh]
            a, rep = J2.repair_islands(a, ncls, nrgb, s)
            alpha_before_fill = a[..., 3].copy()
            v = L.validate(a, ncls, s)
            a, written = L.bleed_fill(a)
            assert (a[..., 3] == alpha_before_fill).all()
            e = L.edge_fill(a)
            v["r5_fringe_px"] = int((e["edge"] & (np.abs(a[..., :3].astype(np.int16) - e["rgb"].astype(np.int16)).max(-1) > 0)).sum())
            vis5, vis = a5[..., 3] != 0, a[..., 3] != 0
            h = L.save_png(f"{out}/keys/{fk}/{key}.png", a)
            kout["files"][fk] = dict(path=f"keys/{fk}/{key}.png", sha256=h, source_j5=dict(path=p5, sha256=f5["sha256"]), scale=s,
                                     native_cells_replaced=int(D.sum()), island_repair=rep, cutout_rgb_written=written, strict=v,
                                     strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                                     r5_zero=v["r5_fringe_px"] == 0,
                                     outside_D_alpha_identical_to_j5=bool((a[..., 3][~Dh] == a5[..., 3][~Dh]).all()),
                                     outside_D_visible_rgb_identical_to_j5=bool((a[..., :3][~Dh & vis & vis5] == a5[..., :3][~Dh & vis & vis5]).all()))
            if fk == "page2048" and tex not in reviewed:
                reviewed.add(tex)
                win = WINDOWS[tex]
                j2a = L.load_rgba(f"{J2D}/keys/page2048/{key}.png")
                x0, y0, x1, y1 = win
                crops = {"native": L.up(np.dstack([nrgb, ncls])[y0:y1, x0:x1], 8), "J2a": J2.crop(j2a, win, 8), "J5": J2.crop(a5, win, 8), "J7": J2.crop(a, win, 8)}
                kout["compare"] = dict(window_uv=win, **{str(sc): {n: J2.shimmer(cr, sc) for n, cr in crops.items()} for sc in (0.5, 0.33)})
                sub = [x0 + 8, y0 + 16, x0 + 40, y0 + 40]
                cc = lambda z: J2.over(z[(sub[1] - y0) * 8:(sub[3] - y0) * 8, (sub[0] - x0) * 8:(sub[2] - x0) * 8])
                sheet.append((f"{key} uv{sub}: native | J2a | J5 | J7", np.concatenate([cc(crops[n]) for n in ("native", "J2a", "J5", "J7")], 1)))
        L.append_jsonl(rows_p, dict(key=key, kout=kout))
        print(key, {fk: (x["strict_pass"], x["r5_zero"], x["island_repair"]["repaired_px"], x["outside_D_alpha_identical_to_j5"]) for fk, x in kout["files"].items()}, flush=True)
    rec = dict(name=os.path.basename(out), owner="claude-einhander-s23", status="PROPOSAL (private; not frozen; not for import)",
               method=__doc__.strip(), pins=PINS, tools={q: L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/" + q)
                                                         for q in ("j7_s3_hybrid.py", "j2_s3_dither_hybrid.py", "s23lib.py")},
               D_texels={t: int(v[1].sum()) for t, v in pages.items()}, sessions=L.read_jsonl(out + "/sessions.jsonl"),
               keys={r["key"]: r["kout"] for r in L.read_jsonl(rows_p)})
    rec["complete"] = len(rec["keys"]) == len(keys)
    if sheet:
        w = max(r.shape[1] for _, r in sheet)
        canvas = np.concatenate([np.pad(r, ((4, 4), (0, w - r.shape[1]), (0, 0))) for _, r in sheet], 0)
        rev = f"{out}/review-native-j2a-j5-j7-s{len(rec['sessions'])}.png"
        Image.fromarray(canvas).save(rev)
        rec["review_this_session"] = dict(path=os.path.basename(rev), sha256=L.sha256_file(rev), rows=[t for t, _ in sheet])
    fs = [f for k in rec["keys"].values() for f in k["files"].values()]
    rec["summary"] = dict(keys=len(rec["keys"]), files=len(fs), strict_pass=sum(f["strict_pass"] for f in fs), r5_zero=sum(f["r5_zero"] for f in fs),
                          outside_D_identical_to_j5=sum(f["outside_D_alpha_identical_to_j5"] and f["outside_D_visible_rgb_identical_to_j5"] for f in fs))
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    target = out + ("/manifest.json" if rec["complete"] else "/PARTIAL.json")
    json.dump(rec, open(target + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(target + ".tmp", target)
    print(json.dumps(dict(rec["summary"], complete=rec["complete"])), os.path.basename(target), L.sha256_file(target))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
