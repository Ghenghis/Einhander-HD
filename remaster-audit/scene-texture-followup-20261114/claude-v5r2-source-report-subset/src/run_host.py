#!/usr/bin/env python3
"""Host verification v5 of the PRIVATE opt-in class-aware mip integration for the frozen v61 renderer: PREPARED
levels in hash-bound native-authority sidecars (HDCMSC02), bounded preload at renderer init, no builder on the draw
thread (DESIGN-V3.md), v4 RGB edges (DESIGN-V4.md) and the v5 separate identity-bound RGB-ONLY sidecar kind
(HDCMRG01, DESIGN-V5.md) for the reviewed census list (drawn, lod-0 fringe_mean >= 8: 136 keys) (claude-einhander).
CPU only, below normal, one logical CPU, one compiler/process at a time; no GPU, no game, no link. Writes ONLY
runs/<UTC>/ (exist_ok=False); a failing step never deletes earlier output; runs/INDEX.jsonl gets one line per run; the
exit code follows the verdict.

Steps:
  1 fixtures   test_hd_class_mips.c (builder == frozen proto-v2b, properties, HDCMSC02 accept + every reject reason,
               fail-closed prepared upload, bounded cache) + hash vectors == independent Python reference;
  2 mutants    mutants of hd_class_mips.inc (builder, R5, hash, parse, levels, M4, admission, upload, cache);
  3 real       real pages: runtime stb decode == PIL; CRC-proven native maps; R1; builder == prototype at every level;
               offline build time; for admitted keys: preload verify time and DRAW-THREAD admit time (hash + R1);
  4 sidecars   HDCMSC02 for the explicit ADMIT list (preverified: whole-cell PASS, R1 0, decoder equal) + index.txt;
               prepared bytes == prototype levels; real-data negatives (O pair LEVEL0/KEY, RISE refused offline,
               falsely flagged RISE rejected at admission by R1);
  4b rgbonly   v5: HDCMRG01 for every census-listed key (runtime stb decode == PIL, CRC-proven native dims, exact
               level-0 hash + has-cutout bound) + index.txt; round trip through the runtime parse/admit; negatives
               (false opaque, false has-cutout, changed pixel); the harness directories (opaque, false, both, caps);
  5 glue       the EXACT make_patch.GLUE text compiled in glue_harness.c with recording GL stubs and counted
               heap/file calls, run OFF/ON (v4 modes + v5 RGB-only modes) against the real sidecar directories and
               real decoded pixels, plus mutants of the glue text;
  6 patch      make_patch.patch() on the sha-pinned frozen v61 renderer -> patched copy + receipts (+ control);
  7 compile    compile-only with the exact v61 flags (-O3) of patched AND control; warnings compared; the patched
               preprocessed TU must not contain the level builder;
  8 glsl       HD_FS extracted from both preprocessed TUs, validated offline with glslangValidator."""
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import ctypes
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
CM = HERE.parent
FROZEN = CM / "frozen/class-mip-v2b-breakdown-v1"
PROTO = FROZEN / "proto-v2b"
BREAKDOWN = FROZEN / "runs/runs-breakdown-v2b/20261114T102254Z/result.json"
AB = HERE / "runs-ab/20261114T111427Z/result.json"
STB_DIR = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime/third_party")
STB_SHA256 = "866095d4107665b4f2ac84e5aa25c7b4bd2f89c5408348c87fdec8891661cace"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
GLSLANG = "C:/VulkanSDK/1.4.363.0/Bin/glslangValidator.exe"
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
V61 = E / "sampling-build-v61-view-metrics-r2"
PACKROOT = E / "world-integrated-crisp-v4/pack"
PACK = PACKROOT / "einhander-texture-replacements"
KPANEL = CM.parent / "95a3-k-panel/frozen/95A3BCF8-K-panel-v1/page2048/95A3BCF8-723E222C.png"
# Explicit admission list (runs-ab/20261114T111427Z: drawn, whole-cell PASS, alpha-structured keys where class levels
# change the minified result; one key per page variant; <= HDCM_CACHE_MAX). Region O is NOT admitted: fully opaque,
# class chain == box chain within 2/255 (no visible benefit).
ADMIT = ["11CFE2E3-0E09E912", "E360C964-C1B5906C", "31214B41-73AF4FAA", "67DC56D7-96998A63",
         "327E6D9E-5039A9C5", "E360C964-DF4F533F", "73BF9877-803A474F", "A34295C8-FBCA4A8A"]
NEG = ["95A3BCF8-60245B3A", "95A3BCF8-07A9568D", "82831823-06BDD2F5"]      # negatives only (never admitted)
EXTRA = [("K panel page2048", KPANEL, "95A3BCF8-723E222C", "k-panel-page2048"),
         ("95A3 397FBE8A", PACK / "95A3BCF8-397FBE8A.png", "95A3BCF8-397FBE8A", "pack")]
PRELOAD_CAP = 96 * 1024 * 1024
CACHE_MAX = 8
# v5: the reviewed RGB-only list = census rows drawn (mapped, drawn cells, mixed footprints) with fringe_mean >= 8
CENSUS = HERE / "runs-census/20261114T114657Z/result.json"
RGB_FRINGE_MIN = 8
RG_BYTES = 48
RG_CACHE_MAX = 256
CFLAGS = ["-std=c11", "-O1", "-Wall", "-Wextra"]
REASONS = ["OK", "NOFILE", "SIZE", "MAGIC", "SELFHASH", "KEY", "NATIVE_DIMS", "HD_DIMS", "SCALE", "LEVELS", "FLAGS",
           "CLASS", "LEVEL0", "R1", "ALLOC", "BUILD", "GL", "LEVELHASH", "LEVELDATA", "CUTOUT"]

