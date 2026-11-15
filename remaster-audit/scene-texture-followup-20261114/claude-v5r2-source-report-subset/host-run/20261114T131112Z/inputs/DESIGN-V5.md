# Private opt-in RGB-only sidecars on the frozen v61 renderer: design v5 (claude-einhander, 2026-11-14)

This builds on `DESIGN-V4.md` and `DESIGN-V3.md`, which are unchanged. **Frozen v4 is preserved exactly.** v5 follows
root's approval in msg_040f69ea (option a, CPU only).

v5 adds a **separate, identity-bound, RGB-only sidecar kind** (`HDCMRG01`). It lets the reviewed v4 RGB-edge
renormalization reach drawn keys that have no class sidecar. It carries **no class or R1 authority**: art that fails R1
is still a defect and still needs re-authoring (RISE, for example).

## Scope: why a second kind
- The census (`runs-census/20261114T114657Z`, sha256 406ef8fb…) found 136 drawn keys with a lod-0 fringe_mean ≥ 8, and
  101 of them ≥ 32.
- Of those 101, 59 fail R1. They can never hold a class sidecar, and v4 confined RGB edges to class-sidecar keys.
- **The RGB-only kind verifies only what RGB edges need:**
  - the key;
  - the native dims;
  - the HD dims;
  - the exact decoded level-0 hash;
  - the has-cutout truth.
- **It never uploads a level.** Alpha, STP, discard, the point path and the native edge path are not touched. Class
  sampling stays exactly v61/v4.

## Opt-ins: default OFF, exactly "1"
| Environment | Effect |
|---|---|
| `PSXRECOMP_HD_CLASS_MIPS=1` + `PSXRECOMP_HD_CLASS_MIPS_DIR` | prepared class levels (v3) |
| `PSXRECOMP_HD_RGB_EDGES=1` + `PSXRECOMP_HD_CLASS_MIPS_DIR` | RGB edges for class-sidecar keys (v4, has-cutout bit) |
| `PSXRECOMP_HD_RGB_EDGES=1` + `PSXRECOMP_HD_RGB_EDGES_DIR` | **v5:** RGB edges for keys listed in the RGB-only dir |

- Any other value ("true", "0") or an empty or unset directory leaves the feature off. This is tested.
- An RGB-only directory without `PSXRECOMP_HD_RGB_EDGES=1` is never opened. That holds even when class levels are on
  (tested).
- **Precedence:** a key with a class sidecar always uses it, so class authority comes first. A class sidecar that fails
  admission leaves the slot on the original v61 path and **never falls back** to an RGB-only entry (tested, and a
  mutant proves it). RGB-only entries apply only to keys that have no class sidecar.

## Format HDCMRG01 (exactly 48 bytes, little endian)
| Offset | Field |
|---|---|
| 0 | magic `HDCMRG01` |
| 8 | texture hash |
| 12 | palette hash |
| 16 | native width (u16) |
| 18 | native height (u16) |
| 20 | HD width |
| 24 | HD height |
| 28 | flags (bit 0 = has cutout; any other bit is rejected) |
| 32 | level-0 identity: **HDCM-X4** of the stb-decoded RGBA (`hdcm_rgb_level0`) |
| 40 | self-hash over bytes 0–39 (`hdcm_hash64`) |

### Level-0 identity HDCM-X4 (why not `hdcm_hash64`)
- **Run 1 (`runs/20261114T122214Z`) used the class kind's `hdcm_hash64`.** That is one serial multiply chain, measured
  on the real pages at -O3 at about 2.9 GB/s.
  - First-build admission on the draw thread cost a median 20.7 ms for 4096² pages (7 keys) and 5.6 ms for 2048²
    (46 keys).
  - v61 decodes asynchronously, so this hash would have been the largest new hitch. Run 1 is kept as superseded
    (`FAILED-RUNS.md`).
- **The spec of HDCM-X4:**
  - The seed is `hdcm_hash64`'s seed xor the tag "RGONLY01", which keeps it a separate domain.
  - Four lanes are seeded with `seed ^ k·0xD6E8FEB86659FD93`.
  - In every row, 8-byte little-endian word j (an odd-width tail texel is zero-padded) is mixed into lane j mod 4 with
    the same per-word mix.
  - The lanes are folded 1, 2, 3 into lane 0, then finalized.
- It is still an exact 64-bit identity of every byte of level 0, in one pass that also finds the cutout truth.
- **Run 2 (`runs/20261114T123131Z`) measured no gain on real pages,** and found why (kept as superseded):
  - `hdcm_rd64` read byte by byte, and clang only merged that into one load when the dimensions were compile-time
    constants;
  - the per-word alpha test cost as much as the hash.
