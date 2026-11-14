#!/usr/bin/env python3
"""Registration-shift audit (claude-einhander). Read-only, CPU only, below normal, one image at a time.
Question: is a page's whole-cell class mismatch a REGISTRATION OFFSET (the HD art is the native silhouette, moved by a
whole number of HD pixels), or a genuine shape change?

For each texture page with visible-transparency pixels in a breakdown_v2b run (its worst key), with V = HD visible
(alpha != 0), N = native visible upsampled to HD (cell class != 0) and Dp = drawn texels (same mapping as breakdown_v2b):
    mismatch(d) = sum_x Dp(x) * [V(x - d) != N(x)]        for every HD shift d = (dx, dy), |dx|,|dy| <= R
computed for all d at once with FFT correlations (V shifted with zero fill). Reports mismatch at d = 0, the best d,
mismatch there, and the same in native-texel units. A large drop at a non-zero d means the art is offset, not reshaped.
Writes ONLY runs-shift/<UTC>/ (exist_ok=False): result.json, a copy of this script."""
import argparse
import collections
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "class-audit"))
import audit_native_classes_v2 as A  # noqa: E402
import breakdown_v2b as B  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def corr_all(a, b, R):
    """c[dy, dx] = sum_x a(x) * b(x - d) for |d| <= R (zero fill), via FFT on padded float64 arrays."""
    H, W = a.shape
    ph, pw = H + R, W + R
    fa = np.fft.rfft2(a, s=(ph, pw))
    fb = np.fft.rfft2(b, s=(ph, pw))
    c = np.fft.irfft2(fa * np.conj(fb), s=(ph, pw))      # c[k] = sum_x a(x) b(x - k), k mod (ph, pw)
    out = np.empty((2 * R + 1, 2 * R + 1))
    for i, dy in enumerate(range(-R, R + 1)):
        for j, dx in enumerate(range(-R, R + 1)):
            out[i, j] = c[dy % ph, dx % pw]
    return np.rint(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, help="runs-breakdown-v2b/<UTC> folder")
    ap.add_argument("--radius-texels", type=float, default=1.5, help="search radius in native texels")
    a = ap.parse_args()
    A.below()
    res = json.loads((a.run / "result.json").read_text(encoding="utf-8"))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    od = HERE / "runs-shift" / stamp
    od.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), od / Path(__file__).name)
    rows = {(r["group"], r["key"]): r for g in res["rows"].values() for r in g}
    pack = Path(res["pack"])
    regions = {}
    for line in (pack / "pack/ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    best = {}
    for (g, k), r in rows.items():
        if "visibility" in r and r["visibility"]["visible-transparency"]:
            pk = (g, k[:8])
            if r["visibility"]["visible-transparency"] > best.get(pk, (0, None))[0]:
                best[pk] = (r["visibility"]["visible-transparency"], k)
    want = [(pk[0], v[1]) for pk, v in sorted(best.items(), key=lambda kv: -kv[1][0])]
    draws = B.load_draws([Path(m["path"]) for m in res["capture_logs"]], collections.Counter(), regions)
    order = [A.STOCK, A.UHU] + sorted(A.CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in A.E.glob("*/hd-on_rewind-off/*") if p.is_dir())

    def source(key):                                    # identical lookup order to breakdown_v2b
        for d in ([pack / "pack"] if key in regions else order):
            s, c = A.try_dump(d, key, regions)
            if s:
                return s, c
        if key not in regions:
            for d in cap_dirs:
                s, c = A.try_dump(d, key, regions)
                if s:
                    return s, c
        return None, None

    out = []
    for grp, key in want:
        r = rows[(grp, key)]
        if sha(r["png"]) != r["png_sha256"]:
            out.append(dict(group=grp, key=key, error="png changed since the breakdown run"))
            continue
        _, cls = source(key)
        with Image.open(r["png"]) as im:
            alpha = np.asarray(im.convert("RGBA"))[..., 3]
        th, tw = cls.shape
        H, W = alpha.shape
        s = W // tw
        dk = draws.get(key)
        if dk and not dk["unmapped"] and dk["dims"] == (tw, th):
            D, _ = B.raster(dk["tris"], tw, th)
        else:
            D = np.ones((th, tw), bool)
        Dp = np.repeat(np.repeat(D, s, 0), s, 1).astype(np.float64)
        N = np.repeat(np.repeat(cls != 0, s, 0), s, 1).astype(np.float64)
        V = (alpha != 0).astype(np.float64)
        R = max(1, int(round(a.radius_texels * s)))
        t1 = corr_all(Dp, V, R)                          # sum Dp(x) V(x-d)
        t2 = corr_all(Dp * N, V, R)                      # sum Dp(x) N(x) V(x-d)
        mism = t1 + float((Dp * N).sum()) - 2.0 * t2
        i0 = R
        m0 = mism[i0, i0]
        bi, bj = np.unravel_index(np.argmin(mism), mism.shape)
        dy, dx = int(bi - R), int(bj - R)
        direct = float((Dp * (V != N)).sum())            # cross-check of the FFT path at d = 0
        out.append(dict(group=grp, key=key, provenance=r["provenance"], scale=s, native=[tw, th], drawn_texels=int(D.sum()),
                        mismatch_d0=int(m0), mismatch_d0_direct=int(direct), best_shift_px=[dx, dy],
                        best_shift_texels=[round(dx / s, 3), round(dy / s, 3)], mismatch_best=int(mism[bi, bj]),
                        reduction=round(1.0 - mism[bi, bj] / m0, 4) if m0 else 0.0,
                        mismatch_unit_shifts={f"{ddx},{ddy}": int(mism[i0 + ddy, i0 + ddx])
                                              for ddx in (-s // 2, 0, s // 2) for ddy in (-s // 2, 0, s // 2)}))
        print(json.dumps(out[-1]), flush=True)
        del alpha, Dp, N, V
    (od / "result.json").write_text(json.dumps(dict(run=stamp, breakdown_run=str(a.run),
                                                    breakdown_result_sha256=sha(a.run / "result.json"),
                                                    radius_texels=a.radius_texels, pages=out), indent=1) + "\n",
                                    encoding="utf-8")
    with open(HERE / "runs-shift" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, result_sha256=sha(od / "result.json"))) + "\n")


if __name__ == "__main__":
    main()
