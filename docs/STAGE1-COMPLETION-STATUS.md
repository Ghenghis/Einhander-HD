# Stage 1 completion status

November 12, 2026. **The remaster and Stage 1 release are incomplete.**

The [matched 24-room facade footage](H24-IN-GAME-RESULTS.md) remains the published
visual result. Its disclosed timer-assisted private run does not establish an
unassisted stage clear or production installation.

Current verified work includes stock-menu routing fixtures, per-vertex UV draw
receipts, a private Robin controller run without RAM writes, and native source
verification for 373 captured texture/CLUT pairs. The source run needed one
recorded bot restart after a startup read timeout. Later native play reached the
night skyline and facade section using ordinary controller input. Stage clear
has not been established.

A private world composition now contains 207 delivered artwork entries alongside
the existing pack, including the authored wall and tunnel window band. All 219 exact-region bindings passed the production source
matcher, and nine sky word/CLUT pairs passed CRC and SHA checks. It uses the
current immutable sign revisions and retains input-manifest snapshots. This is
registration evidence, not live visual acceptance. The frozen artwork's documented
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

The position controller's old render-vector address was transient. Ordinary-input
calibrations in the opening City and night section agree at a different integer
coordinate pair, but that pair also failed live qualification. Position mode is
experimental and is not the default acceptance route. Eight behavior checks pass,
including refusing Continue input when revival is disabled; full-stage route
qualification remains pending. A failed bot run reached native results naturally;
that is end-state evidence, not a stage clear.

Runtime diagnostics show substantial HD/rewind overhead and audio starvation.
Disabling GPU timer queries did not restore sustained normal cadence. The scoped
filtering experiment passes synthetic and production-draw GL checks, but its early
live comparison never activated the target textures. No filtering speed improvement
is claimed, and the experiment remains disabled by default.

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