- **Run 3 fixes both:**
  - `hdcm_rd64` is a single little-endian 8-byte load (same value; the byte loop remains for other hosts);
  - the alpha test is branchless. Both alpha bytes are shifted to bytes 0 and 4 and 0xFF is added, so bit 8/40 is set
    exactly when that alpha is non-zero; these are AND-ed over all words. The odd tail texel is tested directly.
- **Scratch benchmark, real decoded pages, run-time dims, -O3, best of 7:**

| Page | X4 + cutout | `hdcm_hash64` alone (one chain, no cutout scan) |
|---|---|---|
| 4096² | 4.5 ms | 12.7 ms |
| 2048² | 1.05 ms | 3.2 ms |
| 512² | 0.06 ms | — |

  - Run 1's admission path cost about 20.7 ms cold at 4096².
  - Run 3 records the per-page numbers itself (`hash_speed_by_size`, best of 3, plus the cold admit time).
- **Two independent references check it:** a naive word-by-word C reference in the tests (14 widths, padded strides,
  cutout in each word position) and a pure-Python reference (hash vectors).

- **Parse rejects:**
  - SIZE: the length is not exactly 48;
  - MAGIC;
  - SELFHASH;
  - SCALE: zero dims, native dims above 256, HD dims above 8192, a non-integer scale or unequal x and y scales;
  - FLAGS: unknown bits.

## Runtime
- **Preload** runs at renderer init, in the same place as v3 (`hd_facade_motion_init`, before gameplay).
  - It reads `<rgb dir>/index.txt` and consumes at most `HDCM_RG_CACHE_MAX` (256) lines.
  - Each `<KEY>.hdrg` must be exactly 48 bytes. This is checked by fseek/ftell **before** reading, into a fixed stack
    buffer, so larger files are never read.
  - `hdcm_rgb_cache_add` verifies the entry and that the key named in the file matches the index line, and rejects
    duplicates.
  - Entries are copied into fixed static storage (256 × 40 bytes): **no heap at all.**
  - Rejections are counted per reason in `rgbonly_preload_rejected[]`.
- **Draw-time admission** happens once, after `hd_tex_object()` uploads level 0 on the non-resident path. It costs one
  cache lookup and one pass over the live decode, which yields the identity hash and the cutout scan together
  (`hdcm_hash64_cutout`, equal to `hdcm_hash64` by test).
  - It checks the key, the native dims (derived from the live upload exactly as for class sidecars), the HD dims (both
    the decode's and the slot's) and level 0.
  - The has-cutout flag must equal the pixels. A false "opaque" claim and a false "has cutout" claim are both rejected
    as `CUTOUT`.
  - It makes **no GL call, no allocation and no file access** (counted in the harness).
  - A verified fully-opaque entry **bypasses**: `rgb_edges` stays 0 and no extra fetches are made.
  - Rejections are counted in `rgbonly_rejected[]`. The slot stays on the original path.
- **Sampling:** `hd_class_mips_sampling` sets `u_hd_rgb_edges = 1` only for flagged slots, in filter mode only.
  `u_hd_class_levels` stays 0 and no filter is changed. HD_FS is **byte-identical to v4**, so the shader takes v4's
  level-0 branch (class levels 0, facade off), and root's v4 GPU self-test covers the shader.
- **Slot recycle:** v61 `hd_tex_release_slot` memsets the slot, and the next build re-admits from the verified cache
  (tested).
- **Counters:** `gl_renderer_class_mips_counters` returns 13 head values, then four reason tables, each `HDCM_REASONS`
  long, in this order:
  - head values: preload_ok, preload_bytes, preload_ticks, attempted, admitted, levels_uploaded, bytes, ticks,
    rgb_edge_slots, rgb_opaque_skipped, rgbonly_preload_ok, rgbonly_admitted, rgbonly_opaque_bypass;
  - reason tables: class preload, class draw, RGB-only preload, RGB-only draw.
- No printing; no fprintf.

## The explicit list (no auto-broadening)
- **Selection:** census rows with `draw == "mapped"`, drawn cells, mixed footprints and `fringe_mean ≥ 8`.
- **Ordering:** by mixed_footprints × fringe_mean.
- **Per key:**
  - the pack PNG is decoded by the runtime's stb_image (sha 866095d4…, PNG only, no stdio), and the decode must equal
    PIL;
  - the native dims come from the CRC-proven dumps (breakdown_v2b rows);
  - the scale must be exact;
  - the 48 bytes are written by an independent Python writer (`rg_bytes`; the C test uses its own `make_rg`), sharing
    only the hash function;
  - each entry is round-tripped through the runtime parse and admit.
