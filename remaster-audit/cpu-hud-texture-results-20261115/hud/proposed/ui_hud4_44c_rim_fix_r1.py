"""J-H4 FIX r1: one-key image-edge rim correction for coherent-v4 44C16454-72FBA1C5 (PROPOSAL; needs review + CPU grant).

Diagnosis (existing J-H4 r2 sheet 7cb2f952, read in a browser canvas, no job run):
  all 2028 conn flags of this key are yellow (displaced, bit 2) and lie ONLY on the image's outermost HD rows:
  row 0 (606 px) and row 127 (1422 px) of the 4096x128 strip (ROI = whole strip [0,0,256,8)). Native there is opaque art;
  v4 is alpha 0 there (sheet 24,24,24), while the adjacent inner rows (1 and 126) are opaque art of matching hue.
  The strip is MIXED (numeral plus blue/green icon parts): this is a geometric edge-row correction, NOT a glyph repair.

Correction (minimal, one key, private output only):
  for every flagged ROI pixel, REQUIRE it lies on HD row 0 or row 127, and copy RGBA from the adjacent inner row
  (0 <- 1, 127 <- 126). The source must be unflagged and its alpha must equal the native class of the same native cell.
  This is a native-class ALPHA correction plus an RGB copy: v4's defective alpha at those pixels is REPLACED, not kept.

Refuses (exit 2) unless ALL hold:
  - r2 tool, v4 PNG, words/CLUT/meta, class_mip.c/.h, clang launcher pinned by sha256 (r2 is loaded only after its hash
    check; this is not an atomic whole-toolchain pin);
  - before: r1_region 0, metric_agree, conn_region == 2028, every flagged pixel on row 0 or 127;
  - after: conn_region 0, r1_region 0, metric_agree, nonclass_region 0, conn_outside and r1_outside unchanged,
    changed-pixel mask == flagged mask exactly, every changed alpha == native class of its cell,
    all pixels outside the ROI byte-identical (none exist here: ROI = whole image), all native-cell centres byte-identical.
Writes ONLY into a new run folder next to this file: the corrected PNG, top/bottom before/after crops, result.json,
receipt.json. Never writes into any pack, never installs. Exit codes: 0 fixed+verified, 2 refused, 5 exception.
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
sys.dont_write_bytecode = True
if sys.flags.optimize:
    raise SystemExit("CHECK FAILED: refusing to run under python -O")

import ctypes  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/hud4-v4-audit")
R2 = (HERE / "ui_hud4_v4_region_audit_r2.py", "c5d0e375e1b69f4156a0828a8d8492e6423df5c0cd2e366a3ed1fc2fe8bf5f13")
KEY = "44C16454-72FBA1C5"
EXPECT_FLAGS = 2028
EDGE_SRC = {0: 1, 127: 126}            # flagged HD row -> inner source row
STATE = {"phase": "start", "before": None, "after": None, "compile": None, "artifacts": {}, "error": None}


def _hb(b):
    return hashlib.sha256(b).hexdigest()


def load_r2():
    b = R2[0].read_bytes()
    if _hb(b) != R2[1]:
        raise SystemExit("CHECK FAILED: r2 tool sha256 differs")
    spec = importlib.util.spec_from_file_location("hud4_r2_frozen", R2[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # module level only: env, imports, constants; main() is __main__-guarded
    return mod


def main(rd):
    t0 = time.time()
    m2 = load_r2()
    need, hb, read_pinned, summarize = m2.need, m2.hb, m2.read_pinned, m2.summarize
    T = m2.TARGETS[KEY]
    STATE["phase"] = "pins"
    fixed = {k: read_pinned(p, h, k) for k, (p, h) in m2.PINS_FIXED.items()}
    vb = read_pinned(*T["v4"], KEY + " v4")
    wb = read_pinned(*T["words"], KEY + " words")
    cb = read_pinned(*T["clut"], KEY + " clut")
    read_pinned(*T["meta"], KEY + " meta")
    need(m2.ihdr(vb) == T["size"], "v4 IHDR")
    gw, gh = T["geom"]
    s = T["size"][0] // (gw * 4)
    need(s == 16, "scale", s)
    x0, y0, x1, y1 = T["region"]

    STATE["phase"] = "libraries"
    import numpy as np
    import PIL
    from PIL import Image
    got = {"python": sys.version.split()[0], "numpy": np.__version__, "pillow": PIL.__version__}
    need(got == m2.VERSIONS, "library versions differ", got, m2.VERSIONS)
    Image.MAX_IMAGE_PIXELS = 4096 * 4096

    STATE["phase"] = "compile"
    for name in ("class_mip.c", "class_mip.h"):
        with open(rd / name, "xb") as fh:
            fh.write(fixed[name])
        back = hb((rd / name).read_bytes())
        STATE["artifacts"][name] = back
        need(back == m2.PINS_FIXED[name][1], "executed copy differs from pin", name)
    cmd = [str(m2.CLANG), "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")]
    c = subprocess.run(cmd, capture_output=True, text=True, timeout=60, creationflags=0x4000 | 0x08000000)
    STATE["compile"] = dict(argv=cmd, rc=c.returncode, stdout=c.stdout[-2000:], stderr=c.stderr[-2000:])
    need(c.returncode == 0, "class_mip compile failed", c.returncode)
    STATE["artifacts"]["class_mip.dll"] = hb((rd / "class_mip.dll").read_bytes())
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]

    def flags(img, ncls, bound):
        img = np.ascontiguousarray(img)
        ncls = np.ascontiguousarray(ncls.astype(np.uint8))
        th, tw = ncls.shape
        H, W = img.shape[:2]
        fl = np.zeros((H, W), np.uint8)
        rc = lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, bound, 0, fl.ctypes.data)
        need(rc == 0, "cm_flags_ex rc", rc, bound)
        return fl

    STATE["phase"] = "decode"
    w = np.frombuffer(wb, "<u2").reshape(gh, gw)
    idx = np.zeros((gh, gw * 4), np.uint8)
    for i in range(4):
        idx[:, i::4] = (w >> (4 * i)) & 15
    val = np.frombuffer(cb, "<u2")[idx].astype(np.uint16)
    ncls = np.where(val == 0, 0, np.where(val & 0x8000, 255, 127)).astype(np.uint8)
    with Image.open(io.BytesIO(vb)) as im:
        need(im.size == T["size"] and im.mode == "RGBA", "v4 must be RGBA at pinned size", im.size, im.mode)
        orig = np.array(im, dtype=np.uint8)          # writable copy
    H, W = orig.shape[:2]

    STATE["phase"] = "before"
    cf0, sf0 = flags(orig, ncls, 1.0e9), flags(orig, ncls, 0.5)
    b = summarize(orig, ncls, cf0, sf0, s, T["region"], np)
    STATE["before"] = b
    need(b["metric_agree"] and b["r1_region"] == 0, "before: expected r1 0 / metric agree", b)
    need(b["conn_region"] == EXPECT_FLAGS, "before: conn_region differs from the diagnosed 2028", b["conn_region"])
    rpx = np.zeros((H, W), bool); rpx[y0 * s:y1 * s, x0 * s:x1 * s] = True
    fmask = ((cf0 & m2.CONN_BITS) != 0) & rpx
    ys, xs = np.nonzero(fmask)
    need(H == 128 and (y0, y1) == (0, 8), "unexpected strip geometry", H, y0, y1)
    need(int(fmask.sum()) == EXPECT_FLAGS and bool(np.isin(ys, list(EDGE_SRC)).all()), "flags not confined to HD rows 0/127",
         sorted(set(ys.tolist()))[:10])
    yb = np.array([EDGE_SRC[int(v)] for v in ys], dtype=np.intp)
    need(bool((yb // s == ys // s).all()), "source row not in the same native cell")
    src = orig[yb, xs]
    need(not bool(((cf0[yb, xs] & m2.CONN_BITS) != 0).any()), "source rows have flags")
    need(bool((src[:, 3] == ncls[ys // s, xs // s]).all()), "source alpha != native class of the same cell")

    STATE["phase"] = "fix"
    img = orig.copy()
    img[ys, xs] = src

    STATE["phase"] = "after"
    cf1, sf1 = flags(img, ncls, 1.0e9), flags(img, ncls, 0.5)
    a = summarize(img, ncls, cf1, sf1, s, T["region"], np)
    STATE["after"] = a
    changed = (img != orig).any(-1)
    c2 = s // 2
    checks = dict(
        after_pass=a["region_verdict"] == "R1_CONNECTIVITY_PASS" and a["conn_region"] == 0 and a["r1_region"] == 0,
        metric_agree=a["metric_agree"], nonclass_zero=a["nonclass_region"] == 0,
        outside_counts_unchanged=a["conn_outside"] == b["conn_outside"] and a["r1_outside"] == b["r1_outside"],
        changed_equals_flagged=bool((changed == fmask).all()),
        changed_alpha_is_native_class=bool((img[changed][:, 3] == ncls[np.nonzero(changed)[0] // s,
                                                                       np.nonzero(changed)[1] // s]).all()),
        outside_roi_identical=bool((img[~rpx] == orig[~rpx]).all()),
        centres_identical=bool((img[c2::s, c2::s] == orig[c2::s, c2::s]).all()),
    )
    STATE["checks"] = checks
    need(all(checks.values()), "post-fix checks failed", checks)

    STATE["phase"] = "write"
    fn = f"{KEY}.rimfix-r1.png"
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG", optimize=False)
    with open(rd / fn, "xb") as fh:
        fh.write(buf.getvalue())
    with Image.open(rd / fn) as im:
        need(np.array_equal(np.asarray(im.convert("RGBA")), img), "readback differs")
    crop = np.concatenate([orig[0:16], img[0:16], orig[112:128], img[112:128]], 0)   # top before/after, bottom before/after
    with open(rd / "before_after_edges.png", "xb") as fh:
        Image.fromarray(crop).save(fh, format="PNG")
    out = dict(owner="claude-einhander-ui", job="J-H4 FIX r1 one-key image-edge (rows 0/127) rim correction, " + KEY,
               tool_sha256=hb(Path(__file__).read_bytes()), r2_sha256=R2[1], versions=got,
               input_v4=[str(T["v4"][0]), T["v4"][1]], changed_px=int(changed.sum()),
               changed_rows=sorted(set(np.nonzero(changed)[0].tolist())),
               changed_x=[int(xs.min()), int(xs.max())], before=b, after=a, checks=checks,
               output=dict(path=fn, sha256=hb((rd / fn).read_bytes())),
               crop=dict(path="before_after_edges.png", sha256=hb((rd / "before_after_edges.png").read_bytes())),
               executed_artifacts=STATE["artifacts"],
               not_claimed="private candidate only; not installed in any pack; no admission, composed or live acceptance",
               seconds=round(time.time() - t0, 1))
    with open(rd / "result.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    STATE["phase"] = "done"
    print(json.dumps({"checks": checks, "output": out["output"], "out": str(rd)}))
    return 0


if __name__ == "__main__":
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RD = HERE / "fix-44c-rim" / "runs" / stamp
    RD.mkdir(parents=True, exist_ok=False)
    rc = 5
    try:
        rc = main(RD)
    except SystemExit as e:
        if isinstance(e.code, str):
            STATE["error"] = dict(kind="REFUSED", reason=e.code)
            rc = 2
        else:
            STATE["error"] = dict(kind="EXIT", code=e.code)
            rc = e.code if isinstance(e.code, int) and e.code != 0 else 5
    except Exception as e:  # noqa: BLE001
        STATE["error"] = dict(kind="EXCEPTION", reason=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-4000:])
        rc = 5
    finally:
        STATE["exit_code"] = rc
        STATE["pid"] = os.getpid()
        try:
            with open(RD / "receipt.json", "x", encoding="utf-8") as fh:
                fh.write(json.dumps(STATE, indent=1, default=str) + "\n")
        except Exception as e:  # noqa: BLE001
            print(f"receipt write failed: {e}", file=sys.stderr)
            rc = rc or 5
        if STATE["error"]:
            print(json.dumps(STATE["error"])[:2000], file=sys.stderr)
    sys.exit(rc)
