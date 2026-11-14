#!/usr/bin/env python3
"""claude-einhander-ui (EIN-MENU-HUD-20261114), job J-S1 r3: MEASURE-ONLY speckle census for the three w4 menu-class-exact
1AD90FC9 spec-text keys at runtime-2048. New file; v2 4957470c is unchanged and superseded (root review msg_97376b75).
No repair path exists in r3 (no mask, no R5 claims): it writes only counts, a candidate map sheet and result.json.
Binding, all checked BEFORE any decode or library use on data:
  * scope is fixed in code: exactly the 3 keys below, folder w4-menus/menu-class-exact-v1, runtime-2048; no CLI widening;
  * EXPECTED table (below) pins, per key: authored + v5 snap-native PNG sha256 and IHDR size (parsed from raw bytes),
    words sha256 / CRC32 (== RAW key) / length, words .source.json sha256 and geometry, CLUT sha256 / CRC32 (== CLUT key) /
    exact 32-byte length; the verified summary e124d0e8 is re-read and must list the same pins;
  * no project author code is imported (no classcheck/w6lib/w2lib): the 4bpp decode (low nibble first) is inline;
  * library versions are compared to the pinned set and the run refuses on mismatch; python -O is refused; BLAS/OMP
    threads = 1 before numpy import; every file is read once into bytes, verified, then decoded from those bytes.
Measure per key (authored and snap-native), inside luminance-scoped native glyph cells (scope only; no repair licence):
alpha-0 pixels (RGBA holes) and visible dark pixels (lum < 140; RGB-only speck candidates), component counts, size
histogram, and how many components are enclosed holes under the per-component ring rule (8-neighbour (pixel,label)
pairs; any non-ok ring pixel vetoes every adjacent component; border components rejected). Synthetic selftest controls
run first. Sheet: authored | snap-native | candidate map, 9 px/texel ATLAS SIMULATION. Writes ONLY <out>/<UTC>/ (exclusive)."""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
sys.dont_write_bytecode = True
if sys.flags.optimize:
    raise SystemExit("CHECK FAILED: refusing to run under python -O")

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
EXPECTED = [
    {
        "key": "1AD90FC9-4315989E.png",
        "authored": "C:/github/Einhander/remaster-audit/comfy-authoring/w4-menus/frozen/menu-class-exact-v1/runtime-2048/1AD90FC9-4315989E.png",
        "authored_sha256": "9e05ff74765ebe05be046f582e42dee6864c6be740847a031b4dc1178b222560",
        "authored_ihdr": [
            2048,
            2048
        ],
        "snap": "C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/classsnap-v5/20261114T180407Z/snap-native/w4-menus__menu-class-exact-v1__runtime-2048__1AD90FC9-4315989E.png",
        "snap_sha256": "dd5b4c97d272c9702b724be10534d3a192331ef9035c0ab67466c001fde1098a",
        "snap_ihdr": [
            2048,
            2048
        ],
        "words": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.words.bin",
        "words_sha256": "32861a1726c1ee0be1b76bbdd65040f95106084d0d361b883ab4f3df77ce2fc8",
        "words_crc": "1AD90FC9",
        "words_len": 32768,
        "meta": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.source.json",
        "meta_sha256": "15dab1ad9dc24a31900a9b7036a02c9aefb5c6956f2705477a667a45cf7e8037",
        "meta_geom": [
            64,
            256,
            0
        ],
        "clut": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-4315989E.clut.bin",
        "clut_sha256": "0e6962d7d9fe6b052732d62144e26b04d96db6e144c35ed53b8720f2c3358657",
        "clut_crc": "4315989E",
        "clut_len": 32
    },
    {
        "key": "1AD90FC9-02491337.png",
        "authored": "C:/github/Einhander/remaster-audit/comfy-authoring/w4-menus/frozen/menu-class-exact-v1/runtime-2048/1AD90FC9-02491337.png",
        "authored_sha256": "3eae507320ef8345010a2f096b3e039f9a8fdd599df38b9343071a3fd340dbb2",
        "authored_ihdr": [
            2048,
            2048
        ],
        "snap": "C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/classsnap-v5/20261114T180407Z/snap-native/w4-menus__menu-class-exact-v1__runtime-2048__1AD90FC9-02491337.png",
        "snap_sha256": "a3035801bbab95c92dcd3d0adbef31a85086dcdbb029c9a31cd21ef0f9fcb7e3",
        "snap_ihdr": [
            2048,
            2048
        ],
        "words": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.words.bin",
        "words_sha256": "32861a1726c1ee0be1b76bbdd65040f95106084d0d361b883ab4f3df77ce2fc8",
        "words_crc": "1AD90FC9",
        "words_len": 32768,
        "meta": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.source.json",
        "meta_sha256": "15dab1ad9dc24a31900a9b7036a02c9aefb5c6956f2705477a667a45cf7e8037",
        "meta_geom": [
            64,
            256,
            0
        ],
        "clut": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.clut.bin",
        "clut_sha256": "3b2c7aaef20d4f9368dd6d479773cb9cb4915624a39fd9a849d25031769a806b",
        "clut_crc": "02491337",
        "clut_len": 32
    },
    {
        "key": "1AD90FC9-79902A90.png",
        "authored": "C:/github/Einhander/remaster-audit/comfy-authoring/w4-menus/frozen/menu-class-exact-v1/runtime-2048/1AD90FC9-79902A90.png",
        "authored_sha256": "d67b4c1959165d887aa01db9ecf63e46ff3f83a71f36f200d3e51be12fe1e26e",
        "authored_ihdr": [
            2048,
            2048
        ],
        "snap": "C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/classsnap-v5/20261114T180407Z/snap-native/w4-menus__menu-class-exact-v1__runtime-2048__1AD90FC9-79902A90.png",
        "snap_sha256": "3e4f462464a796fee468ab1b12ecfacdc8600b18343b9fe4dc52138e0488a9e7",
        "snap_ihdr": [
            2048,
            2048
        ],
        "words": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.words.bin",
        "words_sha256": "32861a1726c1ee0be1b76bbdd65040f95106084d0d361b883ab4f3df77ce2fc8",
        "words_crc": "1AD90FC9",
        "words_len": 32768,
        "meta": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-02491337.source.json",
        "meta_sha256": "15dab1ad9dc24a31900a9b7036a02c9aefb5c6956f2705477a667a45cf7e8037",
        "meta_geom": [
            64,
            256,
            0
        ],
        "clut": "C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/1AD90FC9-79902A90.clut.bin",
        "clut_sha256": "ae941bea285cc8fcbb8ddd189766d81bd0dfae2f459836561bafabc9bba72d76",
        "clut_crc": "79902A90",
        "clut_len": 32
    }
]
GLYPH_LUM, DARK_LUM, BRIGHT_LUM, RING_FRAC, MAX_SPECK = 180.0, 140.0, 200.0, 0.9, 64


