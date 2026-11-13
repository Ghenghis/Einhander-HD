# Stage 1 completion status

November 12, 2026. **The remaster and Stage 1 release are incomplete.**

The latest [assembled facade footage](H24-IN-GAME-RESULTS.md) uses the 559-entry,
1,492-key candidate. Its disclosed timer-assisted private run submitted 368
authored entries, including all ten delivered building tiles, the wall/tunnel
band, the delivered Mk.II hull entries, some Gunpod entries and all five enemy
page groups. The continuous
49.6-second excerpt preserves actual packet content and timing. A telemetry
bracket containing both facade mappings averaged 59.93 guest frames/s with no
audio-starvation increment. The full recording averaged 59.21 and still recorded
starvation; full-stage pacing/audio, art acceptance and installation remain open.

Current verified work includes stock-menu routing fixtures, per-vertex UV draw
receipts, a private Robin controller run without RAM writes, and native source
verification for 373 captured texture/CLUT pairs. The source run needed one
recorded bot restart after a startup read timeout. Later native play reached the
night skyline and facade section using ordinary controller input. Stage clear
has not been established.

A newer private composition now contains 559 delivered artwork entries in a
1,492-key pack, adding the latest sky, native-style menu set, Mk.II hulls, three
Gunpod families and five enemy page groups. The 311 added actor source pairs
passed native word/CLUT CRC checks. Predicted strip uploads retain their
unobserved labels; 19 transparent null palettes stay native.
All 219 exact-region bindings passed the production source
matcher, and nine sky word/CLUT pairs passed CRC and SHA checks. It uses the
current immutable sign revisions and retains input-manifest snapshots. This is
registration evidence; those latest additions still need live acceptance. The frozen artwork's documented
defects remain open. Lamp/flare sprites that were only baseline upscales were not
counted as newly authored. A private runtime now accepts overlapping VRAM regions
at different texture depths, with both interpretations tested; conflicts at the
same depth remain rejected.

Two runtime diagnostic defects were found during cold boot: concurrent heartbeat
sampling could underflow the watchdog age, and stack reporting could leave the
main thread suspended while waiting for its locks. The private fix uses atomic
timestamp snapshots and resumes the target before stack walking/symbol lookup.
Nine timestamp checks and a real Windows lock-owning-thread regression pass.
The four-second watchdog remains enabled. The combined runtime has reached native
gameplay and closed cleanly. Repeat boot/route and full-stage verification remain
in progress; failed launches remain excluded. One route missed the title while a
process identity check ran; that check now precedes boot observation.

Both RAM position candidates failed live qualification and were removed from
the controller. A read-only Mk.II source-matched hull observer now publishes
completed-frame bounds. Its native live attempt ended at Continue without
confirming it; bounded respawn handling has since been revised and still needs
full-stage qualification. Native fighter references for Mk.III and Astraea have
also been captured. Alternate selection requires a distinct label match after
each finite down input; a failed match cannot confirm the craft. A closed Mk.III
run supplied 890 verified native source pairs; two incomplete validity maps were
excluded. Its actual gameplay ended at Continue. Astraea's revised route verified
both distinct ARM slots, reached native City, then Continue and Total Evaluation.
Its closed run supplied 900 verified source pairs with one incomplete dump
excluded, including a previously missing interface key. These separate runs
overlap in source content and do not establish a stage clear.
A subsequent targeted Mk.III capture recovered both formerly incomplete strips
with all 512 native words and independently verified pixels. The original
incomplete receipts remain preserved and excluded.

Runtime diagnostics show substantial HD/rewind overhead and audio starvation.
Disabling GPU timer queries did not restore sustained normal cadence. The scoped
filtering experiment passes synthetic and production-draw GL checks, but its early
live comparison never activated the target textures. No filtering speed improvement
is claimed, and the experiment remains disabled by default.

An independent [opaque draw-batching experiment](STAGE1-RUNTIME-RESULTS.md)
passes 680/682 real-GL checks with pixel-identical comparison scenes. An early
same-binary pair measured 53.44 guest frames/s with batching off and 56.91 on.
A later pair measured 40.60 off and 57.66 on while host CPU load differed.
Neither establishes sustained 60 fps or resolved audio starvation. The feature
remains opt-in and uninstalled; a quieter repeated comparison is pending.

Remaining release work:

- Resolve runtime pacing/audio and verify efficient texture/palette handling.
- Integrate and review the remaining sky, buildings, windows, roads, lights and
  sign phases, including known geometry, lettering and motion defects.
- Complete and verify actual player, Gunpod, enemy, boss and effect textures.
- Finish native-style title/menu/HUD work and the missing interface states.
- Qualify Robin through the boss and stage clear with invincibility off; verify
  death, Continue, restart, results, save/load and a separate Game Over run.
- Reconcile one frozen pack, install a versioned build with rollback, then test
  the normal launcher and publish actual footage/stills with their limitations.

Later stages, alternate craft/loadouts, unlocks and end states remain in the full
remaster scope after this immediate Stage 1 milestone. Texture counts are not
completion percentages. The installed HD launcher still needs the reconciled
release; private candidates must not be presented as that installation.