MUTANTS = [
    ("builder follows the HD centre, not the native map", "const uint8_t C = ncls[(size_t)cy * tw + cx];",
     "const uint8_t C = hdcm_class(HDCM_PX(cx * s + s / 2, cy * s + s / 2)[3]);"),
    ("M3 coverage floor instead of round",
     "k = (int)(((int64_t)2 * vis0 * k2 + (int64_t)s * s) / ((int64_t)2 * s * s));",
     "k = (int)(((int64_t)vis0 * k2) / ((int64_t)s * s));"),
    ("M3 never-empty removed", "                if (C != 0 && k == 0) k = 1;                                             /* never empty */\n", ""),
    ("STP tie no longer follows the native class", "else cls = C != 0 ? C : 127;", "else cls = 127;"),
    ("R5 fill seeds in reverse scan order",
     "    for (size_t i = 0; i < n; i++) {\n        done[i] = (uint8_t)(rgba[i * 4 + 3] != 0);",
     "    for (size_t i = n; i-- > 0;) {\n        done[i] = (uint8_t)(rgba[i * 4 + 3] != 0);"),
    ("row stride ignored by the builder", "#define HDCM_PX(x, y) (&lvl0[(size_t)(y) * stride + (size_t)(x) * 4])",
     "#define HDCM_PX(x, y) (&lvl0[(size_t)(y) * (size_t)w * 4 + (size_t)(x) * 4])"),
    ("M4 native level removed", "if (cs == 1) k = C != 0;", "if (cs == 1) k = vis0 * 2 >= s * s;"),
    ("tie toward the edge instead of the centre", "(ca < cc || (ca == cc && a < cur))", "(ca > cc || (ca == cc && a < cur))"),
    ("M2 RGB averages cutout children", "                        if (!p[3]) continue;\n                        sr += p[0];",
     "                        sr += p[0];"),
    ("level cutout RGB not filled", "    hdcm_fill_cutout_rgb(dst, lw, h >> L, queue, done);\n    return 0;", "    return 0;"),
    ("L bound removed (shift before bounds)", " || L < 1 || L > hdcm_levels_for_scale(s)) return -1;", " || L < 1) return -1;"),
    # v5: anchors extended with context (hdcm_hash64_cutout repeats these lines; each anchor must stay unique)
    ("hash ignores the row stride", "    for (uint32_t r = 0; r < rows; r++) {\n        const uint8_t *q = p + (size_t)r * stride;",
     "    for (uint32_t r = 0; r < rows; r++) {\n        const uint8_t *q = p + (size_t)r * row_bytes;"),
    ("hash drops the row tail", "        if (i < row_bytes) {\n", "        if (0) {\n"),
    ("parse skips the self-hash",
     "    if (hdcm_hash64(buf, len - 8, (uint32_t)(len - 8), 1) != hdcm_rd64(buf + len - 8)) return HDCM_E_SELFHASH;\n", ""),
    ("parse accepts an unverified R1 flag", "    if (!(sc->flags & HDCM_FLAG_R1_VERIFIED)) return HDCM_E_FLAGS;\n", ""),
    # run 5 deleted this line outright, leaving the for loop without a statement body (mutant did not compile);
    # an empty statement keeps the mutant compilable and removes only the check
    ("parse accepts non-class native values",
     "        if (sc->map[i] != 0 && sc->map[i] != 127 && sc->map[i] != 255) return HDCM_E_CLASS;\n", "        ;\n"),
    ("parse skips the per-level hash",
     "        if (hdcm_hash64(p, (size_t)lw * 4u, lw * 4u, lh) != hdcm_rd64(buf + 56 + 8 * (l - 1))) return HDCM_E_LEVELHASH;\n", ""),
    ("parse accepts non-class level alpha", "            if (a != 0 && a != 127 && a != 255) return HDCM_E_LEVELDATA;\n", ""),
    ("parse skips the M4 last-level check",
     "        if (sc->level[L][(size_t)i * 4 + 3] != sc->map[i]) return HDCM_E_LEVELDATA;\n", ""),
    ("parse accepts a wrong level-byte total", "    if (want != sc->level_bytes) return HDCM_E_SIZE;\n", ""),
    ("admission skips the level-0 hash",
     "    if (hdcm_hash64(rgba, stride, w * 4u, h) != sc->level0_hash) return HDCM_E_LEVEL0;\n", ""),
    ("admission skips the runtime R1 re-check",
     "            if (hdcm_class(a) != sc->map[(size_t)cy * sc->nw + cx]) return HDCM_E_R1;\n", ""),
    ("upload verification result ignored", "        if (up(ctx, L, lw, lh, sc->level[L])) return HDCM_E_GL;\n",
     "        (void)up(ctx, L, lw, lh, sc->level[L]);\n"),
    ("level counted before its upload is verified",
     "        if (up(ctx, L, lw, lh, sc->level[L])) return HDCM_E_GL;\n        ++*uploaded;\n",
     "        ++*uploaded;\n        if (up(ctx, L, lw, lh, sc->level[L])) return HDCM_E_GL;\n"),
    ("cache ignores the byte cap", " && len <= c->cap_bytes - c->bytes;", ";"),
    ("cache accepts duplicates",
     "        if (c->e[i].sc.th == th && c->e[i].sc.ph == ph) rc = HDCM_E_KEY;            /* duplicate */\n", ""),
    ("cache accepts a file whose key differs from the index",
     "    int rc = hdcm_sidecar2_parse(buf, len, &sc);\n    if (rc == HDCM_OK && (sc.th != th || sc.ph != ph)) rc = HDCM_E_KEY;\n",
     "    int rc = hdcm_sidecar2_parse(buf, len, &sc);\n"),
    ("parse accepts unknown flag bits",
     "    if (sc->flags & ~(HDCM_FLAG_R1_VERIFIED | HDCM_FLAG_HAS_CUTOUT)) return HDCM_E_FLAGS;   /* unknown bits */\n", ""),
    # ---- v5 RGB-only kind (HDCMRG01) ----
    ("RGB parse accepts a longer file", "    if (!buf || !sc || len != HDCM_RG_BYTES) return HDCM_E_SIZE;",
     "    if (!buf || !sc || len < HDCM_RG_BYTES) return HDCM_E_SIZE;"),
    ("RGB parse skips the self-hash", "    if (hdcm_hash64(buf, 40, 40, 1) != hdcm_rd64(buf + 40)) return HDCM_E_SELFHASH;\n", ""),
    ("RGB parse accepts unknown flag bits", "    if (sc->flags & ~HDCM_RG_FLAG_HAS_CUTOUT) return HDCM_E_FLAGS;\n", ""),
    ("RGB parse skips the scale divisibility",
     " || sc->hw % sc->nw || sc->hh % sc->nh || sc->hw / sc->nw != sc->hh / sc->nh)", ")"),
    ("RGB admit skips the native dims",
     "    if (sc->nw != native_w || sc->nh != native_h) return HDCM_E_NATIVE_DIMS;\n"
     "    if (sc->hw != w || sc->hh != h || stride < (size_t)w * 4) return HDCM_E_HD_DIMS;\n    int cut = 0;",
     "    if (sc->hw != w || sc->hh != h || stride < (size_t)w * 4) return HDCM_E_HD_DIMS;\n    int cut = 0;"),
    ("RGB admit skips the level-0 identity",
     "    if (hdcm_rgb_level0(rgba, stride, w, h, &cut) != sc->level0_hash) return HDCM_E_LEVEL0;",
     "    (void)hdcm_rgb_level0(rgba, stride, w, h, &cut);"),
    ("RGB admit ignores the has-cutout truth",
     "    if (((sc->flags & HDCM_RG_FLAG_HAS_CUTOUT) != 0) != (cut != 0)) return HDCM_E_CUTOUT;\n", ""),
    ("RGB admit trusts a false opaque claim",
     "    if (((sc->flags & HDCM_RG_FLAG_HAS_CUTOUT) != 0) != (cut != 0)) return HDCM_E_CUTOUT;\n",
     "    if ((sc->flags & HDCM_RG_FLAG_HAS_CUTOUT) && !cut) return HDCM_E_CUTOUT;\n"),
    ("RGB admit trusts a false has-cutout claim",
     "    if (((sc->flags & HDCM_RG_FLAG_HAS_CUTOUT) != 0) != (cut != 0)) return HDCM_E_CUTOUT;\n",
     "    if (!(sc->flags & HDCM_RG_FLAG_HAS_CUTOUT) && cut) return HDCM_E_CUTOUT;\n"),
    # HDCM-X4 identity (v5 run 2; run 1's single-chain hash was too slow for 4096^2 pages on the draw thread)
    ("X4 cutout check misses the 2nd texel of a word", "#define HDCM_ABITS 0x0000010000000100ull",
     "#define HDCM_ABITS 0x0000000000000100ull"),
    ("X4 alpha test without the +0xFF carry", "#define HDCM_ANZ(v) ((((v) >> 24) & HDCM_AMASK) + HDCM_AMASK)",
     "#define HDCM_ANZ(v) (((v) >> 24) & HDCM_AMASK)"),
    ("X4 cutout scan misses the odd-width tail texel", "            cut |= q[i + 3] == 0;\n            tv[k++]", "            tv[k++]"),
    ("X4 cutout scan skips the main groups",
     "            nz &= HDCM_ANZ(v0) & HDCM_ANZ(v1) & HDCM_ANZ(v2) & HDCM_ANZ(v3);\n", ""),
    ("X4 cutout scan skips whole row-tail words", "            nz &= HDCM_ANZ(tv[k]);\n", ""),
    ("X4 main-loop lanes 1/2 swapped", "HDCM_MIX(l1, v1); HDCM_MIX(l2, v2);", "HDCM_MIX(l1, v2); HDCM_MIX(l2, v1);"),
    ("X4 row-tail word 1 mixed into lane 0", "        if (k > 1) HDCM_MIX(l1, tv[1]);", "        if (k > 1) HDCM_MIX(l0, tv[1]);"),
    ("X4 fold drops lane 3", "    hsh ^= l3; hsh *= 0xC4CEB9FE1A85EC53ull; hsh ^= hsh >> 33;\n", ""),
    ("X4 lane 1 seed equals lane 0", "l1 = seed ^ HDCM_X4_LANE,", "l1 = seed,"),
    ("X4 not domain-separated (tag dropped)", "^ (uint64_t)h ^ HDCM_X4_TAG;", "^ (uint64_t)h;"),
    ("X4 ignores the row stride", "        const uint8_t *q = p + (size_t)r * stride;\n        uint32_t i = 0;\n        for (; i + 32 <= row_bytes",
     "        const uint8_t *q = p + (size_t)r * row_bytes;\n        uint32_t i = 0;\n        for (; i + 32 <= row_bytes"),
    ("RGB cache cap returns OK without storing", "    if (c->n >= HDCM_RG_CACHE_MAX) return HDCM_E_ALLOC;",
     "    if (c->n >= HDCM_RG_CACHE_MAX) return HDCM_OK;"),
    ("RGB cache accepts duplicates",
     "        if (c->e[i].th == th && c->e[i].ph == ph) rc = HDCM_E_KEY;                 /* duplicate */\n", "        ;\n"),
    ("RGB cache accepts a file whose key differs from the index",
     "    int rc = hdcm_rgb_parse(buf, len, &sc);\n    if (rc == HDCM_OK && (sc.th != th || sc.ph != ph)) rc = HDCM_E_KEY;\n",
     "    int rc = hdcm_rgb_parse(buf, len, &sc);\n"),
    ("RGB cache find ignores the palette hash", "        if (c->e[i].th == th && c->e[i].ph == ph) return &c->e[i];",
     "        if (c->e[i].th == th) return &c->e[i];"),
]

