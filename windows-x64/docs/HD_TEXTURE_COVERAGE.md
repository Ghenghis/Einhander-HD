# Stage 1 HD textures — November 12, 2026

Run `C:/github/Einhander/windows-x64/Play-HD.cmd` for the local HD option.
It selects `hd-textures/stage1-v1`, enables native-page fallback, and keeps the
CPU decode cache at 256 MiB. Its environment changes last only for that launch.
The regular executable continues to use the existing settings. A persisted
`[video] hd_textures = false` takes precedence over the launch environment.
`Play-HD.cmd --check` validates the launch paths without starting the game.
The previous executable is preserved at
`build-release/backups/20261112-hd-coverage/Einhander_Recompiled.exe`.
`C:/github/REMASTER_STAGING/hd-coverage/delivery.json` records the installed
binary, rollback and launcher hashes.

The pack contains 964 verified PNGs: 579 upload identities and 385 full-page
identities. Of these, 311 contain neural restoration and 653 preserve native
pixel art at a larger size. Text, effects, palette cycling and PS1 transparency
classes require those conservative entries. Replacement coverage must not be
reported as the proportion of the image containing new neural detail.

## Runtime change

Full-page replacements cover draws that span several small native uploads.
Their identity includes the native page CRC and live palette CRC. Texture
windows, framebuffer pages, wrapped framebuffer overlap, self-referencing
draws and unsafe CLUT overlap continue through the native renderer.

The renderer also previously requested CPU decoding before every replacement
draw, even if the GPU already owned that texture. CPU cache eviction therefore
made an otherwise usable GPU texture disappear temporarily and caused repeated
decodes. The renderer now checks its independent GPU LRU first. Each key uses
the same uploaded replacement until GPU eviction or process restart. Editing
pack files requires restarting the game.

## Measured coverage

Each result is a separate 120-second, stationary Cross+Square Stage 1 route
with isolated lives/invulnerability assists and no user cards. These are
observed routes with different starting frames and frame rates, not an exact
frame replay. The measure counts textured-triangle replacement queries, not
visible pixels or neural detail. Counter snapshots are published every 120
guest frames, so the reported counter-window boundaries are quantized.

- Upload-only baseline: 440,473 of 2,274,099 queries, **19.37%**.
- Page fallback with the old cache path: 1,264,979 of 2,054,703, **61.57%**.
- Larger 512 MiB CPU cache: 1,541,256 of 1,921,803, **80.20%**.
- Page fallback plus GPU reuse, original 256 MiB budget: 1,672,771 of
  1,902,921, **87.91%**.

In the final coverage window, 1,293,454 draws used full-page replacements and
379,317 used upload replacements. There were 5,922 decode waits (0.31% of
queries), 207,447 unavailable replacement queries (10.90%), and 16,781 source
matching misses (0.88%). Unavailable includes absent, ambiguous, failed or
over-budget entries; it is not itself proof that every such file is missing.
The key receipts separately identify absent pack keys, including palette
variants. They include menus and later samples as well as the coverage window.

Evidence is under `C:/github/REMASTER_STAGING/hd-coverage/`:
`coverage-report.json` collects raw counters and observed missing keys;
each named run retains its captures, receipts and `coverage-summary.json`.
The early page-fallback receipt log reached its old 1,024-record cap, so its
distinct-key counts are incomplete. The final log has a 4,096-record bound.

## Verification

- All 964 packaged PNGs matched the recorded SHA256 values before and after
  copying into the local pack.
- All 385 page sources passed independent native decode, raw/CLUT CRC,
  source/output SHA256 and exact transparency/STP class checks. Conservative
  RGB and 91 protected lettering rectangles also matched.
- `python remaster-audit/run_vram_coherence.py --hd-cache` passed 18 real-GL
  checks across normal and CPU-authority modes. It evicts the CPU image,
  disables further decoding, checks exact GPU pixels and continued replacement
  draws, checks a different source identity, then verifies GPU eviction recovery.
  The pre-fix renderer fails four of these checks.
- `python remaster-audit/run_vram_coherence.py` passed all 24 native VRAM and
  polyline-parser checks after the cache change.
- The native-page coherence fixture passed all 61 checks.

The instrumented 4x post-route sample measured 55.48 FPS, p95 23 ms, and no GL
errors. The earlier fallback sample measured 48.39 FPS in a different scene.
Those samples do not establish a controlled speedup. Normal-use 2x pacing is
measured separately without per-primitive receipt logging. Three 10-second
windows at 1920-wide/2x measured 52.25, 56.57 and 59.69 presented FPS, with
p95 intervals of 26, 21 and 19 ms and zero GL-error events. The first window's
maximum interval was 93 ms. The HD option is therefore opt-in; it does not
promise locked 60 FPS. See `hd-coverage/delivery-2x/evidence/` for raw rings
and timings. These samples include low-rate debug writes for the isolated
gameplay assists; no screenshots were taken inside a measurement window.

## Remaining work

Prioritize absent page/palette variants from the final receipt list, then
capture the stage boss, continue/respawn and later stages. New neural artwork
still needs scene-specific visual review; increasing the replacement query
ratio alone does not improve all visible texture detail. This pass validates
bounded Stage 1 routes and does not claim complete-stage or full-game coverage.