- Keys on the class ADMIT list stay in the RGB-only list but are listed separately, because the class sidecar wins.

## Tests (host run `runs/<UTC>`, exit code follows the verdict)
**Fixtures, `test_hd_class_mips.c` → `rgb_only()`:**
- `hdcm_hash64x4_cutout` equals the naive X4 reference, and its cutout truth equals a naive scan. This covers 14 widths
  (every row-tail shape), padded strides (padding never hashed) and a cutout texel in each word position and the
  odd-width tail. It always differs from `hdcm_hash64` (domain);
- parse and admit OK;
- every reject reason (SIZE ±1, MAGIC, SELFHASH, FLAGS, SCALE ×2, KEY, NATIVE_DIMS, HD_DIMS, LEVEL0, CUTOUT for a false
  opaque and for a false has-cutout);
- an opaque page with flag 0 is admitted;
- the cache: 256 entries then ALLOC, find, duplicate, key mismatch, corrupt entry, len+1.

**Real data, step 4b:** all 136 keys written and round-tripped. In-memory negatives:
- false opaque → CUTOUT;
- changed pixel → LEVEL0;
- wrong key → KEY;
- opaque region-O true claim → OK;
- false has-cutout → CUTOUT.

**Glue harness** (the exact GLUE text, recording GL stubs, counted heap and file calls):
- **v4 modes, unchanged contract:**
  - each mode also checks that no allocation or file access happens on the draw path;
  - slot recycle;
  - the RGB-only state is never used;
  - an RGB-only dir set without `RGB_EDGES=1` is not opened.
- **v5 badenv:** RGB `"true"`, an empty dir, and class levels with only an RGB dir all stay disabled, and nothing is
  opened.
- **`rgbdir`** (the 136-key dir):
  - preload I/O is exact: 1 + N opens, N × 48 bytes, no heap;
  - admission sets the flag with no GL call;
  - uniforms are correct per filter mode;
  - once per slot, and slot recycle;
  - negatives: LEVEL0, NOFILE (the class table is not charged), HD_DIMS, NATIVE_DIMS;
  - experiment slots are untouched;
  - no draw-path I/O.
- **`rgbopaque`:** bypass, uniform 0.
- **`rgbfalse`:** a false opaque claim is rejected as CUTOUT.
- **`rgbcaps`** (300-line crafted dir):
  - exactly 256 lines consumed;
  - ok 1, SIZE 2 (a 49-byte file and a 1 MiB file, **neither read**, although both begin with a valid entry),
    NOFILE 246, KEY 2 (wrong file, duplicate), SELFHASH 1, FLAGS 1, MAGIC 1, SCALE 1;
  - 256 opens, 7 × 48 bytes read.
- **`both`** (class dir + RGB dir holding an RGB-only entry for the class key too):
  - the class key gets class levels plus its class has-cutout flag, and the RGB-only counters do not move;
  - a class LEVEL0 rejection does not fall back;
  - the RGB-only key still uses its RGB-only entry, with no level.

**Mutants:** 24 of the runtime `.inc` and 12 of the glue, each of which must fail. They cover:
- skipped self-hash, flags, size, scale, native dims, identity and cutout truth;
- one-sided cutout checks;
- the cutout scan missing the 2nd texel, the carry, the main groups, whole tail words or the odd tail texel;
- X4: lanes swapped, tail word to the wrong lane, a lane dropped from the fold, equal lane seeds, the domain tag
  dropped, the stride ignored;
- cache cap, duplicates, key mismatch, find ignoring the palette;
- precedence inverted, fallback after a class rejection;
- the RGB dir used without `RGB_EDGES=1`;
- reading before the size check, no line cap;
- a GL call, a per-draw file read, a per-draw allocation;
- no slot-dims check, native dims taken from the sidecar.

Three v4 `.inc` mutant anchors became ambiguous because `hdcm_hash64_cutout` and the RGB cache repeat lines. Their
anchors were extended with context; the mutations are the same.

## Limits
- The admitted list is the census list as reviewed. Live qualification is root's: the live census, binary, cache and
  GPU checks. That includes whether every listed key's live upload derives the same native dims; if not, admission
  rejects it as NATIVE_DIMS and counts it (fail closed).
- RGB edges change only edge-fragment RGB. They do not repair class geometry: failed-R1 art remains a defect.
- Keys with a class sidecar keep v4 behaviour.
