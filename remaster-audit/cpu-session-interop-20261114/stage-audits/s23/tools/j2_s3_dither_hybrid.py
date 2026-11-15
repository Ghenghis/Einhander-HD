"""J2 (claude-einhander-s23): isolated, source-faithful repair proposal for the documented Stage 3 dither/blob
defects on E49BC3F1 (brick/stone wall, CAUTION-plate stipple) and AA5DBEF2 (granite panel fill).
PIXEL JOB: run only inside a granted CPU slot.

  python -I j2_s3_dither_hybrid.py <out_dir> <budget_seconds> [a|b]

Problem (w7-stage3 LEDGER, signage-v1 honest read): the categorical index master turns native dither/stipple and
low-contrast mottling into a rounded cellular "camouflage" that reads worse than native; a CPU stipple-to-mean pilot
(work/failed-dither-rebuild-pilot) erased brick courses and FAILED. Those cells "should stay native until a better
method exists".

Proposal P1 "native-dither hybrid" (nothing invented, CPU, deterministic):
  * D = noise texels on the CLUT-free native index map, restricted to the ledger-named surfaces (REGIONS below):
      small-component density: share of texels in a 5x5 window whose same-index 4-connected component has <= 3 texels
      >= SMALL_THR, and long-run share (texels on a same-index horizontal/vertical run >= 4) <= LONG_THR;
      3x3 closing; components < MIN_COMPONENT texels dropped. Index-based, so every CLUT phase of the page gets the
      same D (phase-consistent shape).
  * Every native cell in D takes the exact native texel (nearest: colour = CLUT entry, alpha = native class) over the
    whole s x s cell, at page2048 (s=8) and page1024 (s=4). Every other pixel is byte-identical to frozen
    stage3-signage-props-v1 (read only).
  * Whole-cell class check (s23lib independent rules R1-R4). Any R4 island created where a v1 contour chained through
    a now-native cell is repaired by giving the violating pixel its cell's native class (RGB = native texel RGB when it
    becomes visible); passes and pixels are reported.
  * R5 bleed fill on cutout RGB only (alpha and visible RGB byte-identical) -> proto-v2b R5 == 0.
Outputs (NEW, private, not frozen, not for import): <out_dir>/keys/page2048|page1024/<key>.png, masks, review sheets,
manifest.json with source hashes, D statistics, class results, sampled fringe, and a shimmer SIMULATION
(bilinear-no-mip minus 2x2-supersampled reference, frame difference under a sub-pixel pan) native vs v1 vs P1.
"""
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import s23lib as L  # noqa: E402
from scipy import ndimage  # noqa: E402
from PIL import Image  # noqa: E402

V1 = L.ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen/stage3-signage-props-v1"
V1_MANIFEST_SHA = "d1b212e91777310f25fa433227cfb1333d8ba838a5de1e7ed98239748b675282"
# Ledger-named surfaces, native texel rects [x0, y0, x1, y1) read off the native pages (see review sheets).
REGIONS = {
    "E49BC3F1": {"brick_stone_wall": [0, 0, 128, 128], "caution_plate": [128, 128, 256, 256]},
    "AA5DBEF2": {"granite_panels": [0, 64, 256, 192]},
}
SMALL_THR, LONG_THR, MIN_COMPONENT, SMALL_MAX = 0.40, 0.45, 24, 3
MOTTLE_RANGE, MOTTLE_LONG = 3, 0.80


def run_lengths(idx):
    out = np.zeros(idx.shape, np.int32)
    for axis in (0, 1):
        a = idx if axis == 1 else idx.T
        r = np.zeros(a.shape, np.int32)
        for y in range(a.shape[0]):
            row = a[y]
            ch = np.flatnonzero(np.diff(row) != 0) + 1
            st, en = np.r_[0, ch], np.r_[ch, row.size]
            for s_, e_ in zip(st, en):
                r[y, s_:e_] = e_ - s_
        out = np.maximum(out, r if axis == 1 else r.T)
    return out


