# View provenance v2: per-primitive census, TCP control and MAC-overflow metadata (claude-einhander, 2026-11-14)

**Status: private candidate source, host-tested.**
- Canonical runtime files were read only, never written.
- The delivered v1 folder (`../impl`) is unchanged; v2 imports its edit lists from the hash-pinned v1 generator.
- Not built into a game, not run in-game, no live coverage measured.
- Not ray tracing and not a Remix backend.
- **Default OFF:** nothing is allocated and no hook does work until the census is armed.

This answers Codex's msg_9eabf5c84a0f3ff2 (opt-in independence, MAC overflow) and msg_a1d476554fb161fb (TCP control and
stats, textured-primitive consumer coverage with geometry correction off, per-triangle/quad hits and miss reasons,
independent commit/liveness checks, host regression tests).

## Files (`remaster-audit/runtime-review/remix-provenance/impl-v2/`)
| File | sha256 | Diff vs canonical |
|---|---|---|
| `make_view_provenance_v2_patch.py` (generator) | 5e7fe501…8940 | |
| `src/gte.cpp` | 1d676058…4216 | 146 lines |
| `src/pgxp.cpp` | c46cbe4f…087b | 448 |
| `include/pgxp.h` | a9b65872…108e | 206 |
| `src/gpu.c` | 0175da5b…215c | 93 |
| `include/gpu.h` | 2403a6ba…f405 | 15 |
| `src/debug_server.c` | 6942a1ef…6bc6e | 117 |
| `src/pgxp_view_census.cpp` (**new TU**: add it to the runtime sources next to `pgxp.cpp`) | ab91ed31…4b0 | new |
| `tests/test_pgxp_view_v2.cpp`, `tests/gpu_census_harness.c`, `run_host_test_v2.py` | 1f4ce34e… / 7f1d2766… / 7c18b7e6… | |
| `host-test-v2.json`, `tcp-replies.json`, `patch-receipt.json` | f42fdb66… / 3efcee7d… / a1f7234f… | |

Bases are hash-asserted against canonical:
- `gpu.c` 8eade36e…
- `gpu.h` f36519ed…
- `debug_server.c` 86ce765b…
- plus the v1 bases.

Outputs keep each base's CRLF and BOM, so they drop in. The `diffs/` are LF unified diffs.

(The delivered v1 outputs in `../impl/src` are LF-normalized; their diffs apply the same way.)

## What v2 adds
1. **MAC overflow metadata (gte.cpp producer).** Per axis:
   - `MACn_OVF44`: the raw `TR·4096 + RT·V` is outside the signed 44-bit accumulator range (≥ 2^43 or < −2^43).
   - `MACn_WRAP32`: `MAC >> sf·12` is outside int32, so the 32-bit MAC register, and IR from it, wrapped. For axis 3 with
     sf = 1 this is also the SZ path.
   - `PGXP_VIEW_NATIVE_DIVERGED` = IR_SAT | SZ_SAT | DIV_OVF | XY_SAT | XY_CLAMP | all OVF44 and WRAP32. When any of these is
     set, a pinhole re-projection of the payload must not be taken as the native vertex.
   - WS_SQUASH and DOME stay separate (deliberate screen-X changes).
   - The payload is still the exact int64.
   - I dropped a redundant axis-3 `>>12` clause: with sf = 0 the unshifted value wraps whenever its `>>12` view would, so the
     clause could never fire on its own.
2. **Miss reasons (pgxp.cpp).** `pgxp_get_precise_vertex_view_ex(addr, word, &view, &reason)` returns one of no_source
   (immediate GP0), disabled, no_shadow, value_mismatch, no_view, evicted or incoherent.
   - It is still DATAFLOW only and never uses the position cache.
   - The v1 entry point is now a wrapper.
   - New stat: `no_source`.
3. **Census (new `pgxp_view_census.cpp`).** For each textured triangle and each textured quad it records:
   - prims, all-hit, partial, none, verts and vert_hits, and **per-vertex miss reasons**;
   - `hit_committed` (the ring commit was validated);
   - `hit_ring_live` (an **independent re-check at draw time** through `gte_rtp_ring_seq_live`);
   - `hit_diverged`;
   - `all_hit_one_command` (every vertex committed from one RTPS/RTPT).
   - A lazily allocated ring of the newest 4,096 primitive records (frame, kind, hits, and per vertex: reason, lane, tag, view
     z). If its allocation fails the census runs on counters only; the failure is counted, never fatal.
4. **Census-only arming (gpu.c).**
   - `gpu_view_census_set(1)` enables the view payload, fails closed on allocation failure, and arms the PGXP transport
     **without touching geometry or texture correction**: `s_view_census` is ORed into `gpu_pgxp_rederive_enable()`.
   - `gpu_view_census_set(0)` re-derives the transport from the user's own geometry, texture and NCLIP modes. cpu_mode and
     tolerance are never touched.
   - Hooks:
     - every textured triangle, at the top of `prepare_texture_triangle` (covering textured, shaded-textured and quad halves);
     - every textured quad, in `gp0_exec_textured_quad` **before the rect fast path** and in
       `gp0_exec_shaded_textured_quad`.
   - The hooks read gp0 state only.