def need(cond, *msg):
    if not cond:
        raise SystemExit("CHECK FAILED: " + " | ".join(str(m) for m in msg))


def hb(b):
    return hashlib.sha256(b).hexdigest()


def ihdr(b):
    need(len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR", "not a PNG with IHDR first")
    return tuple(struct.unpack(">II", b[16:24]))


def main():
    t0 = time.time()
    # ---- all byte-level verification first (no numpy/scipy/PIL use on data, no author code) ----
    sb = SUMMARY.read_bytes()
    need(hb(sb) == SUMMARY_SHA256, "summary sha256")
    summ = json.loads(sb)
    mem = {}
    for u in summ["units_detail"]:
        if u["folder"] == FOLDER and u["dir"] == DIR:
            for m in u["members"]:
                mem[os.path.basename(m["file"])] = m
    blobs = {}
    for e in EXPECTED:
        k = e["key"]
        m = mem.get(k)
        need(m is not None and m.get("built"), k, "not in verified summary")
        need(m["input_sha256"] == e["authored_sha256"] and m["candidate_sha256"] == e["snap_sha256"] and
             m["words_sha256"] == e["words_sha256"] and m["clut_sha256"] == e["clut_sha256"], k, "summary pins differ from table")
        raw, clutk = k[:-4].split("-")
        ab, nb_ = Path(e["authored"]).read_bytes(), Path(e["snap"]).read_bytes()
        wb, cb, mb = Path(e["words"]).read_bytes(), Path(e["clut"]).read_bytes(), Path(e["meta"]).read_bytes()
        need(hb(ab) == e["authored_sha256"] and list(ihdr(ab)) == e["authored_ihdr"] == list(SIZE), k, "authored pin/IHDR")
        need(hb(nb_) == e["snap_sha256"] and list(ihdr(nb_)) == e["snap_ihdr"] == list(SIZE), k, "snap-native pin/IHDR")
        need(hb(wb) == e["words_sha256"] and "%08X" % zlib.crc32(wb) == e["words_crc"] == raw and len(wb) == e["words_len"],
             k, "words pin/CRC/length")
        need(hb(cb) == e["clut_sha256"] and "%08X" % zlib.crc32(cb) == e["clut_crc"] == clutk and len(cb) == e["clut_len"] == 32,
             k, "CLUT pin/CRC/32-byte bound")
        need(hb(mb) == e["meta_sha256"], k, "words meta sha256")
        meta = json.loads(mb)
        need([meta["width_words"], meta["height"], meta["depth"]] == e["meta_geom"] == [64, 256, 0] and
             len(wb) == 64 * 256 * 2, k, "words geometry/depth")
        blobs[k] = (ab, nb_, wb, cb)
    # ---- libraries: import, then refuse on any version mismatch before touching data ----
    import numpy as np
    import PIL
    import scipy
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    got = {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__, "pillow": PIL.__version__}
    need(got == VERSIONS, "library versions differ from pinned set", got, VERSIONS)
    Image.MAX_IMAGE_PIXELS = SIZE[0] * SIZE[1]
    offs = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)]

    def shift(a, dy, dx):
        out = np.zeros_like(a)
        H, W = a.shape
        out[slice(max(-dy, 0), H + min(-dy, 0)), slice(max(-dx, 0), W + min(-dx, 0))] = \
            a[slice(max(dy, 0), H + min(dy, 0)), slice(max(dx, 0), W + min(dx, 0))]
        return out

    def qualify(dark, ok_ring, bright_ring):
        H, W = dark.shape
        lab, n = ndi.label(dark, structure=np.ones((3, 3), bool))
        if n == 0:
            return lab, 0, np.zeros(1, bool)
        size = np.bincount(lab.ravel(), minlength=n + 1)
        ring = ~dark
        parts = []
        for dy, dx in offs:
            nbl = shift(lab, dy, dx)
            idx = np.flatnonzero(ring & (nbl > 0))
            parts.append(idx.astype(np.int64) * (n + 1) + nbl.ravel()[idx])
        pairs = np.unique(np.concatenate(parts))
        pix, lbl = pairs // (n + 1), pairs % (n + 1)
        rn = np.bincount(lbl, minlength=n + 1)
        rok = np.bincount(lbl, weights=ok_ring.ravel()[pix].astype(np.float64), minlength=n + 1)
        rbr = np.bincount(lbl, weights=bright_ring.ravel()[pix].astype(np.float64), minlength=n + 1)
        border = np.zeros(n + 1, bool)
        for i, sl in enumerate(ndi.find_objects(lab), start=1):
            if sl is not None and (sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == H or sl[1].stop == W):
                border[i] = True
        ok = np.zeros(n + 1, bool)
        ids = np.arange(1, n + 1)
        ok[ids] = (size[ids] <= MAX_SPECK) & (rn[ids] > 0) & (rok[ids] == rn[ids]) & (rbr[ids] >= RING_FRAC * rn[ids]) & ~border[ids]
        return lab, n, ok

    # synthetic controls (no files)
    z = np.zeros((20, 20), bool)
    st = {}
    d = z.copy(); d[10, 10] = True
    st["enclosed_dot_qualifies"] = bool(qualify(d, ~d, ~d)[2][1])
    o = ~d; o[10, 11] = False
    st["dot_touching_counter_rejected"] = not qualify(d, o, ~d)[2][1]
    d2 = z.copy(); d2[10, 9] = True; d2[10, 11] = True
    o2 = ~d2; o2[10, 10] = False
    r = qualify(d2, o2, ~d2); st["shared_bad_ring_vetoes_both"] = (r[1] == 2 and not r[2][1] and not r[2][2])
    d3 = z.copy(); d3[0, 5] = True
    st["border_rejected"] = not qualify(d3, ~d3, ~d3)[2][1]
    d4 = z.copy(); d4[5:15, 5:15] = True
    st["oversize_rejected"] = not qualify(d4, ~d4, ~d4)[2][1]
    st["dim_ring_rejected"] = not qualify(d, ~d, np.zeros_like(d))[2][1]
    st["no_candidates_noop"] = qualify(z, ~z, ~z)[1] == 0
    need(all(st.values()), "selftest controls failed", st)

    def lum(rgb):
        return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114

    def decode(b):
        with Image.open(io.BytesIO(b)) as im:
            need(im.size == SIZE, "decoded size")
            return np.ascontiguousarray(np.asarray(im.convert("RGBA")))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = UI_OUT / "speck-measure" / stamp
    (rd / "review").mkdir(parents=True, exist_ok=False)
    with open(rd / "pid.txt", "x", encoding="utf-8") as fh:
        fh.write(f"{os.getpid()} {stamp}\n")
    rows = []
    for e in EXPECTED:
        k = e["key"]
        ab, nb_, wb, cb = blobs[k]
        w = np.frombuffer(wb, "<u2").reshape(256, 64)
        idx = np.zeros((256, 256), np.uint8)
        for i in range(4):
            idx[:, i::4] = (w >> (4 * i)) & 15
        v = np.frombuffer(cb, "<u2")[idx].astype(np.uint16)
        nrgb = np.stack([(v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3], -1).astype(np.float32)
        ncls = np.where(v == 0, 0, np.where(v & 0x8000, 255, 127)).astype(np.uint8)
        s = SIZE[0] // 256
        scope_t = (ncls != 0) & (lum(nrgb) >= GLYPH_LUM)
        scope = np.repeat(np.repeat(scope_t, s, 0), s, 1)
        au, sn = decode(ab), decode(nb_)

        def measure(img):
            L = lum(img[..., :3].astype(np.float32))
            vis = img[..., 3] != 0
            hole = scope & ~vis
            dark = scope & vis & (L < DARK_LUM)
            lab, n, ok = qualify(dark, vis & scope, vis & (L >= BRIGHT_LUM))
            sizes = np.bincount(lab.ravel())[1:] if n else np.zeros(0, int)
            return (dict(rgba_hole_px=int(hole.sum()), dark_visible_px=int(dark.sum()), dark_components=int(n),
                         size_hist={"1": int((sizes == 1).sum()), "2-4": int(((sizes >= 2) & (sizes <= 4)).sum()),
                                    "5-16": int(((sizes >= 5) & (sizes <= 16)).sum()),
                                    "17-64": int(((sizes >= 17) & (sizes <= 64)).sum()), ">64": int((sizes > 64).sum())},
                         enclosed_hole_components=int(ok.sum())), hole, dark, ok[lab])
        m_a = measure(au)[0]
        m_s, hole_s, dark_s, qual_s = measure(sn)
        TH = TW = 256
        ch, cw = 16, 64
        sc = dark_s.reshape(TH, s, TW, s).sum(axis=(1, 3)).astype(np.float32)
        cs = ndi.uniform_filter(sc, size=(ch, cw), mode="constant")
        cy0, cx0 = np.unravel_index(int(np.argmax(cs)), cs.shape)
        y0 = int(min(max(cy0 - ch // 2, 0), TH - ch)); x0 = int(min(max(cx0 - cw // 2, 0), TW - cw))
        cmap = np.zeros_like(sn); cmap[..., 3] = 255
        cmap[scope, 2] = 50; cmap[dark_s, 0] = 255; cmap[hole_s, 0] = 255; cmap[hole_s, 2] = 255; cmap[qual_s, 1] = 255

        def sim(arr):
            c = arr[y0 * s:(y0 + ch) * s, x0 * s:(x0 + cw) * s].astype(np.float32)
            vv = np.where(c[..., 3:4] > 0, c[..., :3], 24.0)
            return Image.fromarray(vv.astype(np.uint8)).resize((cw * 9, ch * 9), Image.BOX)
        tiles = [("w4 authored", au), ("w4 v5 snap-native", sn),
                 ("candidates: red dark-visible, magenta alpha-hole, yellow enclosed", cmap)]
        sheet = Image.new("RGB", (cw * 9, len(tiles) * (ch * 9 + 16) + 14), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for i, (lb, arr) in enumerate(tiles):
            sheet.paste(sim(arr), (0, i * (ch * 9 + 16) + 16))
            dr.text((4, i * (ch * 9 + 16) + 2), f"{lb} | {k} texels {[x0, y0, x0 + cw, y0 + ch]}", fill=(255, 255, 0))
        dr.text((4, sheet.height - 12), "ATLAS SIMULATION, 9 px/texel (measurement only)", fill=(160, 160, 160))
        fs = rd / "review" / f"{DIR}__{k[:-4]}__speck-measure.png"
        with open(fs, "xb") as fh:
            sheet.save(fh, format="PNG")
        rows.append(dict(key=k, scope_texels=int(scope_t.sum()), authored=m_a, snap_native=m_s,
                         review=dict(path=fs.relative_to(rd).as_posix(), sha256=hb(fs.read_bytes()), crop_texels=[x0, y0, x0 + cw, y0 + ch])))
        print(k, "authored hole/dark", m_a["rgba_hole_px"], m_a["dark_visible_px"], "snap hole/dark", m_s["rgba_hole_px"],
              m_s["dark_visible_px"], "comps", m_s["dark_components"], "enclosed", m_s["enclosed_hole_components"], flush=True)
        del au, sn, scope, cmap, dark_s, hole_s, qual_s
    res = dict(run=stamp, owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114", job="J-S1 r3 MEASURE-ONLY",
               status="measurement only; no art written; 1AD90FC9 x3 w4 runtime-2048; main decides next",
               tool_sha256=hb(Path(__file__).read_bytes()), versions=got, selftest=st, summary_sha256=SUMMARY_SHA256,
               expected=EXPECTED, thresholds=dict(glyph=GLYPH_LUM, dark=DARK_LUM, bright=BRIGHT_LUM, ring=RING_FRAC, max_speck=MAX_SPECK),
               rows=rows, seconds=round(time.time() - t0, 1))
    with open(rd / "result.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(res, indent=1) + "\n")
    print("done", res["seconds"], "s result", hb((rd / "result.json").read_bytes()), flush=True)


if __name__ == "__main__":
    main()