def small_components(idx):
    small = np.zeros(idx.shape, bool)
    st = ndimage.generate_binary_structure(2, 1)
    for i in np.unique(idx):
        lab, n = ndimage.label(idx == i, st)
        if n:
            sz = np.bincount(lab.ravel())
            sz[0] = 0
            small |= (sz[lab] <= SMALL_MAX) & (lab > 0)
    return small


def detect(idx, regions, keep_structure=False):
    """Variant a: D as below. Variant b (keep_structure): texels on a same-index horizontal/vertical run >= 4 (letter
    strokes, mortar lines, slats) are removed from D after closing, so they keep the v1 smooth contours and only the
    short noise texels between them take native texels.
    D = noise/stipple (small-component density, few long runs) OR low-contrast mottling (>= 3 distinct indices
    within an index range <= MOTTLE_RANGE in the 5x5 window, few long runs). The mottling rule assumes palette ramps are
    stored in index order; where a CLUT is not luminance-monotone the rule only changes which cells keep native texels
    (never their colours or classes), so a misclassification costs smoothing, not faithfulness."""
    small_d = ndimage.uniform_filter(small_components(idx).astype(np.float32), 5, mode="nearest")
    long_d = ndimage.uniform_filter((run_lengths(idx) >= 4).astype(np.float32), 5, mode="nearest")
    mx = ndimage.maximum_filter(idx, 5, mode="nearest").astype(np.int16)
    mn = ndimage.minimum_filter(idx, 5, mode="nearest").astype(np.int16)
    distinct = np.stack([ndimage.maximum_filter((idx == i).astype(np.uint8), 5, mode="nearest") for i in range(16)]).sum(0)
    R = np.zeros(idx.shape, bool)
    for x0, y0, x1, y1 in regions.values():
        R[y0:y1, x0:x1] = True
    noise = (small_d >= SMALL_THR) & (long_d <= LONG_THR)
    mottle = (distinct >= 3) & ((mx - mn) <= MOTTLE_RANGE) & (long_d <= MOTTLE_LONG)
    D = (noise | mottle) & R
    D = ndimage.binary_closing(D, np.ones((3, 3), bool)) & R
    if keep_structure:
        D &= run_lengths(idx) < 4
    lab, n = ndimage.label(D)
    if n:
        sz = np.bincount(lab.ravel())
        sz[0] = 0
        D = (sz[lab] >= MIN_COMPONENT) & (lab > 0)
    return D, dict(small_share=float(small_d.mean()), long_share=float(long_d.mean()))


def repair_islands(a, ncls, nrgb, s, max_passes=8):
    total, passes = 0, 0
    for passes in range(1, max_passes + 1):
        v, fl = L.validate(a, ncls, s, want_flags=True)
        bad = fl["r1"] | fl["r2"] | fl["r4"]
        nb = int(bad.sum())
        if nb == 0:
            return a, dict(passes=passes - 1, repaired_px=total, residual=0)
        C = L.up(ncls, s)
        becomes_vis = bad & (a[..., 3] == 0) & (C != 0)
        a[..., 3] = np.where(bad, C, a[..., 3])
        rgb_up = L.up(nrgb, s)
        a[becomes_vis, :3] = rgb_up[becomes_vis]
        total += nb
    v = L.validate(a, ncls, s)
    return a, dict(passes=passes, repaired_px=total, residual=v["r1_centre_bad"] + v["r2_displaced_px"] + v["r4_island_px"])


