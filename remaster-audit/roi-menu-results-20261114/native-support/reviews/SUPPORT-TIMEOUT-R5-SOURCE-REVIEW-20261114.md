# Timeout-profile r5: read-only source re-review (claude-einhander-support, 2026-11-14 ~16:31Z)

- Task: EIN-SUPPORT-TIMEOUT-VERIFY-20261114.
- Scope: source reading only. The r5 suite has NOT been run, by s67 or by support. The replay is held behind root's
  fenced modern-GPU probe (msg_ec2f161d, msg_d524afb0).
- Predecessor review: SUPPORT-TIMEOUT-R4-REVIEW-20261114.md (b8a508ec…).

## Inputs (sha256)

**r5** (`remaster-audit/parallel-stages-20261114/s67/tooling/timeout-profile/`):
- validate_timeout_leg.py: 49dcfc3a3a71741bae4fec3be87f5fa5e649c1ac4c4d253f3849b18602e43fd5
- test_timeout_leg.py: 9e12f47c5d257de40888f3cf8758aa295fc0faaaa63e812b6ae3f17ad7bd0484
- r4-to-r5-validator.diff: c3a80935b5eedfed9921f71f7d7c4f333d6770808aca4cc0ed369513d0d51408
- r4-to-r5-tests.diff: 7cd695b0986deed31e4d25251d6c8ce868569854a0718b996a8b2a0cb7e4b194

**r4 preserved in r4/, unchanged**:
- validator b36c7ef6…
- test 06d33f25…
- results dfef2bd7…
- README ee778f8b…

## The fixes match the runtime

**F1** (declared_rect, rect_crc, drawn_rows; validator:105-176):
- There is no default rect.
- native_page: requires depth 0/1/2 and width_words = 64<<depth, or a declared narrowed multiple of 64 in [64, full).
  The CRC is over width x 256 with the runtime's &511/&1023 wrap. This matches hd_page_hash_width in hd_native_page.h:68-96.
- upload: the CRC is over the declared x,y,w,h, as in hd_texture_pack.cpp:1340-1385.
- The claimed TEX must appear in a draw row, and the row's source_kind, native_words, page and depth must agree with the
  declared rect. The renderer emits exactly these fields:
  - native_words = [upload_width_words, upload_height] (hd_research_renderer.h:115);
  - for native pages that is [page_w, 256] (gpu_gl_renderer.c:3851).

**F2** (validator:226-233):
- Mark rows come only from capture logs in the event file's own directory.
- That directory must contain no logs or more than one row: either fails closed. Exactly one row is required.

**F4** (validator:207-208, 234-238):
- Reserved bytes 88..95 must be zero.
- The row's host_mono_ms and its gpu_dirty / pending / pack_dirty / dual flags must equal the header.
- mark_rows now extracts those fields (validator:94-98).

**F3**: stays fail-closed, as agreed.

## Optional, low (none blocks r5)

- **a.** The upload branch of drawn_rows does not compare the row's source_word_xy with the declared x,y. Content equality
  is already proven by the CRC, so this is binding hardening only.
- **b.** No test controls these cases, although the code checks them:
  - pending_cpu_upload_rects or cpu_authority_dual row mismatches (only gpu_dirty and pack_dirty are tested);
  - an upload rect that does not overlap the page;
  - an upload declared but drawn only as a native page.
- **c.** The upload overlap test uses the 4bpp footprint (64 words). That is documented, and it is right for the 4bpp
  narration page.
- **d.** README.md is still r4 (mtime before r5). It needs the r5 entry once results exist.

## Addendum ~16:35Z: what source_word_xy means at runtime (s67 asked, msg_c831c786)

- **It is not the upload's VRAM origin.** It is the word/row offset INSIDE the upload (or exact region) of the draw's
  first texel.
- **Upload path** (hd_texture_pack.cpp:1548-1561 and 1630-1642):
  - first_x = (page_x + u_first / ppw) & 1023, where ppw = 4 >> depth (hd_texture_pack.h:16: 4BPP = 0).
  - first_y = (page_y + v_first) & 511.
  - The fragment that contains that point gives source_word_x = fragment.source_x + first_x - fragment.rect.x, and the same
    for source_y.
  - covered_by_upload runs first (:1535, :1616), so a matched row always has its first texel inside a fragment.
- **Exact-region path** (:885-886): page_x + u_first/(4>>depth) - region_x, and the same for y. This is also
  region-relative.
- **Native-page rows**: the field is not set. m is memset to 0 (gpu_gl_renderer.c:3848), so it carries no information.
- **The row's own fields** (hd_research_renderer.h:115): source_word_xy = [m->source_word_x, m->source_y];
  uv_bounds = [u_first, v_first, u_last, v_last]; page_xy; depth.
- **The correct origin check** for upload and exact_region rows:
  - origin_x = (page_x + u_first // (4 >> depth) - source_word_x) mod 1024;
  - origin_y = (page_y + v_first - source_y) mod 512;
  - require (origin_x, origin_y) == the declared (x, y).
  - A direct `source_word_xy == declared x,y` compare would wrongly reject valid evidence.

## Not done

- No execution.
- The 25 cases at test lines 324-350 (r4 and r5 snapshot controls) and the full suite are unverified until the granted replay.
