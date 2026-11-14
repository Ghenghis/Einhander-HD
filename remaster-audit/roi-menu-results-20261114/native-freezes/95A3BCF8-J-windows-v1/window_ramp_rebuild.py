#!/usr/bin/env python3
"""95A3BCF8 ramp-palette window regions M, I and J: faithful window rebuild (claude-einhander), revision r1.
CPU only, below normal, one logical CPU, threads 1 (set before numpy is imported). No GPU, no ComfyUI, no generated
imagery, no fonts.

r1 fixes the independent review of r0 (d80e2dd7, kept as window_ramp_rebuild.r0-reviewed.py, never run on real data):
  D1  exact mean preservation: the residual is spread in proportion to each sample's headroom, so no clip remains
      (r0 left errors of up to 27 levels);
  D2  validation now gates on cell-mean error, exact walls and 4096 alpha uniformity;
  D3  READY.json is written only when validation passes; otherwise FAILED.json is written;
  D4  explicit checks instead of assert;
  D5  thread variables are set before numpy is imported;
  D6  the manifest wording is corrected.
Review observations adopted:
  * per palette, every index whose colour equals the wall colour (index 15) is treated as wall;
  * no frame is drawn on a region-border edge whose neighbour just outside the region is a window texel.

Why: each region is drawn only with its own two palettes (t3-green-lights draw-census). All six palettes are
monotone brightness ramps, and the native classes are only 127 (opaque) or 255 (STP bit). The live parent pages
smear window light across window/wall borders, giving texel-cell mean errors of up to 112-196. In I and J the live
alpha at texel centres also differs from the native class map.

Rebuild, per region and palette:
  * Wall set = indices whose colour equals the index-15 colour. Wall texels keep that exact colour. Every native
    texel keeps its own cell. No window is added, removed or moved.
  * Inside windows, the index field is interpolated bilinearly. Weights are normalised over in-region window texels
    only, so no light bleeds into walls or past the region. Native steps of >= STEP ramp entries stay crisp; these
    are pane/sill divisions. A fractional index maps to a lerp of adjacent ramp entries. Luminance monotonicity is
    checked; the frame and the mean correction move final colours slightly off that curve.
  * A thin dark frame (left/right 1/16, lintel 1.5/16, sill 2/16 of a texel), colour 0.3 C + 0.7 W, is drawn only
    on edges facing a wall texel. The neighbourhood just outside the region is read from the atlas, so frames are
    not drawn mid-window at region borders.
  * Per texel and channel, a two-pass correction makes every cell MEAN equal the native colour exactly:
    an additive pass on the glass, then a headroom-proportional residual that cannot clip.
    4x4 supersampling per output pixel.
  * ALPHA = the native class of each texel (127 or 255), uniform per texel block, inside the region ROI only.
    Classes outside {127, 255} are refused.

Outputs:
  --preview OUTDIR [--regions M,I,J]  region-only renders (8x and 16x), review sheets and preview-stats.json; writes
                                      nothing else.
  --freeze [--regions ...]            frozen/95A3BCF8-<R>-windows-v1 next to this file (exist_ok=False), per region:
      page2048/<key>.png  the live parent page with ONLY the region ROI RGBA replaced; every other pixel is
                          byte-identical;
      page4096/<key>.png  the full page from the w2-v2 float master, with the region at 16x (optional; it changes
                          pixels outside the ROI);
      review/, manifest.json, validation.json, SHA256SUMS.txt, and READY.json (pass) or FAILED.json (fail).
Integration is ROI-only (claude-einhander reviews/ROI-INTEGRATION-PLAN-95A3BCF8-20261114.md)."""
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = Path(__file__).resolve().parent
CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
IDX = CA / "t3-green-lights/indices-256.npy"
PALS = CA / "t3-green-lights/palettes.json"
CENSUS = CA / "t3-green-lights/draw-census.json"
MASTER = CA / "w2-polish/frozen/atlas-95A3BCF8-w2-v2/master/master-w2-v2.npy"
LIVE = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/pack/"
            "einhander-texture-replacements")
