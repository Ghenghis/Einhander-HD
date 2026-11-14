# Stage 1 completion status

November 13, 2026. **The remaster and Stage 1 release are incomplete.**

The existing normal Play-HD binary, tested in a private copy with the installed
964-PNG pack, 256 MB decode budget, scale 2 and rewind 50/15, passes the
bounded boss timing check with only `PSX_DISPLAY_RING=0`: 350 consecutive
application frame submissions, p95 17 ms, longest 21 ms, no interval over 25 ms,
and zero new audio starvation across 120 seconds. Originals were re-hashed
unchanged; user cards were never mounted. Normal Play-HD, material and Development launches now disable continuous
forensic readback, with hashed rollback copies of the changed local files. No binary or artwork
was replaced. The former material binding still failed with 15,378 starved
output sample frames. A private saved-material test on the existing Play-HD
runtime and its own cache then passed: 60.0072 fps, zero new gameplay
starvation, 350 consecutive boss submissions and a longest interval of 20 ms.
Live reads confirmed both selected profiles, exact keys and active detail maps.
The local material receipt now selects that tested runtime, with rollback and
shared-settings backups. All three additional shortcut configurations pass
receipt checks; their other profile pairs and the real frontend path have not
yet been tested live. Existing cache shards and stages 2–7 remain unqualified.

The larger frozen artwork candidate remains separate and still fails:
39 boss uploads moved about 801 MiB, including 29 reuploads after eviction.
A private bounded-retention experiment removed all reuploads and reduced boss
traffic to 88 MiB, but had a 169 ms native VRAM upload-block stall. A repeat
with extra passive timing still had a 94 ms boss gap. Neither candidate is
installed. Exact native-call attribution and a buffered-upload experiment are
in progress; unassisted full-stage and listening acceptance remain open.

An [isolated default-off display-history fix](media/gallery/stage1-display-history-results.json)
now averages about 60 guest frames/s in the 350-frame mini-boss window, with zero
new audio starvation over two minutes. The profiler and an independent parser
agree: continuous diagnostic GPU readback took about 25.7% of the main thread
samples in the fight. In a same-binary OFF/ON comparison, disabling that history
measured 60.01 fight frames/s and zero starvation; re-enabling it measured 57.75
and 9,482 starved output sample frames. Earlier recorder-OFF tests still had
this forensic ring ON. An actual rebuilt default-unset runtime, without the
new collision/CPS or lock-free audio objects, measured 59.99 fight frames/s
and zero starvation with scale 2 and rewind depth 50/interval 15. One-shot
screenshots still work. Only one gameplay rewind snapshot was stored; most
rewind attempts were skipped as unsafe. These are assisted Stage 1 results:
the authorized hold writes the existing invincibility-countdown byte only,
with held fire and no stage jumps or state loads. Visible recording, unassisted
normal-launch acceptance and stages 2–7 remain pending. The final hardened
source build also averages about 60 in a recorded test with zero starvation,
but its passive swap ring shows seven intervals over 25 ms (longest 43 ms).
All 350 application frames were submitted once. Capture itself also missed
frames: the video is not a complete 60-fps stream. Fully even presentation
remains open. A repeat with the same final binary and no recorder submitted all
350 boss frames but still had eight intervals over 25 ms (longest 40 ms). It
averaged 60.00 fight frames/s, with zero boss starvation, but 310 sample frames
starved outside the boss at gameplay second 26 (frame 4631). Late intervals
again coincide with first-use
texture uploads; per-upload timing is being added to test that lead. The
recorder is therefore not required for the hitch. Normal-player results are
listed above. These experimental binaries are not installed. Exact 12-second callback excerpts are available for
[history OFF](media/gallery/stage1-display-history-off-boss.wav),
[history ON](media/gallery/stage1-display-history-on-boss.wav), and the
[rebuilt recorder-free runtime](media/gallery/stage1-display-history-v54-boss.wav).
They retain the original PCM; source offsets and hashes are in the report. The
[normal Play-HD excerpt](media/gallery/stage1-display-history-normal-playhd-boss.wav)
is also retained; subjective listening acceptance is pending.