# v4: mutants of the EXACT glue text (glue.c), each must fail at least one harness case
GLUE_MUTANTS = [
    ("RGB flag ignores the has-cutout bit", "slot->rgb_edges = (sc->flags & HDCM_FLAG_HAS_CUTOUT) ? 1u : 0u;", "slot->rgb_edges = 1u;"),
    ("levels uploaded when only RGB edges are on", "    if (rc == HDCM_OK && s_hdcm_levels_on) {\n", "    if (rc == HDCM_OK) {\n"),
    ("RGB uniform set in point mode", "(s_hdcm_rgb_on && s_tex_filter && slot && slot->rgb_edges)", "(s_hdcm_rgb_on && slot && slot->rgb_edges)"),
    ("class uniform set in point mode", "(s_hdcm_levels_on && s_tex_filter && slot && slot->class_mip_levels)",
     "(s_hdcm_levels_on && slot && slot->class_mip_levels)"),
    ("fail-closed MAX_LEVEL restore removed", "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 1000);\n", ""),
    ("RGB env not exact \"1\"", 's_hdcm_rgb_on = rgb && strcmp(rgb, "1") == 0 &&', "s_hdcm_rgb_on = rgb && *rgb &&"),
    ("class env not exact \"1\"", 's_hdcm_levels_on = levels && strcmp(levels, "1") == 0 &&', "s_hdcm_levels_on = levels && *levels &&"),
    ("admission skips the R1/identity check", "        rc = hdcm_sidecar_admit(sc, m->texture_hash, m->palette_hash,",
     "        rc = HDCM_OK; (void)hdcm_sidecar_admit(sc, m->texture_hash, m->palette_hash,"),
    # Not used: removing the preload's pre-read hdcm_cache_fits check is behaviourally EQUIVALENT (hdcm_cache_add
    # re-checks the same caps and rejects with the same reason); it only changes how much memory is read first.
    # ---- v5 RGB-only kind ----
    ("RGB-only admission skips the identity check", "            rrc = hdcm_rgb_admit(rs, m->texture_hash, m->palette_hash,",
     "            rrc = HDCM_OK; (void)hdcm_rgb_admit(rs, m->texture_hash, m->palette_hash,"),
    ("RGB-only flag ignores the has-cutout bit", "slot->rgb_edges = (rs->flags & HDCM_RG_FLAG_HAS_CUTOUT) ? 1u : 0u;",
     "slot->rgb_edges = 1u;"),
    ("class precedence inverted (RGB-only first)", "    if (!sc && s_hdcm_rgb_dir_on) {", "    if (s_hdcm_rgb_dir_on) {"),
    ("a rejected class sidecar falls back to RGB-only", "    if (!sc && s_hdcm_rgb_dir_on) {",
     "    if ((!sc || hdcm_sidecar_admit(sc, m->texture_hash, m->palette_hash,\n"
     "                                   (uint32_t)m->upload_width_words * (4u >> q->depth), m->upload_height,\n"
     "                                   px->rgba, px->stride, px->width, px->height) != HDCM_OK) && s_hdcm_rgb_dir_on) {"),
    ("RGB-only dir used without RGB_EDGES=1", "s_hdcm_rgb_dir_on = rdir_ok && s_hdcm_rgb_on;", "s_hdcm_rgb_dir_on = rdir_ok;"),
    ("RGB preload reads before the exact-size check",
     "        if (n == (long)HDCM_RG_BYTES && fseek(f, 0, SEEK_SET) == 0) got = fread(buf, 1, sizeof buf, f);",
     "        if (fseek(f, 0, SEEK_SET) == 0) got = fread(buf, 1, sizeof buf, f);"),
    ("RGB preload index line cap removed",
     "    for (int lines = 0; lines < HDCM_RG_CACHE_MAX && fgets(line, sizeof line, idx); lines++) {",
     "    for (int lines = 0; fgets(line, sizeof line, idx); lines++) {"),
    ("RGB-only admission touches GL", "        slot->rgb_edges = (rs->flags & HDCM_RG_FLAG_HAS_CUTOUT) ? 1u : 0u;\n",
     "        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);\n"
     "        slot->rgb_edges = (rs->flags & HDCM_RG_FLAG_HAS_CUTOUT) ? 1u : 0u;\n"),
    ("RGB-only admission reads files per draw", "        const HdcmRgbSidecar *rs = hdcm_rgb_cache_find(",
     "        hdcm_preload_rgb();\n        const HdcmRgbSidecar *rs = hdcm_rgb_cache_find("),
    ("RGB-only admission allocates per draw", "        int rrc = rs ? HDCM_OK : HDCM_E_NOFILE;",
     "        free(malloc(64));\n        int rrc = rs ? HDCM_OK : HDCM_E_NOFILE;"),
    ("RGB-only slot dims check removed",
     "        if (rrc == HDCM_OK && (slot->w != px->width || slot->h != px->height)) rrc = HDCM_E_HD_DIMS;\n", ""),
    ("RGB-only native dims taken from the sidecar",
     "            rrc = hdcm_rgb_admit(rs, m->texture_hash, m->palette_hash,\n"
     "                                 (uint32_t)m->upload_width_words * (4u >> q->depth), m->upload_height,",
     "            rrc = hdcm_rgb_admit(rs, m->texture_hash, m->palette_hash,\n"
     "                                 rs->nw, rs->nh,"),
]


def hdcm_flags(blob):
    return int.from_bytes(blob[44:48], "little")


def hash_ref(buf, stride, row_bytes, rows):
    """Independent pure-Python reference of hdcm_hash64 (written from the format description)."""
    M = (1 << 64) - 1
    h = (0x9E3779B97F4A7C15 ^ ((row_bytes * 0x100000001B3) & M) ^ rows) & M
    for r in range(rows):
        row = bytes(buf[r * stride:r * stride + row_bytes])
        for i in range(0, row_bytes, 8):
            h ^= int.from_bytes(row[i:i + 8].ljust(8, b"\0"), "little")
            h = (h * 0xFF51AFD7ED558CCD) & M
            h ^= h >> 29
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & M
    h ^= h >> 33
    return h


def hash_ref_x4(buf, stride, w, rows):
    """Independent pure-Python reference of the v5 HDCM-X4 identity (written from the spec in hd_class_mips.inc)."""
    M = (1 << 64) - 1
    rb = w * 4
    seed = (0x9E3779B97F4A7C15 ^ ((rb * 0x100000001B3) & M) ^ rows ^ 0x52474F4E4C593031) & M
    L = [(seed ^ ((k * 0xD6E8FEB86659FD93) & M)) & M for k in range(4)]
    for r in range(rows):
        row = bytes(buf[r * stride:r * stride + rb])
        for j, i in enumerate(range(0, rb, 8)):
            k = j % 4
            L[k] ^= int.from_bytes(row[i:i + 8].ljust(8, b"\0"), "little")
            L[k] = (L[k] * 0xFF51AFD7ED558CCD) & M
            L[k] ^= L[k] >> 29
    h = L[0]
    for k in (1, 2, 3):
        h ^= L[k]
        h = (h * 0xC4CEB9FE1A85EC53) & M
        h ^= h >> 33
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & M
    h ^= h >> 33
    return h


def check_vectors(out):
    buf = bytes((i * 37 + 11) & 255 for i in range(64 * 3 + 16))
    exp = {"empty": hash_ref(buf, 0, 0, 0), "one13": hash_ref(buf, 13, 13, 1),
           "rows3x20s24": hash_ref(buf, 24, 20, 3), "rows3x64s64": hash_ref(buf, 64, 64, 3),
           "x4empty": hash_ref_x4(buf, 0, 0, 0), "x4w1h1s4": hash_ref_x4(buf, 4, 1, 1),
           "x4w7h3s32": hash_ref_x4(buf, 32, 7, 3), "x4w9h2s40": hash_ref_x4(buf, 40, 9, 2),
           "x4w16h3s64": hash_ref_x4(buf, 64, 16, 3)}
    got = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"HASHVEC (\S+) ([0-9a-f]{16})", out)}
    return got == exp


def below_normal():
    """Below-normal priority and one logical CPU for this process (children inherit both); verified, not assumed."""
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    pin = dict(priority=str(me.nice()), affinity=me.cpu_affinity())
    assert me.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS and len(pin["affinity"]) == 1, pin
    return pin


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, log, timeout=600, cwd=None, env=None):
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, creationflags=0x4000,
                       encoding="utf-8", errors="replace", env=env)
    log.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    return r.returncode, round(time.perf_counter() - t0, 3), (r.stdout or "") + (r.stderr or "")


def write_sc2(T, th, ph, a, ncls, s):
    """HDCMSC02 bytes for decoded level 0 `a` (H, W, 4) and native map `ncls` (levels built by the C builder)."""
    H, W = a.shape[:2]
    nh, nw = ncls.shape
    L = s.bit_length() - 1
    levels, hashes = [], []
    for l in range(1, L + 1):
        lw, lh = W >> l, H >> l
        d = np.zeros((lh, lw, 4), np.uint8)
        q = np.zeros(lw * lh, np.int32)
        dn = np.zeros(lw * lh, np.uint8)
        rc = T.hdcm_tool_build_level(a.ctypes.data, W * 4, W, H, ncls.ctypes.data, nw, nh, s, l, d.ctypes.data,
                                     q.ctypes.data, dn.ctypes.data)
        assert rc == 0
        b = d.tobytes()
        levels.append(b)
        hashes.append(T.hdcm_tool_hash(b, lw * 4, lw * 4, lh))
    l0 = T.hdcm_tool_hash(a.ctypes.data_as(ctypes.c_char_p), W * 4, W * 4, H)
    hdr = bytearray(b"HDCMSC02")
    hdr += th.to_bytes(4, "little") + ph.to_bytes(4, "little")
    hdr += nw.to_bytes(2, "little") + nh.to_bytes(2, "little") + s.to_bytes(2, "little") + L.to_bytes(2, "little")
    hdr += W.to_bytes(4, "little") + H.to_bytes(4, "little") + l0.to_bytes(8, "little")
    flags = 1 | (2 if (a[..., 3] == 0).any() else 0)          # R1 verified | v4 has-cutout (bound by the level-0 hash)
    hdr += (nw * nh).to_bytes(4, "little") + flags.to_bytes(4, "little")
    hdr += sum(len(x) for x in levels).to_bytes(8, "little")
    for i in range(6):
        hdr += (hashes[i] if i < L else 0).to_bytes(8, "little")
    assert len(hdr) == T.hdcm_tool_header_bytes() == 104
    body = bytes(hdr) + bytes(ncls.astype(np.uint8).ravel()) + b"".join(levels)
    sh = T.hdcm_tool_hash(body, len(body), len(body), 1)
    return body + sh.to_bytes(8, "little"), l0, levels


