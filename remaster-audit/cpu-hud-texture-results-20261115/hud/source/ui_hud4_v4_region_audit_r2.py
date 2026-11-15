#!/usr/bin/env python3
"""claude-einhander-ui J-H4 r2: MEASURE-ONLY, region-scoped R1/connectivity audit of the 4 existing coherent-v4 HUD files.
Requested by main msg_55b91412 and crash-check msg_95212d5a. NOT RUN by its author. Writes no art.

r2 vs r1 (b540a372, frozen read-only), per root msg_f2d32dfb and msg_c6b1e0ac:
  - Verdict:
    - METRIC_DISAGREE (R1 flag count != centre-alpha cross-check) OVERRIDES any pass.
    - The label is now R1_CONNECTIVITY_PASS / R1_CONNECTIVITY_FAIL / METRIC_DISAGREE. This is NOT a full native-class gate.
    - nonclass_region (alpha outside {0,127,255}) is REPORTED and not part of the pass. The full primary-audit fields are
      reported separately.
  - The verdict is a pure function summarize(img, ncls, flags, s, region). Controls exercise it with injected flags:
    - flag 16 set on a centre whose alpha is native gives METRIC_DISAGREE;
    - a real centre flip gives FAIL, with the cross-check agreeing.
  - Provenance:
    - the executed class_mip.c/.h copies are re-hashed BEFORE compile;
    - the compiled DLL is hashed BEFORE CDLL load;
    - the compile command, stdout, stderr and return code are recorded.
  - Durable failure receipt: the run folder is created FIRST, and an exclusive receipt.json is written in a try/finally
    with phase, error, controls, partial rows and the compile record. On any refusal or exception it keeps the original
    reason. No art is written in any path. A failure never exits 0.

Scope (fixed in code; no CLI widening):
  - 44C16454-72FBA1C5: small numeral strip, native 256x8. Region = the whole strip.
  - 8BA3BB4D-190A55AD / -36D62A31 / -E0AE221F: Hit Gauge on a mixed 256x256 page.
    Region = texels x in [0,64), y in [64,96), from hud-restoration/e2e-coverage.json
    "restored_native_regions": [[0,64,64,96]] and the S45 register "rect [0,64,64,96]". Read as [x0,y0,x1,y1); this axis
    order is an UNKNOWN made explicit.
  - The input is the exact coherent-v4 pack bytes, which root confirmed match the 37c staging copies (msg_d8c9fff2).
  - Every other copy is untouched.
Metric: the same as ui_menu_primary_audit_v4 93e13bb4, with the FROZEN class_mip proto-v2b (c84efa60 / 90e68bdd) compiled
  into the run folder with the pinned clang.
  - Whole-image cm_validate (reported).
  - cm_flags_ex at bound 1e9 (conn-only, flags & (2|4|16)) and at bound 0.5 (s/2 diagnostic).
  - In region: r1_region = cells whose centre pixel floor((i+0.5)s) carries flag 16; conn_region = conn-only pixels.
  - Cross-check: centre alpha != native class.
Native authority: 4bpp words, low nibble first; CLUT 5-bit<<3 RGB; class 0/127/255 from value==0 or the STP bit
  (the same inline decode as r6 / C1). No author imports.
Exit: 0 = all 4 keys measured and the receipt written (per-key verdicts inside; a FAIL verdict is a finding, not an error);
  2 = REFUSED (pin/precondition); 5 = EXCEPTION.
Outputs: <UI_OUT>/hud4-v4-audit/runs/<UTC>/ containing receipt.json (always), result.json (on completion),
  review_<key>_region_1x.png, and the executed class_mip.c/.h/.dll. Written exclusively.
No install, admission, readability, composed or live claim.
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
import io  # noqa: E402
import json  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import zlib  # noqa: E402
from pathlib import Path  # noqa: E402

UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
V4 = Path("C:/github/Einhander/remaster-audit/hud-restoration/candidate-20261112-coherent-v4/pack/einhander-texture-replacements")
STOCK1 = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
STOCK44 = Path("C:/github/REMASTER_STAGING/full-remaster/ui-capture-v2/stock/einhander-texture-replacements")
PROTO = Path("C:/github/Einhander/remaster-audit/claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b")
CLANG = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe")
PINS_FIXED = {
    "class_mip.c": (PROTO / "class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    "class_mip.h": (PROTO / "class_mip.h", "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"),
    "clang.exe": (CLANG, "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85"),
}
W8BA = (STOCK1 / "8BA3BB4D-190A55AD.words.bin", "ecf45868d413de845c7a9ddc002ea935bd1b6f8dd2d0137476a39ca7fe601c0f")
TARGETS = {
    "44C16454-72FBA1C5": dict(
        v4=(V4 / "44C16454-72FBA1C5.png", "f9d459b45d3a6ae1c191b9a2a455da34107081c9077512264c84a0a50ea380d7"),
        words=(STOCK44 / "44C16454-72FBA1C5.words.bin", "267b142a89914066bd3cc4a149365116f6a9429b56677940f6d7bce9fe085198"),
        clut=(STOCK44 / "44C16454-72FBA1C5.clut.bin", "bdb1cab4dc8f0e34c5a3b9382c06bc742a5e05cf9b0a45afbb4cca5e6687cbe3"),
        meta=(STOCK44 / "44C16454-72FBA1C5.source.json", "b546dfef524558407239a38270c7fd90a5aa3307612d69387794a7bd187d91f4"),
        geom=(64, 8), size=(4096, 128), region=(0, 0, 256, 8), role="small numeral strip (whole)"),
    "8BA3BB4D-190A55AD": dict(
        v4=(V4 / "8BA3BB4D-190A55AD.png", "9511a22f75360eab0bda10888422b7ff8c6ac825fa270c63f885e8f56afea0b5"),
        words=W8BA,
        clut=(STOCK1 / "8BA3BB4D-190A55AD.clut.bin", "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"),
        meta=(STOCK1 / "8BA3BB4D-190A55AD.source.json", "5e2bfe4c7c4000f120b85cfe704ab215545c231eada0276249087d39a4957a62"),
        geom=(64, 256), size=(4096, 4096), region=(0, 64, 64, 96), role="Hit Gauge rect on mixed page"),
    "8BA3BB4D-36D62A31": dict(
        v4=(V4 / "8BA3BB4D-36D62A31.png", "4255b3e5102cb78b26c06c6618b9fdff9203a23f57fde6e8bca67f6f6bbef3c1"),
        words=W8BA,
        clut=(STOCK1 / "8BA3BB4D-36D62A31.clut.bin", "1e8ea3c6cd7ef8939bebb39dc90af3a304318740c518f692f22fc1d0b3d8acd9"),
        meta=(STOCK1 / "8BA3BB4D-36D62A31.source.json", "5a194ff7ea7ad64eea9f89b4de6acca905ac52dacf566195c48a3cdb3788ff2b"),
        geom=(64, 256), size=(4096, 4096), region=(0, 64, 64, 96), role="Hit Gauge rect on mixed page"),
    "8BA3BB4D-E0AE221F": dict(
        v4=(V4 / "8BA3BB4D-E0AE221F.png", "c82058bfb3a14257d46a39355692560f8cede710f1163b7d3c565fe4bf04afb9"),
        words=W8BA,
        clut=(STOCK1 / "8BA3BB4D-E0AE221F.clut.bin", "2c2370edf6f6dc6a9835ca94b43cd54b17e55ee9496bcc47d400eb718f9db501"),
        meta=(STOCK1 / "8BA3BB4D-E0AE221F.source.json", "f47cd89c124a7f3ce9faf5d72247486f6d509cb132f5f602312c21dd873f39bf"),
        geom=(64, 256), size=(4096, 4096), region=(0, 64, 64, 96), role="Hit Gauge rect on mixed page"),
}
VERSIONS = {"python": "3.14.5", "numpy": "2.5.2", "pillow": "12.3.0"}
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")
CONN_BITS = 2 | 4 | 16
STATE = {"phase": "start", "controls": None, "rows": {}, "compile": None, "artifacts": {}, "error": None}


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def need(cond, *msg):
    if not cond:
        raise SystemExit("CHECK FAILED: " + " | ".join(str(m) for m in msg))


def hb(b):
    return hashlib.sha256(b).hexdigest()


def ihdr(b):
    need(len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR", "not a PNG with IHDR first")
    return tuple(struct.unpack(">II", b[16:24]))


def read_pinned(p, want, what):
    b = Path(p).read_bytes()
    need(hb(b) == want, what, "sha256", p)
    return b


def summarize(img, ncls, conn_fl, s2_fl, s, region, np):
    """PURE verdict function (no library calls). Used identically by the controls and by the real keys."""
    th, tw = ncls.shape
    H, W = img.shape[:2]
    x0, y0, x1, y1 = region
    rpx = np.zeros((H, W), bool); rpx[y0 * s:y1 * s, x0 * s:x1 * s] = True
    rcell = np.zeros((th, tw), bool); rcell[y0:y1, x0:x1] = True
    c = s // 2
    centre_r1 = (conn_fl[c::s, c::s] & 16) != 0
    conn_px = (conn_fl & CONN_BITS) != 0
    s2_px = (s2_fl & (2 | 4 | 8 | 16)) != 0
    xcheck = img[c::s, c::s, 3] != ncls
    out = dict(
        r1_region=int((centre_r1 & rcell).sum()), conn_region=int((conn_px & rpx).sum()),
        s2_region=int((s2_px & rpx).sum()),
        nonclass_region=int((~np.isin(img[..., 3], (0, 127, 255)) & rpx).sum()),
        r1_outside=int((centre_r1 & ~rcell).sum()), conn_outside=int((conn_px & ~rpx).sum()),
        centre_alpha_mismatch_region=int((xcheck & rcell).sum()), region_cells=int(rcell.sum()), region_px=int(rpx.sum()))
    out["metric_agree"] = out["r1_region"] == out["centre_alpha_mismatch_region"]
    if not out["metric_agree"]:
        out["region_verdict"] = "METRIC_DISAGREE"            # overrides any pass
    elif out["r1_region"] == 0 and out["conn_region"] == 0:
        out["region_verdict"] = "R1_CONNECTIVITY_PASS"       # not a full native-class gate (nonclass reported only)
    else:
        out["region_verdict"] = "R1_CONNECTIVITY_FAIL"
    return out


def write_excl(path, data):
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(data)


def main(rd):
    t0 = time.time()
    STATE["phase"] = "pins"
    fixed = {k: read_pinned(p, h, k) for k, (p, h) in PINS_FIXED.items()}
    blobs = {}
    for key, T in TARGETS.items():
        vb = read_pinned(*T["v4"], key + " v4")
        wb = read_pinned(*T["words"], key + " words")
        cb = read_pinned(*T["clut"], key + " clut")
        mb = read_pinned(*T["meta"], key + " meta")
        need(ihdr(vb) == T["size"], key, "v4 IHDR", ihdr(vb), T["size"])
        need("%08X" % zlib.crc32(wb) == key[:8] and "%08X" % zlib.crc32(cb) == key[9:], key, "words/CLUT CRC != key")
        need(len(cb) == 32 and len(wb) == T["geom"][0] * T["geom"][1] * 2, key, "words/CLUT length")
        meta = json.loads(mb)
        need([meta["width_words"], meta["height"], meta["depth"]] == [T["geom"][0], T["geom"][1], 0], key, "meta geometry")
        tw, th = T["geom"][0] * 4, T["geom"][1]
        x0, y0, x1, y1 = T["region"]
        need(0 <= x0 < x1 <= tw and 0 <= y0 < y1 <= th, key, "region bounds")
        s = T["size"][0] // tw
        need(s * tw == T["size"][0] and s * th == T["size"][1] and s % 2 == 0, key, "non-integer/anisotropic/odd scale")
        blobs[key] = (vb, wb, cb, s)
    STATE["phase"] = "libraries"
    import numpy as np
    import PIL
    from PIL import Image, ImageDraw
    got = {"python": sys.version.split()[0], "numpy": np.__version__, "pillow": PIL.__version__}
    STATE["versions"] = got
    need(got == VERSIONS, "library versions differ", got, VERSIONS)
    Image.MAX_IMAGE_PIXELS = 4096 * 4096
    STATE["phase"] = "compile"
    for name in ("class_mip.c", "class_mip.h"):
        with open(rd / name, "xb") as fh:
            fh.write(fixed[name])
        back = hb((rd / name).read_bytes())
        STATE["artifacts"][name] = back
        need(back == PINS_FIXED[name][1], "executed copy differs from pin", name)
    cmd = [str(CLANG), "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")]
    c = subprocess.run(cmd, capture_output=True, text=True, timeout=60, creationflags=0x4000 | 0x08000000)
    STATE["compile"] = dict(argv=cmd, rc=c.returncode, stdout=c.stdout[-2000:], stderr=c.stderr[-2000:])
    need(c.returncode == 0, "class_mip compile failed", c.returncode)
    STATE["artifacts"]["class_mip.dll"] = hb((rd / "class_mip.dll").read_bytes())   # hashed BEFORE load
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]

    def library_flags(img, ncls, s):
        img = np.ascontiguousarray(img)
        ncls = np.ascontiguousarray(ncls.astype(np.uint8))
        th, tw = ncls.shape
        H, W = img.shape[:2]
        rep = CmReport()
        rc = lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, ctypes.byref(rep))
        need(rc == 0, "cm_validate rc", rc)
        whole = {n: int(getattr(rep, n)) for n in RF}
        fls = []
        for bound in (1.0e9, 0.5):
            fl = np.zeros((H, W), np.uint8)
            rc = lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, bound, 0, fl.ctypes.data)
            need(rc == 0, "cm_flags_ex rc", rc, bound)
            fls.append(fl)
        whole["primary_pass_whole_page"] = whole["r1_centre_bad"] == 0 and int(((fls[0] & CONN_BITS) != 0).sum()) == 0
        return whole, fls[0], fls[1]

    def up(t, s):
        return np.repeat(np.repeat(t, s, 0), s, 1)

    STATE["phase"] = "controls"
    ctl = {}
    s_t = 16
    tc = np.zeros((8, 8), np.uint8); tc[2:6, 1:7] = 255
    clean = np.zeros((8 * s_t, 8 * s_t, 4), np.uint8); clean[..., :3] = 200; clean[..., 3] = up(tc, s_t)
    _, cf, sf = library_flags(clean, tc, s_t)
    m = summarize(clean, tc, cf, sf, s_t, (0, 0, 8, 4), np)
    ctl["clean_exact_class_is_pass"] = m["region_verdict"] == "R1_CONNECTIVITY_PASS" and m["r1_outside"] == 0
    bad_in = clean.copy(); bad_in[3 * s_t + 8, 2 * s_t + 8, 3] = 0      # real centre flip, cell (3,2), inside rows 0..3
    _, bf, bs = library_flags(bad_in, tc, s_t)
    m = summarize(bad_in, tc, bf, bs, s_t, (0, 0, 8, 4), np)
    ctl["real_centre_flip_inside_is_fail_and_agrees"] = (m["region_verdict"] == "R1_CONNECTIVITY_FAIL" and m["r1_region"] == 1
                                                         and m["metric_agree"] and m["conn_region"] >= 1)
    m = summarize(bad_in, tc, bf, bs, s_t, (0, 4, 8, 8), np)
    ctl["half_open_region_excludes_row_above"] = m["r1_region"] == 0 and m["r1_outside"] == 1 and m["region_verdict"] == "R1_CONNECTIVITY_PASS"
    inj = cf.copy(); inj[2 * s_t + 8, 3 * s_t + 8] |= 16               # injected R1 flag on a centre whose alpha IS native
    m = summarize(clean, tc, inj, sf, s_t, (0, 0, 8, 4), np)
    ctl["injected_flag_without_alpha_error_is_metric_disagree"] = (m["region_verdict"] == "METRIC_DISAGREE"
                                                                    and m["r1_region"] == 1 and m["centre_alpha_mismatch_region"] == 0)
    m = summarize(bad_in, tc, cf, sf, s_t, (0, 0, 8, 4), np)          # alpha error but its flag withheld
    ctl["alpha_error_without_flag_is_metric_disagree"] = (m["region_verdict"] == "METRIC_DISAGREE"
                                                          and m["r1_region"] == 0 and m["centre_alpha_mismatch_region"] == 1)
    nc = clean.copy(); nc[2 * s_t + 3, 3 * s_t + 3, 3] = 200             # non-class alpha off-centre: reported only
    m = summarize(nc, tc, cf, sf, s_t, (0, 0, 8, 4), np)
    ctl["nonclass_reported_not_gated"] = m["nonclass_region"] == 1
    STATE["controls"] = ctl
    need(all(ctl.values()), "controls failed", ctl)

    STATE["phase"] = "measure"
    for key, T in TARGETS.items():
        vb, wb, cb, s = blobs[key]
        gw, gh = T["geom"]
        w = np.frombuffer(wb, "<u2").reshape(gh, gw)
        idx = np.zeros((gh, gw * 4), np.uint8)
        for i in range(4):
            idx[:, i::4] = (w >> (4 * i)) & 15
        val = np.frombuffer(cb, "<u2")[idx].astype(np.uint16)
        nrgb8 = np.stack([(val & 31) << 3, ((val >> 5) & 31) << 3, ((val >> 10) & 31) << 3], -1).astype(np.uint8)
        ncls = np.where(val == 0, 0, np.where(val & 0x8000, 255, 127)).astype(np.uint8)
        with Image.open(io.BytesIO(vb)) as im:
            need(im.size == T["size"], key, "decoded size")
            mode = im.mode
            img = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
        whole, cf, sf = library_flags(img, ncls, s)
        res = summarize(img, ncls, cf, sf, s, T["region"], np)
        res.update(key=key, role=T["role"], scale=s, png_mode=mode, region_texels=list(T["region"]),
                   whole_page_report_not_judged=whole,
                   pins={k: [str(T[k][0]), T[k][1]] for k in ("v4", "words", "clut", "meta")})
        x0, y0, x1, y1 = T["region"]
        sl = (slice(y0 * s, y1 * s), slice(x0 * s, x1 * s))
        nat = np.dstack([up(nrgb8[..., k], s) for k in range(3)])[sl]
        natv = np.where(up(ncls, s)[sl][..., None] > 0, nat, 24).astype(np.uint8)
        v4v = np.where(img[sl][..., 3:4] > 0, img[sl][..., :3], 24).astype(np.uint8)
        fm = np.zeros(v4v.shape, np.uint8)
        f = cf[sl]
        fm[(f & 16) != 0] = (255, 0, 0); fm[(f & 4) != 0] = (255, 160, 0); fm[(f & 2) != 0] = (255, 255, 0)
        tiles = [("native (nearest)", natv), ("coherent-v4 1:1", v4v), ("flags: red R1, orange island, yellow displaced", fm)]
        hgt, wid = v4v.shape[:2]
        sheet = Image.new("RGB", (wid * 3, hgt + 16), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for i, (lab, arr) in enumerate(tiles):
            sheet.paste(Image.fromarray(arr), (i * wid, 16))
            dr.text((i * wid + 4, 2), f"{lab} | {key} {res['region_verdict']}", fill=(255, 255, 0))
        fn = f"review_{key}_region_1x.png"
        with open(rd / fn, "xb") as fh:
            sheet.save(fh, format="PNG")
        res["review_1x"] = dict(path=fn, sha256=hb((rd / fn).read_bytes()))
        STATE["rows"][key] = res
        del img, cf, sf
    STATE["phase"] = "result"
    out = dict(owner="claude-einhander-ui", job="J-H4 r2 region-scoped R1/connectivity MEASURE of 4 coherent-v4 HUD files",
               tool_sha256=hb(Path(__file__).read_bytes()), versions=got, controls=ctl,
               policy=("region verdict: METRIC_DISAGREE overrides; R1_CONNECTIVITY_PASS iff r1_region == 0 and conn_region == 0 "
                       "(conn = cm_flags_ex bound 1e9, flags & (2|4|16)); nonclass_region reported only; NOT a full native-class "
                       "gate; whole-page primary fields reported, not judged"),
               class_mip_pins={k: v[1] for k, v in PINS_FIXED.items()}, executed_artifacts=STATE["artifacts"],
               compile=STATE["compile"], rows=STATE["rows"],
               summary={k: v["region_verdict"] for k, v in STATE["rows"].items()},
               not_claimed="no art written; no install, admission, readability, composed or live acceptance",
               seconds=round(time.time() - t0, 1))
    write_excl(rd / "result.json", json.dumps(out, indent=1) + "\n")
    STATE["phase"] = "done"
    print(json.dumps({"summary": out["summary"], "out": str(rd)}))
    return 0


if __name__ == "__main__":
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RD = UI_OUT / "hud4-v4-audit" / "runs" / stamp
    RD.mkdir(parents=True, exist_ok=False)                 # created FIRST so every failure keeps a durable receipt
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
            write_excl(RD / "receipt.json", json.dumps(STATE, indent=1, default=str) + "\n")
        except Exception as e:  # noqa: BLE001
            print(f"receipt write failed: {e}", file=sys.stderr)
            rc = rc or 5
        if STATE["error"]:
            print(json.dumps(STATE["error"])[:2000], file=sys.stderr)
    sys.exit(rc)
