#!/usr/bin/env python3
"""s45: REVIEW of the newly-visible pixels in the J-F cm_repair copies (audit probes) against exact native colours.

For each repaired key and size: newly visible = probe alpha 0 -> repaired alpha != 0. Measures, over those pixels:
  * |assigned RGB - native texel RGB| (CLUT[index] as the w7 render scale, (c & 31) * 8),
  * |assigned RGB - mean of the originally visible neighbours within 2 px| (seam / flat-patch contrast),
  * cells where newly visible pixels are >= 50 % of the cell (a whole flat cell-mean square),
and writes zoomed review crops (probe | repair | change mask | native nearest) around the densest cluster at 2048.
Read-only on probes and repairs; writes s45/review/jf-<UTC>/. Below normal, one CPU (not 13/15)."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None
RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
STATIC = RA / "fullgame-prep/static-extraction/stages/stage5"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "review" / f"jf-{stamp}"
    rd.mkdir(parents=True, exist_ok=False)
    cl = {(e["x"], e["y"], e["pal"]): e["words_hex"] for e in json.loads((STATIC / "cluts.json").read_text(encoding="utf-8"))}
    out = dict(run=rd.name, owner="claude-einhander-s45", rows=[], status="REVIEW ONLY; audit-probe repair copies; nothing modified")
    for d in sorted((S45 / "repairs").glob("2026*-cmrepair-*")):
        res = json.loads((d / "result.json").read_text(encoding="utf-8"))
        key = res["key"]
        tex, pal = key.split("-")
        xy = res["clut_xy"]
        clut = np.frombuffer(bytes.fromhex(cl[(xy[0], xy[1], pal)]), "<u2").astype(np.int64)
        crgb = np.stack([(clut & 31) * 8, ((clut >> 5) & 31) * 8, ((clut >> 10) & 31) * 8], -1).astype(np.float32)
        w16 = np.frombuffer((STATIC / f"textures/{tex}.words.bin").read_bytes(), "<u2").reshape(256, 64)
        idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)
        for row in res["rows"]:
            src, rep = Path(row["source"]), d / row["output"]
            with Image.open(src) as im:
                b = np.asarray(im.convert("RGBA")).astype(np.int16)
            with Image.open(rep) as im:
                a = np.asarray(im.convert("RGBA")).astype(np.int16)
            s = a.shape[0] // 256
            newv = (b[..., 3] == 0) & (a[..., 3] != 0)
            origv = (b[..., 3] != 0) & (a[..., 3] != 0)
            nat = np.repeat(np.repeat(crgb[idx], s, 0), s, 1)
            ys, xs = np.nonzero(newv)
            d_native = np.abs(a[..., :3].astype(np.float32) - nat).mean(-1)[newv]
            # mean colour of originally visible neighbours within 2 px (box 5x5)
            k = np.ones((5, 5), np.float32)
            ov = origv.astype(np.float32)
            nsum = np.stack([ndi.convolve(a[..., c].astype(np.float32) * ov, k, mode="constant") for c in range(3)], -1)
            ncnt = ndi.convolve(ov, k, mode="constant")
            has = ncnt[newv] > 0
            nmean = nsum[newv][has] / ncnt[newv][has][:, None]
            d_neigh = np.abs(a[..., :3][newv][has].astype(np.float32) - nmean).mean(-1)
            cellnew = newv.reshape(256, s, 256, s).sum(axis=(1, 3))
            flat_cells = int((cellnew >= 0.5 * s * s).sum())
            r = dict(key=key, file=row["file"], scale=s, newly_visible_px=int(newv.sum()),
                     d_native_mean=round(float(d_native.mean()), 2) if d_native.size else None,
                     d_native_p95=round(float(np.percentile(d_native, 95)), 2) if d_native.size else None,
                     d_neighbour_mean=round(float(d_neigh.mean()), 2) if d_neigh.size else None,
                     d_neighbour_p95=round(float(np.percentile(d_neigh, 95)), 2) if d_neigh.size else None,
                     newly_visible_without_visible_neighbour=int((~has).sum()),
                     cells_touched=int((cellnew > 0).sum()), cells_ge_half_new=flat_cells,
                     max_new_px_in_one_cell=int(cellnew.max()), cell_px=s * s)
            if s == 8 and newv.any():   # crops at 2048: densest 32x32-texel window
                dens = ndi.uniform_filter(cellnew.astype(np.float32), 32, mode="constant")
                cy, cx = np.unravel_index(np.argmax(dens), dens.shape)
                y0, x0 = max(0, min(224, cy - 16)), max(0, min(224, cx - 16))
                sl = (slice(y0 * s, (y0 + 32) * s), slice(x0 * s, (x0 + 32) * s))
                def panel(rgb, alpha):
                    bg = np.where(((np.indices(alpha.shape).sum(0) // 8) % 2)[..., None] == 0, 40, 64).astype(np.uint8)
                    vis = (alpha != 0)[..., None]
                    return np.where(vis, np.clip(rgb, 0, 255).astype(np.uint8), np.repeat(bg, 3, -1))
                p1 = panel(b[sl][..., :3], b[sl][..., 3])
                p2 = panel(a[sl][..., :3], a[sl][..., 3])
                m = np.zeros(p1.shape, np.uint8)
                m[newv[sl]] = (255, 0, 255)
                m[origv[sl]] = (60, 60, 60)
                natc = np.where(nat[sl] >= 0, nat[sl], 0)
                ncls = (clut[idx] != 0)
                p4 = panel(natc, np.repeat(np.repeat(ncls, s, 0), s, 1)[sl].astype(np.uint8))
                tiles = [Image.fromarray(x).resize((512, 512), Image.NEAREST) for x in (p1, p2, m, p4)]
                sheet = Image.new("RGB", (4 * 512 + 30, 540), (0, 0, 0))
                dr = ImageDraw.Draw(sheet)
                for i, (t, lab) in enumerate(zip(tiles, ("probe (before)", "cm_repair copy", "newly visible (magenta)", "native nearest"))):
                    sheet.paste(t, (i * 522, 28))
                    dr.text((i * 522 + 4, 6), f"{lab}  {key} u{x0}-{x0 + 31} v{y0}-{y0 + 31}", fill=(255, 255, 0))
                fn = rd / f"{key}-2048-u{x0}v{y0}.png"
                sheet.save(fn)
                r["crop"] = fn.name
                r["crop_window_texels"] = [int(x0), int(y0), 32, 32]
            out["rows"].append(r)
            print(r)
    (rd / "review.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("run", rd.name, "review.json", sha(rd / "review.json"))


if __name__ == "__main__":
    main()
