#!/usr/bin/env python3
"""v6 decode-worker identity: anchored PURE-ADDITION patch of a NEW PRIVATE COPY of the v48 hd_texture_pack.cpp
(claude-einhander; root msg_26707276, rebased per msg_7755bd3a). BASE = the pinned READ-ONLY snapshot pack-base-v48/
(SNAPSHOT.json) of C:/github/Einhander-wt/upload-index-hitch/.../runtime: its hd_texture_pack.h equals the frozen v61
include header and it keeps the incremental-index API/stats (hd_texture_pack_upload_index_incremental,
index_incremental*, index_pointer_fixups) that the canonical source dropped. The canonical-based generator is kept as
make_pack_patch.canonical-base-REJECTED.py (sha bef13b3d...). Remaining limitation: v61 linked a RETAINED object; root
rebuilds this TU from the private copy and runs the pack regression/lifetime checks before any private link.

Behaviour of the patched copy:
  * PSXRECOMP_HD_DECODE_IDENTITY unset / != "1" (default): no new code runs in the decode path (one getenv at pack open);
    every pre-existing behaviour, mask and alpha unchanged; the accessor reports UNAVAILABLE.
  * == "1": the decode worker computes HDCM-X4 (the v5 RGB-only level-0 identity + has-cutout truth) over the decoded
    RGBA BEFORE the item is published Ready (outside the cache lock, on the below-normal worker thread) and stores it
    in that DecodedImage. Readers obtain it through a VALID acquired lease (shared_ptr to the immutable image), so the
    identity is bound to the exact pixel allocation it describes; re-decode after eviction creates a new image.
  * New C accessor hd_texture_pixels_identity (additive header hd_texture_identity.h): O(1); OK only if the image has
    an identity AND the caller's HdTexturePixels still points at that image's rgba with its width/height/stride;
    otherwise NO_LEASE / UNAVAILABLE / MISMATCH. It cannot validate a forged lease pointer (documented, not claimed).
  * Public HdTexturePixels and hd_texture_pack.h are unchanged; no output/printing added.
Generated alongside: hdcm_x4.h = the hdcm_rd64 + HDCM-X4 block extracted byte-for-byte from hd_class_mips.inc (one
source of truth; the patch run checks the extraction)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# root's frozen, fsynced, read-back-verified closure (BASELINE.json, msg_0be9e145); claude's own identical snapshot
# pack-base-v48/ (SNAPSHOT.json, same three hashes) is kept as a duplicate, not used
BASE = Path("C:/github/Einhander/remaster-audit/runtime-review/gpu-texture-remix-20261114/v6-pack-base-from-v48")
STB_SHA256 = "866095d4107665b4f2ac84e5aa25c7b4bd2f89c5408348c87fdec8891661cace"
PACK_SRC = BASE / "src/hd_texture_pack.cpp"
PACK_SHA256 = "22a97b569e4c3a3ffaff9fff90f37745d1eee92da97f321a1900b452cfee41cd"
PACK_H = BASE / "include/hd_texture_pack.h"        # == frozen v61 include/hd_texture_pack.h
PACK_H_SHA256 = "78234dfdbe4b574b6054b27a65d4cb64877420fa9e67488355542d547969c794"
QUEUE_H_SHA256 = "434b57a1e146c01ac02cb25a990c245e701196b5a3e7b9131e13a7f9941ee0fb"
ENV = "PSXRECOMP_HD_DECODE_IDENTITY"

IDENTITY_H = r'''#ifndef HD_TEXTURE_IDENTITY_H
#define HD_TEXTURE_IDENTITY_H
/* PRIVATE v6 additive header (claude-einhander; renderer-v61-classmip DESIGN-V6.md). hd_texture_pack.h and the public
 * HdTexturePixels are unchanged. With PSXRECOMP_HD_DECODE_IDENTITY=1 (exactly, read once at pack open) the decode
 * worker computes the HDCM-X4 level-0 identity and has-cutout truth of each decoded image before publishing it Ready.
 * hd_texture_pixels_identity returns them in O(1) for a VALID acquired lease whose rgba/width/height/stride still match
 * the leased image. It cannot validate a forged lease pointer. */
#include <stdint.h>
#include "hd_texture_pack.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {
    HD_TEXTURE_IDENTITY_OK = 0,
    HD_TEXTURE_IDENTITY_NO_LEASE = -1,      /* null pixels / no lease / no image */
    HD_TEXTURE_IDENTITY_UNAVAILABLE = -2,   /* identity mode off (or image decoded before it was enabled) */
    HD_TEXTURE_IDENTITY_MISMATCH = -3       /* rgba/width/height/stride differ from the leased image */
};
int hd_texture_pixels_identity(const HdTexturePixels* pixels, uint64_t* level0_x4, int* has_cutout);
#ifdef __cplusplus
}
#endif
#endif
'''

# (name, anchor, inserted text, position)
EDITS = [
    ("include",
     '#include "hd_decode_queue.h"\n',
     '#include "hd_texture_identity.h" /* PRIVATE v6 decode-worker identity */\n'
     '#include "hdcm_x4.h"             /* PRIVATE v6: HDCM-X4, extracted from hd_class_mips.inc */\n', "after"),
    ("image-fields",
     "struct DecodedImage {\n    std::vector<uint8_t> rgba;\n    std::vector<uint8_t> emissive;\n"
     "    uint32_t width = 0;\n    uint32_t height = 0;\n",
     "    /* PRIVATE v6: HDCM-X4 identity of rgba, written by the decode worker BEFORE Ready publication, then\n"
     "     * immutable (id_state 1 = computed). */\n"
     "    uint64_t id_x4 = 0;\n    uint8_t id_state = 0;\n    uint8_t id_has_cutout = 0;\n", "after"),
    ("cache-flag",
     "    bool emissive_enabled = false; /* immutable after pack construction */\n",
     "    bool identity_enabled = false; /* PRIVATE v6: immutable after pack construction */\n", "after"),
    ("worker-identity",
     "        if (loaded) stbi_image_free(loaded);\n",
     "        if (decoded && cache->identity_enabled) { /* PRIVATE v6: identity before Ready publication */\n"
     "            int cut = 0;\n"
     "            decoded->id_x4 = hdcm_hash64x4_cutout(decoded->rgba.data(), size_t(decoded->width) * 4u,\n"
     "                                                  decoded->width, decoded->height, &cut);\n"
     "            decoded->id_has_cutout = uint8_t(cut != 0);\n"
     "            decoded->id_state = 1;\n"
     "        }\n", "after"),
    ("open-env",
     '        pack->decode.emissive_enabled=emissive && std::strcmp(emissive,"1")==0;\n',
     f'        const char* identity=std::getenv("{ENV}"); /* PRIVATE v6, exactly "1" */\n'
     '        pack->decode.identity_enabled=identity && std::strcmp(identity,"1")==0;\n', "after"),
    ("accessor",
     "void hd_texture_pixels_release(HdTexturePixels* pixels) {\n    if (!pixels) return;\n"
     "    delete static_cast<PixelLease*>(pixels->lease);\n    std::memset(pixels, 0, sizeof(*pixels));\n}\n",
     "\n/* PRIVATE v6 (hd_texture_identity.h): O(1) identity of a VALID acquired lease's immutable image. */\n"
     "int hd_texture_pixels_identity(const HdTexturePixels* pixels, uint64_t* level0_x4, int* has_cutout) {\n"
     "    if (!pixels || !pixels->lease) return HD_TEXTURE_IDENTITY_NO_LEASE;\n"
     "    const DecodedImage* image = static_cast<const PixelLease*>(pixels->lease)->image.get();\n"
     "    if (!image) return HD_TEXTURE_IDENTITY_NO_LEASE;\n"
     "    if (image->id_state != 1) return HD_TEXTURE_IDENTITY_UNAVAILABLE;\n"
     "    if (pixels->rgba != image->rgba.data() || pixels->width != image->width ||\n"
     "        pixels->height != image->height || pixels->stride != image->width * 4u)\n"
     "        return HD_TEXTURE_IDENTITY_MISMATCH;\n"
     "    if (level0_x4) *level0_x4 = image->id_x4;\n"
     "    if (has_cutout) *has_cutout = image->id_has_cutout;\n"
     "    return HD_TEXTURE_IDENTITY_OK;\n"
     "}\n", "after"),
]

X4_BEGIN = "static uint64_t hdcm_rd64(const uint8_t *p) {\n"
X4_RD_END = "#endif\n}\n"
X4_BLOCK_BEGIN = "/* v5 RGB-only identity hash HDCM-X4"
X4_BLOCK_END = "    *has_cutout = cut | ((nz & HDCM_ABITS) != HDCM_ABITS);\n    return hsh;\n}\n"


def extract_x4(inc_text):
    """hdcm_rd64 + the HDCM-X4 block, byte-for-byte from hd_class_mips.inc (LF)."""
    a = inc_text.index(X4_BEGIN)
    b = inc_text.index(X4_RD_END, a) + len(X4_RD_END)
    c = inc_text.index(X4_BLOCK_BEGIN)
    d = inc_text.index(X4_BLOCK_END, c) + len(X4_BLOCK_END)
    assert inc_text.count(X4_BEGIN) == 1 and inc_text.count(X4_BLOCK_BEGIN) == 1 and inc_text.count(X4_BLOCK_END) == 1
    return inc_text[a:b], inc_text[c:d]


def x4_header(inc_text, inc_sha):
    rd, blk = extract_x4(inc_text)
    return ("#ifndef HDCM_X4_H\n#define HDCM_X4_H\n"
            f"/* GENERATED by make_pack_patch.py from hd_class_mips.inc (sha256 {inc_sha}): hdcm_rd64 + the HDCM-X4\n"
            " * level-0 identity, byte-for-byte (the renderer's hdcm_rgb_level0 is the same code). Do not edit. */\n"
            "#include <stddef.h>\n#include <stdint.h>\n#include <string.h>\n"
            + rd + blk + "#endif\n"), rd + blk


def edits_for(text):
    nl = "\r\n" if "\r\n" in text else "\n"
    return [(n, a.replace("\n", nl), i.replace("\n", nl), p) for n, a, i, p in EDITS]


def patch(text):
    """Return (patched_text, receipts); pure addition with unique anchors, else AssertionError."""
    out, receipts = text, []
    for name, anchor, ins, pos in edits_for(text):
        cnt = out.count(anchor)
        assert cnt == 1, f"anchor {name} occurs {cnt} times"
        at = out.index(anchor)
        where = at + len(anchor) if pos == "after" else at
        out = out[:where] + ins + out[where:]
        receipts.append(dict(name=name, offset=where, inserted_bytes=len(ins.encode("utf-8"))))
    back = out
    for name, anchor, ins, pos in edits_for(text):
        assert back.count(ins) >= 1, name
        back = back.replace(ins, "", 1)
    assert back == text, "not a pure addition"
    return out, receipts


def generate(out_dir):
    """Write the private copy + headers into out_dir; returns a receipt dict (all hashes)."""
    raw = PACK_SRC.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PACK_SHA256, "base hd_texture_pack.cpp changed"
    assert hashlib.sha256(PACK_H.read_bytes()).hexdigest() == PACK_H_SHA256, "base hd_texture_pack.h changed"
    assert hashlib.sha256((BASE / "src/hd_decode_queue.h").read_bytes()).hexdigest() == QUEUE_H_SHA256, "base queue changed"
    assert hashlib.sha256((BASE / "third_party/stb_image.h").read_bytes()).hexdigest() == STB_SHA256, "base stb changed"
    inc = (HERE / "hd_class_mips.inc").read_bytes()
    inc_sha = hashlib.sha256(inc).hexdigest()
    hdr, block = x4_header(inc.decode("utf-8"), inc_sha)
    patched, receipts = patch(raw.decode("utf-8"))
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "hd_texture_pack.cpp").write_bytes(patched.encode("utf-8"))
    (out_dir / "hd_texture_identity.h").write_text(IDENTITY_H, encoding="utf-8")
    (out_dir / "hdcm_x4.h").write_text(hdr, encoding="utf-8")
    rec = dict(base=dict(snapshot=str(BASE), cpp=str(PACK_SRC), cpp_sha256=PACK_SHA256, h=str(PACK_H), h_sha256=PACK_H_SHA256,
                         queue_h_sha256=QUEUE_H_SHA256,
                         limitation="v61 linked a retained hd_texture_pack object; this v48 snapshot keeps the v61 header "
                                    "and incremental-index API; root rebuilds the TU and runs the pack regression"),
               env=ENV, receipts=receipts, crlf=patched.count("\r\n") == patched.count("\n"),
               x4_extracted_from=dict(inc_sha256=inc_sha, bytes=len(block.encode("utf-8"))),
               files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out_dir.iterdir())})
    (out_dir / "receipts.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    return rec


if __name__ == "__main__":
    import datetime
    import sys
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    r = generate(HERE / "pack-v6" / stamp)
    print(json.dumps(r, indent=1))
    sys.exit(0)