The [guarded native collision comparison](media/gallery/stage1-native51-results.json)
completed with R4 and two leaf handlers qualified on the exact tested runtime.
The 350-frame fight window measured 55.66/56.02 frames/s with native code
OFF/ON; interpreted instructions fell from 38.54 to 36.46 million. Total
starved output sample frames were 22,864/17,262, with zero measured overflow
drops. Both still fail. This was one quiet ordered pair with the same binary,
held fire, timer assistance, scale 2 and rewind OFF. No recorder, shadow, source
collection or measurement screenshots ran. Initial buffer fill and input timing
differed. R4 passed all four required call/return units with 50,534 clean checks,
including 39,240 in the fight, with zero divergence or skips. R5 and B61A4 remain
excluded for missing required paths. No new R1/R2 aliases or lock-free audio
were included. The small gain does not explain enough of the hitch; host CPU
sampling is being prepared. Nothing is installed.

The [minimal audio-ring comparison](media/gallery/stage1-audio52-results.json)
is now measured in one quiet OFF/ON pair using the same executable. Overall
cadence was 59.7810/59.8977 guest frames/s. The exact 350-frame fight window
improved from 55.57 to 57.71, with guest work 5604.242/5378.785 ms.
Starved output sample frames fell from 16,927 to 10,645; both still fail. Every
measured starvation increment falls inside the respective boss observation
bracket. ON reported zero lap hazards, coalesced replays and inexact replays.
Initial buffer fill differed (140/110 ms), live input timing differed, and the
lock-free path includes a faster byte-identical tap loop. This is an observed
pair, not a causal estimate or resolved stutter. The unchanged callback excerpts
are available for [OFF](media/gallery/stage1-audio52-off-hitch.wav) and
[ON](media/gallery/stage1-audio52-on-hitch.wav). The route used held fire,
the disclosed timer aid, scale 2 and rewind OFF; no recorder, shadow, source
collection or measurement screenshots. Nothing is installed.
Separately, the rebuilt guarded native runtime qualified the two collision
leaves with 4,205 and 17,434 clean comparisons, zero divergences/skips and normal
shutdowns. B61A4 remains rejected: 368,054 clean entry returns do not cover its
unobserved call/continuation paths, and 19 checks were skipped. Collision-loop
qualification completed for R4; R5 remains excluded. The merged CPU suite passes 207 case verdicts;
its strict metric equality check still reports the intended failed-replay
cycle difference 847→511 caused by the new bounded abort. Live reference state
and clock remain equal. The original failed strict comparison is retained.


The [index-only experiment](media/gallery/stage1-index48-results.json) removed
95,019 full rebuilds but did not fix the mini-boss hitch or audio starvation.
The 350-frame hitch interval still took about 6.9 seconds; most wall time was
in guest work. Actual instruction sampling identified hot interpreted ranges
around 0x3A998 and 0xB5Cxx.

