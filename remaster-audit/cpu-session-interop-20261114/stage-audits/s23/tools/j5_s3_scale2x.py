"""J5 (claude-einhander-s23): alternative Stage 3 master by exact Scale2x (AdvMAME2x) index upscaling, cell-isolated.
PIXEL JOB: grant required.

  python -I j5_s3_scale2x.py <out_dir> <budget_seconds>

Why: the categorical index master (walls-v1 / signage-v1) rounds every contour, so dither becomes blobs, 1-texel
lines bead and rectangular parts lose their corners (w7-stage3 LEDGER honest read). Scale2x works on palette INDICES
with exact equality tests, so:
  * it never creates a colour or an index that is not in the 3x3 native neighbourhood (nothing invented);
  * isolated texels and interior checkerboard dither/stipple stay exactly native (rule needs B != H and D != F plus a
    matching pair); straight edges stay straight; diagonal staircases are smoothed; a convex 90-degree corner gets a
    bevel confined to its corner texel (unit test: 21 of 64 HD pixels at 8x); at page/cell borders the edge padding can
    alter corner texels of a checkerboard (4 HD pixels in an 8x8 checkerboard test at 2x);
  * it is CLUT-free, so every palette phase of a page gets the identical shape (phase-consistent silhouettes).
Rule per native texel E with neighbours B (up), D (left), F (right), H (down), applied 3 times for 8x (twice for 4x):
  if B != H and D != F: E0 = D if D == B else E; E1 = F if B == F else E; E2 = D if D == H else E; E3 = F if H == F else E
  else E0 = E1 = E2 = E3 = E   (E0 top-left, E1 top-right, E2 bottom-left, E3 bottom-right)
Cell isolation: each inferred atlas cell of the frozen sets (master/<TEX>-cells-32grid.npy, hash-checked) is upscaled
from its own texels only (texels outside the cell replaced by the nearest in-cell texel), so no neighbouring atlas
cell can leak in at a quad edge.
Per key: RGBA = CLUT[index] with native class alpha; strict R1-R4 (s23lib); violators (if any) snap to the native
class of their cell with native RGB (iterated, counted); R5 bleed fill. page2048 = 8x, page1024 = 4x (both from the
index field, so they agree). Review sheet: native | v1 | Scale2x at 8x for one window per page.
Outputs only under <out_dir> (NEW, private, not frozen, not for import).
"""
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import s23lib as L  # noqa: E402
from scipy import ndimage  # noqa: E402
from PIL import Image  # noqa: E402

S3 = L.ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen"
SETS = {"stage3-machinery-walls-v1": "184e8ad8558826ca75177d3e05293d279d4aa6b28eb4eab2a6c6050ba58cd1e0",
        "stage3-signage-props-v1": "d1b212e91777310f25fa433227cfb1333d8ba838a5de1e7ed98239748b675282"}


