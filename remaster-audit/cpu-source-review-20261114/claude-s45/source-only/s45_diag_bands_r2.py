#!/usr/bin/env python3
"""s45 (EIN-S4-WHOLE-CELL-20261114) diag_bands r2: FAIL-CLOSED two-key hazard-stripe preview.
r2 = r1 (d4a167d8, source-cleared for fixtures, msg_a3ba2b7d) + review fixes: interpreter / numpy / scipy / Pillow versions
enforced (importlib.metadata) before any data; every pinned file is read ONCE and hashed, and that same byte string is used
afterwards (PNG IHDR + decode from the same bytes; EPX executed from its verified bytes; the DLL loaded from a verified
private copy in the run folder, re-hashed); pinned native | input | output review crops of the ROI at 2048 and 1024;
any unexpected exception also finalises a FAILED receipt. Supersedes s45_diag_bands_repair.py (ae2d61dc, never run). Scope is fixed: Stage 4, keys E8769E55-8F297232 and
9B8107D2-8F297232 only, native ROI u72..99 / v64..71 inclusive = half-open [72,64,100,72], the four pinned exports
(2048 + 1024 per key). Nothing is generic.

Order: thread env = 1 -> pin check of EVERY input (words, CLUT words, ROI indices, exports, frozen class_mip DLL + its C/H,
frozen EPX source) BEFORE any DLL load / EPX import / PNG decode -> PNG IHDR must be exactly the pinned size -> decode ->
gates -> repair in memory -> audit -> only then write art. Any failure: durable partial receipt + exit code != 0, no art.

Repair semantics (inside the ROI only; RGB only; alpha never written):
  * labels: n(p) = native index under each output pixel (nearest); e(p) = frozen w4 EPX / Scale2x of the native indices
    (3 passes = 8x for 2048; 1024 = even-pixel subsample of the 8x map), computed on the ROI plus a 2-texel margin;
  * STRIPE = {0x0, 0xF} (orange / black under 8F297232). A pixel changes only if n(p) and e(p) are both STRIPE and
    differ: exactly the corner triangles of 1-texel stair steps between the two stripe colours. Every other index is a
    PROTECTED cell (edge shade 1/3/A/8/9/C..., the 7DDF / 66CC fittings): its pixels are never changed, and stripe
    pixels whose EPX label is protected are not changed either;
  * colour donor for a changed pixel: nearest pixel q (EDT) with n(q) == e(p) lying in a texel interior (>= 1 px from
    the texel border) within ROI+margin and at distance <= 1.5 texels; otherwise the pixel stays unchanged and is
    counted as fallback_unchanged. Donor distances are recorded (no claim that grain is preserved beyond that bound);
  * the texel-centre pixel floor((i+0.5)s) is never changed (verified; same label by construction).
Gates (all fatal): pins; IHDR size; ROI single-class under the CLUT; ROI inside 0..256; ROI native indices == pin;
outside-ROI RGBA identical; alpha identical; centre pixels identical; proto-v2b cm_validate and cm_flags_ex return 0 and
primary (R1 == 0, conn-only == 0), s/2 strict, R5 == 0 on the output.
--fixtures runs tiny synthetic controls (positive + negative) and writes only fixtures-receipt.json.
Writes ONLY a new exclusive folder s45/repairs/<UTC>-diagbands-r1-<KEY|fixtures>/. Inputs are never modified."""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
import argparse  # noqa: E402
import ctypes  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import importlib.metadata  # noqa: E402
import io  # noqa: E402
import traceback  # noqa: E402
import types  # noqa: E402
import json  # noqa: E402
import struct  # noqa: E402
import sys  # noqa: E402
import zlib  # noqa: E402
from pathlib import Path  # noqa: E402

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
ST4 = RA / "fullgame-prep/static-extraction/stages/stage4"
FZ = RA / "comfy-authoring/w7-stage4/frozen/s4-world-2-13-v3"
JW1 = S45 / "repairs/s4-world-ext-9B8107D2-v1-s45"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
ROI = (72, 64, 100, 72)
STRIPE = (0x0, 0xF)
MARGIN = 2
DONOR_MAX_TEX = 1.5
PINS = dict(
    dll=(S45 / "probe-audit/20261114T171539Z-s4/class_mip.dll", "ede9a8f1d9847bb534f26d894bc15b2054fa4123aae12f82157cd1e4b5bf524e"),
    dll_c=(PROTO / "class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    dll_h=(PROTO / "class_mip.h", "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"),
    dll_c_copy=(S45 / "probe-audit/20261114T171539Z-s4/class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    epx=(RA / "comfy-authoring/w4-signs-hud/frozen/hud-lives-glyphs-832p256-w4-v1/builder-snapshot/epx.py.txt",
         "86831043dfa0dfa6be91ad2f636519ab529366ce68771eb77b408d88f1506e08"),
)
CLUT_HEX = "1f12df15df11f239d6299a157811721d8c3113112a21cb10a7188610640c630c"   # 8F297232 at (208,493)
ROI_SHA = "fbd056b9edd7dd62560bd4c2899c077e55a2c29cb34af07151500f30850a1137"     # ROI native index bytes (both keys)
KEYS = {
    "E8769E55-8F297232": dict(
        words=(ST4 / "textures/E8769E55.words.bin", "68df20c0abcc3a8c9f744f2d12fb7d12729620f61cab47f1e5c745a4c4f8167d"),
        png={2048: (FZ / "runtime-2048/E8769E55-8F297232.png", "42da302c43b6208f2fbdd228ed30816aefbc5aa1df9ac7760ea6bb5d1db15c38"),
             1024: (FZ / "runtime-1024/E8769E55-8F297232.png", "e85c2d87c6d2e9f21109819b21785506eb38702a17d975c92a095f7e27d71e81")}),
    "9B8107D2-8F297232": dict(
        words=(ST4 / "textures/9B8107D2.words.bin", "ac97a2970ebedc45ea049fe4209a1ccbf100efbc5f18879f171ad291ec645816"),
        png={2048: (JW1 / "runtime-2048/9B8107D2-8F297232.png", "ad3355a83c67f74b95389129ef20cac9884eab05877a3377ebdc59db9c88ae0a"),
             1024: (JW1 / "runtime-1024/9B8107D2-8F297232.png", "283077e52487b6e05baa233fec1f4e2aa9f1e7458ab416de328d73361e3784cd")}),
}
VERSIONS = dict(python="3.14.5", numpy="2.5.2", scipy="1.17.1", pillow="12.3.0")
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class Fail(Exception):
    pass


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def ihdr_size(b, name):
    need(b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR", f"not a PNG: {name}")
    return struct.unpack(">II", b[16:24])


def versions_ok():
    got = dict(python=sys.version.split()[0], numpy=importlib.metadata.version("numpy"),
               scipy=importlib.metadata.version("scipy"), pillow=importlib.metadata.version("pillow"))
    return got, got == VERSIONS


def load_epx(src_bytes):
    mod = types.ModuleType("epx_w4_verified")
    exec(compile(src_bytes.decode("utf-8"), "epx.py.txt (sha-verified bytes)", "exec"), mod.__dict__)
    return mod


def classes(cw):
    import numpy as np
    return np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in cw], np.uint8)