[Actual native qualification](media/gallery/stage1-native48-qualification-results.json)
completed 3,684 and 936 clean same-state comparisons for two resident routines.
Those focused comparisons stopped after verified City; later native gameplay
is not full-fight equivalence or pacing acceptance. The collision-loop candidate
passed 792 early comparisons, then its boss-window shadow stalled at frame 8819.
It is rejected. The old helper falsely accepted the unfinished comparison; a
shared validation gate now rejects unfinished shadows, unrestored native execution
and sustained guest freezes, including when staging an older receipt. The initial
seven checks and revalidation of the actual successful/frozen runs passed. The R1/R2 timing
comparison is now [measured](media/gallery/stage1-native48-performance-results.json):
OFF/ON averaged 58.9406/59.2282 guest frames/s. The exact 350-frame fight window
improved from 53.5496 to 56.2000, while guest-work time fell from 18.0186 to
16.4133 ms/frame and interpreted instructions from 111,933 to 92,977 per frame.
Total starved output sample frames fell from 87,159 to 54,088; both still fail.
This is one ordered pair with different initial audio fill and live input timing,
not a causal estimate or smoothness acceptance. No recorder, shadow replay,
source collection or screenshot polling ran during measurement. The route used
held fire and the disclosed timer-only aid, scale2, rewind OFF. Original candidate
pacing metadata incorrectly said unassisted; the actual command audit is
recorded, originals preserved, and future preparation now marks assistance.
Exact measured hitch audio is available for [OFF](media/gallery/stage1-native48-off-hitch.wav)
and [ON](media/gallery/stage1-native48-on-hitch.wav), with unchanged PCM bytes.
The [complete-unit validation work](media/gallery/stage1-cps-unit-validation-results.json)
resolved the original shadow overrun: the isolated v49 runtime completed 3,468
clean R4 comparisons across guest frames 8800–9668 and closed normally. Review
found those were entry units only; return paths remain unqualified. The updated
staging gate rejects that entry-only receipt and requires exact-code per-unit
call/return evidence. All 13 validator tests passed; an actual staging attempt
was rejected before copying any file. The earlier R1/R2 receipts still pass. A CPU-only self-authored sentinel-loop regression reproduced three
faulty native replays timing out at 3 seconds. With the bounded replay abort,
each returns in about 30 milliseconds, fails TRACE, preserves the first fault,
and retains interpreter CPU/memory/clock state. The clean generated DLL and
reset probes pass. This safeguards validation; it is not a gameplay speed fix.
The v50 live handler run reached frame 11607 and closed normally. Both requested
leaves reached 32 clean comparisons, but the global comparison scope included
older cached routines with seven unrelated failures and device skips. The whole
run is rejected. Narrow handler and continuation qualification, boss-route parity,
and a new quiet timing/audio pair are still pending. Nothing is installed.
A later focused 0x393D8 test made 3,518 boss-window comparison attempts across
frames 8800–9659, reported one SETUP rejection and blocked the candidate.
This is not evidence of a specific MMIO access or native CPU divergence; the
setup cause remains open. The final command audit also failed because two
helpers' timestamp-only receipt names collided. The damaged receipt is preserved.
An independent check found the owned game absent and port closed; its exit code
was not retained by the failed audit. Unique, atomic, exclusive receipt writing
now passes three tests (256 concurrent writers, forced collision and failed
publication), with all 16 combined receipt/qualification checks passing.

The bad segment itself is now recorded: [15-second silent mini-boss video](media/gallery/stage1-miniboss-stutter-20261113.mp4)
and [separate game-process audio](media/gallery/stage1-miniboss-stutter-20261113.wav).
Capture integrity passed with zero missing/filled packets, while the PCM analyzer
found nine likely runtime dropouts. This assisted reproduction includes recording
overhead and is not pacing acceptance. It is different from the post-timing clips below.

After the emergency reboot, the RTX 3090 Ti is responding again. Fresh tests
passed all 14,222 GL checks for the isolated v47 attribute-batching candidate
and all 25,964 GL checks for the isolated source-lookup memo candidate, with
zero failures. The v47 CPU regression fixtures also passed. The
[post-reboot renderer receipt](media/gallery/stage1-post-reboot-renderer-results.json)
records the tested artifacts and log hashes. Both runtime candidates remain
isolated, and neither is installed. A separate isolated
[SYS timing correction](media/gallery/stage1-sys-parity-recovery-results.json)
now matches native OFF/ON through all 1,100 replayed pre-input frames: 177,057
stores and their cycles match, with no fingerprint divergence. The regression
rejects the original frame-1051 failure. This bounded replay does not establish
combat, audio or later-game correctness; the SYS worktree remains unchanged.

Capture preflight now uses bounded direct process inspection in place of the
hanging PowerShell queries, retaining strict process and private-card checks.
All 46 affected tests passed. The [actual firing pair](media/gallery/stage1-reboot-firing-results.json)
then completed with all 1,669 frozen PNGs verified: attribute mode OFF measured
59.4452 guest frames/s and 34,764 output-starved sample frames; ON measured
59.7833 and 15,637. Both used ordinary held fire, scale 2, rewind OFF, CPU
attribution and the disclosed timer-only survival aid. Neither is stage-clear
or normal-settings acceptance. Both still dip near guest frames 9300–9560;
their worst five-second intervals measured 52.60 and 54.80 guest frames/s.
ON was active but merged no additional primitives, so this ordered pair does
not establish a batching benefit or resolved audio. Starting audio fill differed,
and unrelated host activity was reported. Nested CPU times must not be added.

