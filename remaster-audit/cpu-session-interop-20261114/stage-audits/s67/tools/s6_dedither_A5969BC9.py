#!/usr/bin/env python3
"""s67 isolated REPAIR PROPOSAL r1: A5969BC9 (VRAM 448,0, set B) 1-texel column dither -> continuous tone, class plane untouched.

Defect (lane LEDGER frozen_batch2.honest_look + review/A5969BC9-FD5E0863-close-16x.png): the frozen v1 keeps the native 1-texel
vertical dither of the big orange disk (v0-127) as hard 8-px vertical bars at 2048 ('pipe organ'), a shimmer risk without mips.
On the native display the alternating columns read as one blended tone.

Method (CPU, deterministic, no AI, no new palette, no new identity):
  * D (texel space) = every texel of a 1-texel column alternation a,b,a (a != b, idx[y,x] == idx[y,x+2]) held for >= 3 rows,
    restricted to index pairs whose class (0 / 127 / 255) is equal under ALL 14 delivered CLUTs (CLUT-free condition);
  * per delivered key and size, starting from the FROZEN v1 runtime PNG: inside D, RGB := normalised horizontal box mean over
    exactly 2 texels, using only pixels of D with the same alpha class (cutout and STP never mix); feathered 0.5 texel at the
    D border; outside D every byte stays v1;
  * the alpha plane (PS1 class) is byte-identical to v1 at 2048 and 1024 (asserted), so every native-centre and whole-cell
    class property of v1 is unchanged; mean light energy inside D is preserved by the box mean (reported).
Known deviation: inside D the texel-centre RGB becomes the pair mean, not the native per-texel colour. That is intended: it is
the perceived native tone. Class is never changed.
READ-ONLY on comfy-authoring/w7-stage6. Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/repairs/<name>/.
usage: python -B -I s6_dedither_A5969BC9.py mask      (light: texel-space mask + stats only)
       python -B -I s6_dedither_A5969BC9.py build     (HEAVY: 14 keys x 2 sizes; needs a granted CPU slot)"""
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
V1 = ROOT / "remaster-audit/comfy-authoring/w7-stage6/frozen/stage6-vram448-0-03F5CF11-A5969BC9-v1"
OUT = ROOT / "remaster-audit/parallel-stages-20261114/s67/repairs/stage6-vram448-0-A5969BC9-dedither-r1"
TEX = "A5969BC9"
CROPS = [(1, 86), (22, 0), (208, 81), (96, 40), (196, 164)]   # first three = the lane's own review crops; last = lower sheet


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cls_of(w):
    return 0 if w == 0 else (255 if w & 0x8000 else 127)


def load_native():
    w = np.frombuffer((V1 / "source" / f"{TEX}.words.bin").read_bytes(), "<u2").reshape(256, 64)
    idx = np.zeros((256, 256), np.uint8)
    for k in range(4):
        idx[:, k::4] = (w >> (4 * k)) & 0xF
    m = json.loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    keys = [k for k in m["keys"] if k["key"].startswith(TEX)]
    cluts = {k["clut"]: np.frombuffer((V1 / "source" / f"{k['key']}.clut.bin").read_bytes(), "<u2") for k in keys}
    return idx, keys, cluts, m


def dither_mask(idx, cluts):
    eq = np.ones((16, 16), bool)            # class-equal under every delivered CLUT
    for cw in cluts.values():
        c = np.array([cls_of(int(x)) for x in cw])
        eq &= c[:, None] == c[None, :]
    a, b = idx[:, :-2], idx[:, 1:-1]
    alt = (a == idx[:, 2:]) & (a != b) & eq[a, b]
    run = np.zeros_like(alt)
    run[1:-1] = alt[1:-1] & alt[:-2] & alt[2:]
    D = np.zeros(idx.shape, bool)
    for dx in (0, 1, 2):
        D[:, dx:dx + run.shape[1]] |= run
    excluded = np.zeros_like(alt)
    alt_any = (a == idx[:, 2:]) & (a != b)
    excluded[1:-1] = alt_any[1:-1] & alt_any[:-2] & alt_any[2:] & ~run[1:-1]
    pairs = {}
    ys, xs = np.nonzero(run)
    for y, x in zip(ys, xs):
        p = tuple(sorted((int(idx[y, x]), int(idx[y, x + 1]))))
        pairs[p] = pairs.get(p, 0) + 1
    return D, dict(D_texels=int(D.sum()), run_positions=int(run.sum()), excluded_class_changing_positions=int(excluded.sum()),
                   D_bbox=[int(xs.min()), int(ys.min()), int(xs.max()) + 2, int(ys.max())] if len(xs) else None,
                   pairs=sorted([[list(k), v] for k, v in pairs.items()], key=lambda t: -t[1]))