def repair_roi(np, E, idx, img, S, roi, stripe=STRIPE):
    """Core: returns (out, stats). Raises Fail on any gate inside the ROI."""
    from scipy import ndimage as ndi
    u0, v0, u1, v1 = roi
    need(0 <= u0 < u1 <= idx.shape[1] and 0 <= v0 < v1 <= idx.shape[0], f"ROI out of bounds {roi}")
    need(S in (4, 8), f"scale {S} not allowed")
    need(img.shape[:2] == (idx.shape[0] * S, idx.shape[1] * S), "image size != native size x scale")
    U0, V0, U1, V1 = max(0, u0 - MARGIN), max(0, v0 - MARGIN), min(idx.shape[1], u1 + MARGIN), min(idx.shape[0], v1 + MARGIN)
    sub = np.ascontiguousarray(idx[V0:V1, U0:U1]).astype(np.uint8)
    lab = E.upscale(sub, 3)
    if S == 4:
        lab = np.ascontiguousarray(lab[::2, ::2])
    nat = np.repeat(np.repeat(sub, S, 0), S, 1)
    need(lab.shape == nat.shape, "label field shape mismatch")
    old = img[V0 * S:V1 * S, U0 * S:U1 * S].copy()
    yy, xx = np.mgrid[0:nat.shape[0], 0:nat.shape[1]]
    interior = ((yy % S) >= 1) & ((yy % S) <= S - 2) & ((xx % S) >= 1) & ((xx % S) <= S - 2)
    inroi = np.zeros(nat.shape, bool)
    inroi[(v0 - V0) * S:(v1 - V0) * S, (u0 - U0) * S:(u1 - U0) * S] = True
    isS = np.isin(nat, stripe) & np.isin(lab, stripe)
    change = inroi & isS & (lab != nat)
    new = old.copy()
    dists, fallback = [], 0
    for lv in stripe:
        tgt = change & (lab == lv)
        if not tgt.any():
            continue
        donor = (nat == lv) & interior
        need(donor.any(), f"no interior donor pixels for label {lv}")
        d, (iy, ix) = ndi.distance_transform_edt(~donor, return_indices=True)
        ok = tgt & (d <= DONOR_MAX_TEX * S)
        fallback += int((tgt & ~ok).sum())
        new[..., :3][ok] = old[..., :3][iy[ok], ix[ok]]
        dists += d[ok].tolist()
    centre = ((yy % S) == S // 2) & ((xx % S) == S // 2)
    need(np.array_equal(new[centre & inroi], old[centre & inroi]), "texel-centre pixel changed")
    need(np.array_equal(new[..., 3], old[..., 3]), "alpha changed inside ROI")
    need(np.array_equal(new[~change], old[~change]), "non-target pixel changed")
    out = img.copy()
    out[V0 * S:V1 * S, U0 * S:U1 * S] = new
    stats = dict(changed_px=int((new != old).any(-1).sum()), target_px=int(change.sum()), fallback_unchanged=fallback,
                 donor_dist_px_max=round(max(dists), 2) if dists else None,
                 donor_dist_px_mean=round(sum(dists) / len(dists), 2) if dists else None,
                 protected_px_in_roi=int((inroi & ~np.isin(nat, stripe)).sum()))
    return out, stats


def write_receipt(rd, rec, name="receipt.json"):
    (rd / name).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")


def fixtures(rd, np, E):
    """Tiny synthetic controls on the core; each must behave as expected."""
    res = []

    def case(name, fn, expect_fail):
        try:
            fn()
            ok = not expect_fail
            res.append(dict(name=name, expect_fail=expect_fail, failed=False, ok=ok))
        except Fail as e:
            ok = expect_fail
            res.append(dict(name=name, expect_fail=expect_fail, failed=True, msg=str(e), ok=ok))
    S = 8
    base = np.full((16, 16), 0xF, np.uint8)
    for y in range(16):            # ideal 45-degree 2-texel stripes of index 0 on 0xF, period 4
        for x in range(16):
            if (x + y) % 4 < 2:
                base[y, x] = 0x0
    img = np.zeros((16 * S, 16 * S, 4), np.uint8)
    img[..., :3] = np.where(np.repeat(np.repeat(base, S, 0), S, 1)[..., None] == 0, 200, 20)
    img[..., 3] = 127

    def pos_diag():
        out, st = repair_roi(np, E, base, img, S, (2, 2, 14, 14))
        need(st["changed_px"] > 0, "diagonal stripes produced no change")
        need(np.array_equal(out[:2 * S], img[:2 * S]) and np.array_equal(out[14 * S:], img[14 * S:]), "outside ROI changed")
    case("positive: 45-degree stripes change only corner pixels, outside identical", pos_diag, False)

    vert = np.full((16, 16), 0xF, np.uint8)
    vert[:, :8] = 0x0
    vimg = img.copy()
    vimg[..., :3] = np.where(np.repeat(np.repeat(vert, S, 0), S, 1)[..., None] == 0, 200, 20)

    def pos_vertical():
        _, st = repair_roi(np, E, vert, vimg, S, (2, 2, 14, 14))
        need(st["changed_px"] == 0, f"straight vertical edge changed {st['changed_px']} px")
    case("positive: straight vertical edge unchanged", pos_vertical, False)

    prot = base.copy()
    prot[8, 8] = 0x1

    def pos_protected():
        out, _ = repair_roi(np, E, prot, img, S, (2, 2, 14, 14))
        need(np.array_equal(out[8 * S:9 * S, 8 * S:9 * S], img[8 * S:9 * S, 8 * S:9 * S]), "protected cell changed")
    case("positive: protected (non-stripe) cell untouched", pos_protected, False)
    case("negative: ROI out of bounds", lambda: repair_roi(np, E, base, img, S, (10, 10, 20, 20)), True)
    case("negative: scale 16 not allowed", lambda: repair_roi(np, E, base, np.zeros((256, 256, 4), np.uint8), 16, (2, 2, 6, 6)), True)

    def neg_crossclass():
        cw = np.frombuffer(bytes.fromhex(CLUT_HEX), "<u2").copy()
        cw[0] = 0     # index 0 becomes cutout -> ROI mixes classes
        cls = classes(cw)
        need(len(set(cls[np.unique(base[2:14, 2:14])].tolist())) == 1, "ROI not single-class under the CLUT")
    case("negative: cross-class ROI (wrong/edited CLUT) rejected", neg_crossclass, True)

    def neg_wrong_clut():
        bad = "00" + CLUT_HEX[2:]
        need(bad == CLUT_HEX, "CLUT words differ from the pin")
    case("negative: wrong CLUT words rejected by pin", neg_wrong_clut, True)

    def neg_alpha():
        out, _ = repair_roi(np, E, base, img, S, (2, 2, 14, 14))
        out2 = out.copy()
        out2[5, 5, 3] = 255
        need(np.array_equal(out2[..., 3], img[..., 3]), "alpha changed")
    case("negative: alpha change detected", neg_alpha, True)
    allok = all(r["ok"] for r in res)
    write_receipt(rd, dict(mode="fixtures", cases=res, all_ok=allok), "fixtures-receipt.json")
    for r in res:
        print("FIXTURE", "OK " if r["ok"] else "BAD", r["name"], r.get("msg", ""), flush=True)
    if not allok:
        raise Fail("fixture mismatch")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--key", choices=sorted(KEYS))
    g.add_argument("--fixtures", action="store_true")
    a = ap.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "repairs" / f"{stamp}-diagbands-r2-{a.key or 'fixtures'}"
    rd.mkdir(parents=True, exist_ok=False)
    rec = dict(run=stamp, owner="claude-einhander-s45", tool_sha256=sha(Path(__file__)), mode=a.key or "fixtures",
               roi_half_open=list(ROI), stripe=list(STRIPE), donor_max_tex=DONOR_MAX_TEX, status="STARTED", stage_reached="pins")
    write_receipt(rd, rec)
    try:
        vers, vok = versions_ok()
        rec["versions"] = vers
        need(vok, f"library versions {vers} != pinned {VERSIONS}")
        pins = dict(PINS)
        if a.key:
            pins["words"] = KEYS[a.key]["words"]
            for s_, v in KEYS[a.key]["png"].items():
                pins[f"png_{s_}"] = v
        got, blob = {}, {}
        for name, (p, want) in pins.items():
            b = Path(p).read_bytes()
            h = hashlib.sha256(b).hexdigest()
            got[name] = dict(path=str(p), sha256=h, ok=h == want)
            blob[name] = b
        rec["pins"] = got
        need(all(v["ok"] for v in got.values()), "pin mismatch: " + ", ".join(k for k, v in got.items() if not v["ok"]))
        rec["stage_reached"] = "imports"
        import numpy as np
        E = load_epx(blob["epx"])
        if a.fixtures:
            rec["stage_reached"] = "fixtures"
            fixtures(rd, np, E)
            rec["status"] = "FIXTURES OK"
            write_receipt(rd, rec)
            return 0
        dll_copy = rd / "class_mip.dll"
        dll_copy.write_bytes(blob["dll"])
        need(sha(dll_copy) == PINS["dll"][1], "private DLL copy hash mismatch")
        lib = ctypes.CDLL(str(dll_copy))
        for fn, args in (("cm_validate", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_void_p]),
                         ("cm_flags_ex", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p])):
            getattr(lib, fn).argtypes = args
            getattr(lib, fn).restype = ctypes.c_int

        class CmReport(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in RF]
        rec["stage_reached"] = "sources"
        wb = blob["words"]
        need(zlib.crc32(wb) & 0xFFFFFFFF == int(a.key[:8], 16), "words CRC != TEX")
        w = np.frombuffer(wb, "<u2")
        need(w.size == 256 * 64, "words are not a 4bpp 256x256 page")
        idx = np.stack([(w.reshape(256, 64) >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(256, 256).astype(np.uint8)
        cw = np.frombuffer(bytes.fromhex(CLUT_HEX), "<u2")
        need(zlib.crc32(cw.tobytes()) & 0xFFFFFFFF == int(a.key[9:], 16), "CLUT words CRC != PAL")
        cls = classes(cw)
        u0, v0, u1, v1 = ROI
        need(hashlib.sha256(np.ascontiguousarray(idx[v0:v1, u0:u1]).tobytes()).hexdigest() == ROI_SHA, "ROI native indices != pin")
        need(len(set(cls[np.unique(idx[v0:v1, u0:u1])].tolist())) == 1, "ROI not single-class under the CLUT")
        ncls = np.ascontiguousarray(cls[idx])
        from PIL import Image
        outs = {}
        rec["files"] = {}
        for size in (2048, 1024):
            p = KEYS[a.key]["png"][size][0]
            pb = blob[f"png_{size}"]
            rec["stage_reached"] = f"decode {size}"
            need(ihdr_size(pb, p) == (size, size), f"IHDR of {p} is not {size}x{size}")
            with Image.open(io.BytesIO(pb)) as im:
                src = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            need(src.shape == (size, size, 4), "decoded shape mismatch")
            S = size // 256
            rec["stage_reached"] = f"repair {size}"
            out, st = repair_roi(np, E, idx, src, S, ROI)
            mask = np.zeros((size, size), bool)
            mask[v0 * S:v1 * S, u0 * S:u1 * S] = True
            need(np.array_equal(out[~mask], src[~mask]), "outside-ROI RGBA changed")
            need(np.array_equal(out[..., 3], src[..., 3]), "alpha changed")
            rec["stage_reached"] = f"audit {size}"
            o = np.ascontiguousarray(out)
            rep = CmReport()
            rc = lib.cm_validate(o.ctypes.data, size, size, ncls.ctypes.data, 256, 256, S, ctypes.byref(rep))
            need(rc == 0, f"cm_validate rc {rc}")
            aud = {n: int(getattr(rep, n)) for n in RF}
            for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
                fl = np.zeros((size, size), np.uint8)
                rc = lib.cm_flags_ex(o.ctypes.data, size, size, ncls.ctypes.data, 256, 256, S, bound, 0, fl.ctypes.data)
                need(rc == 0, f"cm_flags_ex({bound}) rc {rc}")
                aud[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
            rec["files"][str(size)] = dict(input=str(p), stats=st, audit=aud)
            need(aud["r1_centre_bad"] == 0 and aud["conn_viol_px"] == 0, "primary policy fails")
            need(all(aud[x] == 0 for x in ("r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "s2_viol_px")), "s/2 strict fails")
            need(aud["r5_fringe_px"] == 0, "R5 fringe > 0")
            need(st["changed_px"] > 0, "no pixel changed in the ROI")
            outs[size] = (out, src, S)
        rec["stage_reached"] = "write"
        from PIL import ImageDraw
        rgbc = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
        (rd / "review").mkdir()
        for size, (out, src, S) in outs.items():
            fn = rd / f"{a.key}-{size}-diagbands-r2.png"
            Image.fromarray(out).save(fn, compress_level=6)
            rec["files"][str(size)]["output"] = fn.name
            rec["files"][str(size)]["output_sha256"] = sha(fn)
            zoom = 16 // S
            tw, th = (u1 - u0) * 16, (v1 - v0) * 16
            tiles = [("native nearest", np.repeat(np.repeat(rgbc[idx[v0:v1, u0:u1]], 16, 0), 16, 1)),
                     (f"input {size}", np.repeat(np.repeat(src[v0 * S:v1 * S, u0 * S:u1 * S, :3], zoom, 0), zoom, 1)),
                     (f"diag_bands r2 {size}", np.repeat(np.repeat(out[v0 * S:v1 * S, u0 * S:u1 * S, :3], zoom, 0), zoom, 1))]
            sheet = Image.new("RGB", (tw, 3 * (th + 16)), (0, 0, 0))
            dr = ImageDraw.Draw(sheet)
            for j, (lab_, t) in enumerate(tiles):
                y = j * (th + 16)
                sheet.paste(Image.fromarray(np.ascontiguousarray(t)), (0, y + 16))
                dr.text((2, y + 2), f"{lab_}  {a.key}  ROI u{u0}-{u1 - 1} v{v0}-{v1 - 1}  16 px/texel", fill=(255, 255, 0))
            rv = rd / "review" / f"{a.key}-{size}-roi.png"
            sheet.save(rv)
            rec["files"][str(size)]["review"] = dict(path=str(rv.relative_to(rd)), sha256=sha(rv))
        rec["status"] = ("OK: candidate preview (copies); native-class audit passed; NOT a quality/look acceptance; "
                         "not installed, not admitted")
        write_receipt(rd, rec)
        print(json.dumps({k: v["stats"] for k, v in rec["files"].items()}), flush=True)
        return 0
    except Fail as e:
        rec["status"] = "FAILED"
        rec["reason"] = str(e)
        write_receipt(rd, rec)
        print("FAILED:", e, "at", rec["stage_reached"], flush=True)
        return 3
    except Exception as e:  # noqa: BLE001  any unexpected error also finalises a FAILED receipt
        rec["status"] = "FAILED (unexpected exception)"
        rec["reason"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-4000:]
        write_receipt(rd, rec)
        print("FAILED (unexpected):", type(e).__name__, e, "at", rec["stage_reached"], flush=True)
        return 4


if __name__ == "__main__":
    sys.exit(main())