5. **TCP verb `pgxp_view` (debug_server.c).**
   - `{"cmd":"pgxp_view"}`: state (census, view_payload, pgxp_enabled, geometry_correction, texture_correction), the
     payload stats, ring info, and `triangles`/`quads` objects with a `miss` breakdown.
   - `"census":1|0` arms or disarms. `"reset":1` zeroes the counters. `"recent":N` returns up to 64 newest records, clamped.
   - No printf. One sample reply is in `tcp-replies.json`.

## Verification (`host-test-v2.json`; clang 22.1.8, below normal, one compiler at a time)
- **`view_v2_test`: 58/58 checks.**
  - It links the full v2 `gte.cpp` + `pgxp.cpp` + `pgxp_view_census.cpp` with debug tools on.
  - It also compiles the **actual code cut by anchor from the generated v2 `gpu.c`** (census arming, `gpu_pgxp_rederive_enable`,
    texture set/enabled, `s_texcorr`, `view_census_gp0`, `prepare_texture_triangle`) **and `debug_server.c`**
    (`handle_pgxp_view`, `json_get_int`).
  - Arming:
    - payload allocation failure fails closed;
    - census-ring allocation failure falls back to counters only;
    - armed → `pgxp_enabled` 1 with geometry 0 and texture 0;
    - disarmed → transport off with no user mode set; cpu_mode and tolerance preserved; with the user's texture correction
      on, disarming keeps the transport.
  - **Draws unchanged:** with the census on versus off, and with texture correction off and on, the renderer receives the
    same `gr_set_perspective_triangle` calls and arguments, and `s_texcorr` moves identically.
  - MAC boundaries:
    - 2^43 − 1 / 2^43 and −2^43 / −2^43 − 1 on axis 1;
    - the sf = 0 wrap at 2^31 − 1 / 2^31, with the same MAC under sf = 1 not wrapping;
    - axes 2 and 3;
    - a clean projection is not diverged.
  - Census classification: all-hit from one RTPT (3 committed and 3 ring-live), a mixed-command quad, value_mismatch (a
    different tracked word at the slot), an untracked store (no_shadow), a half write (no_view), an immediate word
    (no_source), an unwritten address, eviction after 64K projections, disabled, and newest-first records.
- **TCP:** 5 replies parsed as JSON and checked by the runner: armed state, all 7 miss keys, record_bytes 80, recent 5,
  recent 999 clamped to min(64, total), disarm, then re-arm + reset.
- **Regression:**
  - the delivered **v1 test passes 137/137 on the v2 sources**;
  - canonical `pgxp_test` and `gte_register_access_test` (no-debug-tools config) pass on the v2 sources.
- **Syntax:** `clang -fsyntax-only` with the real runtime compile argv (the v54 `build.json` template) on canonical and v2
  `gpu.c` and `debug_server.c`. Both exit 0, with **no new diagnostics** under build flags or `-Wall -Wextra`.
- **Mutants: 13/13 caught.**
  - MAC: 44-bit bound off by one; WRAP32 ignores sf; WRAP32 checks only the positive side.
  - Census: counts misses as hits; miss reason collapsed; one-command ignores the seq.
  - Consumer: immediate word reported as no_shadow.
  - Arming: census does not arm the transport; disarm does not re-derive the user's transport; allocation failure fails open.
  - Hook touches the renderer.
  - TCP: reset ignored; disarm ignored.

## Equivalent by construction (stated, not tested)
- `hit_ring_live < hit_committed` can only happen when a view outlives its GTE ring record. The view ring holds 64K records
  and the GTE ring 256K, so in this build a view is always evicted first. The draw-time re-check is a guard for future ring
  sizes; no mutant can distinguish it today.
- Toggling the census or the payload calls `pgxp_invalidate_all()`, so precise geometry loses one frame of precision at the
  toggle. That only matters if geometry correction is on at the same time.

## What it does NOT do
- No camera/object separation, no world space, no Remix submission, no ray tracing.
- Untextured (flat/gouraud) primitives, lines and sprites are not in the census yet.
- No live coverage in Einhänder is known. That needs a Codex leg:
  - build with these sources plus the PGXP hook flavour (G1.10);
  - `{"cmd":"pgxp_view","census":1,"reset":1}`, ordinary play, then read `triangles` and `quads`.

## Suggested live leg (Codex, when you choose)
1. Build a private runtime from these sources (add `src/pgxp_view_census.cpp`). Keep geometry correction and perspective
   texturing **off**.
2. Over TCP, send `pgxp_view` with `census:1` and `reset:1`. Sample at t = 10 s and t = 60 s, and fetch `recent:32` once.
3. The pass/fail evidence:
   - all_hit/prims for triangles and quads;
   - the miss-reason split (no_source = CPU-built UI; no_shadow / value_mismatch = provenance holes);
   - hit_committed equals vert_hits;
   - hit_diverged is small;
   - `geom_correction` shows geometry 0 and texcorr no_correction growing (draws untouched).
