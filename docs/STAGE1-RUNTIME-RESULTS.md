# Stage 1 runtime results

November 12, 2026. The performance and audio release gates remain open.

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
at both framebuffer origins. The route/GPU guard checks passed 29 tests and
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