REGIONS = {
    "M": dict(id="M_window_grid_lower", bbox=(64, 112, 112, 176), palettes=["29595B58", "0D0D6AE1"]),
    "I": dict(id="I_window_grid_lit", bbox=(0, 64, 64, 128), palettes=["E01F52F8", "0361652D"]),
    "J": dict(id="J_office_window_grid", bbox=(64, 64, 128, 112), palettes=["33BC1036", "8C6DBF6D"]),
}
WALL = 15
STEP = 4
FL, FR, FT, FB = 1.0 / 16, 1.0 / 16, 1.5 / 16, 2.0 / 16
SS = 4
MEAN_TOL = 0.5 + 1e-6        # 8-bit rounding bound for an exact float cell mean


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pin():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    return dict(priority=int(me.nice()), affinity=me.cpu_affinity(), threads_env=os.environ.get("OMP_NUM_THREADS"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def class_of(pal):
    return np.array([0 if (r == 0 and g == 0 and b == 0 and not s) else (255 if s else 127)
                     for (r, g, b), s in zip(pal["rgb"], pal["stp"])], np.uint8)


def load(pals, pk):
    require(pk in pals, f"{pk}: palette missing from palettes.json")
    P = np.array(pals[pk]["rgb"], np.float64)
    require(P.shape == (16, 3), f"{pk}: palette shape {P.shape}")
    lum = P @ np.array([0.299, 0.587, 0.114])
    require(bool(np.all(np.diff(lum) <= 1e-9)), f"{pk}: palette is not a monotone brightness ramp")
    cls = class_of(pals[pk])
    require(set(np.unique(cls).tolist()) <= {127, 255}, f"{pk}: classes {sorted(set(cls.tolist()))} not in {{127,255}}")
    wall_set = [i for i in range(16) if np.array_equal(P[i], P[WALL])]
    return P, cls, wall_set


def components(win):
    H, W = win.shape
    lab = -np.ones((H, W), int)
    sizes = []
    for y0 in range(H):
        for x0 in range(W):
            if not win[y0, x0] or lab[y0, x0] >= 0:
                continue
            k = len(sizes)
            stack, n = [(y0, x0)], 0
            lab[y0, x0] = k
            while stack:
                y, x = stack.pop()
                n += 1
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < H and 0 <= xx < W and win[yy, xx] and lab[yy, xx] < 0:
                        lab[yy, xx] = k
                        stack.append((yy, xx))
            sizes.append(n)
    hist = {}
    for n in sizes:
        hist[n] = hist.get(n, 0) + 1
    return dict(count=len(sizes), size_histogram=dict(sorted(hist.items())))


def steps_kept(O, win):
    h = win[:, 1:] & win[:, :-1] & (np.abs(O[:, 1:].astype(int) - O[:, :-1]) >= STEP)
    v = win[1:, :] & win[:-1, :] & (np.abs(O[1:, :].astype(int) - O[:-1, :]) >= STEP)
    return int(h.sum() + v.sum())


def border_window_edges(ring, wall_set):
    """Region-border edges where both the inside texel and the outside neighbour are window texels (no frame)."""
    w = ~np.isin(ring, wall_set)
    inner = w[1:-1, 1:-1]
    return dict(left=int((inner[:, 0] & w[1:-1, 0]).sum()), right=int((inner[:, -1] & w[1:-1, -1]).sum()),
                top=int((inner[0, :] & w[0, 1:-1]).sum()), bottom=int((inner[-1, :] & w[-1, 1:-1]).sum()))


def render_region(O, P, s, wall_set, ring=None):
    """RGB float region at s px per texel (4x4 supersampled, box-averaged). ring: (H+2, W+2) atlas indices around
    the region (frame decisions only); None treats everything outside as wall."""
    H, W = O.shape
    n = s * SS
    win = ~np.isin(O, wall_set)
    if ring is None:
        ring = np.pad(O, 1, constant_values=WALL)
    require(ring.shape == (H + 2, W + 2), "ring shape")
    Np = ~np.isin(ring, wall_set)                         # neighbour is a window texel (frame decision)
    Np[1:-1, 1:-1] = win
    Fp = np.pad(O.astype(np.float64), 1, constant_values=WALL)
    Vp = np.pad(win, 1, constant_values=False)            # interpolation: in-region window texels only
    Wc = P[WALL]
    f = (np.arange(n) + 0.5) / n
    t = np.abs(f - 0.5)
    d = np.where(f < 0.5, -1, 1)
    xs = np.arange(W * n)
    cc = xs // n + 1
    tx, dx, fx = t[xs % n][None, :], d[xs % n], f[xs % n][None, :]
    ty, dy, fy = t[:, None], d[:, None], f[:, None]
    out = np.empty((H * s, W * s, 3))
    for r in range(H):
        rr = r + 1
        Fs, Vs = Fp[rr, cc][None, :], Vp[rr, cc][None, :]
        Fh, Vh = Fp[rr, cc + dx][None, :], Vp[rr, cc + dx][None, :]
        Fv, Vv = Fp[rr + dy, cc[None, :]], Vp[rr + dy, cc[None, :]]
        Fd, Vd = Fp[rr + dy, (cc + dx)[None, :]], Vp[rr + dy, (cc + dx)[None, :]]
        ok_h = Vh & (np.abs(Fh - Fs) < STEP)
        ok_v = Vv & (np.abs(Fv - Fs) < STEP)
        ok_d = Vd & (np.abs(Fd - Fs) < STEP) & ok_h & ok_v
        ws = (1 - tx) * (1 - ty)
        wh, wv, wd = tx * (1 - ty) * ok_h, (1 - tx) * ty * ok_v, tx * ty * ok_d
        Fi = (ws * Fs + wh * Fh + wv * Fv + wd * Fd) / (ws + wh + wv + wd)
        lo = np.floor(Fi).astype(int)
        hi = np.minimum(lo + 1, WALL)
        a = (Fi - lo)[..., None]
        rgb = P[lo] * (1 - a) + P[hi] * a
        frame = Vs & (((fx < FL) & ~Np[rr, cc - 1][None, :]) | ((fx > 1 - FR) & ~Np[rr, cc + 1][None, :])
                      | ((fy < FT) & ~Np[rr - 1, cc][None, :]) | ((fy > 1 - FB) & ~Np[rr + 1, cc][None, :]))
        C = P[O[r, cc - 1]][None, :, :]
        rgb = np.where(frame[..., None], 0.3 * C + 0.7 * Wc, rgb)
        rgb = np.where(Vs[..., None], rgb, Wc)              # wall texels: exact wall colour
        cell = rgb.reshape(n, W, n, 3)
        glass = (Vs & ~frame).reshape(n, W, n)
        winc = np.broadcast_to(Vs, (n, W * n)).reshape(n, W, n)
        Cn = P[O[r]]
        g = glass.sum(axis=(0, 2))
        corr = np.where(g[:, None] > 0, (Cn - cell.mean(axis=(0, 2))) * (n * n) / np.maximum(g, 1)[:, None], 0.0)
        cell = np.clip(np.where(glass[..., None], cell + corr[None, :, None, :], cell), 0, 255)
        # exact residual: spread in proportion to headroom (255 - x when raising, x when lowering); |lam| <= 1
        resid = np.where(winc.any(axis=(0, 2))[:, None], Cn - cell.mean(axis=(0, 2)), 0.0)
        room = np.where(winc[..., None], np.where(resid[None, :, None, :] > 0, 255.0 - cell, cell), 0.0)
        tot = room.sum(axis=(0, 2))
        lam = np.where(tot > 0, resid * (n * n) / np.where(tot > 0, tot, 1.0), 0.0)
        cell = np.clip(cell + room * lam[None, :, None, :], 0, 255)
        out[r * s:(r + 1) * s] = cell.reshape(n, W * n, 3).reshape(s, SS, W * s, SS, 3).mean(axis=(1, 3))
    return out


def class_alpha(O, cls, s):
    return np.repeat(np.repeat(cls[O], s, axis=0), s, axis=1).astype(np.uint8)


def cell_stats(img, O, P, s, wall_set):
    H, W = O.shape
    m = img.reshape(H, s, W, s, 3).mean(axis=(1, 3))
    dd = np.abs(m - P[O])
    win = ~np.isin(O, wall_set)
    return dict(max_abs=float(dd.max()), mean_abs_windows=float(dd[win].mean()) if win.any() else 0.0,
                cells_over_2=int((dd.max(-1) > 2).sum()), cells_over_8=int((dd.max(-1) > 8).sum()),
                window_cells=int(win.sum()), wall_max_abs=float(dd[~win].max()) if (~win).any() else 0.0)


def alpha_stats(alpha, O, cls, s):
    H, W = O.shape
    cen = alpha[s // 2::s, s // 2::s][:H, :W]
    blk = alpha.reshape(H, s, W, s)
    return dict(centre_class_mismatches=int((cen != cls[O]).sum()),
                nonuniform_texel_blocks=int((blk.min(axis=(1, 3)) != blk.max(axis=(1, 3))).sum()), texels=int(H * W))


def to_rgba_strip(M, P, cls):
    tt = np.clip(M, 0, 15)
    lo = np.floor(tt).astype(np.int64); hi = np.minimum(lo + 1, 15); f = (tt - lo)[..., None]
    rgb = P[lo] * (1 - f) + P[hi] * f
    a = cls[np.clip(np.rint(tt).astype(np.int64), 0, 15)]
    return np.dstack([np.clip(np.rint(rgb), 0, 255).astype(np.uint8), a])


def sim(im, h):
    w = int(im.width * h / im.height)
    return im.resize((w, h), Image.BOX)


def review_sheet(path, O, P, cur8, new8, new16):
    H, W = O.shape
    size8 = (W * 8, H * 8)
    nat = Image.fromarray(P[O].astype(np.uint8)).resize(size8, Image.NEAREST)
    cur = Image.fromarray(cur8)
    n8 = Image.fromarray(np.clip(np.rint(new8), 0, 255).astype(np.uint8))
    n16 = Image.fromarray(np.clip(np.rint(new16), 0, 255).astype(np.uint8))
    zc = cur.crop((0, 32, 128, 160)).resize((512, 512), Image.NEAREST)
    zn = n16.crop((0, 64, 256, 320)).resize((512, 512), Image.NEAREST)
    tiles = [("native nearest x8", nat), ("CURRENT pack 2048 (8x)", cur), ("NEW 8x (page2048)", n8),
             ("NEW 16x (page4096) shown at 8x", n16.resize(size8, Image.LANCZOS)),
             ("CURRENT zoom 16x16 texels", zc), ("NEW 16x zoom same texels", zn)]
    sims = []
    for lab, im in (("CURRENT", cur), ("NEW 16x", n16)):
        for h in (360, 120):
            sims.append((f"{lab} box @{h}px", sim(im, h)))
    sheet = Image.new("RGB", (3 * 522, 2 * 530 + 400), (30, 30, 30))
    dr = ImageDraw.Draw(sheet)
    for i, (lab, im) in enumerate(tiles):
        x, y = (i % 3) * 522, (i // 3) * 530
        sheet.paste(im, (x, y + 16)); dr.text((x + 2, y + 2), lab, fill=(255, 255, 0))
    x, y0 = 0, 2 * 530
    for lab, im in sims:
        sheet.paste(im, (x, y0 + 16)); dr.text((x + 2, y0 + 2), lab, fill=(255, 255, 0))
        x += im.width + 10
    sheet.save(path)


def region_view(idx, R):
    u0, v0, u1, v1 = REGIONS[R]["bbox"]
    pad = np.pad(idx.astype(np.int64), 1, constant_values=WALL)
    return idx[v0:v1, u0:u1].astype(np.int64), pad[v0:v1 + 2, u0:u1 + 2], (u0, v0, u1, v1)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview", type=Path)
    g.add_argument("--freeze", action="store_true")
    ap.add_argument("--regions", default="M,I,J")
    a = ap.parse_args()
    regions = [r.strip() for r in a.regions.split(",") if r.strip()]
    require(bool(regions) and all(r in REGIONS for r in regions), f"unknown region in {regions}")
    pinned = pin()
    idx = np.load(IDX)
    require(idx.shape == (256, 256), f"index map shape {idx.shape}")
    pals = json.loads(PALS.read_text(encoding="utf-8"))
    if a.preview:
        a.preview.mkdir(parents=True, exist_ok=False)
        rep = {}
        for R in regions:
            O, ring, (u0, v0, u1, v1) = region_view(idx, R)
            rr = dict(region=REGIONS[R]["id"], bbox=[u0, v0, u1, v1], step=STEP)
            for pk in REGIONS[R]["palettes"]:
                P, cls, wset = load(pals, pk)
                win = ~np.isin(O, wset)
                new8, new16 = render_region(O, P, 8, wset, ring), render_region(O, P, 16, wset, ring)
                with Image.open(LIVE / f"95A3BCF8-{pk}.png") as im:
                    cur = np.asarray(im.convert("RGBA"))[v0 * 8:v1 * 8, u0 * 8:u1 * 8]
                review_sheet(a.preview / f"{R}-{pk}-review.png", O, P, cur[..., :3].copy(), new8, new16)
                rr[pk] = dict(wall_set=wset, components=components(win), native_steps_kept_crisp=steps_kept(O, win),
                              border_window_edges_no_frame=border_window_edges(ring, wset),
                              new8=cell_stats(new8, O, P, 8, wset), new16=cell_stats(new16, O, P, 16, wset),
                              new8_rounded=cell_stats(np.clip(np.rint(new8), 0, 255), O, P, 8, wset),
                              current8=cell_stats(cur[..., :3].astype(np.float64), O, P, 8, wset),
                              current8_alpha=alpha_stats(cur[..., 3], O, cls, 8),
                              new8_alpha=alpha_stats(class_alpha(O, cls, 8), O, cls, 8),
                              classes=sorted(set(cls[O].ravel().tolist())))
            rep[R] = rr
        import shutil
        shutil.copy2(Path(__file__), a.preview / "window_ramp_rebuild.at-preview.py")
        out = dict(pin=pinned, builder_sha256=sha(Path(__file__)), live_base=str(LIVE), stats=rep)
        (a.preview / "preview-stats.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=1))
        return 0
    rc = 0
    for R in regions:
        rc |= freeze(R, idx, pals, pinned)
    return rc


def save_png(arr, path):
    Image.fromarray(arr).save(path, compress_level=6)


def freeze(R, idx, pals, pinned):
    import datetime
    import shutil
    O, ring, (U0, V0, U1, V1) = region_view(idx, R)
    reg = REGIONS[R]
    NAME = f"95A3BCF8-{R}-windows-v1"
    F = HERE / "frozen" / NAME
    F.mkdir(parents=True, exist_ok=False)
    for sub in ("page2048", "page4096", "review"):
        (F / sub).mkdir()
    census = json.loads(CENSUS.read_text(encoding="utf-8"))["95A3BCF8"]
    M = np.load(MASTER)
    require(M.shape == (4096, 4096), f"master shape {M.shape}")
    keys, val = {}, {}
    for pk in reg["palettes"]:
        key = f"95A3BCF8-{pk}"
        P, cls, wset = load(pals, pk)
        new8, new16 = render_region(O, P, 8, wset, ring), render_region(O, P, 16, wset, ring)
        with Image.open(LIVE / f"{key}.png") as im:
            live = np.array(im.convert("RGBA"))
        require(live.shape == (2048, 2048, 4), f"{key}: live shape {live.shape}")
        roi8 = (slice(V0 * 8, V1 * 8), slice(U0 * 8, U1 * 8))
        cur = live[roi8].copy()
        p8 = live.copy()
        p8[roi8 + (slice(0, 3),)] = np.clip(np.rint(new8), 0, 255).astype(np.uint8)
        p8[roi8 + (3,)] = class_alpha(O, cls, 8)
        save_png(p8, F / "page2048" / f"{key}.png")
        p16 = np.empty((4096, 4096, 4), np.uint8)
        for y in range(0, 4096, 512):
            p16[y:y + 512] = to_rgba_strip(M[y:y + 512].astype(np.float32), P, cls)
        roi16 = (slice(V0 * 16, V1 * 16), slice(U0 * 16, U1 * 16))
        p16[roi16 + (slice(0, 3),)] = np.clip(np.rint(new16), 0, 255).astype(np.uint8)
        p16[roi16 + (3,)] = class_alpha(O, cls, 16)
        save_png(p16, F / "page4096" / f"{key}.png")
        r8 = np.asarray(Image.open(F / "page2048" / f"{key}.png").convert("RGBA"))
        r16 = np.asarray(Image.open(F / "page4096" / f"{key}.png").convert("RGBA"))
        outside = np.ones((2048, 2048), bool); outside[roi8] = False
        down = r16[..., :3].astype(np.float64).reshape(2048, 2, 2048, 2, 3).mean(axis=(1, 3))
        val[key] = dict(
            wall_set=wset,
            page2048=dict(readback_equals_written=bool((r8 == p8).all()),
                          outside_roi_rgba_identical_to_live=bool((r8[outside] == live[outside]).all()),
                          roi_alpha=alpha_stats(r8[roi8 + (3,)], O, cls, 8),
                          current_roi_alpha=alpha_stats(cur[..., 3], O, cls, 8),
                          region_cell_mean_vs_native=cell_stats(r8[roi8 + (slice(0, 3),)].astype(np.float64), O, P, 8, wset),
                          current_region_cell_mean_vs_native=cell_stats(cur[..., :3].astype(np.float64), O, P, 8, wset)),
            page4096=dict(readback_equals_written=bool((r16 == p16).all()),
                          roi_alpha=alpha_stats(r16[roi16 + (3,)], O, cls, 16),
                          region_cell_mean_vs_native=cell_stats(r16[roi16 + (slice(0, 3),)].astype(np.float64), O, P, 16, wset),
                          outside_roi_box2_vs_live2048_mean_abs=float(np.abs(down - live[..., :3])[outside].mean()),
                          outside_roi_box2_vs_live2048_max_abs=float(np.abs(down - live[..., :3])[outside].max())))
        review_sheet(F / "review" / f"{R}-{pk}-review.png", O, P, cur[..., :3].copy(), new8, new16)
        pk_c = census["per_key"].get(key, {})
        keys[key] = dict(region_draws=census["region_palettes"][reg["id"]].get(pk), draws=pk_c.get("draws"),
                         uv_union=pk_c.get("uv_union"), max_quad_area=pk_c.get("max_quad_area"),
                         live=dict(path=str(LIVE / f"{key}.png"), sha256=sha(LIVE / f"{key}.png")))
        del p16, r16, down
    del M
    checks = {}
    for k, v in val.items():
        a8, a16 = v["page2048"], v["page4096"]
        checks[k] = dict(
            p2048_readback=a8["readback_equals_written"], p2048_outside_identical=a8["outside_roi_rgba_identical_to_live"],
            p2048_alpha_centre=a8["roi_alpha"]["centre_class_mismatches"] == 0,
            p2048_alpha_uniform=a8["roi_alpha"]["nonuniform_texel_blocks"] == 0,
            p2048_cell_mean=a8["region_cell_mean_vs_native"]["max_abs"] <= MEAN_TOL,
            p2048_walls_exact=a8["region_cell_mean_vs_native"]["wall_max_abs"] == 0,
            p4096_readback=a16["readback_equals_written"],
            p4096_alpha_centre=a16["roi_alpha"]["centre_class_mismatches"] == 0,
            p4096_alpha_uniform=a16["roi_alpha"]["nonuniform_texel_blocks"] == 0,
            p4096_cell_mean=a16["region_cell_mean_vs_native"]["max_abs"] <= MEAN_TOL,
            p4096_walls_exact=a16["region_cell_mean_vs_native"]["wall_max_abs"] == 0)
    ok = all(all(c.values()) for c in checks.values())
    (F / "validation.json").write_text(json.dumps(dict(passed=ok, checks=checks, mean_tolerance=MEAN_TOL, keys=val),
                                                  indent=1) + "\n", encoding="utf-8")
    src = dict(indices=IDX, palettes=PALS, census=CENSUS, w2_master=MASTER, builder=Path(__file__))
    man = dict(
        name=NAME, status="candidate (private; not integrated, not live-tested)" if ok else "FAILED validation (preserved)",
        owner="claude-einhander",
        gpu="none: CPU-only RGB authoring of native texels (no ComfyUI, no generated imagery, no fonts)",
        region=f"{reg['id']} uv [{U0},{V0}]-[{U1},{V1}] half-open (t3-green-lights/regions.json)",
        why=__doc__.split("Why: ", 1)[1].split("Rebuild, per", 1)[0].strip(),
        method=__doc__.split("Rebuild, per region and palette:", 1)[1].split("Outputs:", 1)[0].strip(),
        params=dict(step=STEP, frame_left=FL, frame_right=FR, lintel=FT, sill=FB, supersample=SS, wall_index=WALL,
                    mean_tolerance=MEAN_TOL),
        keys=keys, validation_passed=ok,
        integration="ROI-only: overlay the region ROI (RGBA) of page2048 onto the current private parent page; every "
                    "other pixel stays the parent's. page4096 is optional (changes outside the ROI, 4x upload).",
        known_limits=[
            "faithful re-rendering of native window texels: no window invented; in-window steps >= STEP are kept crisp "
            "by a threshold heuristic, smaller differences are interpolated along the native ramp",
            "exact cell means can lighten a frame where a bright texel has little headroom",
            "alpha is the native class per texel (127/255); STP semantics follow the native map, not the parent page",
            "no runtime mipmaps by default: crisp frames can shimmer when the region is minified",
            "SIMULATION only: not integrated, not seen live"],
        sources={k: dict(path=str(p), sha256=sha(p)) for k, p in src.items()},
        pin=pinned, built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (F / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    shutil.copy2(Path(__file__), F / Path(__file__).name)
    files = sorted(p for p in F.rglob("*") if p.is_file())
    for p in files:
        with open(p, "rb+") as fh:
            os.fsync(fh.fileno())
    sums = [f"{sha(p)}  {p.relative_to(F).as_posix()}" for p in files]
    (F / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    with open(F / "SHA256SUMS.txt", "rb+") as fh:
        os.fsync(fh.fileno())
    for line in (F / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        b = (F / rel).read_bytes()
        require(hashlib.sha256(b).hexdigest() == h, f"read-back mismatch {rel}")
        require(not (b and b.count(0) == len(b)), f"all-NUL {rel}")
    status = dict(name=NAME, validation_passed=ok, files=len(sums), sha256sums=sha(F / "SHA256SUMS.txt"),
                  manifest_sha256=sha(F / "manifest.json"), durability="every file fsynced and re-hashed",
                  failed_checks={k: [n for n, okk in c.items() if not okk] for k, c in checks.items()} if not ok else {},
                  status=man["status"], at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    marker = F / ("READY.json" if ok else "FAILED.json")
    with open(marker, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(status, indent=1) + "\n"); fh.flush(); os.fsync(fh.fileno())
    print(json.dumps(dict(region=R, marker=marker.name, status=status, marker_sha256=sha(marker),
                          outputs={p.relative_to(F).as_posix(): sha(p) for p in files if p.suffix == ".png" and "page" in p.parts[-2]},
                          validation={k: dict(p2048=v["page2048"]["region_cell_mean_vs_native"],
                                              alpha=v["page2048"]["roi_alpha"],
                                              current_alpha=v["page2048"]["current_roi_alpha"])
                                      for k, v in val.items()}), indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