def box_h(x, n):
    """Horizontal box sum over pixels x-n/2 .. x+n/2-1 (exactly n pixels; any 2-texel window of a pure a,b column alternation
    holds s pixels of each); edge-clamped, output width == input width."""
    pw = ((0, 0), (n // 2, n // 2 - 1), (0, 0)) if x.ndim == 3 else ((0, 0), (n // 2, n // 2 - 1))
    c = np.cumsum(np.pad(x, pw, mode="edge"), axis=1)
    z = np.zeros_like(c[:, :1])
    c = np.concatenate([z, c], axis=1)
    return c[:, n:] - c[:, :-n]


def feather(D, s):
    from scipy import ndimage
    up = np.kron(D.astype(np.float32), np.ones((s, s), np.float32))
    return np.clip(ndimage.gaussian_filter(up, 0.5 * s * 0.6), 0, 1) * up  # inside D only, soft 0.5-texel ramp at its border


def repair(png, D, s):
    rgb = png[..., :3].astype(np.float32)
    a = png[..., 3]
    Dp = np.kron(D, np.ones((s, s), bool))
    m = feather(D, s)
    out = rgb.copy()
    for c in (127, 255):
        wgt = (Dp & (a == c)).astype(np.float32)
        if not wgt.any():
            continue
        num = box_h(rgb * wgt[..., None], 2 * s)
        den = box_h(wgt, 2 * s)[..., None]
        dd = np.where(den > 0, num / np.maximum(den, 1e-6), rgb)
        sel = (a == c) & Dp
        mm = m[..., None]
        out = np.where(sel[..., None], rgb * (1 - mm) + dd * mm, out)
    new = png.copy()
    new[..., :3] = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    return new, Dp


def stripe_metric(img, Dp, s):
    """mean |RGB(x) - RGB(x+s)| (one texel apart) over D pixels: the 1-texel column contrast."""
    rgb = img[..., :3].astype(np.float32)
    d = np.abs(rgb[:, s:] - rgb[:, :-s]).mean(-1)
    msk = Dp[:, s:] & Dp[:, :-s] & (img[:, s:, 3] != 0) & (img[:, :-s, 3] != 0)
    return round(float(d[msk].mean()), 3) if msk.any() else None


def lum(img, Dp):
    rgb = img[..., :3].astype(np.float32)
    msk = Dp & (img[..., 3] != 0)
    return float((rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722)[msk].mean()) if msk.any() else None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "mask"
    t0 = time.time()
    idx, keys, cluts, m = load_native()
    D, info = dither_mask(idx, cluts)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if mode == "mask":
        OUT.parent.mkdir(parents=True, exist_ok=True)
        dst = OUT.parent / f"A5969BC9-dedither-mask-{stamp}.json"
        dst.write_text(json.dumps(dict(run=stamp, v1_manifest_sha256=sha(V1 / "manifest.json"), keys=[k["key"] for k in keys],
                                       **info, D_rows=[[int(y), int(D[y].sum())] for y in range(256) if D[y].any()]), indent=1) + "\n",
                       encoding="utf-8")
        print(json.dumps({k: v for k, v in info.items() if k != "pairs"}), "pairs", info["pairs"][:10])
        print("out", dst, sha(dst))
        return
    assert mode == "build", mode
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([me.cpu_affinity()[-1]])
        prio = dict(pid=me.pid, nice="below_normal", affinity=me.cpu_affinity())
    except Exception as e:
        prio = dict(error=repr(e))
    from PIL import Image
    assert not OUT.exists(), "output exists (immutable): bump the revision"
    OUT.mkdir(parents=True)
    rows = []
    for k in keys:
        row = dict(key=k["key"], clut=k["clut"], files={})
        for tag, s in (("2048", 8), ("1024", 4)):
            src = V1 / k[f"png_{tag}"]["path"]
            assert sha(src) == k[f"png_{tag}"]["sha256"], f"v1 hash mismatch {src}"
            with Image.open(src) as im:
                v1 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            new, Dp = repair(v1, D, s)
            assert np.array_equal(new[..., 3], v1[..., 3]), "class plane changed"
            outside_same = bool(np.array_equal(new[~Dp], v1[~Dp]))
            p = OUT / f"runtime-{tag}" / f"{k['key']}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(new, "RGBA").save(p, optimize=True)
            row["files"][tag] = dict(path=f"runtime-{tag}/{k['key']}.png", sha256=sha(p), v1_sha256=k[f"png_{tag}"]["sha256"],
                                     alpha_identical_to_v1=True, outside_D_identical_to_v1=outside_same,
                                     stripe_metric_v1=stripe_metric(v1, Dp, s), stripe_metric_r1=stripe_metric(new, Dp, s),
                                     D_lum_v1=lum(v1, Dp), D_lum_r1=lum(new, Dp),
                                     pixels_changed=int((new != v1).any(-1).sum()))
            if tag == "2048" and k["clut"] in ("FD5E0863", "28E85C14"):
                tiles = []
                for (u, v) in CROPS:
                    sl = (slice(v * s, (v + 48) * s), slice(u * s, (u + 48) * s))
                    a1 = Image.fromarray(v1[sl][..., :3]).resize((384, 384), Image.NEAREST)
                    a2 = Image.fromarray(new[sl][..., :3]).resize((384, 384), Image.NEAREST)
                    small1 = Image.fromarray(v1[..., :3]).resize((256 * 2, 256 * 2), Image.BOX).crop((u * 2, v * 2, (u + 48) * 2, (v + 48) * 2)).resize((384, 384), Image.NEAREST)
                    small2 = Image.fromarray(new[..., :3]).resize((256 * 2, 256 * 2), Image.BOX).crop((u * 2, v * 2, (u + 48) * 2, (v + 48) * 2)).resize((384, 384), Image.NEAREST)
                    t = Image.new("RGB", (384 * 4 + 18, 384), (12, 12, 16))
                    for i, im_ in enumerate((a1, a2, small1, small2)):
                        t.paste(im_, (i * (384 + 6), 0))
                    tiles.append(t)
                sheet = Image.new("RGB", (tiles[0].width, len(tiles) * (384 + 6)), (12, 12, 16))
                for i, t in enumerate(tiles):
                    sheet.paste(t, (0, i * (384 + 6)))
                rv = OUT / "review" / f"{k['key']}-v1-vs-r1-[2048crop|r1crop|2pxTexel-v1|2pxTexel-r1].png"
                rv.parent.mkdir(exist_ok=True)
                sheet.save(rv, optimize=True)
                row["review"] = rv.name
            del v1, new
        rows.append(row)
        print(row["key"], {t: (f["stripe_metric_v1"], f["stripe_metric_r1"], f["outside_D_identical_to_v1"]) for t, f in row["files"].items()},
              flush=True)
    man = dict(name=OUT.name, status="proposal (s67 repair r1; NOT frozen lane art; NOT accepted)", owner="claude-einhander-s67",
               task="EIN-S6-WHOLE-CELL-20261114", created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               base=dict(folder=str(V1.relative_to(ROOT)).replace("\\", "/"), manifest_sha256=sha(V1 / "manifest.json")),
               import_rule=m.get("import_rule"), provenance="predicted-static (inherits v1); live key/CLUT unconfirmed",
               method=__doc__, mask=info, priority=prio, elapsed_s=round(time.time() - t0, 1), keys=rows,
               builder=dict(path=str(Path(__file__)), sha256=sha(Path(__file__))))
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print("out", OUT, "manifest", sha(OUT / "manifest.json"), "elapsed", man["elapsed_s"])


if __name__ == "__main__":
    main()
