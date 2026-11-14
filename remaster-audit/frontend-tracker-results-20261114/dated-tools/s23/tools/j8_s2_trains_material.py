"""J8 (claude-einhander-s23): Stage 2 train-car hybrid = J5 crisp Scale2x geometry x the frozen train-cars-v4 material layer.
PIXEL JOB: grant required.

  python -I j8_s2_trains_material.py <out_dir> <budget_seconds>

Why (runs/j5t-20261114T160110Z/compare.json): J5 s2-trains fixes the ledger's rounded-corner defect (straight panel
borders, square machine parts) but has no material (flat painted panels); train-cars-v4 has the weathered-steel layer
but categorical rounded geometry. The v4 material layer is a frozen, CLUT-free multiplicative factor per page
(stage2-train-cars-v4/master/<TEX>-material-factor-8x.npz, factor_f16 with strength folded in: exactly 1.0 within one
texel of transparency and on the protected 1BC35EBE lettering), applied by the lane as rgb = clip(rint(rgb * factor)).
J8 applies that same rule to the J5 colours:
  * page2048: rgb = clip(rint(J5_rgb * factor_8x)) on visible pixels; alpha = J5 alpha byte for byte;
  * page1024: factor_4x = 2x2 area mean of factor_8x; rgb = clip(rint(J5_rgb_1024 * factor_4x)); alpha = J5 alpha;
  * R5 bleed fill (cutout RGB only); strict (s23lib) must equal J5's (alpha unchanged => class unchanged);
  * checks: alpha identical to J5, pixels with factor == 1 identical to J5, mean luminance ratio J8/J5 per key;
  * shimmer SIMULATION on the same windows as the J5 post-check (native | v4 | J5 | J8) and a review sheet.
Known limit stated up front: the high-contrast camouflage on 0F01F0FA keeps J5's diagonal 'worm' shapes (v4's shape
pass only softens low-contrast mottling). Inputs pinned and read only; outputs only in <out_dir>; resumable.
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
import j5_s3_scale2x as J5  # noqa: E402
from PIL import Image  # noqa: E402

V4 = L.ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen/stage2-train-cars-v4"
J5D = L.S23 + "/proposals/s2-trains-scale2x-20261114T160110Z"
PINS = {V4 + "/manifest.json": "28821a39c2cd59704d4e276ff2f2e0b7fbc1d0c6c5cfb8737f8a6129fafcdeb2",
        J5D + "/manifest.json": "46c26204d95de0d85182074528121afa9789f9df5801e7706d9c4478dd0c0871"}
COMPARE = L.S23 + "/runs/j5t-20261114T160110Z/compare.json"


def area_half(f):
    return f.reshape(f.shape[0] // 2, 2, f.shape[1] // 2, 2).mean(axis=(1, 3))


def lum(rgb):
    return rgb[..., :3].astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722])


def main(out, budget):
    L.below_normal()
    b = L.Budget(float(budget))
    assert not os.path.exists(out + "/manifest.json"), "refusing to overwrite a finished proposal"
    os.makedirs(out, exist_ok=True)
    for p, h in PINS.items():
        assert L.sha256_file(p) == h, ("pinned input changed", p)
    v4 = json.load(open(V4 + "/manifest.json", encoding="utf-8"))
    j5 = json.load(open(J5D + "/manifest.json", encoding="utf-8"))
    windows = {k: v["window_uv"] for k, v in json.load(open(COMPARE, encoding="utf-8"))["compare"].items()}
    pages = J5.stage_pages(L.ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen")
    rows_p = out + "/rows.jsonl"
    done = {r["key"] for r in L.read_jsonl(rows_p)}
    L.append_jsonl(out + "/sessions.jsonl", dict(start_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
                                                 affinity=os.environ.get("S23_CPU"), resumed_keys=len(done)))
    factors, natidx, sheet = {}, {}, []
    keys = sorted(v4["keys"])
    for key in keys:
        if key in done:
            continue
        if b.left() < 20:
            break
        tex = v4["keys"][key]["tex"]
        if tex not in factors:
            ml = v4["pages"][tex]["material_layer"]
            mp = f"{V4}/{ml['path']}"
            assert L.sha256_file(mp) == ml["sha256"], ("material layer changed", tex)
            f8 = np.load(mp)["factor_f16"].astype(np.float32)
            factors[tex] = (f8, area_half(f8), dict(path=mp, sha256=ml["sha256"], k_lp=ml.get("k_lp")))
            pg = pages[tex]
            idx, wsha, ok = L.load_words(pg["words"]["path"], pg["vram_rect_words"], tex)
            assert ok and wsha == pg["words"]["sha256"]
            natidx[tex] = idx
        f8, f4, finfo = factors[tex]
        idx = natidx[tex]
        c = L.clut_words(v4["keys"][key]["clut"]["words_hex"])
        ncls, nrgb = L.clut_classes(c)[idx], L.clut_rgb(c)[idx]
        kout = dict(material=finfo, files={})
        for fk, fac in (("page2048", f8), ("page1024", f4)):
            fj = j5["keys"][key]["files"][fk]
            pj = f"{J5D}/{fj['path']}"
            assert L.sha256_file(pj) == fj["sha256"]
            a5 = L.load_rgba(pj)
            s = a5.shape[1] // idx.shape[1]
            a = a5.copy()
            vis = a5[..., 3] != 0
            rgb = np.clip(np.rint(a5[..., :3].astype(np.float32) * fac[..., None]), 0, 255).astype(np.uint8)
            a[..., :3] = np.where(vis[..., None], rgb, a5[..., :3])
            a, written = L.bleed_fill(a)
            v = L.validate(a, ncls, s)
            h = L.save_png(f"{out}/keys/{fk}/{key}.png", a)
            unit = (fac == 1.0) & vis
            l5, l8 = lum(a5)[vis].mean(), lum(a)[vis].mean()
            kout["files"][fk] = dict(path=f"keys/{fk}/{key}.png", sha256=h, source_j5=dict(path=pj, sha256=fj["sha256"]), scale=s,
                                     cutout_rgb_written=written, strict=v,
                                     strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                                     r5_zero=v["r5_fringe_px"] == 0, alpha_identical_to_j5=bool((a[..., 3] == a5[..., 3]).all()),
                                     unit_factor_px_identical_to_j5=bool((a[..., :3][unit] == a5[..., :3][unit]).all()),
                                     mean_lum_ratio_j8_j5=round(float(l8 / l5), 4) if l5 else None,
                                     factor_range_visible=[round(float(fac[vis].min()), 3), round(float(fac[vis].max()), 3)] if vis.any() else None)
            if fk == "page2048" and key in windows:
                win = windows[key]
                v4img = L.load_rgba(f"{V4}/{v4['keys'][key]['files']['page2048']['path']}")
                x0, y0, x1, y1 = win
                crops = {"native": L.up(np.dstack([nrgb, ncls])[y0:y1, x0:x1], 8), "v4": J2.crop(v4img, win, 8),
                         "J5": J2.crop(a5, win, 8), "J8": J2.crop(a, win, 8)}
                kout["compare"] = dict(window_uv=win, **{str(sc): {n: J2.shimmer(cr, sc) for n, cr in crops.items()} for sc in (0.5, 0.33)})
                w, hh = min(32, x1 - x0), min(24, y1 - y0)
                cc = lambda z: J2.over(z[:hh * 8, :w * 8])
                sheet.append((f"{key} uv{win}: native | v4 | J5 | J8", np.concatenate([cc(crops[n]) for n in ("native", "v4", "J5", "J8")], 1)))
        L.append_jsonl(rows_p, dict(key=key, kout=kout))
        print(key, {fk: (x["strict_pass"], x["r5_zero"], x["alpha_identical_to_j5"], x["mean_lum_ratio_j8_j5"]) for fk, x in kout["files"].items()}, flush=True)
    rec = dict(name=os.path.basename(out), owner="claude-einhander-s23", status="PROPOSAL (private; not frozen; not for import)",
               method=__doc__.strip(), pins=PINS, tools={q: L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/" + q)
                                                         for q in ("j8_s2_trains_material.py", "j5_s3_scale2x.py", "s23lib.py")},
               sessions=L.read_jsonl(out + "/sessions.jsonl"), keys={r["key"]: r["kout"] for r in L.read_jsonl(rows_p)})
    rec["complete"] = len(rec["keys"]) == len(keys)
    if sheet:
        wmax = max(r.shape[1] for _, r in sheet)
        canvas = np.concatenate([np.pad(r, ((4, 4), (0, wmax - r.shape[1]), (0, 0))) for _, r in sheet], 0)
        rev = f"{out}/review-native-v4-j5-j8-s{len(rec['sessions'])}.png"
        Image.fromarray(canvas).save(rev)
        rec["review_this_session"] = dict(path=os.path.basename(rev), sha256=L.sha256_file(rev), rows=[t for t, _ in sheet])
    fs = [f for k in rec["keys"].values() for f in k["files"].values()]
    rec["summary"] = dict(keys=len(rec["keys"]), files=len(fs), strict_pass=sum(f["strict_pass"] for f in fs), r5_zero=sum(f["r5_zero"] for f in fs),
                          alpha_identical_to_j5=sum(f["alpha_identical_to_j5"] for f in fs),
                          unit_factor_identical=sum(f["unit_factor_px_identical_to_j5"] for f in fs))
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    target = out + ("/manifest.json" if rec["complete"] else "/PARTIAL.json")
    json.dump(rec, open(target + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(target + ".tmp", target)
    print(json.dumps(dict(rec["summary"], complete=rec["complete"])), os.path.basename(target), L.sha256_file(target))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