Actual silent gameplay clips are available for [OFF](media/gallery/stage1-reboot-attrib-off-gameplay.mp4)
and [ON](media/gallery/stage1-reboot-attrib-on-gameplay.mp4). They were recorded
after timing. Exact recorded audio excerpts around the measured hitch are
available for [OFF](media/gallery/stage1-reboot-attrib-off-hitch.wav) and
[ON](media/gallery/stage1-reboot-attrib-on-hitch.wav); these are separate
intervals and are not presented as synchronized video/audio. Full callback
WAVs and separate post-timing process captures are indexed in the result receipt.

The [post-reboot inbox test](media/gallery/stage1-inbox-p3-results.json) observed
Claude idle before sending a nonce, received its exact model acknowledgement
and verified a replacement receiver checkpoint. The receiver still needs
renewal after messages or deadlines; one successful test does not establish
uninterrupted future availability.

The user's current priority is extreme stutter/jitter and broken audio. The
fresh [0.5% versus1% live audio comparison](STAGE1-AUDIO-RESULTS.md) did not
resolve starvation at either limit. Quiet interval-level runtime attribution is
in progress. The [enemy-aware Robin prototype](STAGE1-CONTROLLER-RESULTS.md)
now has actual targeting/firing/evasion footage, but lost lives and did not clear
the stage. Normal launcher/runtime promotion remains pending. Claude now has
twelve durable workstreams and a queue-aware continuity guard; this coordination
improvement is not project completion.

The latest private Wave 3 composition contains 837 authored entries in 1,669
keys. All 226 native region checks pass. The [updated full facade and lighting test](STAGE1-EMISSIVE-RESULTS.md)
adds the brighter canyon pair, two optional emissive masks and class-correct
Greif v3 pages/strips. Its continuous 52.77-second pass includes entry and exit;
all ten delivered building tiles submitted. The facade bracket measured 60.00
guest frames/s with no starvation increment; the full recording averaged 59.43
and still accumulated starvation. Recorder-off opening samples measured 60.07
with masks off and 60.00 on, with different starting audio-buffer levels.
The masks remain off by default, and nothing is installed. A later same-route
170-second observation without video, source dumps or measurement screenshots
averaged 59.9238 and accumulated 9,061 starved sample frames, concentrated near
148–149 seconds. It still used the disclosed timer-only aid and no firing;
full-combat cadence and audible audio acceptance remain open.

The preceding composition combines the new Astraea hulls and
32 canopy phases, scoped Gunpod cells, approved sign revisions, three canyon
wall/band bindings and revised HUD/results glyphs. The [live Astraea test](STAGE1-WAVE3-RESULTS.md)
positively submitted all five new hull bindings and all 32 canopy phases, with
448 authored entries submitted overall. It closed cleanly after 180 seconds,
without a stage clear. A subsequent [HUD/results census](STAGE1-UI-RESULTS.md)
positively submitted nine new font bindings and observed Total Evaluation and
Field Evaluation. Exit reached the opening movie and story text; return to title
remains unverified. Greif v2
failed an independent transparency check; the corrected v3 is now imported and
observed in the later fly-past, with pose/material acceptance still open.
Another 157 historical HUD fade aliases still lack
captured palette bytes and remain unresolved.

A newer private composition adds two delivered distant-city window masks while
retaining all 837 authored RGB entries and passing all 226 native region checks.
The v28 mask shader preserves above-neutral vertex lighting while lifting shaded
channels; 735/737 real-GL checks pass with zero failures. Its live acceptance is
in progress. Both additional atlas bindings were submitted and captured.
The [stage-relative controller trial](STAGE1-CONTROLLER-RESULTS.md) ended at the
third verified Continue prompt after two Continues, without a stage clear.
Its camera-gap and bounded recovery fixes pass 25 controller checks; threat
avoidance remains unfinished. Neither candidate has been installed or accepted
as a completed stage.

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
