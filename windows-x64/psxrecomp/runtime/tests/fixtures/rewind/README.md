# Rewind media-signal fixtures

These traces contain frame/cycle counts and XA, display-depth and MDEC signals,
not disc, BIOS, image, audio or guest instruction bytes.

- `rec_stage1_gameplay_xa.trace`: observed `fmv_state` and `gpu_state` during
  `normal2-rewind-on-v2`, a 120-second assisted Stage 1 gameplay window after
  the native City gate. XA music remains active without movie decoding.
- `rec_boot_intro_movie.trace`: boot observation and media counters from the
  same local diagnostic series; the intro was skipped after 21 decodes.
  Display depth is inferred for this trace, not directly polled.

The test compiles the real rewind unit, MDEC and snapshot ring. Hardware edges,
snapshot safety and serialization are controlled stubs; this tests selection
and accounting, not actual full-machine snapshot restore or audio quality.
Synthetic silent/15-bit/24-bit movies, texture decodes, static screens and CD
stalls are separately labelled inside the test.