def scale2x(a):
    p = np.pad(a, 1, mode="edge")
    B, D, F, H, E = p[:-2, 1:-1], p[1:-1, :-2], p[1:-1, 2:], p[2:, 1:-1], a
    act = (B != H) & (D != F)
    e0 = np.where(act & (D == B), D, E)
    e1 = np.where(act & (B == F), F, E)
    e2 = np.where(act & (D == H), D, E)
    e3 = np.where(act & (H == F), F, E)
    out = np.empty((a.shape[0] * 2, a.shape[1] * 2), a.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out


def up_isolated(idx, labels, times):
    s = 2 ** times
    out = np.empty((idx.shape[0] * s, idx.shape[1] * s), idx.dtype)
    for c in np.unique(labels):
        m = labels == c
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub, mm = idx[y0:y1, x0:x1], m[y0:y1, x0:x1]
        if not mm.all():
            _, (iy, ix) = ndimage.distance_transform_edt(~mm, return_indices=True)
            sub = sub[iy, ix]
        u = sub
        for _ in range(times):
            u = scale2x(u)
        mh = L.up(mm, s)
        blk = out[y0 * s:y1 * s, x0 * s:x1 * s]
        blk[mh] = u[mh]
    return out


def repair(a, idx_up, ncls, nrgb, s, max_passes=8):
    total = 0
    for p in range(1, max_passes + 1):
        v, fl = L.validate(a, ncls, s, want_flags=True)
        bad = fl["r1"] | fl["r2"] | fl["r4"]
        if not bad.any():
            return a, dict(passes=p - 1, repaired_px=total, residual=0)
        C = L.up(ncls, s)
        a[..., 3] = np.where(bad, C, a[..., 3])
        a[bad, :3] = L.up(nrgb, s)[bad]
        total += int(bad.sum())
    v = L.validate(a, ncls, s)
    return a, dict(passes=max_passes, repaired_px=total, residual=v["r1_centre_bad"] + v["r2_displaced_px"] + v["r4_island_px"])


def over(a, bg=(40, 40, 40)):
    al = (a[..., 3:4] != 0).astype(np.float32)
    return (a[..., :3] * al + np.array(bg) * (1 - al)).astype(np.uint8)


def main(out, budget):
    L.below_normal()
    b = L.Budget(float(budget))
    assert not os.path.exists(out + "/manifest.json"), "refusing to overwrite a finished proposal"
    os.makedirs(out, exist_ok=True)
    rec = dict(name=os.path.basename(out), owner="claude-einhander-s23", status="PROPOSAL (private; not frozen; not for import)",
               created_utc=datetime.now(timezone.utc).isoformat(), method=__doc__.strip(),
               tool_sha256={q: L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/" + q) for q in ("j5_s3_scale2x.py", "s23lib.py")},
               sets={}, pages={}, keys={})
    sheet = []
    for setname, msha in SETS.items():
        d = f"{S3}/{setname}"
        assert L.sha256_file(d + "/manifest.json") == msha, setname
        m = json.load(open(d + "/manifest.json", encoding="utf-8"))
        rec["sets"][setname] = msha
        for tex, pg in m["pages"].items():
            idx, wsha, ok = L.load_words(pg["words"]["path"], pg["vram_rect_words"], tex)
            assert ok and wsha == pg["words"]["sha256"]
            lp = f"{d}/{pg['cells']['file']}"
            assert L.sha256_file(lp) == pg["cells"]["sha256"]
            labels = np.load(lp)
            up8, up4 = up_isolated(idx, labels, 3), up_isolated(idx, labels, 2)
            changed8 = int((up8 != L.up(idx, 8)).sum())
            rec["pages"][tex] = dict(set=setname, words_sha256=wsha, cells=int(len(np.unique(labels))),
                                     px_changed_vs_nearest_8x=changed8, share_changed_8x=round(changed8 / up8.size, 4))
            np.save(f"{out}/{tex}-index-8x.npy", up8)
            rec["pages"][tex]["index_8x"] = dict(path=f"{tex}-index-8x.npy", sha256=L.sha256_file(f"{out}/{tex}-index-8x.npy"))
            first = True
            for key, ke in sorted(m["keys"].items()):
                if ke["tex"] != tex:
                    continue
                if b.left() < 25:
                    rec["stopped_on_budget_before"] = key
                    break
                c = L.clut_words(ke["clut"]["words_hex"])
                cls, rgb = L.clut_classes(c), L.clut_rgb(c)
                ncls, nrgb = cls[idx], rgb[idx]
                kout = dict(set=setname, files={})
                for fk, up, s in (("page2048", up8, 8), ("page1024", up4, 4)):
                    a = np.dstack([rgb[up], cls[up]])
                    a, rep = repair(a, up, ncls, nrgb, s)
                    a, written = L.bleed_fill(a)
                    v = L.validate(a, ncls, s)
                    h = L.save_png(f"{out}/keys/{fk}/{key}.png", a)
                    kout["files"][fk] = dict(path=f"keys/{fk}/{key}.png", sha256=h, scale=s, repair=rep, cutout_rgb_written=written, strict=v,
                                             strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                                             r5_zero=v["r5_fringe_px"] == 0)
                    if fk == "page2048" and first:
                        v1 = L.load_rgba(f"{d}/{ke['files']['page2048']['path']}")
                        ys, xs = np.nonzero(L.up(ncls != 0, 1))
                        cy0 = int(np.clip(np.median(ys) - 16, 0, idx.shape[0] - 32))
                        cx0 = int(np.clip(np.median(xs) - 24, 0, idx.shape[1] - 48))
                        r = (cx0, cy0, cx0 + 48, cy0 + 32)
                        nat = over(L.up(np.dstack([nrgb, ncls])[r[1]:r[3], r[0]:r[2]], 8))
                        cr = lambda z: over(z[r[1] * 8:r[3] * 8, r[0] * 8:r[2] * 8])
                        sheet.append((f"{key} uv{list(r)}: native 8x | v1 | scale2x-8x", np.concatenate([nat, cr(v1), cr(a)], 1)))
                        first = False
                rec["keys"][key] = kout
                print(key, {fk: (x["strict_pass"], x["repair"]["repaired_px"], x["r5_zero"]) for fk, x in kout["files"].items()}, flush=True)
    if sheet:
        wmax = max(r.shape[1] for _, r in sheet)
        canvas = np.concatenate([np.pad(r, ((4, 4), (0, wmax - r.shape[1]), (0, 0))) for _, r in sheet], 0)
        Image.fromarray(canvas).save(f"{out}/review-native-v1-scale2x.png")
        rec["review"] = dict(path="review-native-v1-scale2x.png", sha256=L.sha256_file(f"{out}/review-native-v1-scale2x.png"),
                             rows=[t for t, _ in sheet])
    files = [f for k in rec["keys"].values() for f in k["files"].values()]
    rec["summary"] = dict(keys=len(rec["keys"]), files=len(files), strict_pass=sum(f["strict_pass"] for f in files),
                          r5_zero=sum(f["r5_zero"] for f in files), repaired_px=sum(f["repair"]["repaired_px"] for f in files))
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    json.dump(rec, open(out + "/manifest.json.tmp", "w", encoding="utf-8"), indent=1)
    os.replace(out + "/manifest.json.tmp", out + "/manifest.json")
    print(json.dumps(rec["summary"]), "manifest", L.sha256_file(out + "/manifest.json"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
