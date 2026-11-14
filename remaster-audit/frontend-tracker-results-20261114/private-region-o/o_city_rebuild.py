#!/usr/bin/env python3
"""95A3BCF8 region O (uv [176,112]-[240,176], 'dotted city mass') - faithful crisp window rebuild (claude-einhander).
CPU only, below normal, one logical CPU, threads 1. No GPU, no ComfyUI, no generated imagery, no fonts.

Why: the user's distant green/pink "signs" are this region (claude-backlog/sign-census/WORLD-SIGN-CENSUS.md section 4). It is
drawn ONLY with palettes 60245B3A (green, 714 draws, max quad 13,932 native px^2 ~ 118 px) and 07A9568D (pink/orange/white,
510 draws), both fully opaque (stp 0, no raw 0x0000 colour => class 127 at every texel). At a 4K output the largest draw is
~1,000 px for 64 texels, so a 16x page is shown ~1:1; the live 2048 page (w2-v2) renders every window texel as a flat
rectangle with a faint vertical stripe.

Rebuild, authored in RGB per palette (the palettes are NOT brightness ramps, so index interpolation would invent hues):
  * every native texel keeps its own cell; no window is added, removed or moved;
  * wall texels (index 13/14) and building-structure texels (index 15) keep their exact native colour;
  * every window texel (index 0..12) becomes a pane: a thin frame (left/right 1/16, lintel 1.5/16, sill 2/16 of a texel) in a
    dark mix of the window colour and its wall (0.3 C + 0.7 W; W = mean colour of its non-window 4-neighbours), and glass with
    a vertical light falloff (ceiling brighter, sill darker; lit windows 0..8 also get a ceiling light strip);
  * the glass level is solved per texel and channel so the cell MEAN equals the native colour (minified/mipped look ==
    native), clipped at 255 (deviation reported);
  * 4x4 supersampling per output pixel (anti-aliased frames); alpha = 127 (native class) on every pixel.
Outputs (--freeze, frozen/95A3BCF8-O-city-v1, exist_ok=False):
  page2048/<key>.png  live 2048 page (frozen-w3-lit-v1) with only region O replaced; every other pixel byte-identical;
  page4096/<key>.png  full page from the w2-v2 float index master (the w2 pipeline: palette lerp + nearest-index class),
                      region O at 16x;
  review/, manifest.json, validation.json.
--preview OUTDIR renders region O only (both palettes, 8x and 16x) plus the review sheet; it writes nothing else."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
IDX = CA / "t3-green-lights/indices-256.npy"
PALS = CA / "t3-green-lights/palettes.json"
CENSUS = CA / "t3-green-lights/draw-census.json"
MASTER = CA / "w2-polish/frozen/atlas-95A3BCF8-w2-v2/master/master-w2-v2.npy"
LIVE = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/pack/"
            "einhander-texture-replacements")
PALETTES = ["60245B3A", "07A9568D"]
U0, V0, U1, V1 = 176, 112, 240, 176
NAME = "95A3BCF8-O-city-v1"
# pane geometry in texel units
FL, FR, FT, FB = 1.0 / 16, 1.0 / 16, 1.5 / 16, 2.0 / 16
TOP_GAIN, BOT_GAIN, STRIP_H, STRIP_GAIN = 1.12, 0.90, 1.0 / 16, 1.25
SS = 4


def pin():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    return dict(priority=int(me.nice()), affinity=me.cpu_affinity())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def class_of(pal):
    return np.array([0 if (r == 0 and g == 0 and b == 0 and not s) else (255 if s else 127)
                     for (r, g, b), s in zip(pal["rgb"], pal["stp"])], np.uint8)


def texel_params(O, P):
    """Per texel: window flag, native colour C, frame colour Fc, glass gain k (per channel) and the lit flag."""
    H, W = O.shape
    win = O <= 12
    C = P[O]
    pad = np.pad(O, 1, mode="edge")
    nb = [pad[1:-1, :-2], pad[1:-1, 2:], pad[:-2, 1:-1], pad[2:, 1:-1]]
    acc = np.zeros((H, W, 3)); cnt = np.zeros((H, W, 1))
    for n in nb:
        m = (n > 12)[..., None]
        acc += np.where(m, P[n], 0.0); cnt += m
    Wc = np.where(cnt > 0, acc / np.maximum(cnt, 1), P[14])
    Fc = 0.3 * C + 0.7 * Wc
    return win, C, Fc, O <= 8


def pane_masks(n):
    """Within-texel masks at n samples per texel edge: frame (bool) and glass gain profile g (float, 1 outside glass)."""
    f = (np.arange(n) + 0.5) / n
    fx, fy = f[None, :], f[:, None]
    glass = (fx >= FL) & (fx < 1 - FR) & (fy >= FT) & (fy < 1 - FB)
    t = np.clip((fy - FT) / (1 - FT - FB), 0, 1)
    g = TOP_GAIN + (BOT_GAIN - TOP_GAIN) * t
    strip = glass & (fy < FT + STRIP_H)
    return ~glass, np.broadcast_to(g, (n, n)), np.broadcast_to(strip, (n, n))


def render_region(O, P, s):
    """RGB float region at s px per texel (4x4 supersampled, box-averaged)."""
    H, W = O.shape
    n = s * SS
    win, C, Fc, lit = texel_params(O, P)
    frame, g, strip = pane_masks(n)
    gl = np.where(strip, g * STRIP_GAIN, g)                         # lit profile (with ceiling strip)
    A_f = frame.mean()
    mean_g_unlit = np.where(~frame, g, 0).sum() / (n * n)
    mean_g_lit = np.where(~frame, gl, 0).sum() / (n * n)
    mg = np.where(lit, mean_g_lit, mean_g_unlit)[..., None]
    # cell mean = A_f * Fc + k * C * mg  ==  C   =>  k = (C - A_f * Fc) / (C * mg)
    k = np.where(C > 0, (C - A_f * Fc) / np.maximum(C * mg, 1e-9), 1.0)
    out = np.empty((H * s, W * s, 3), np.float32)
    for r in range(H):                                              # row of texels at a time (bounded memory)
        Cr, Fr, kr, wr, lr = C[r], Fc[r], k[r], win[r], lit[r]
        prof = np.where(lr[:, None, None], gl[None], g[None])      # (W, n, n)
        glass = np.clip(kr[:, None, None, :] * Cr[:, None, None, :] * prof[..., None], 0, 255)
        # bright panes clip at 255: lighten only that pane's frame (never above C) so the cell mean stays == native
        gm = np.where(frame[None, ..., None], 0.0, glass).sum(axis=(1, 2)) / (n * n)
        Fr = np.where(wr[:, None], np.maximum(Fr, np.minimum(Cr, (Cr - gm) / A_f)), Fr)
        cell = np.where(frame[None, ..., None], Fr[:, None, None, :], glass)
        cell = np.where(wr[:, None, None, None], cell, Cr[:, None, None, :])
        cell = cell.transpose(1, 0, 2, 3).reshape(n, W * n, 3)     # (n, W*n, 3)
        out[r * s:(r + 1) * s] = cell.reshape(s, SS, W * s, SS, 3).mean(axis=(1, 3))
    return out


def cell_stats(img, O, P, s):
    """Mean colour per texel cell vs native colour (what a box filter / mip level 0->native would show)."""
    H, W = O.shape
    m = img.reshape(H, s, W, s, 3).mean(axis=(1, 3))
    d = np.abs(m - P[O])
    win = O <= 12
    return dict(max_abs=float(d.max()), mean_abs_windows=float(d[win].mean()), cells_over_2=int((d.max(-1) > 2).sum()),
                cells_over_8=int((d.max(-1) > 8).sum()), window_cells=int(win.sum()))


def to_rgba_strip(M, P, cls):
    t = np.clip(M, 0, 15)
    lo = np.floor(t).astype(np.int64); hi = np.minimum(lo + 1, 15); f = (t - lo)[..., None]
    rgb = P[lo] * (1 - f) + P[hi] * f
    a = cls[np.clip(np.rint(t).astype(np.int64), 0, 15)]
    return np.dstack([np.clip(np.rint(rgb), 0, 255).astype(np.uint8), a])


def sim(im, h):
    w = int(im.width * h / im.height)
    return im.resize((w, h), Image.BOX)


def review_sheet(path, O, P, cur8, new8, new16):
    nat = Image.fromarray(P[O].astype(np.uint8)).resize((512, 512), Image.NEAREST)
    cur = Image.fromarray(cur8)
    n8 = Image.fromarray(np.clip(np.rint(new8), 0, 255).astype(np.uint8))
    n16 = Image.fromarray(np.clip(np.rint(new16), 0, 255).astype(np.uint8))
    zc = cur.crop((192, 64, 320, 192)).resize((512, 512), Image.NEAREST)        # texels u+24..40, v+8..24 at 8x, 4x zoom
    zn = n16.crop((384, 128, 640, 384)).resize((512, 512), Image.NEAREST)       # same texels at 16x, 2x zoom
    tiles = [("native nearest x8", nat), ("CURRENT pack 2048 (8x)", cur), ("NEW 8x (page2048)", n8),
             ("NEW 16x (page4096) shown at 8x", n16.resize((512, 512), Image.LANCZOS)),
             ("CURRENT zoom 16x16 texels", zc), ("NEW 16x zoom same texels", zn)]
    sims = []
    for lab, im in (("CURRENT", cur), ("NEW 16x", n16)):
        for h in (360, 120):
            sims.append((f"{lab} box @{h}px", sim(im, h)))
    sheet = Image.new("RGB", (3 * 522, 2 * 530 + 400), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (lab, im) in enumerate(tiles):
        x, y = (i % 3) * 522, (i // 3) * 530
        sheet.paste(im, (x, y + 16)); d.text((x + 2, y + 2), lab, fill=(255, 255, 0))
    x, y0 = 0, 2 * 530
    for lab, im in sims:
        sheet.paste(im, (x, y0 + 16)); d.text((x + 2, y0 + 2), lab, fill=(255, 255, 0))
        x += im.width + 10
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview", type=Path)
    g.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    pinned = pin()
    idx = np.load(IDX)
    pals = json.loads(PALS.read_text(encoding="utf-8"))
    O = idx[V0:V1, U0:U1].astype(np.int64)
    if a.preview:
        a.preview.mkdir(parents=True, exist_ok=True)
        rep = {}
        for pk in PALETTES:
            P = np.array(pals[pk]["rgb"], np.float64)
            new8, new16 = render_region(O, P, 8), render_region(O, P, 16)
            with Image.open(LIVE / f"95A3BCF8-{pk}.png") as im:
                cur8 = np.asarray(im.convert("RGB"))[V0 * 8:V1 * 8, U0 * 8:U1 * 8]
            review_sheet(a.preview / f"O-{pk}-review.png", O, P, cur8, new8, new16)
            rep[pk] = dict(new8=cell_stats(new8, O, P, 8), new16=cell_stats(new16, O, P, 16),
                           current8=cell_stats(cur8.astype(np.float64), O, P, 8))
        print(json.dumps(dict(pin=pinned, stats=rep), indent=1))
        return 0
    return freeze(O, idx, pals, pinned)


def save_png(arr, path):
    Image.fromarray(arr).save(path, compress_level=6)


def freeze(O, idx, pals, pinned):
    import datetime
    F = HERE / "frozen" / NAME
    F.mkdir(parents=True, exist_ok=False)
    for sub in ("page2048", "page4096", "review"):
        (F / sub).mkdir()
    census = json.loads(CENSUS.read_text(encoding="utf-8"))["95A3BCF8"]
    M = np.load(MASTER)
    assert M.shape == (4096, 4096)
    keys, val = {}, {}
    for pk in PALETTES:
        key = f"95A3BCF8-{pk}"
        pal = pals[pk]
        P = np.array(pal["rgb"], np.float64)
        cls = class_of(pal)
        assert (cls == 127).all(), f"{pk}: palette is not fully opaque; this builder assumes class 127 everywhere"
        new8, new16 = render_region(O, P, 8), render_region(O, P, 16)
        # page2048: live page, region O RGB replaced; alpha stays the native class (127)
        with Image.open(LIVE / f"{key}.png") as im:
            live = np.array(im.convert("RGBA"))
        assert live.shape == (2048, 2048, 4)
        cur8 = live[V0 * 8:V1 * 8, U0 * 8:U1 * 8, :3].copy()
        p8 = live.copy()
        p8[V0 * 8:V1 * 8, U0 * 8:U1 * 8, :3] = np.clip(np.rint(new8), 0, 255).astype(np.uint8)
        p8[..., 3] = 127
        save_png(p8, F / "page2048" / f"{key}.png")
        # page4096: full page from the w2-v2 float index master (palette lerp + nearest-index class), O at 16x
        p16 = np.empty((4096, 4096, 4), np.uint8)
        for y in range(0, 4096, 512):
            p16[y:y + 512] = to_rgba_strip(M[y:y + 512].astype(np.float32), P, cls)
        p16[V0 * 16:V1 * 16, U0 * 16:U1 * 16, :3] = np.clip(np.rint(new16), 0, 255).astype(np.uint8)
        p16[..., 3] = 127
        save_png(p16, F / "page4096" / f"{key}.png")
        # read back and validate
        r8 = np.asarray(Image.open(F / "page2048" / f"{key}.png").convert("RGBA"))
        r16 = np.asarray(Image.open(F / "page4096" / f"{key}.png").convert("RGBA"))
        outside = np.ones((2048, 2048), bool); outside[V0 * 8:V1 * 8, U0 * 8:U1 * 8] = False
        c8, c16 = np.arange(256) * 8 + 4, np.arange(256) * 16 + 8
        down = r16[..., :3].astype(np.float64).reshape(2048, 2, 2048, 2, 3).mean(axis=(1, 3))
        val[key] = dict(
            page2048=dict(readback_equals_written=bool((r8 == p8).all()),
                          outside_O_rgb_identical_to_live=bool((r8[outside][:, :3] == live[outside][:, :3]).all()),
                          live_alpha_values=sorted(int(x) for x in np.unique(live[..., 3])),
                          alpha_all_127=bool((r8[..., 3] == 127).all()),
                          centre_class_mismatches=int((r8[np.ix_(c8, c8)][..., 3] != cls[idx]).sum()),
                          region_cell_mean_vs_native=cell_stats(r8[V0 * 8:V1 * 8, U0 * 8:U1 * 8, :3].astype(np.float64), O, P, 8),
                          current_region_cell_mean_vs_native=cell_stats(cur8.astype(np.float64), O, P, 8)),
            page4096=dict(readback_equals_written=bool((r16 == p16).all()), alpha_all_127=bool((r16[..., 3] == 127).all()),
                          centre_class_mismatches=int((r16[np.ix_(c16, c16)][..., 3] != cls[idx]).sum()),
                          region_cell_mean_vs_native=cell_stats(r16[V0 * 16:V1 * 16, U0 * 16:U1 * 16, :3].astype(np.float64), O, P, 16),
                          outside_O_box2_vs_live2048_mean_abs=float(np.abs(down - live[..., :3])[outside].mean()),
                          outside_O_box2_vs_live2048_max_abs=float(np.abs(down - live[..., :3])[outside].max())))
        review_sheet(F / "review" / f"O-{pk}-review.png", O, P, cur8, new8, new16)
        pk_c = census["per_key"].get(key, {})
        keys[key] = dict(region_draws=census["region_palettes"]["O_dotted_city_mass"].get(pk), draws=pk_c.get("draws"),
                         uv_union=pk_c.get("uv_union"), max_quad_area=pk_c.get("max_quad_area"),
                         live=dict(path=str(LIVE / f"{key}.png"), sha256=sha(LIVE / f"{key}.png")))
        del p16, r16, down
    del M
    ok = all(v["page2048"]["readback_equals_written"] and v["page2048"]["outside_O_rgb_identical_to_live"]
             and v["page2048"]["alpha_all_127"] and v["page2048"]["centre_class_mismatches"] == 0
             and v["page4096"]["readback_equals_written"] and v["page4096"]["alpha_all_127"]
             and v["page4096"]["centre_class_mismatches"] == 0 for v in val.values())
    (F / "validation.json").write_text(json.dumps(dict(passed=ok, keys=val), indent=1) + "\n", encoding="utf-8")
    src = dict(indices=IDX, palettes=PALS, census=CENSUS, w2_master=MASTER, builder=Path(__file__))
    man = dict(
        name=NAME, status="candidate (private; not integrated, not live-tested)", owner="claude-einhander",
        gpu="none: CPU-only RGB authoring of native texels (no ComfyUI, no generated imagery, no fonts)",
        region="O_dotted_city_mass uv [176,112]-[240,176] half-open (t3-green-lights/regions.json)",
        why=__doc__.split("Why: ", 1)[1].split("Rebuild,", 1)[0].strip(),
        method=__doc__.split("Rebuild, ", 1)[1].split("Outputs", 1)[0].strip(),
        pane=dict(frame_left=FL, frame_right=FR, lintel=FT, sill=FB, top_gain=TOP_GAIN, bottom_gain=BOT_GAIN,
                  lit_strip=STRIP_H, lit_strip_gain=STRIP_GAIN, supersample=SS),
        keys=keys, validation_passed=ok,
        integration="drop-in: replace pack files 95A3BCF8-60245B3A.png and 95A3BCF8-07A9568D.png with page2048/ (same size "
                    "as live; only region O RGB differs) or page4096/ (4K option: 4x the upload bytes; the rest of the page "
                    "is re-rendered from the w2-v2 float master, see validation outside_O_box2_vs_live2048_*)",
        known_limits=[
            "faithful re-rendering of the native window texels: no window is invented; each lit window reads as one framed "
            "pane, not a detailed room",
            "the w3-emissive set 95A3BCF8-O-emissive-v1 derives its masks from the w2-v2 PNGs; it does NOT match this "
            "rebuild. Regenerate masks from these pages before using emissive with them",
            "no runtime mipmaps by default: crisp frames can shimmer when the region is minified; the private v5/v6 "
            "RGB-only class-mip sidecars address that",
            "page4096 raises upload size (stutter risk on first use); page2048 is the size-neutral option",
            "SIMULATION only: not integrated, not seen live"],
        sources={k: dict(path=str(p), sha256=sha(p)) for k, p in src.items()},
        pin=pinned, built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (F / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    import shutil
    shutil.copy2(Path(__file__), F / Path(__file__).name)
    files = sorted(p for p in F.rglob("*") if p.is_file())
    for p in files:                                                  # durable: flush every file before READY
        with open(p, "rb+") as fh:
            os.fsync(fh.fileno())
    sums = [f"{sha(p)}  {p.relative_to(F).as_posix()}" for p in files]
    (F / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    with open(F / "SHA256SUMS.txt", "rb+") as fh:
        os.fsync(fh.fileno())
    for line in (F / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        b = (F / rel).read_bytes()
        assert hashlib.sha256(b).hexdigest() == h, f"read-back mismatch {rel}"
        assert not (b and b.count(0) == len(b)), f"all-NUL {rel}"
    ready = dict(name=NAME, validation_passed=ok, files=len(sums), sha256sums=sha(F / "SHA256SUMS.txt"),
                 manifest_sha256=sha(F / "manifest.json"), durability="every file fsynced and re-hashed before READY",
                 status=man["status"], at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with open(F / "READY.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(ready, indent=1) + "\n"); fh.flush(); os.fsync(fh.fileno())
    print(json.dumps(dict(ready=ready, ready_sha256=sha(F / "READY.json"),
                          outputs={p.relative_to(F).as_posix(): sha(p) for p in files if p.suffix == ".png" and "page" in p.parts[-2]},
                          validation={k: dict(p2048=v["page2048"]["region_cell_mean_vs_native"],
                                              p4096_outside_box2=v["page4096"]["outside_O_box2_vs_live2048_mean_abs"])
                                      for k, v in val.items()}), indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