def shimmer(a, scale, frames=6, seed=0):
    """SIMULATION: mean |e_t - e_(t-1)| with e = bilinear-no-mip minus 2x2-supersampled reference, sub-pixel pan."""
    H, W = a.shape[:2]
    vis = a[..., 3] != 0
    rgb = np.where(vis[..., None], a[..., :3], 0).astype(np.float64)
    oh, ow = int(H * scale), int(W * scale)
    ys, xs = np.mgrid[0:oh, 0:ow]
    errs, prev = [], None
    for t in range(frames):
        dx = dy = 0.37 * t
        u = ((xs + 0.5 + dx) / scale).ravel()
        v = ((ys + 0.5 + dy) / scale).ravel()
        cur = L.bilinear(rgb, np.clip(u, 0, W - 1e-3), np.clip(v, 0, H - 1e-3))
        ref = 0
        for oy in (-0.25, 0.25):
            for ox in (-0.25, 0.25):
                ref = ref + L.bilinear(rgb, np.clip(u + ox / scale, 0, W - 1e-3), np.clip(v + oy / scale, 0, H - 1e-3))
        e = cur - ref / 4
        if prev is not None:
            errs.append(float(np.abs(e - prev).mean()))
        prev = e
    return round(float(np.mean(errs)), 4)


def crop(a, r, s):
    x0, y0, x1, y1 = r
    return a[y0 * s:y1 * s, x0 * s:x1 * s]


def over(a, bg=(40, 40, 40)):
    al = (a[..., 3:4] != 0).astype(np.float32)
    return (a[..., :3] * al + np.array(bg) * (1 - al)).astype(np.uint8)


