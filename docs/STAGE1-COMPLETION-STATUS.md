# Stage 1 completion status

November 13, 2026. **The remaster and Stage 1 release are incomplete.**

The latest private Wave 3 composition contains 837 authored entries in 1,669
keys. All 226 native region checks pass. It combines the new Astraea hulls and
32 canopy phases, scoped Gunpod cells, approved sign revisions, three canyon
wall/band bindings and revised HUD/results glyphs. The [live Astraea test](STAGE1-WAVE3-RESULTS.md)
positively submitted all five new hull bindings and all 32 canopy phases, with
448 authored entries submitted overall. It closed cleanly after 180 seconds,
without a stage clear. The canyon windows need a brighter revision under native
vertex shading, and the new HUD/results font was not exercised. Greif v2 failed an independent transparency check and is
excluded pending correction. Another 157 historical HUD fade aliases still lack
captured palette bytes and remain unresolved.

The newer [Wave 2 gameplay test](STAGE1-WAVE2-RESULTS.md) exercised a 723-entry,
1,559-key private composition. All 219 native region checks passed, and the
corrected sampled log submitted 375 authored entries. The revised HUD, fire/smoke, Continue
and evaluation screens have actual captures. With survival assistance off, the
controller lost all remaining lives; no stage clear was established. The whole
276-second observation averaged 55.55 guest frames/s and still accumulated
output-starved sample frames. A separate one-credit, visually verified Continue
route passed and resumed gameplay, then stopped at the next prompt under its
bounded limit. The legacy blind revival inputs are not used for acceptance.

A following Mk.III composition has 729 authored entries in 1,562 keys and passes
220 native region checks. It adds two verified hulls, two recovered native strips,
one exact mechanical-cell binding and a strip-cell overlay that preserves nearby
HUD pixels. The [Mk.III live test](STAGE1-MK3-RESULTS.md) positively submitted all
six new bindings and closed after 180 seconds with two lives remaining. Pose,
palette and material acceptance remains open. A longer ordinary-input stage
attempt ended after 810 seconds and five visually verified native Continues,
without a stage clear. A following 180-second upper-lane experiment verified
one Continue but exposed downward movement drift; its replacement uses fresh
source-matched hull geometry for finite controller pulses. A separate v18 run
positively recorded the authored SPREADER strip being submitted; missing sampled
receipts in the earlier run did not establish an admission failure.

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

A preceding private composition contains 559 delivered artwork entries in a
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
confirming it. Revised respawn handling was exercised in the Wave 2 run but
also ended at Continue; full-stage qualification remains open. Native fighter references for Mk.III and Astraea have
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