def rg_bytes(T, th, ph, nw, nh, hw, hh, flags, l0, magic=b"HDCMRG01"):
    """v5 HDCMRG01 (48 bytes): magic, key, native dims, HD dims, flags, level-0 hash, self-hash over bytes 0..39.
    Written here independently of the C test writer (make_rg); only the hash function is shared."""
    b = magic + th.to_bytes(4, "little") + ph.to_bytes(4, "little") + nw.to_bytes(2, "little") + nh.to_bytes(2, "little")
    b += hw.to_bytes(4, "little") + hh.to_bytes(4, "little") + flags.to_bytes(4, "little") + l0.to_bytes(8, "little")
    assert len(b) == 40
    return b + T.hdcm_tool_hash(b, 40, 40, 1).to_bytes(8, "little")


def write_rg(T, th, ph, nw, nh, a, flags=None):
    """HDCMRG01 for decoded level 0 `a`: the level-0 identity is the runtime's own HDCM-X4 (hdcm_rgb_level0); the
    has-cutout flag is numpy's truth (the round trip then proves the runtime agrees)."""
    H, W = a.shape[:2]
    a = np.ascontiguousarray(a)
    l0 = T.hdcm_tool_rgb_level0(a.ctypes.data, W * 4, W, H, None)
    f = (1 if (a[..., 3] == 0).any() else 0) if flags is None else flags
    return rg_bytes(T, th, ph, nw, nh, W, H, f, l0), l0


def make_caps_dir(T, d, valid_key, valid_blob):
    """The read-cap directory (glue_harness.c run_rgb 'rgbcaps' contract, 300 index lines): 1 valid, 49-byte file,
    1 MiB file (both start with a VALID sidecar of their own key, so only the pre-read size check rejects them),
    missing file, a file holding another key's sidecar, duplicate of the valid line, corrupt self-hash, unknown flag,
    bad magic, bad scale, one garbage line, then 289 fake keys without files (only 256 lines may be consumed)."""
    d.mkdir()
    k = lambda i: (0xCA000000 + i, 0x5EED0000 + i)                          # noqa: E731
    name = lambda t: f"{t[0]:08X}-{t[1]:08X}"                               # noqa: E731
    ok = lambda t, **kw: rg_bytes(T, t[0], t[1], 64, 32, 1024, 512, kw.get("flags", 1), 0x0123456789ABCDEF)  # noqa: E731
    lines = [valid_key]
    (d / f"{valid_key}.hdrg").write_bytes(valid_blob)
    a, b, c, dd, e, f, g, hh, i = (k(n) for n in range(1, 10))
    (d / f"{name(a)}.hdrg").write_bytes(ok(a) + b"\0")                     # 49 bytes -> SIZE (never read)
    (d / f"{name(b)}.hdrg").write_bytes(ok(b) + bytes(1024 * 1024 - RG_BYTES))  # 1 MiB -> SIZE (never read)
    (d / f"{name(dd)}.hdrg").write_bytes(ok(e))                            # another key's sidecar -> KEY
    bad = bytearray(ok(f)); bad[44] ^= 1
    (d / f"{name(f)}.hdrg").write_bytes(bytes(bad))                        # SELFHASH
    (d / f"{name(g)}.hdrg").write_bytes(ok(g, flags=1 | 4))                # unknown flag bit -> FLAGS
    (d / f"{name(hh)}.hdrg").write_bytes(rg_bytes(T, hh[0], hh[1], 64, 32, 1024, 512, 1, 7, magic=b"HDCMRG02"))  # MAGIC
    (d / f"{name(i)}.hdrg").write_bytes(rg_bytes(T, i[0], i[1], 64, 32, 1000, 512, 1, 7))  # 1000 % 64 -> SCALE
    lines += [name(a), name(b), name(c), name(dd), valid_key, name(f), name(g), name(hh), name(i), "not-a-key line"]
    lines += [f"FA000000-{n:08X}" for n in range(289)]
    assert len(lines) == 300
    (d / "index.txt").write_text("".join(x + "\n" for x in lines), encoding="ascii")
    return dict(lines=len(lines), expect=dict(ok=1, SIZE=2, NOFILE=246, KEY=2, SELFHASH=1, FLAGS=1, MAGIC=1, SCALE=1,
                                              fopen=256, fread_bytes=7 * RG_BYTES))


