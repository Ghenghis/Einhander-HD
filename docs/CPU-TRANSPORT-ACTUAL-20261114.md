# CPU transport and continuation results — November 14, 2026

The corrected T1 reprojection fixture passed 36 checks. T2 r4 then passed 55
unit checks and 21 checks against the real VRAM ledger policy. A task-routing
fix passed all 12 continuation regression tests. These are actual CPU results;
they do not establish working in-game Remix rendering, ray tracing or DLSS.
No Einhander game, GPU or audio device was launched for this work.

[Pinned source, receipts and independent readbacks](../remaster-audit/cpu-transport-actual-20261114/README.md).
[Earlier private v69 audio build and PR7 CPU probe](CPU-ENGINE-BUILDS-ACTUAL-20261114.md).

## Geometry and transport

T1 r3 ran once under its fresh CPU15 grant. Compilation and all 36 checks
succeeded: 0.651 seconds for the whole Job, 94,371,840 bytes peak memory,
exit 0, empty Job and absent tree. The private executable is
`ecd4aa0353d397d27b23c4dca02ef75a98b09292c3dfbe9371ba9eff0dbcbdf4`.
The inherited fixture still labels itself revision r0; that label was preserved.

The earlier compile failure remains in the previous packet with zero checks
executed. The corrected build changes exactly one comment token in a derived
private pgxp.h: raw `1f50599f` becomes `50a6ef6d`, with original line endings
preserved. It keeps strict warnings and the same extracted native GTE divide
code. A separate reviewer checked the inputs, copies, executable, comment delta
and recorded process identities. Root read and pinned the actual result;
it did not rerun the fixture or repeat that entire peer sweep.

T2 r4 ran once under a separate CPU15 grant. Its unit fixture passed 55/55 and
its integration fixture passed 21/21. Both executables compiled and exited 0.
Whole Job: 2.242 seconds, 97,165,312 bytes peak memory, BelowNormal, one CPU,
120-second/1-GiB limits verified before child resume, active processes 0,
tree absent. The sampled descendant list missed two short-lived fixture PIDs;
their separate recorded creation times remain available.

Root independently checked 14 source inputs, 12 executed copies, both fixture
receipts and executable hashes, the exact comment-only header derivation,
the generated native unpack file, and six recorded PID/creation identities
absent. It checked the 12 extraction result pins without repeating extraction,
and did not rehash the large compiler libraries again.

The tests exercise the final transported primitive set, VRAM mutation,
draw feedback, display overlap, readback, stale epochs and foreign-owner
invalidation. They prove refusal and bookkeeping on synthetic inputs.
Per-draw material/content identity, camera binding, actual capture glue,
the consumer, compositor and presentation synchronization remain unqualified.

## Claude continuation fix

The local continuation hook previously recognized literal queue-owner names
but missed their anchored exact form. The new helper recognizes either the
legacy literal or `^escaped-owner$`, and keeps primary, UI and Stage 2/3 worker
tasks separate. It does not evaluate arbitrary regular expressions.
Future queue producers must use anchored exact owners: the legacy bare primary
pattern remains ambiguous in Hermes itself.

The single granted CPU13 run used copied, hash-verified hook and test scripts:
12 tests, 12 passed, zero failed, skipped or cancelled. Whole Job: 1.065 seconds,
120,098,816 bytes peak, BelowNormal, 30 seconds/256 MiB, exit 0, empty Job/tree.
Root subsequently checked the TAP and copies and three recorded identities
absent. Node's executable hash was recorded at execution; it was not claimed
as an independently preapproved binary pin. No live native-session hook,
permission or write-guard bypass was invoked by the tests.

## Adapter diagnostics

The audited-binding fixture passed all 41 pure controls in a separate CPU14
Job: 2.336 seconds, 21,639,168 bytes peak, exit 0 and empty tree. These tests
use doubles; they do not prove actual Windows socket ownership or game cleanup.
The owner reported a PowerShell launcher error before the actual A spawn;
its original directory and one-line log are preserved separately. This is
not a second fixture execution or an overwritten failure.

