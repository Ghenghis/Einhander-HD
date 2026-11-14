#!/usr/bin/env python3
"""s45: tools/w7m2 = tools/w7m + ONE opt-in patch: fx_region(class_aware=True).

Finding (J-B 20261114T140010Z-s5): lane-s5 fx_region's docstring says 'near' is 'same class under every renderable static
CLUT of the page', but the code uses N = np.ones((16, 16)) (any index pair may blend). With centres not forced, class
contours then drift beyond s/2 across STP/opaque borders (Duerer v2 BFC445B0: 386 px R2 in the FX flame box).
class_aware=True builds N[i, j] = class(P_k[i]) == class(P_k[j]) for EVERY candidate CLUT k (the `cluts` the caller already
passes), i.e. what the docstring describes: blending stays inside same-class tone groups and class borders keep the crisp
contour. Default False keeps w7m byte-identical. Jobs opt in with job['fx_region']['class_aware'] = true.
Write-once output; each anchor must match exactly once."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

T = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45/tools")
SRC, OUT = T / "w7m", T / "w7m2"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"anchor for {what}: {n} matches")
    return text.replace(old, new)


def main():
    if OUT.exists():
        sys.exit(f"{OUT} exists (write-once)")
    shutil.copytree(SRC, OUT)
    L = (OUT / "w7lib.py").read_text(encoding="utf-8")
    L = once(L, "def fx_region(L, Wt, idx, cluts, box, blend_sigma=1.0, crisp=(0.42, 4.0), beta=(0.15, 0.4), margin=4):",
             "def fx_region(L, Wt, idx, cluts, box, blend_sigma=1.0, crisp=(0.42, 4.0), beta=(0.15, 0.4), margin=4,\n"
             "              class_aware=False):", "fx_region signature")
    L = once(L, "    N = np.ones((16, 16), bool)        # any pair may blend: render() keeps only the labels of the dominant label's\n",
             "    N = np.ones((16, 16), bool)        # any pair may blend: render() keeps only the labels of the dominant label's\n"
             "    if class_aware:   # s45 w7m2 opt-in: blend only index pairs of the same class under EVERY candidate CLUT\n"
             "        C = np.stack([np.asarray(c) for _, c in cluts])          # (n_cluts, 16) classes 0 / 127 / 255\n"
             "        N = (C[:, :, None] == C[:, None, :]).all(0)\n", "class-aware near matrix")
    L = once(L, "    return dict(kind='fx', box=list(box[:4]), blend_sigma=blend_sigma, crisp=list(crisp), beta_window=list(beta),\n"
                "                near='any index pair (render keeps only labels of the dominant class per CLUT)',\n",
             "    return dict(kind='fx', box=list(box[:4]), blend_sigma=blend_sigma, crisp=list(crisp), beta_window=list(beta),\n"
             "                near=('same class under every candidate CLUT (s45 class_aware)' if class_aware else\n"
             "                      'any index pair (render keeps only labels of the dominant class per CLUT)'),\n"
             "                near_pairs=int(N.sum() - 16) // 2,\n", "record field")
    (OUT / "w7lib.py").write_text(L, encoding="utf-8")
    shutil.copy2(Path(__file__), OUT / "make_w7m2.py")
    rec = dict(base="tools/w7m", base_merge_record_sha256=sha(SRC / "MERGE-RECORD.json"), base_w7lib_sha256=sha(SRC / "w7lib.py"),
               patch="fx_region(class_aware=False) opt-in; record fields near/near_pairs",
               note="near_pairs is a NEW record field in every fx region record (build-record.json / manifest regions); exports and masters are unaffected when class_aware is False",
               outputs={f.name: sha(f) for f in sorted(OUT.glob("*.py"))})
    (OUT / "MERGE-RECORD2.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