def main():
    pin = below_normal()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "runs" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    inp = rd / "inputs"
    inp.mkdir()
    for p in (HERE / "hd_class_mips.inc", HERE / "test_hd_class_mips.c", HERE / "hdcm_tool.c", HERE / "glue_harness.c",
              HERE / "make_patch.py", Path(__file__), HERE / "DESIGN-V4.md", HERE / "DESIGN-V5.md", PROTO / "class_mip.c",
              PROTO / "class_mip.h"):
        shutil.copy2(p, inp / p.name)
    res = dict(run=stamp, pin=pin, inputs={p.name: sha(p) for p in sorted(inp.iterdir())}, steps={}, admit_list=ADMIT,
               stb_image=dict(path=str(STB_DIR / "stb_image.h"), sha256=sha(STB_DIR / "stb_image.h"), pinned=STB_SHA256),
               ab_result_sha256=sha(AB), census=dict(path=str(CENSUS), sha256=sha(CENSUS), fringe_min=RGB_FRINGE_MIN))

    def save():
        (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")

    save()
    # 1 fixtures
    exe = rd / "test_hd_class_mips.exe"
    rc, secs, out = run([CLANG, *CFLAGS, "-I", str(inp), str(inp / "test_hd_class_mips.c"), str(inp / "class_mip.c"),
                         "-o", str(exe)], rd / "fixtures-compile.log")
    st = dict(compile_rc=rc, compile_s=secs, warnings=out.count("warning:"))
    if rc == 0:
        rc2, secs2, out2 = run([str(exe)], rd / "fixtures-run.log")
        m = re.search(r"checks (\d+) failures (\d+)", out2)
        st.update(run_rc=rc2, run_s=secs2, checks=int(m.group(1)) if m else None, failures=int(m.group(2)) if m else None,
                  metrics=[l for l in out2.splitlines() if l.startswith("METRIC")], hash_vectors_match_python=check_vectors(out2))
    res["steps"]["1-fixtures"] = st
    save()

    # 2 mutants
    base = (inp / "hd_class_mips.inc").read_text(encoding="utf-8")
    muts = []
    for i, (label, old, new) in enumerate(MUTANTS):
        md = rd / "mutants" / f"m{i:02d}"
        md.mkdir(parents=True)
        if base.count(old) != 1:
            muts.append(dict(label=label, error=f"anchor count {base.count(old)}"))
            continue
        (md / "hd_class_mips.inc").write_text(base.replace(old, new), encoding="utf-8")
        shutil.copy2(inp / "test_hd_class_mips.c", md / "test_hd_class_mips.c")
        rc, _, out = run([CLANG, *CFLAGS, "-I", str(md), "-I", str(inp), str(md / "test_hd_class_mips.c"),
                          str(inp / "class_mip.c"), "-o", str(md / "t.exe")], md / "compile.log")
        if rc:
            muts.append(dict(label=label, error="mutant did not compile"))
            continue
        rc2, _, out2 = run([str(md / "t.exe")], md / "run.log")
        vec_ok = check_vectors(out2)
        first = next((l for l in out2.splitlines() if l.startswith("FAIL")), "")
        muts.append(dict(label=label, caught=rc2 != 0 or not vec_ok, by="test" if rc2 else ("hash vectors" if not vec_ok else ""),
                         first_failure=first[:200]))
    res["steps"]["2-mutants"] = dict(mutants=muts, caught=f"{sum(1 for x in muts if x.get('caught'))}/{len(MUTANTS)}")
    save()

    # 3 real pages
    tool_p, proto_p = rd / "hdcm_tool.dll", rd / "proto.dll"
    rct, _, _ = run([CLANG, "-shared", "-O3", "-std=c11", "-I", str(inp), "-I", str(STB_DIR), str(inp / "hdcm_tool.c"),
                     "-o", str(tool_p)], rd / "tool-dll.log")
    rcp, _, _ = run([CLANG, "-shared", "-O2", "-std=c11", str(inp / "class_mip.c"), "-o", str(proto_p)], rd / "proto-dll.log")
    res["steps"]["3-real"] = dict(tool_dll_rc=rct, proto_dll_rc=rcp)
    save()
    if rct or rcp:
        save()
        return 1
    T, P = ctypes.CDLL(str(tool_p)), ctypes.CDLL(str(proto_p))
    T.hdcm_tool_decode.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    T.hdcm_tool_hash.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    T.hdcm_tool_hash.restype = ctypes.c_uint64
    T.hdcm_tool_parse_admit.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    T.hdcm_tool_prepared_levels.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p]
    T.hdcm_tool_build_level.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_void_p]
    P.cm_build_level.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    T.hdcm_tool_rgb_parse_admit.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32,
                                            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_int),
                                            ctypes.POINTER(ctypes.c_double)]
    T.hdcm_tool_rgb_level0.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.c_int)]
    T.hdcm_tool_rgb_level0.restype = ctypes.c_uint64
    T.hdcm_tool_hash_speed.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    assert T.hdcm_tool_reasons() == len(REASONS)
    assert T.hdcm_tool_rgb_bytes() == RG_BYTES
    sys.path.insert(0, str(CM.parent / "class-audit"))
    import audit_native_classes_v2 as A  # noqa: E402
    regions = {}
    for line in (PACKROOT / "ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    order = [A.STOCK, A.UHU] + sorted(A.CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in A.E.glob("*/hd-on_rewind-off/*") if p.is_dir())

    def native_source(key):                             # identical lookup order to breakdown_v2b / f6_real_data_v2
        for d in ([PACKROOT] if key in regions else order):
            s, c = A.try_dump(d, key, regions)
            if s:
                return s, c
        if key not in regions:
            for d in cap_dirs:
                s, c = A.try_dump(d, key, regions)
                if s:
                    return s, c
        return None, None

    bd = json.loads(BREAKDOWN.read_text(encoding="utf-8"))
    bdrow = {(r["group"], r["key"]): r for g in bd["rows"].values() for r in g}
    targets = [(k, PACK / f"{k}.png", k, "pack") for k in ADMIT + NEG] + EXTRA
    pages, decoded = [], {}
    for label, png, key, grp in targets:
        raw = png.read_bytes()
        W, H = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        buf = np.zeros(W * H * 4, np.uint8)
        w_, h_ = ctypes.c_int(), ctypes.c_int()
        drc = T.hdcm_tool_decode(raw, len(raw), buf.ctypes.data, buf.nbytes, ctypes.byref(w_), ctypes.byref(h_))
        a = buf.reshape(H, W, 4)
        with Image.open(png) as im:
            pil = np.asarray(im.convert("RGBA"))
        src, cls = native_source(key)
        row = dict(label=label, key=key, group=grp, png=str(png), png_sha256=sha(png), size=[W, H], stb_rc=drc,
                   stb_equals_pil=bool(drc == 0 and np.array_equal(a, pil)), native_source=src["dir"] if src else None)
        del pil
        if src is None or drc:
            row["error"] = "no native dump" if src is None else "stb decode failed"
            pages.append(row)
            continue
        th_, tw_ = cls.shape
        s = W // tw_
        ncls = np.ascontiguousarray(cls, dtype=np.uint8)
        cen = a[s // 2::s, s // 2::s, 3]
        cen_cls = np.where(cen == 0, 0, np.where(cen >= 128, 255, 127)).astype(np.uint8)
        levels, build_ms = [], 0.0
        for L in range(1, s.bit_length()):
            lw, lh = W >> L, H >> L
            pa = np.zeros((lh, lw, 4), np.uint8)
            pb = np.zeros((lh, lw, 4), np.uint8)
            q = np.zeros(lw * lh, np.int32)
            dn = np.zeros(lw * lh, np.uint8)
            r1 = P.cm_build_level(a.ctypes.data, W, H, ncls.ctypes.data, tw_, th_, s, L, pa.ctypes.data)
            t0 = time.perf_counter()
            r2 = T.hdcm_tool_build_level(a.ctypes.data, W * 4, W, H, ncls.ctypes.data, tw_, th_, s, L, pb.ctypes.data,
                                         q.ctypes.data, dn.ctypes.data)
            build_ms += (time.perf_counter() - t0) * 1000
            levels.append(dict(L=L, equal=bool(np.array_equal(pa, pb)), proto_rc=r1, port_rc=r2))
        b = bdrow.get((grp, key), {})
        row.update(native=[tw_, th_], scale=s, r1_centre_vs_native_cells=int((cen_cls != ncls).sum()),
                   breakdown_status=b.get("status"), offline_build_ms_all_levels=round(build_ms, 2), levels=levels,
                   all_equal=all(x["equal"] and x["proto_rc"] == 0 and x["port_rc"] == 0 for x in levels))
        pages.append(row)
        decoded[key] = (a, ncls, s)
    res["steps"]["3-real"].update(pages=pages)
    save()

    # 4 sidecars (explicit ADMIT list only)
    sd = rd / "sidecars"
    sd.mkdir()
    side, index = [], []
    cache_bytes = 0
    for key in ADMIT:
        pr = next(p for p in pages if p["key"] == key)
        if key not in decoded or pr["r1_centre_vs_native_cells"] or pr.get("breakdown_status") != "PASS" or not pr["stb_equals_pil"]:
            side.append(dict(key=key, written=False, reason="not preverified (R1/breakdown/decoder)"))
            continue
        a, ncls, s = decoded[key]
        th, ph = (int(x, 16) for x in key.split("-"))
        blob, l0, lv = write_sc2(T, th, ph, a, ncls, s)
        f = sd / f"{key}.hdcm"
        f.write_bytes(blob)
        H, W = a.shape[:2]
        pms, ams = ctypes.c_double(), ctypes.c_double()
        rc = T.hdcm_tool_parse_admit(blob, len(blob), th, ph, ncls.shape[1], ncls.shape[0], a.ctypes.data, W * 4, W, H,
                                     ctypes.byref(pms), ctypes.byref(ams))
        prep = np.zeros(sum(len(x) for x in lv), np.uint8)
        n_up = T.hdcm_tool_prepared_levels(blob, len(blob), prep.ctypes.data)
        same_prep = n_up == len(lv) and prep.tobytes() == b"".join(lv)
        fits = len(index) < CACHE_MAX and cache_bytes + len(blob) <= PRELOAD_CAP
        if rc == 0 and fits:
            index.append(key)
            cache_bytes += len(blob)
        side.append(dict(key=key, written=True, path=str(f), sha256=sha(f), bytes=len(blob), native=[ncls.shape[1], ncls.shape[0]],
                         scale=s, levels=s.bit_length() - 1, level0_hash=f"{l0:016x}", round_trip=REASONS[rc],
                         preload_verify_ms=round(pms.value, 3), draw_thread_admit_ms=round(ams.value, 3),
                         prepared_bytes_equal_builder=bool(same_prep), in_index=bool(rc == 0 and fits)))
    (sd / "index.txt").write_text("".join(k + "\n" for k in index), encoding="ascii")
    neg = {}
    if all(k in decoded for k in NEG[:2]):
        (ga, gn, gs), (pa_, pn, ps) = decoded[NEG[0]], decoded[NEG[1]]
        th, ph = (int(x, 16) for x in NEG[0].split("-"))
        blob, _, _ = write_sc2(T, th, ph, ga, gn, gs)                        # in memory only, never admitted
        H, W = pa_.shape[:2]
        neg["o_green_sidecar_vs_pink_pixels"] = REASONS[T.hdcm_tool_parse_admit(blob, len(blob), th, ph, gn.shape[1], gn.shape[0],
                                                                                pa_.ctypes.data, W * 4, W, H, None, None)]
        th2, ph2 = (int(x, 16) for x in NEG[1].split("-"))
        neg["o_green_sidecar_for_pink_key"] = REASONS[T.hdcm_tool_parse_admit(blob, len(blob), th2, ph2, gn.shape[1], gn.shape[0],
                                                                              pa_.ctypes.data, W * 4, W, H, None, None)]
    if NEG[2] in decoded:
        a, ncls, s = decoded[NEG[2]]
        pr = next(p for p in pages if p["key"] == NEG[2])
        neg["rise_offline"] = ("REFUSED: R1 centre vs native mismatches %d" % pr["r1_centre_vs_native_cells"]
                               if pr["r1_centre_vs_native_cells"] else "would be written")
        blob, _, _ = write_sc2(T, 0x82831823, 0x06BDD2F5, a, ncls, s)       # falsely flagged R1-verified
        H, W = a.shape[:2]
        neg["rise_falsely_flagged_admission"] = REASONS[T.hdcm_tool_parse_admit(blob, len(blob), 0x82831823, 0x06BDD2F5,
                                                                                ncls.shape[1], ncls.shape[0], a.ctypes.data,
                                                                                W * 4, W, H, None, None)]
    res["steps"]["4-sidecars"] = dict(sidecars=side, index=index, index_bytes=cache_bytes, negatives=neg)
    (sd / "MANIFEST.json").write_text(json.dumps(dict(run=stamp, format="HDCMSC02 (hd_class_mips.inc)", index=index,
                                                      sidecars=side, negatives=neg,
                                                      status="PRIVATE; for the private v61 class-mip copy only"), indent=1) + "\n",
                                      encoding="utf-8")
    save()

    # 4b v5 RGB-only sidecars (HDCMRG01) for the reviewed census list
    cen = json.loads(CENSUS.read_text(encoding="utf-8"))
    rank = {x["key"]: x["mixed_footprints"] * x["fringe_mean"] for x in cen["rows"]
            if x.get("draw") == "mapped" and x.get("drawn_cells") and x.get("mixed_footprints")
            and x.get("fringe_mean", 0) >= RGB_FRINGE_MIN}
    rgb_list = sorted(rank, key=lambda k: (-rank[k], k))
    bdpack = {r["key"]: r for r in bd["rows"]["pack"]}
    rsd = rd / "sidecars-rgb"
    rsd.mkdir()
    rgb_rows, rgb_index = [], []
    for key in rgb_list:
        b = bdpack.get(key, {})
        png = Path(b.get("png", ""))
        row = dict(key=key, census_rank_score=round(rank[key], 1), class_admit=key in ADMIT, png=str(png))
        if not png.is_file() or "native" not in b:
            row.update(written=False, reason="no pack png / no CRC-proven native dims")
            rgb_rows.append(row)
            continue
        tw_, th_ = b["native"]
        raw = png.read_bytes()
        W, H = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        buf = np.zeros(W * H * 4, np.uint8)
        w_, h_ = ctypes.c_int(), ctypes.c_int()
        drc = T.hdcm_tool_decode(raw, len(raw), buf.ctypes.data, buf.nbytes, ctypes.byref(w_), ctypes.byref(h_))
        a = buf.reshape(H, W, 4)
        with Image.open(png) as im:
            pil = np.asarray(im.convert("RGBA"))
        eq = bool(drc == 0 and np.array_equal(a, pil))
        del pil
        row.update(png_sha256=sha(png), size=[W, H], native=[tw_, th_], stb_rc=drc, stb_equals_pil=eq)
        if drc or not eq or not tw_ or not th_ or W % tw_ or H % th_ or W // tw_ != H // th_ or tw_ > 256 or th_ > 256:
            row.update(written=False, reason="decoder mismatch or dims not an exact native scale")
            rgb_rows.append(row)
            continue
        thh, phh = (int(x, 16) for x in key.split("-"))
        blob, l0 = write_rg(T, thh, phh, tw_, th_, a)
        f = rsd / f"{key}.hdrg"
        f.write_bytes(blob)
        cut, ams = ctypes.c_int(), ctypes.c_double()
        rc = T.hdcm_tool_rgb_parse_admit(blob, len(blob), thh, phh, tw_, th_, a.ctypes.data, W * 4, W, H,
                                         ctypes.byref(cut), ctypes.byref(ams))
        in_idx = rc == 0 and len(rgb_index) < RG_CACHE_MAX
        if in_idx:
            rgb_index.append(key)
        s1, s4 = ctypes.c_double(), ctypes.c_double()
        T.hdcm_tool_hash_speed(a.ctypes.data, W * 4, W, H, 3, ctypes.byref(s1), ctypes.byref(s4))
        row.update(written=True, path=str(f), sha256=sha(f), bytes=len(blob), scale=W // tw_, level0_hash=f"{l0:016x}",
                   has_cutout_numpy=bool((a[..., 3] == 0).any()), has_cutout_runtime=bool(cut.value),
                   round_trip=REASONS[rc], draw_thread_admit_ms=round(ams.value, 3), in_index=in_idx,
                   hash_ms_single_chain_best3=round(s1.value, 3), hash_ms_x4_best3=round(s4.value, 3))
        rgb_rows.append(row)
        del a, buf
    (rsd / "index.txt").write_text("".join(k + "\n" for k in rgb_index), encoding="ascii")
    # the harness key: the highest-ranked admitted RGB-only key without a class sidecar
    k1 = next((k for k in rgb_index if k not in ADMIT), None)
    rneg, rdirs = {}, {}
    gd = rd / "glue"
    gd.mkdir()
    if k1:
        r1 = next(r for r in rgb_rows if r["key"] == k1)
        raw = Path(r1["png"]).read_bytes()
        W1, H1 = r1["size"]
        buf = np.zeros(W1 * H1 * 4, np.uint8)
        w_, h_ = ctypes.c_int(), ctypes.c_int()
        assert T.hdcm_tool_decode(raw, len(raw), buf.ctypes.data, buf.nbytes, ctypes.byref(w_), ctypes.byref(h_)) == 0
        a1 = buf.reshape(H1, W1, 4)
        (gd / "rgba-rgb.bin").write_bytes(a1.tobytes())
        th1, ph1 = (int(x, 16) for x in k1.split("-"))
        nw1, nh1 = r1["native"]
        good1 = (rsd / f"{k1}.hdrg").read_bytes()
        false1, _ = write_rg(T, th1, ph1, nw1, nh1, a1, flags=0)                # FALSE "opaque" claim
        rneg["false_opaque_claim"] = REASONS[T.hdcm_tool_rgb_parse_admit(false1, RG_BYTES, th1, ph1, nw1, nh1, a1.ctypes.data,
                                                                         W1 * 4, W1, H1, None, None)]
        a1[H1 // 2, W1 // 2, 0] ^= 1
        rneg["changed_pixel"] = REASONS[T.hdcm_tool_rgb_parse_admit(good1, RG_BYTES, th1, ph1, nw1, nh1, a1.ctypes.data,
                                                                    W1 * 4, W1, H1, None, None)]
        a1[H1 // 2, W1 // 2, 0] ^= 1
        rneg["wrong_key"] = REASONS[T.hdcm_tool_rgb_parse_admit(good1, RG_BYTES, th1, ph1 ^ 1, nw1, nh1, a1.ctypes.data,
                                                                W1 * 4, W1, H1, None, None)]
        rdirs["false"] = rd / "sidecars-rgb-false"
        rdirs["false"].mkdir()
        (rdirs["false"] / f"{k1}.hdrg").write_bytes(false1)
        (rdirs["false"] / "index.txt").write_text(k1 + "\n", encoding="ascii")
        rdirs["caps"] = rd / "sidecars-rgb-caps"
        caps = make_caps_dir(T, rdirs["caps"], k1, good1)
        if index and index[0] in decoded:                                       # both kinds: k1 + the class key
            ca, cn, cs = decoded[index[0]]
            tc, pc = (int(x, 16) for x in index[0].split("-"))
            cblob, _ = write_rg(T, tc, pc, cn.shape[1], cn.shape[0], ca)
            rdirs["both"] = rd / "sidecars-rgb-both"
            rdirs["both"].mkdir()
            (rdirs["both"] / f"{k1}.hdrg").write_bytes(good1)
            (rdirs["both"] / f"{index[0]}.hdrg").write_bytes(cblob)
            (rdirs["both"] / "index.txt").write_text(k1 + "\n" + index[0] + "\n", encoding="ascii")
        del a1, buf
    if NEG[0] in decoded:                                                        # verified fully-opaque entry
        ga, gn, gs = decoded[NEG[0]]
        tg, pg = (int(x, 16) for x in NEG[0].split("-"))
        oblob, _ = write_rg(T, tg, pg, gn.shape[1], gn.shape[0], ga)
        rneg["opaque_true_claim"] = REASONS[T.hdcm_tool_rgb_parse_admit(oblob, RG_BYTES, tg, pg, gn.shape[1], gn.shape[0],
                                                                        ga.ctypes.data, ga.shape[1] * 4, ga.shape[1],
                                                                        ga.shape[0], None, None)]
        fblob, _ = write_rg(T, tg, pg, gn.shape[1], gn.shape[0], ga, flags=1)   # FALSE "has cutout" claim
        rneg["false_has_cutout_claim"] = REASONS[T.hdcm_tool_rgb_parse_admit(fblob, RG_BYTES, tg, pg, gn.shape[1], gn.shape[0],
                                                                             ga.ctypes.data, ga.shape[1] * 4, ga.shape[1],
                                                                             ga.shape[0], None, None)]
        rdirs["opaque"] = rd / "sidecars-rgb-opaque"
        rdirs["opaque"].mkdir()
        (rdirs["opaque"] / f"{NEG[0]}.hdrg").write_bytes(oblob)
        (rdirs["opaque"] / "index.txt").write_text(NEG[0] + "\n", encoding="ascii")
    written = [r for r in rgb_rows if r.get("written")]
    speed = {}
    for r in written:
        speed.setdefault(f'{r["size"][0]}x{r["size"][1]}', []).append(r)
    speed = {k: dict(pages=len(v), mib=round(v[0]["size"][0] * v[0]["size"][1] * 4 / 2 ** 20, 1),
                     single_chain_ms_median=sorted(x["hash_ms_single_chain_best3"] for x in v)[len(v) // 2],
                     x4_ms_median=sorted(x["hash_ms_x4_best3"] for x in v)[len(v) // 2],
                     x4_ms_max=max(x["hash_ms_x4_best3"] for x in v),
                     admit_ms_median=sorted(x["draw_thread_admit_ms"] for x in v)[len(v) // 2])
             for k, v in sorted(speed.items(), key=lambda kv: -kv[1][0]["size"][0] * kv[1][0]["size"][1])}
    res["steps"]["4b-rgbonly"] = dict(hash_speed_by_size=speed,
        listed=len(rgb_list), written=len(written), in_index=len(rgb_index), harness_key=k1,
        overlap_with_class_admit=[r["key"] for r in rgb_rows if r["class_admit"]],
        all_round_trip_ok=all(r["round_trip"] == "OK" for r in written),
        cutout_truth_agrees=all(r["has_cutout_numpy"] == r["has_cutout_runtime"] for r in written),
        has_cutout=sum(1 for r in written if r["has_cutout_runtime"]), negatives=rneg,
        caps_dir=caps if k1 else None, rows=rgb_rows)
    (rsd / "MANIFEST.json").write_text(json.dumps(dict(run=stamp, format="HDCMRG01 (hd_class_mips.inc, v5 RGB-only)",
                                                       selection=f"census {CENSUS.parent.name}: draw mapped, drawn cells, "
                                                                 f"mixed footprints, fringe_mean >= {RGB_FRINGE_MIN}",
                                                       index=rgb_index, rows=rgb_rows,
                                                       status="PRIVATE; RGB edge renormalization only, no class/R1 authority"),
                                                  indent=1) + "\n", encoding="utf-8")
    save()

    # 5 the EXACT glue in a host harness (recording GL stubs)
    sys.path.insert(0, str(inp))
    import make_patch as MP  # noqa: E402  (the byte copy in inputs/)
    (gd / "glue.c").write_text(MP.GLUE, encoding="utf-8")
    shutil.copy2(inp / "glue_harness.c", gd / "glue_harness.c")
    rc, _, out = run([CLANG, *CFLAGS, "-Wno-unused-function", "-I", str(gd), "-I", str(inp), str(gd / "glue_harness.c"),
                      "-o", str(gd / "glue_harness.exe")], gd / "compile.log")
    gst = dict(compile_rc=rc, warnings=out.count("warning:"), glue_sha256=sha(gd / "glue.c"))
    import os
    env_base = {k: v for k, v in os.environ.items() if not k.startswith(("PSXRECOMP_HD_CLASS_MIPS", "PSXRECOMP_HD_RGB_EDGES"))}
    # opaque control: region-O green (fully opaque, has-cutout bit 0), its own one-entry sidecar dir
    od = rd / "sidecars-opaque-control"
    od.mkdir()
    ok_ctl = NEG[0] in decoded
    if ok_ctl:
        ga, gn, gs = decoded[NEG[0]]
        th, ph = (int(x, 16) for x in NEG[0].split("-"))
        blob, _, _ = write_sc2(T, th, ph, ga, gn, gs)
        (od / f"{NEG[0]}.hdcm").write_bytes(blob)
        (od / "index.txt").write_text(NEG[0] + "\n", encoding="ascii")
        (gd / "rgba-opaque.bin").write_bytes(ga.tobytes())
    gst["opaque_control_has_cutout_bit"] = bool(ok_ctl and (hdcm_flags(blob) & 2))

    def cases(k0):
        """(mode, control, args, env) for every harness case; the same list for the base build and every mutant."""
        a, ncls, s = decoded[k0]
        H, W = a.shape[:2]
        if not (gd / "rgba.bin").exists():
            (gd / "rgba.bin").write_bytes(a.tobytes())
        # the glue derives native width = upload_width_words * (4 >> depth); depth 2 (1 texel/word) with
        # words = native width reproduces it exactly for any page depth
        base_args = [str(gd / "rgba.bin"), str(W), str(H), k0.split("-")[0], k0.split("-")[1], str(ncls.shape[1]),
                     str(ncls.shape[0]), "2", str(ncls.shape[1]), str(s.bit_length() - 1), str(len(index))]
        want_rgb = "1" if (decoded[k0][0][..., 3] == 0).any() else "0"
        on = dict(PSXRECOMP_HD_CLASS_MIPS_DIR=str(sd))
        rgbd = dict(PSXRECOMP_HD_RGB_EDGES_DIR=str(rsd))
        out = [("off", "key", base_args + [want_rgb], dict(env_base)),
               ("badenv", "key", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_CLASS_MIPS="true", PSXRECOMP_HD_RGB_EDGES="0", **on)),
               ("on", "key", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_CLASS_MIPS="1", PSXRECOMP_HD_RGB_EDGES="1", **on)),
               # an RGB-only dir without PSXRECOMP_HD_RGB_EDGES=1 must stay unused
               ("levels", "key+rgbdir-env", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_CLASS_MIPS="1", **on, **rgbd)),
               ("rgb", "key", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_RGB_EDGES="1", **on))]
        if ok_ctl:
            ga, gn, gs = decoded[NEG[0]]
            oa = [str(gd / "rgba-opaque.bin"), str(ga.shape[1]), str(ga.shape[0]), NEG[0].split("-")[0], NEG[0].split("-")[1],
                  str(gn.shape[1]), str(gn.shape[0]), "2", str(gn.shape[1]), str(gs.bit_length() - 1), "1", "0"]
            out.append(("rgb", "opaque", oa, dict(env_base, PSXRECOMP_HD_RGB_EDGES="1", PSXRECOMP_HD_CLASS_MIPS_DIR=str(od))))
        # v5 env: everything disabled
        out += [("badenv", "rgb-true", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_RGB_EDGES="true", **rgbd)),
                ("badenv", "rgb-emptydir", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_RGB_EDGES="1", PSXRECOMP_HD_RGB_EDGES_DIR="")),
                ("badenv", "levels-rgbdir-only", base_args + [want_rgb], dict(env_base, PSXRECOMP_HD_CLASS_MIPS="1", **rgbd))]
        if k1:
            r1 = next(r for r in rgb_rows if r["key"] == k1)
            nw1, nh1 = r1["native"]
            k1a = [str(gd / "rgba-rgb.bin"), str(r1["size"][0]), str(r1["size"][1]), k1.split("-")[0], k1.split("-")[1],
                   str(nw1), str(nh1), "2", str(nw1)]
            cut1 = "1" if r1["has_cutout_runtime"] else "0"
            on1 = dict(env_base, PSXRECOMP_HD_RGB_EDGES="1")
            out += [("rgbdir", "census-list", k1a + [str(len(rgb_index)), cut1], dict(on1, **rgbd)),
                    ("rgbfalse", "false-opaque", k1a + ["1", cut1], dict(on1, PSXRECOMP_HD_RGB_EDGES_DIR=str(rdirs["false"]))),
                    ("rgbcaps", "read-caps", k1a + ["1", cut1], dict(on1, PSXRECOMP_HD_RGB_EDGES_DIR=str(rdirs["caps"])))]
            if "both" in rdirs:
                out.append(("both", "class+rgb", k1a + ["2", cut1, str(gd / "rgba.bin"), str(W), str(H), k0.split("-")[0],
                                                        k0.split("-")[1], str(ncls.shape[1]), str(ncls.shape[0]),
                                                        str(s.bit_length() - 1), str(len(index))],
                            dict(env_base, PSXRECOMP_HD_CLASS_MIPS="1", PSXRECOMP_HD_RGB_EDGES="1", **on,
                                 PSXRECOMP_HD_RGB_EDGES_DIR=str(rdirs["both"]))))
        if "opaque" in rdirs:
            ga, gn, gs = decoded[NEG[0]]
            out.append(("rgbopaque", "opaque-bypass",
                        [str(gd / "rgba-opaque.bin"), str(ga.shape[1]), str(ga.shape[0]), NEG[0].split("-")[0],
                         NEG[0].split("-")[1], str(gn.shape[1]), str(gn.shape[0]), "2", str(gn.shape[1]), "1", "0"],
                        dict(env_base, PSXRECOMP_HD_RGB_EDGES="1", PSXRECOMP_HD_RGB_EDGES_DIR=str(rdirs["opaque"]))))
        return out

    def run_cases(exe, tag):
        res_c = []
        for i, (mode, control, args, env) in enumerate(cases(index[0])):
            rc_c, _, o = run([str(exe), mode] + args, gd / f"{tag}-{i:02d}-{mode}-{control}.log", env=env)
            mm = re.search(r"checks (\d+) failures (\d+)", o)
            res_c.append(dict(mode=mode, control=control, rc=rc_c, checks=mm.group(0) if mm else None,
                              timing=[l for l in o.splitlines() if l.startswith("TIMING")],
                              preload=next((l for l in o.splitlines() if l.startswith("PRELOAD")), None),
                              first_failure=next((l for l in o.splitlines() if l.startswith("FAIL")), None)))
        return res_c

    if rc == 0 and index:
        gst["key"] = index[0]
        gst["rgb_key"] = k1
        gst["cases"] = run_cases(gd / "glue_harness.exe", "run")
        want_n = 5 + int(ok_ctl) + 3 + (3 + int("both" in rdirs) if k1 else 0) + int("opaque" in rdirs)
        gst["expected_cases"] = want_n
        gst["all_cases_pass"] = (all(c["rc"] == 0 for c in gst["cases"]) and len(gst["cases"]) == want_n
                                 and k1 is not None and "both" in rdirs and "opaque" in rdirs and ok_ctl)
        # glue mutants: each must make at least one case fail
        gm = []
        glue_src = (gd / "glue.c").read_text(encoding="utf-8")
        for j, (label, old, new) in enumerate(GLUE_MUTANTS):
            md = gd / "mutants" / f"g{j:02d}"
            md.mkdir(parents=True)
            if glue_src.count(old) != 1:
                gm.append(dict(label=label, error=f"anchor count {glue_src.count(old)}"))
                continue
            (md / "glue.c").write_text(glue_src.replace(old, new), encoding="utf-8")
            shutil.copy2(gd / "glue_harness.c", md / "glue_harness.c")
            rcm, _, _ = run([CLANG, *CFLAGS, "-Wno-unused-function", "-I", str(md), "-I", str(inp), str(md / "glue_harness.c"),
                             "-o", str(md / "h.exe")], md / "compile.log")
            if rcm:
                gm.append(dict(label=label, error="mutant did not compile"))
                continue
            rr = run_cases(md / "h.exe", f"mutants/g{j:02d}/case")
            gm.append(dict(label=label, caught=any(c["rc"] != 0 for c in rr),
                           failing_cases=[f'{c["mode"]}/{c["control"]}' for c in rr if c["rc"] != 0]))
        gst["glue_mutants"] = gm
        gst["glue_mutants_caught"] = f"{sum(1 for x in gm if x.get('caught'))}/{len(GLUE_MUTANTS)}"
    res["steps"]["5-glue"] = gst
    save()

    # 6 patch
    raw = MP.V61_SRC.read_bytes()
    st = dict(v61_src=str(MP.V61_SRC), v61_sha256=hashlib.sha256(raw).hexdigest(), pinned=MP.V61_SHA256)
    try:
        assert st["v61_sha256"] == MP.V61_SHA256, "v61 renderer hash changed"
        patched, receipts = MP.patch(raw.decode("utf-8"))
        pd = rd / "patched"
        pd.mkdir()
        (pd / "gpu_gl_renderer.c").write_bytes(patched.encode("utf-8"))
        shutil.copy2(inp / "hd_class_mips.inc", pd / "hd_class_mips.inc")
        cd = rd / "control"
        cd.mkdir()
        (cd / "gpu_gl_renderer.c").write_bytes(raw)
        st.update(ok=True, receipts=receipts, patched_sha256=sha(pd / "gpu_gl_renderer.c"),
                  lines_in=raw.count(b"\n"), lines_out=patched.count("\n"), pure_addition=True,
                  crlf_preserved=patched.count("\r\n") == patched.count("\n"))
    except AssertionError as e:
        st.update(ok=False, error=str(e))
    res["steps"]["6-patch"] = st
    save()
    if not st.get("ok"):
        return 1

    # 7 compile-only (exact v61 flags) control + patched; builder absent from the patched preprocessed TU
    b = json.loads((V61 / "build.json").read_text(encoding="utf-8"))
    rcmd = next(c for c in b["commands"] if c["label"] == "compile-gpu_gl_renderer.c")
    cmd, ccwd = rcmd["arguments"], rcmd.get("cwd") or "C:/github/Einhander"
    comp, pre = {}, {}
    for which in ("control", "patched"):
        src = rd / which / "gpu_gl_renderer.c"
        a = list(cmd)
        a[a.index("-MF") + 1] = str(rd / which / "gpu_gl_renderer.c.obj.d")
        a[a.index("-c") + 1] = str(src)
        a[a.index("-o") + 1] = str(rd / which / "gpu_gl_renderer.c.obj")
        rc, secs, out = run(a, rd / which / "compile.log", cwd=ccwd)
        lines = [l for l in out.splitlines() if "warning:" in l]
        kinds = sorted(set(re.sub(r"^.*?:\d+:\d+: ", "", l) for l in lines))
        comp[which] = dict(rc=rc, seconds=secs, warnings=len(lines), warning_kinds=kinds[:60],
                           obj_sha256=sha(rd / which / "gpu_gl_renderer.c.obj") if rc == 0 else None)
        e = [x for x in cmd if x != "-MD"]
        e = [x for i, x in enumerate(e) if not (i > 0 and e[i - 1] in ("-MF", "-o"))]
        e = [x for x in e if x not in ("-MF", "-o")]
        i = e.index("-c")
        e[i:i + 2] = ["-E", "-P", str(src)]
        r = subprocess.run(e, capture_output=True, text=True, timeout=600, creationflags=0x4000, cwd=ccwd,
                           encoding="utf-8", errors="replace")
        (rd / which / "pre.i").write_text(r.stdout, encoding="utf-8")
        pre[which] = r.stdout
    comp["new_warning_kinds"] = sorted(set(comp["patched"]["warning_kinds"]) - set(comp["control"]["warning_kinds"]))
    comp["builder_in_patched_tu"] = "hdcm_build_level" in pre["patched"] or "hdcm_fill_cutout_rgb" in pre["patched"]
    comp["glue_in_patched_tu"] = "hd_class_mips_admit_slot" in pre["patched"] and "hd_class_mips_preload" in pre["patched"]
    res["steps"]["7-compile"] = comp
    save()

    # 8 GLSL
    gl = {}
    esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}
    for which in ("control", "patched"):
        m = re.search(r"static const char \*HD_FS\s*=\s*((?:\s*\"(?:[^\"\\]|\\.)*\")+)\s*;", pre[which])
        if not m:
            gl[which] = dict(error="HD_FS not found in preprocessed output")
            continue
        parts = re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1))
        glsl = "".join(re.sub(r"\\(.)", lambda mm: esc.get(mm.group(1), mm.group(0)), p) for p in parts)
        frag = rd / which / "HD_FS.frag"
        frag.write_text(glsl, encoding="utf-8")
        rc, secs, out = run([GLSLANG, "-S", "frag", str(frag)], rd / which / "glslang.log")
        gl[which] = dict(rc=rc, frag_sha256=sha(frag), lines=glsl.count("\n"), errors=out.count("ERROR"),
                         has_class_levels="u_hd_class_levels" in glsl, output=out.strip()[-600:])
    res["steps"]["8-glsl"] = gl

    f = res["steps"]
    g = f["5-glue"]
    checks = dict(
        fixtures=f["1-fixtures"].get("run_rc") == 0 and f["1-fixtures"].get("hash_vectors_match_python") is True,
        mutants=f["2-mutants"]["caught"] == f"{len(MUTANTS)}/{len(MUTANTS)}",
        real=all(p.get("all_equal") and p.get("stb_equals_pil") for p in f["3-real"]["pages"] if "error" not in p)
        and not any("error" in p for p in f["3-real"]["pages"]),
        sidecars=len(f["4-sidecars"]["index"]) >= 1 and all(s.get("round_trip") == "OK" and s.get("prepared_bytes_equal_builder")
                                                            for s in f["4-sidecars"]["sidecars"] if s.get("written"))
        and f["4-sidecars"]["negatives"].get("o_green_sidecar_vs_pink_pixels") == "LEVEL0"
        and f["4-sidecars"]["negatives"].get("o_green_sidecar_for_pink_key") == "KEY"
        and f["4-sidecars"]["negatives"].get("rise_falsely_flagged_admission") == "R1",
        rgbonly=f["4b-rgbonly"]["listed"] == f["4b-rgbonly"]["written"] == f["4b-rgbonly"]["in_index"] >= 1
        and f["4b-rgbonly"]["all_round_trip_ok"] and f["4b-rgbonly"]["cutout_truth_agrees"]
        and all(r.get("stb_equals_pil") for r in f["4b-rgbonly"]["rows"])
        and f["4b-rgbonly"]["negatives"] == dict(false_opaque_claim="CUTOUT", changed_pixel="LEVEL0", wrong_key="KEY",
                                                 opaque_true_claim="OK", false_has_cutout_claim="CUTOUT"),
        glue=g.get("compile_rc") == 0 and g.get("all_cases_pass") is True
        and g.get("glue_mutants_caught") == f"{len(GLUE_MUTANTS)}/{len(GLUE_MUTANTS)}",
        patch=bool(f["6-patch"].get("ok")),
        compile=comp["patched"]["rc"] == 0 and comp["control"]["rc"] == 0 and not comp["new_warning_kinds"]
        and not comp["builder_in_patched_tu"] and comp["glue_in_patched_tu"],
        glsl=gl.get("patched", {}).get("rc") == 0 and gl.get("control", {}).get("rc") == 0)
    res["checks"] = checks
    res["verdict"] = "pass" if all(checks.values()) else "FAIL"
    save()
    with open(HERE / "runs" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, verdict=res["verdict"], checks=checks, result_sha256=sha(rd / "result.json"))) + "\n")
    print(json.dumps(dict(verdict=res["verdict"], checks=checks), indent=1))
    return 0 if res["verdict"] == "pass" else 1          # exit code follows the verdict


if __name__ == "__main__":
    sys.exit(main())
