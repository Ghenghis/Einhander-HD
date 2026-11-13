# Stage 1 runtime results

November 12, 2026. The performance and audio release gates remain open.

The later [723-entry Wave 2 observation](STAGE1-WAVE2-RESULTS.md) used v17 with
batching on, CPU/GPU attribution off, rewind off, source capture and NVENC video.
Its complete 276-second interval averaged 55.55 guest frames/s and accumulated
962,902 output-starved sample frames. That interval includes Continue and results
after the unassisted controller lost all lives; it does not measure a complete
stage or qualify recorder-off pacing/audio.

CPU attribution in an early City scene measured 18,284 ms in replacement draw
submission out of 21,316 ms total HD processing over a 60-second run. Source
matching used 1,930 ms and decode queue/acquire calls 16 ms; there were no
readbacks during that interval. Worker-thread PNG time is excluded, and nested
timers overlap. These findings describe that scene, not the whole game.

The private renderer can batch adjacent opaque replacement triangles with
matching resources and state. Its fixed buffer holds at most 256 primitives.
Native draws, blend/mask changes, source changes, cache eviction, material
changes, coherency operations and presentation flush the pending work. Actual
GL submission receipts are emitted after drawing. Semi-transparent, wide-mode
and framebuffer-edge replacement paths retain immediate submission.

`PSXRECOMP_HD_OPAQUE_BATCH=1` enables the experiment; it is disabled by default.
No installed runtime or normal launcher has been promoted by these tests.

The latest private build passed 33 native region checks, 21 hull-observer
checks, nine watchdog checks and the Windows suspended-thread diagnostic
regression. Real OpenGL runs passed 680 and 682 checks, including byte-identical
framebuffers with batching off/on across overlap, UV limits, native interleaving,
semi-transparency, masks, uploads, copies, live material changes, perspective,
capacity, eviction and readback boundaries. Exact-region draws were compared
at both framebuffer origins. The route/GPU guard checks passed 30 tests and
Robin/devtools checks passed 38 tests.

Actual City runs used the same binary within each pair, the same frozen artwork,
rewind off, turbo off, no video recorder, no survival aid or RAM writes, GPU
timer queries off and CPU attribution on. They targeted 1,800 guest frames,
sampled once per second; overshoot and ordinary play make them different scene
runs rather than identical replays.

- V14: batching off **53.44**, on **56.91** guest frames/s. Output-starved sample
  frames increased by 175,468 and 76,336 respectively.
- V16: off **40.60**, on **57.66** guest frames/s. Output-starved sample frames
  increased by 693,362 and 56,503. A host sample found art export, application
  and antivirus CPU load. A settled causal cadence gain is not claimed from
  this pair; a coordinated quieter repeat is pending.

These audio counters count sample frames needing output, not audible gaps.
Both pairs reached native gameplay and closed cleanly. Neither proves sustained
60 fps, full-stage pacing, audio acceptance or a production release. The later
redundant draw-state skip counter stayed zero in live play, so it has no claimed
performance benefit. [Machine-readable measurements](media/gallery/stage1-runtime-results.json)
retain the build hashes and measured deltas.

A later authoring-only source-cache fix addresses incomplete native dumps after
VRAM overwrites: an explicit raw-CRC shortlist retains requested original upload
bytes without unrelated LRU churn. Fourteen parser/bounds checks and the updated
684/686-check GL suites pass. A fresh ordinary-input Mk.III run recovered both
`DB715733-E0AE221F` and `B24C6DA2-E0AE221F` with all 512 words, matching source
and CLUT CRCs, and independently decoded PNG pixels. No missing words were
inferred. The old partial captures remain rejected; this proves the two requested
sources, not every source in the targeted run. No cadence gain is claimed from
this capture-only change.