def main(out, budget, variant="a"):
    assert variant in ("a", "b"), variant
    L.below_normal()
    b = L.Budget(float(budget))
    assert not os.path.exists(out + "/manifest.json"), "refusing to overwrite a finished proposal"
    os.makedirs(out, exist_ok=True)
    msha = L.sha256_file(V1 + "/manifest.json")
    assert msha == V1_MANIFEST_SHA, msha
    m = json.load(open(V1 + "/manifest.json", encoding="utf-8"))
    rec = dict(name=os.path.basename(out), variant=variant, owner="claude-einhander-s23", status="PROPOSAL (private; not frozen; not for import)",
               created_utc=datetime.now(timezone.utc).isoformat(), method=__doc__.strip(),
               base=dict(path=V1, manifest_sha256=msha), regions=REGIONS,
               params=dict(small_thr=SMALL_THR, long_thr=LONG_THR, min_component=MIN_COMPONENT, small_max=SMALL_MAX,
                           mottle_range=MOTTLE_RANGE, mottle_long=MOTTLE_LONG),
               tools={q: L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/" + q) for q in ("j2_s3_dither_hybrid.py", "s23lib.py")},
               pages={}, keys={}, review=[])
    pages = {}
    for tex in REGIONS:
        pg = m["pages"][tex]
        idx, wsha, crc_ok = L.load_words(pg["words"]["path"], pg["vram_rect_words"], tex)
        assert crc_ok and wsha == pg["words"]["sha256"], (tex, wsha)
        D, st = detect(idx, REGIONS[tex], keep_structure=(variant == "b"))
        pages[tex] = (idx, D)
        Image.fromarray((D * 255).astype(np.uint8)).save(f"{out}/{tex}-D-native.png")
        rec["pages"][tex] = dict(words=pg["words"], D_texels=int(D.sum()), D_share_of_page=round(float(D.mean()), 4),
                                 D_share_of_regions={n: round(float(D[r[1]:r[3], r[0]:r[2]].mean()), 4) for n, r in REGIONS[tex].items()},
                                 D_mask=dict(path=f"{tex}-D-native.png", sha256=L.sha256_file(f"{out}/{tex}-D-native.png")), detector=st)
        print(tex, "D texels", int(D.sum()), flush=True)
    sheet_rows = []
    for key, ke in sorted(m["keys"].items()):
        tex = ke["tex"]
        if tex not in pages:
            continue
        if b.left() < 25:
            rec["stopped_on_budget_before"] = key
            break
        idx, D = pages[tex]
        c = L.clut_words(ke["clut"]["words_hex"])
        ncls, nrgb = L.clut_classes(c)[idx], L.clut_rgb(c)[idx]
        kout = dict(clut=ke["clut"]["crc32"], files={})
        for fk, f in ke["files"].items():
            src = f"{V1}/{f['path']}"
            ssha = L.sha256_file(src)
            assert ssha == f["sha256"], (src, ssha)
            a0 = L.load_rgba(src)
            s = a0.shape[1] // idx.shape[1]
            a = a0.copy()
            Dh = L.up(D, s)
            nat = np.dstack([L.up(nrgb, s), L.up(ncls, s)])
            a[Dh] = nat[Dh]
            a, rep = repair_islands(a, ncls, nrgb, s)
            a, written = L.bleed_fill(a)
            v = L.validate(a, ncls, s)
            vis0, vis1 = a0[..., 3] != 0, a[..., 3] != 0
            untouched = ~Dh
            p = f"{out}/keys/{fk}/{key}.png"
            h = L.save_png(p, a)
            back = L.load_rgba(p)
            assert (back == a).all()
            fr = L.sampled_fringe(a, n=50000)
            kout["files"][fk] = dict(path=f"keys/{fk}/{key}.png", sha256=h, source=dict(path=src, sha256=ssha), scale=s,
                                     native_cells_replaced=int(D.sum()), island_repair=rep, cutout_rgb_written=written,
                                     outside_D_alpha_identical_to_v1=bool((a[..., 3][untouched] == a0[..., 3][untouched]).all()),
                                     outside_D_visible_rgb_identical_to_v1=bool((a[..., :3][untouched & vis0 & vis1] == a0[..., :3][untouched & vis0 & vis1]).all()),
                                     strict=v, strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                                     r5_zero=v["r5_fringe_px"] == 0, sampled_fringe_after=fr)
            if fk == "page2048":
                for name, r in REGIONS[tex].items():
                    x0, y0, x1, y1 = r
                    natc = np.dstack([nrgb, ncls])[y0:y1, x0:x1]
                    kout.setdefault("shimmer_sim", {})[name] = {
                        sc: dict(native_nearest=shimmer(L.up(natc, 8), sc), v1=shimmer(crop(a0, r, 8), sc), p1=shimmer(crop(a, r, 8), sc))
                        for sc in (0.5, 0.33)}
                if len(sheet_rows) < 6:
                    for name, r in REGIONS[tex].items():
                        x0, y0, x1, y1 = r
                        w = min(48, x1 - x0)
                        hh = min(32, y1 - y0)
                        sub = [x0 + (x1 - x0 - w) // 2, y0 + (y1 - y0 - hh) // 2]
                        rr = [sub[0], sub[1], sub[0] + w, sub[1] + hh]
                        natc = over(L.up(np.dstack([nrgb, ncls])[rr[1]:rr[3], rr[0]:rr[2]], 8))
                        row = np.concatenate([natc, over(crop(a0, rr, 8)), over(crop(a, rr, 8))], 1)
                        sheet_rows.append((f"{key} {name} uv{rr}: native 8x | v1 | P1", row))
        rec["keys"][key] = kout
        print(key, {k: (x["strict_pass"], x["r5_zero"], x["island_repair"]["repaired_px"]) for k, x in kout["files"].items()}, flush=True)
    if sheet_rows:
        wmax = max(r.shape[1] for _, r in sheet_rows)
        canvas = np.concatenate([np.pad(r, ((4, 4), (0, wmax - r.shape[1]), (0, 0))) for _, r in sheet_rows], 0)
        Image.fromarray(canvas).save(f"{out}/review-native-v1-p1.png")
        rec["review"] = [dict(path="review-native-v1-p1.png", sha256=L.sha256_file(f"{out}/review-native-v1-p1.png"),
                              rows=[t for t, _ in sheet_rows])]
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    files = rec["keys"].values()
    rec["summary"] = dict(keys=len(rec["keys"]), files=sum(len(k["files"]) for k in files),
                          strict_pass=sum(f["strict_pass"] for k in files for f in k["files"].values()),
                          r5_zero=sum(f["r5_zero"] for k in files for f in k["files"].values()))
    json.dump(rec, open(out + "/manifest.json.tmp", "w", encoding="utf-8"), indent=1)
    os.replace(out + "/manifest.json.tmp", out + "/manifest.json")
    print(json.dumps(rec["summary"]), "manifest", L.sha256_file(out + "/manifest.json"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "a")
