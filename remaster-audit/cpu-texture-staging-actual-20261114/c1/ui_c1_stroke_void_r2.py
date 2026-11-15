#!/usr/bin/env python3
"""claude-einhander-ui J-C1V r2: ONE-ROI stroke-interior void correction for 1AD90FC9-02491337, ROI B ("30mm to RAIL").
Requested by main (msg_ed550dd2); derived from CORRECTION-MAP-1AD90FC9-02491337-B.md correction C1. NOT RUN by its author.

r2 vs r1 (5ef8da10, frozen read-only), per c1-review msg_449f9270:
  - Exit status: 0 ONLY on verdict PASS; BLOCKED 3, FAIL 4, REFUSED (pin/precondition) 2, EXCEPTION 5, so the fa5 wrapper cannot
    false-pass.
  - G4 is the GLOBAL contract, strictly enforced:
    - the centre-sample RGBA arrays are exactly equal before and after;
    - every one of the 65,536 centres is native before (cen_before.all());
    - every centre is native after (centre_ok(out).all()).
    A non-native centre anywhere (inside or outside ROI B) is recorded as BLOCKER "non-native centre" and no art is written.
  - New direct negative and positive controls:
    - an injected centre void is rejected;
    - a non-native centre outside the ROI fails the global contract;
    - a class-127 cell fills with alpha 127;
    - the exact class-mismatch delta equals |V|.
  - Dry-run disclosure: dry-run is NOT write-free. It creates runs/<UTC>/ and writes result.json plus the review sheet
    review_roiB_1x.png, which shows PROPOSED pixels even when the verdict is BLOCKED or FAIL; the sheet is labelled with the
    verdict. The standalone corrected PNG is written only in --mode write with verdict PASS.
r1 header follows (still accurate except G4 and the exit status above).

Scope (fixed in code; no CLI widening):
  - input: the v5 snap-native candidate a3035801… (w4 menu-class-exact-v1 runtime-2048), never the frozen w4 art;
  - native authority: words 32861a17… (CRC 1AD90FC9) and CLUT 3b2c7aae… (CRC 02491337), decoded inline
    (4bpp, low nibble first, 5-bit<<3 RGB, class 0 / 127 / 255 from value==0 / STP bit), the same decode as r6 29958167;
  - region: texels [0,58,124,158) = r6 TEXT_ROIS["B_spec_left_30mm_to_RAIL"]; protected EXCLUDE boxes asserted disjoint.

Correction (C1), applied ONLY to pixels in mask V:
  V = HD pixel inside ROI B
      & inside the 2-pixel-eroded HD footprint of the native glyph mask (r6 hd_interior, erosion s//4 = 2 px at s=8)
      & its own native cell is a visible-class glyph texel (class 127 or 255, lum >= 180)
      & the candidate pixel is alpha 0 (a void).
  Each pixel in V becomes exactly its own cell's native colour and class alpha: RGB = native RGB8, A = 127 or 255.
  This changes RGB AND alpha. ALPHA EXCEPTION: alpha 0 -> native class alpha, only inside V. Every other pixel's RGBA is untouched.

Protected and never changed (gated):
  - every pixel outside V, which includes counters/background (native non-glyph cells), the contour band (glyph footprint minus
    the eroded interior), all other ROIs and every excluded emblem/icon/digit box;
  - each native cell's centre sample at (s/2, s/2). The candidate must ALREADY hold the exact native value there for every
    cell in ROI B. If any centre in V is a void, the run stops with BLOCKER "centre void" and writes no art.

Gates (all must hold, or verdict BLOCKED/FAIL with no art written):
  G1 the changed-pixel mask equals V exactly, and the full-image RGBA outside V is byte-identical to the input;
  G2 every changed pixel's (RGB, A) equals its own cell's native (RGB8, class);
  G3 class mismatches (pixel alpha class vs its cell's native class, whole image, s/2-centre and all pixels) after == before - |V|,
     with no new mismatch anywhere;
  G4 centre samples unchanged and equal to native for all 65,536 cells;
  G5 |V| equals the dry-run count (in write mode, |V| must equal the --expect-voids value from the reviewed dry run).
  R5 (compositor/blend appearance) is NOT evaluated or claimed; readability still needs the final composed game background.

Modes: --mode dry-run (default) writes only result.json plus review sheets. --mode write also writes the corrected PNG
<out>/1AD90FC9-02491337.c1.png, and requires --expect-voids N from a reviewed dry run.
Outputs: <UI_OUT>/c1-stroke-void/runs/<UTC>/ (exclusive). Threads = 1; python -O refused; library versions pinned.
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
sys.dont_write_bytecode = True
if sys.flags.optimize:
    raise SystemExit("CHECK FAILED: refusing to run under python -O")

import argparse  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import struct  # noqa: E402
import time  # noqa: E402
import zlib  # noqa: E402
from pathlib import Path  # noqa: E402

UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
SUMMARY = UI_OUT / "integration/runtime-summary-v5-20261114T180533Z.json"
SUMMARY_SHA256 = "e124d0e814d2d7b9d503c7df36df1a6aba62cc18e6a9483f6ab2a7e0fa092a1b"
FOLDER, DIR, SIZE = "w4-menus/menu-class-exact-v1", "runtime-2048", (2048, 2048)
VERSIONS = {"python": "3.14.5", "numpy": "2.5.2", "scipy": "1.17.1", "pillow": "12.3.0"}
KEY = "1AD90FC9-02491337.png"
PIN = {
    # frozen w4 authored art: verified ONLY via the pinned SUMMARY metadata (input_sha256); the raw frozen file is never read
    "authored_sha256": "3eae507320ef8345010a2f096b3e039f9a8fdd599df38b9343071a3fd340dbb2",
    "snap": UI_OUT / "classsnap-v5/20261114T180407Z/snap-native/w4-menus__menu-class-exact-v1__runtime-2048__1AD90FC9-02491337.png",
    "snap_sha256": "a3035801bbab95c92dcd3d0adbef31a85086dcdbb029c9a31cd21ef0f9fcb7e3",
    "words": Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.words.bin"),
    "words_sha256": "32861a1726c1ee0be1b76bbdd65040f95106084d0d361b883ab4f3df77ce2fc8",
    "meta": Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.source.json"),
    "meta_sha256": "15dab1ad9dc24a31900a9b7036a02c9aefb5c6956f2705477a667a45cf7e8037",
    "clut": Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.clut.bin"),
    "clut_sha256": "3b2c7aaef20d4f9368dd6d479773cb9cb4915624a39fd9a849d25031769a806b",
}
R6_RESULT = UI_OUT / "speck-measure-roi-r6/20261114T215719Z/result.json"
R6_RESULT_SHA256 = "5f70c178844604447a24a2d3a5c27b755fee57c92d033a9a974563fc35f59a25"
R6_EXPECTED_SNAP_HD_INTERIOR_ALPHA0 = 240  # r6: 02491337 ROI B hd_interior_quarter_texel snap_native alpha0_px
ROI_B = (0, 58, 124, 158)
EXCLUDE = {"selene_emblem": (128, 86, 216, 152), "eye_emblem": (74, 158, 168, 240),
           "pad_icons": (212, 40, 256, 80), "digits_stage_select": (0, 160, 74, 216)}
GLYPH_LUM = 180.0


def need(cond, *msg):
    if not cond:
        raise SystemExit("CHECK FAILED: " + " | ".join(str(m) for m in msg))


def hb(b):
    return hashlib.sha256(b).hexdigest()


def ihdr(b):
    need(len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR", "not a PNG with IHDR first")
    return tuple(struct.unpack(">II", b[16:24]))


def overlap(a, b):  # half-open [x0, y0, x1, y1)
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("dry-run", "write"), default="dry-run")
    ap.add_argument("--expect-voids", type=int, default=None)
    a = ap.parse_args()
    need(a.mode == "dry-run" or a.expect_voids is not None, "write mode requires --expect-voids from a reviewed dry run")
    t0 = time.time()
    # ---- byte-level verification first ----
    sb = SUMMARY.read_bytes()
    need(hb(sb) == SUMMARY_SHA256, "summary sha256")
    mem = {}
    for u in json.loads(sb)["units_detail"]:
        if u["folder"] == FOLDER and u["dir"] == DIR:
            for m in u["members"]:
                mem[os.path.basename(m["file"])] = m
    m = mem.get(KEY)
    need(m is not None and m.get("built") and m["input_sha256"] == PIN["authored_sha256"] and
         m["candidate_sha256"] == PIN["snap_sha256"] and m["words_sha256"] == PIN["words_sha256"] and
         m["clut_sha256"] == PIN["clut_sha256"], "summary pins differ")
    r6b = R6_RESULT.read_bytes()
    need(hb(r6b) == R6_RESULT_SHA256, "r6 result sha256")
    nb, wb, cb, mb = (Path(PIN["snap"]).read_bytes(), PIN["words"].read_bytes(), PIN["clut"].read_bytes(),
                      PIN["meta"].read_bytes())
    need(hb(nb) == PIN["snap_sha256"] and ihdr(nb) == SIZE, "snap pin/IHDR")
    need(hb(wb) == PIN["words_sha256"] and "%08X" % zlib.crc32(wb) == "1AD90FC9" and len(wb) == 32768, "words pin/CRC/len")
    need(hb(cb) == PIN["clut_sha256"] and "%08X" % zlib.crc32(cb) == "02491337" and len(cb) == 32, "CLUT pin/CRC/len")
    need(hb(mb) == PIN["meta_sha256"], "meta sha256")
    meta = json.loads(mb)
    need([meta["width_words"], meta["height"], meta["depth"]] == [64, 256, 0], "words geometry")
    for ex_name, ex in EXCLUDE.items():
        need(overlap(ROI_B, ex) == 0, "ROI B overlaps protected box", ex_name)
    r6_rows = {r["key"]: r for r in json.loads(r6b)["rows"]}
    r6_v = r6_rows[KEY]["rois"]["B_spec_left_30mm_to_RAIL"]["masks"]["hd_interior_quarter_texel"]["snap_native"]["alpha0_px"]
    need(r6_v == R6_EXPECTED_SNAP_HD_INTERIOR_ALPHA0, "r6 recorded void count differs", r6_v)
    # ---- libraries ----
    import numpy as np
    import PIL
    import scipy
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    got = {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__, "pillow": PIL.__version__}
    need(got == VERSIONS, "library versions differ", got, VERSIONS)
    Image.MAX_IMAGE_PIXELS = SIZE[0] * SIZE[1]
    s = SIZE[0] // 256
    c = s // 2  # centre sample offset inside each cell

    def lum(rgb):
        return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114

    def hd_interior(glyph_sub):  # r6 hd_interior, verbatim logic
        gp = np.repeat(np.repeat(glyph_sub, s, 0), s, 1)
        return ndi.binary_erosion(gp, structure=np.ones((3, 3), bool), iterations=max(1, s // 4), border_value=0)

    def up(t):
        return np.repeat(np.repeat(t, s, 0), s, 1)

    def void_mask(img, glyph_t, ncls, roi):
        """Production mask V (pure; explicit roi so the synthetic controls exercise this exact code; the CLI fixes ROI_B)."""
        x0, y0, x1, y1 = roi
        v = np.zeros(img.shape[:2], bool)
        sub = hd_interior(glyph_t[y0:y1, x0:x1]) & up(ncls[y0:y1, x0:x1] != 0)
        v[y0 * s:y1 * s, x0 * s:x1 * s] = sub & (img[y0 * s:y1 * s, x0 * s:x1 * s, 3] == 0)
        return v

    def apply_c1(img, v, nrgb_up, ncls_up):
        out = img.copy()
        out[v, :3] = nrgb_up[v]
        out[v, 3] = ncls_up[v]
        return out

    def centre_ok(img, nrgb8, ncls):
        cs = img[c::s, c::s]
        return (cs[..., :3] == nrgb8).all(-1) & (cs[..., 3] == ncls)

    def mismatch(img, ncls_up):
        return img[..., 3] != ncls_up

    # ---- synthetic controls on a 4x4-texel toy at s=8 (no files) ----
    ctl = {}
    tg = np.zeros((16, 16), bool); tg[4:12, 6:9] = True               # 3-texel-wide vertical stroke
    tcls = np.where(tg, 255, 0).astype(np.uint8); trgb = np.where(tg[..., None], 248, 0).astype(np.uint8) * np.ones(3, np.uint8)
    timg = np.dstack([up(trgb[..., 0]), up(trgb[..., 1]), up(trgb[..., 2]), up(tcls)]).astype(np.uint8)
    hv = np.repeat(np.repeat(tg, s, 0), s, 1)
    hi = ndi.binary_erosion(hv, structure=np.ones((3, 3), bool), iterations=2, border_value=0)
    centre_px = np.logical_and.outer(np.arange(128) % s == c, np.arange(128) % s == c)
    ys, xs = np.argwhere(hi & ~centre_px)[5]
    timg[ys, xs, 3] = 0                                                   # one interior non-centre void
    edge = np.argwhere(hv & ~hi)[0]; timg[edge[0], edge[1], 3] = 0         # one contour-band void (protected)
    timg[0, 0, :3] = 7                                                    # counter pixel oddity (protected)
    # r2: V for the toy comes from the PRODUCTION void_mask (roi = the whole 16x16-texel toy), not a hand-built mask
    tv = void_mask(timg, tg, tcls, (0, 0, 16, 16))
    ctl["production_mask_matches_rule"] = bool((tv == (hi & (timg[..., 3] == 0))).all())
    ctl["production_mask_excludes_outside_roi"] = not bool(void_mask(timg, tg, tcls, (0, 0, 5, 16)).any())
    fixed = apply_c1(timg, tv, np.stack([up(trgb[..., k]) for k in range(3)], -1), up(tcls))
    ctl["interior_void_filled_with_native"] = bool(tv.sum() == 1 and fixed[ys, xs, 3] == 255 and (fixed[ys, xs, :3] == 248).all())
    ctl["contour_band_void_untouched"] = bool(fixed[edge[0], edge[1], 3] == 0)
    ctl["counter_pixel_untouched"] = bool((fixed[0, 0, :3] == 7).all())
    ctl["only_v_changed"] = bool(((fixed != timg).any(-1) == tv).all())
    cy, cx = 6 * s + c, 7 * s + c   # centre sample of interior cell (6,7)
    ctl["centre_detected_by_sampler"] = bool(hi[cy, cx] and centre_px[cy, cx] and timg[c::s, c::s][6, 7, 3] == 255)
    # r2 direct controls
    cimg = timg.copy(); cimg[cy, cx, 3] = 0                               # injected centre void
    cv = void_mask(cimg, tg, tcls, (0, 0, 16, 16))
    ctl["injected_centre_void_rejected"] = bool(cv[c::s, c::s].any())     # -> BLOCKER "centre void" path
    ok_img = np.dstack([up(trgb[..., 0]), up(trgb[..., 1]), up(trgb[..., 2]), up(tcls)]).astype(np.uint8)
    ctl["clean_toy_all_centres_native"] = bool(centre_ok(ok_img, trgb, tcls).all())
    bad = ok_img.copy(); bad[1 * s + c, 1 * s + c, :3] = 9                # non-native centre OUTSIDE any ROI
    ctl["outside_roi_nonnative_centre_fails_global"] = not bool(centre_ok(bad, trgb, tcls).all())
    t127 = tcls.copy(); t127[tg] = 127
    f127 = apply_c1(timg, tv, np.stack([up(trgb[..., k]) for k in range(3)], -1), up(t127))
    ctl["class127_cell_fills_alpha127"] = bool(f127[ys, xs, 3] == 127)
    ctl["exact_class_delta_equals_V"] = bool(int(mismatch(timg, up(tcls)).sum()) - int(mismatch(fixed, up(tcls)).sum()) ==
                                             int(tv.sum()))
    need(all(ctl.values()), "C1 controls failed", ctl)

    # ---- real data ----
    w = np.frombuffer(wb, "<u2").reshape(256, 64)
    idx = np.zeros((256, 256), np.uint8)
    for i in range(4):
        idx[:, i::4] = (w >> (4 * i)) & 15
    val = np.frombuffer(cb, "<u2")[idx].astype(np.uint16)
    nrgb8 = np.stack([(val & 31) << 3, ((val >> 5) & 31) << 3, ((val >> 10) & 31) << 3], -1).astype(np.uint8)
    ncls = np.where(val == 0, 0, np.where(val & 0x8000, 255, 127)).astype(np.uint8)
    glyph_t = (ncls != 0) & (lum(nrgb8.astype(np.float32)) >= GLYPH_LUM)
    with Image.open(io.BytesIO(nb)) as im:
        need(im.size == SIZE and im.mode == "RGBA", "snap decode mode/size", im.mode)
        src = np.ascontiguousarray(np.asarray(im))
    nrgb_up = np.stack([up(nrgb8[..., k]) for k in range(3)], -1)
    ncls_up = up(ncls)
    v = void_mask(src, glyph_t, ncls, ROI_B)
    nv = int(v.sum())
    cen_before = centre_ok(src, nrgb8, ncls)
    cell_has_void = v.reshape(256, s, 256, s).any((1, 3))
    centre_void = v[c::s, c::s]
    x0, y0, x1, y1 = ROI_B
    roi_cells = np.zeros((256, 256), bool); roi_cells[y0:y1, x0:x1] = True
    res = dict(owner="claude-einhander-ui", job="J-C1V r2 one-ROI stroke-void correction", mode=a.mode,
               tool_sha256=hb(Path(__file__).read_bytes()), versions=got, controls=ctl, key=KEY, roi_b_texels=list(ROI_B),
               pins={k: (str(v_) if isinstance(v_, Path) else v_) for k, v_ in PIN.items()},
               r6_result_sha256=R6_RESULT_SHA256, r6_recorded_voids=r6_v, voids=nv,
               cells_with_voids=int(cell_has_void.sum()), centre_voids=int(centre_void.sum()),
               roi_centres_native_before=int(cen_before[roi_cells].sum()), roi_cells=int(roi_cells.sum()),
               all_centres_native_before=int(cen_before.sum()), alpha_exception="alpha 0 -> native class alpha (127/255) only in V",
               r5="not evaluated; no compositor/appearance claim")
    blockers = []
    if int(centre_void.sum()):
        blockers.append("centre void: a void lies on a native cell centre sample")
    if int(cen_before[roi_cells].sum()) != int(roi_cells.sum()):
        blockers.append("ROI B has centre samples that are not native in the input candidate")
    if not bool(cen_before.all()):
        blockers.append(f"non-native centre: {int((~cen_before).sum())} of 65536 centre samples are not native in the input "
                        "(global G4 contract)")
    if nv != r6_v:
        blockers.append(f"void count {nv} differs from r6 recorded {r6_v}")
    if a.mode == "write" and nv != a.expect_voids:
        blockers.append(f"void count {nv} differs from reviewed dry-run --expect-voids {a.expect_voids}")
    out = apply_c1(src, v, nrgb_up, ncls_up)
    changed = (out != src).any(-1)
    mm_b, mm_a = mismatch(src, ncls_up), mismatch(out, ncls_up)
    gates = {
        "G1_changed_equals_V_and_outside_identical": bool((changed == v).all() and (out[~v] == src[~v]).all()),
        "G2_changed_equal_native": bool((out[v, :3] == nrgb_up[v]).all() and (out[v, 3] == ncls_up[v]).all()),
        "G3_mismatch_after_eq_before_minus_V_no_new": bool(int(mm_a.sum()) == int(mm_b.sum()) - nv and not (mm_a & ~mm_b).any()),
        "G4_centres_exact_equal_and_all_native": bool((out[c::s, c::s] == src[c::s, c::s]).all() and cen_before.all() and
                                                       centre_ok(out, nrgb8, ncls).all()),
        "G5_count_matches_r6": nv == r6_v,
    }
    res.update(gates=gates, mismatch_before=int(mm_b.sum()), mismatch_after=int(mm_a.sum()), changed_pixels=int(changed.sum()),
               contour_band_alpha0_untouched=int(((up(glyph_t) & ~v) & (src[..., 3] == 0) & up(roi_cells)).sum()))
    verdict = "BLOCKED" if blockers else ("PASS" if all(gates.values()) else "FAIL")
    res.update(blockers=blockers, verdict=verdict)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = UI_OUT / "c1-stroke-void" / "runs" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    # review: whole ROI B at 1:1 (fixed window, no data-driven choice): input | proposed | map (V red, contour band green)
    sl = (slice(y0 * s, y1 * s), slice(x0 * s, x1 * s))
    mp = np.zeros(src.shape[:2] + (3,), np.uint8)
    mp[(up(glyph_t) & ~hd_interior_full(glyph_t, hd_interior, ROI_B, s, np))] = (0, 90, 0)
    mp[v] = (255, 0, 0)
    tiles = [("input v5 snap-native a3035801", src), (f"PROPOSED C1 (V only) - verdict {verdict}, not accepted art", out),
             ("map: red = V changed, green = protected contour band", mp)]
    sheet_h = (y1 - y0) * s
    sheet = Image.new("RGB", ((x1 - x0) * s * 3, sheet_h + 16), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    for i, (lab, arr) in enumerate(tiles):
        t = arr[sl]
        rgb = np.where(t[..., 3:4] > 0, t[..., :3], 24).astype(np.uint8) if t.shape[-1] == 4 else t
        sheet.paste(Image.fromarray(rgb), (i * (x1 - x0) * s, 16))
        dr.text((i * (x1 - x0) * s + 4, 2), lab, fill=(255, 255, 0))
    with open(rd / "review_roiB_1x.png", "xb") as fh:
        sheet.save(fh, format="PNG")
    res["review_1x"] = dict(path="review_roiB_1x.png", sha256=hb((rd / "review_roiB_1x.png").read_bytes()))
    if a.mode == "write" and verdict == "PASS":
        buf = io.BytesIO()
        Image.fromarray(out, "RGBA").save(buf, format="PNG")
        with open(rd / "1AD90FC9-02491337.c1.png", "xb") as fh:
            fh.write(buf.getvalue())
        res["output_png"] = dict(path="1AD90FC9-02491337.c1.png", sha256=hb(buf.getvalue()))
    res["seconds"] = round(time.time() - t0, 1)
    with open(rd / "result.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"verdict": verdict, "voids": nv, "blockers": blockers, "gates": gates, "out": str(rd)}))
    return {"PASS": 0, "BLOCKED": 3, "FAIL": 4}[verdict]


def hd_interior_full(glyph_t, hd_interior, roi, s, np):
    """Full-image boolean of the eroded interior inside the ROI (for the review map only)."""
    x0, y0, x1, y1 = roi
    full = np.zeros((256 * s, 256 * s), bool)
    full[y0 * s:y1 * s, x0 * s:x1 * s] = hd_interior(glyph_t[y0:y1, x0:x1])
    return full


def _refusal_receipt(kind, detail):
    """Best-effort exclusive receipt for a refusal or exception; the outer fa5 receipt stays authoritative."""
    try:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        d = UI_OUT / "c1-stroke-void" / "runs"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{stamp}-{kind}.json", "x", encoding="utf-8") as fh:
            fh.write(json.dumps({"verdict": kind.upper(), "detail": str(detail)[:2000], "pid": os.getpid()}, indent=1) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    # exit codes: 0 PASS, 3 BLOCKED, 4 FAIL (gate), 2 REFUSED (pin/precondition CHECK FAILED), 5 EXCEPTION
    try:
        rc = main()
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            _refusal_receipt("refused", e.code)
            sys.exit(2)
        raise
    except Exception as e:  # noqa: BLE001
        print(f"EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr)
        _refusal_receipt("exception", f"{type(e).__name__}: {e}")
        sys.exit(5)
    sys.exit(rc)