The separate owned-loopback probe returned **5, INCONCLUSIVE**, after 13.912
seconds with 51,249,152 bytes peak and an empty tree. The positive listener was
visible before accept, both real positive queries passed, and an ambiguous
listener was rejected without connecting. However, every accepted collision
test connected to the expected owned stub. The foreign-peer negative never
ran, so the probe correctly refused full qualification. No retry or actual
game/adapter acceptance is claimed. A deterministic negative needs a new
source proposal and its own review and grant.

## Menus, textures and runtime acceptance

The private F6 player-color proposal's post-close event-batch bug was corrected.
Its merge into the v69 main preserves the audio changes. The reviewed build
recipe uses all three files: merged main, host_keymap.c and host_keymap.h.
It rebuilds both affected translation units, checks the historical main
dependency hashes and preserves 153 link inputs, including v69's debug object.
The historical D: include closure of the replaced old keymap object is unknown;
no D: read or baseline-keymap reproduction is claimed.

The single granted build actually passed all 12 required recipe steps.
Main compiled in 6.205 seconds, keymap in 0.291 seconds and link in 0.376 seconds.
Whole Job: 8.768 seconds, 275,922,944 bytes peak, CPU15/BelowNormal/120 seconds/
1 GiB, child and wrapper exit 0, empty Job and absent tree. It retains the
inherited pgxp.h nested-comment warning.

Private executable: 21,473,280 bytes, SHA256
`37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc`,
under the UI worktree's `builds/p1-v69-2240/`. The original v69 executable is
unchanged. Root independently checked all three source copies, the new objects
and executable, the recorded 1142-entry main closure against v69, the new
118-entry C: keymap closure, exact response-file bytes with only two object
paths replaced, and five recorded process identities absent. The driver hashed
the current dependencies and 155 input files; root did not repeat their full
hash sweep or recompile anything.

This is a private incremental build, not an installed selector or in-game
input acceptance. The panel selects existing player color presets; it is not
proof of realistic new ship, enemy, boss, weapon or effect artwork.

The Stage 2 dither index actually covered 71 of 390 drawn keys. The sole
threshold crop was reviewed as incidental grey texture noise rather than a
persuasive intentional dither pattern. That indexed branch was closed without
repair. The other 319 keys and Stage 3 were outside this index; there is no
all-stage dither-clear claim.

The J10 corner method remains provisional until a composed in-game view.
Its isolated pilot setup had an unchanged-setting/count mismatch caught in
source review; the corrected proposal separates one assertion from four
mutations and uses private cache copies. No pilot launch is claimed.
Its settings-only fixture passed all seven LF/CRLF and anchor conditions in
0.106 seconds, with 14,073,856 bytes peak and an empty Job/tree. This did not
inventory or copy the cache, stage the pilot, process pixels or launch a game.
The visually rejected Stage 4 stripe r2 remains rejected. Its direction-aware
r3 actually passed 16 synthetic fixture cases in 1.532 seconds, with
82,542,592 bytes peak memory and an empty Job/tree. No key repair ran.
The fixtures exposed substantial kept-center RGB dots, weak small-size gains
and some edge kinks. A new RGB-only proposal may correct center colors while
preserving native alpha, class, geometry and protected fittings. No new art
is admitted by those fixture results.

The audio acceptance analyzer also required source corrections: failed samples
could be filtered, candidate identity and cleanup checks were incomplete, and
field types were insufficiently strict. Its latest proposal deliberately
cannot report full acceptance without a qualified cleanup contract.
Real SDL device/callback lifecycle, audible listening, mini-boss pacing,
background/sign/building clarity, modern HUD/menus, realistic skins and their
selectors, all seven stages/options/outcomes, Remix GPU rendering, RT/DLSS,
installation and rollback remain open.
