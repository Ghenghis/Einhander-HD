# CPU texture correction, pilot staging and scheduling — November 14, 2026

The additional results below record the completed three-key lettering batch,
50 present-lifecycle checks, 17 cleanup checks, corrected coverage accounting,
and the preserved raw-driver failures. They supersede the earlier one-ROI
candidate status without turning CPU checks into live acceptance.

One private weapon-menu lettering correction passed its CPU checks and was
written to a new candidate. A separate Stage 2 one-key texture pilot was copied
to isolated storage. A scheduling probe confirmed that a future game can retain
all 16 CPU cores and Normal priority while its watcher runs BelowNormal.
Those initial CPU results involved no game, GPU or audio-device launch. A later
coordinator-owned startup attempt is recorded separately below.

[Pinned sources, actual receipts and root readback](../remaster-audit/cpu-texture-staging-actual-20261114/README.md).
[Earlier private menu build and transport checks](CPU-TRANSPORT-ACTUAL-20261114.md).

## Weapon-menu lettering candidate

C1 repairs 240 alpha-zero pixels inside 60 native glyph cells of
`1AD90FC9-02491337.png`, ROI B `[0,58,124,158)` in native texel coordinates.
It restores only those pixels to their own native cell's RGB and alpha class.
Counters, contours, protected centre samples and every other pixel stay exact.
This is weapon-menu text; it does not repair the distant green and pink signs.

The first actual r2 dry run returned **3, BLOCKED**. Its G4 incorrectly required
native palette RGB at every protected centre, although the existing R1 contract
requires native alpha class and allows authored HD RGB. That failure and its
proposed sheet are preserved. No r2 standalone candidate was written.

Immutable r3 changes that guard to exact before/after centre RGBA equality plus
correct native class at all 65,536 centres. Native-RGB centre counts remain
reported. It does not broaden the repair mask or permit an alpha-class repair
elsewhere. Its production controls include authored-RGB/correct-class acceptance
and wrong-class rejection outside the ROI.

The actual r3 dry run passed 14 controls and G1–G5, with 240 changed pixels,
zero centre voids and all 65,536 input centre classes correct. Class mismatches
fell exactly from 442,466 to 442,226. Whole Job: 1.262 seconds and 238,276,608
bytes peak. After reading that result, the owner used the separately authorized
conditional write once: 1.452 seconds and 238,489,600 bytes peak, with the same
checks passing. Both jobs used CPU13/BelowNormal, a verified 60-second/1-GiB
Job, exit 0, empty Job and absent tree. No retries occurred.

The new 2048×2048 PNG is 885,600 bytes, SHA256
`e469e26f3acf5230634d51de5775a01c7a57fbc0b553f2d99f9c2d5f9fbfd6d0`.
Root checked the source, receipts, output hash and PNG dimensions and viewed
the full before/after sheet `b03b7ded…`. Small interior holes improve; rough
glyph contours and the existing counter style remain. This is a private,
uninstalled candidate. Readability, class mip output, composed appearance and
in-game acceptance remain open. The frozen input artwork was not overwritten.

## Isolated Stage 2 pilot

The owner first inventoried the current v68 cache: 4,405 files, 239,111,587
bytes, manifest `bbcb9abeecb227d5e29705584f6955a06b06386c414c2298933d917b917e9b9f`.
Actual qualification Job: 5.529 seconds, 19,144,704 bytes peak. This is a current
inventory, not historical provenance or executable/cache ABI qualification.

The subsequent COPY-only staging Job succeeded in 55.228 seconds with
21,921,792 bytes peak. Each copied cache file was checked against that manifest
by the staging tool. Only `28127931-7C2D834A.png` is in the isolated HD root,
SHA256 `40434c40285348142b15c2609e572c0aa640eca9d886e3021e50d6c7fb5ff70a`.
Four private settings paths changed; HD-on was asserted unchanged. Both jobs
used CPU12/BelowNormal, 120-second/1-GiB limits, exit 0 and absent Job trees.
Root checked the receipts, tool, manifest, staged settings and image hash;
it did not repeat the full cache copy or hash sweep.

The preserved staged tree uses the older v68 executable `5c1436ff…`, not the
new private menu/audio build `37c137e8…`. Its source-only launch delta specifies
separate writable pilot and native-baseline settings/cards/cache, disables the
absent second card, and strips inherited skin/HD/proof controls. The disc BIN
has only a size check so far. Hash it once when binding the actual owned launch.
There is no recorded AQ-01 replay/input harness; historical Stage 2 draw frames
40,717–41,099 are targets, not a reproducible replay identity. Ordinary-play
route, replacement proof and composed baseline comparisons remain unexecuted.

## Scheduling and remaining engine work

The separate Normal-child wrapper `c1fc81d4…` passed one harmless scheduling
probe: all 16 cores and priority 32 before resume and inside the actual child;
watcher CPU11/priority 16384. Whole Job: 0.108 seconds, 13,312,000 bytes peak,
exit 0 and empty tree. This proves scheduling only, not game performance.
It does not change global Windows, GPU or driver settings.

Root independently read five successful envelopes and checked ten recorded
PID/creation identities absent, plus 19 source/artifact pins. It did not replay
image processing or launch a GPU job. The packet includes the readback recipe
and scope limits; it omits EXE, object, DLL, ROM, card and PNG payloads.

Capture glue r2 and per-target skin generation fixes have source review only;
their new builds/live integration remain open. The combined raw menu/audio
driver's first revision is source-blocked on complete pack revalidation,
inherited environment isolation, per-connection ownership, bounded reads and
failure evidence. These are concrete followups, not successful game results.
Real audio/listening, mini-boss pacing, distant signs/buildings, realistic ship
and weapon skins, HUD/menus, all seven stages and installed release acceptance
remain incomplete. No working ray tracing or DLSS is established by these CPU
checks; the last actual Remix GPU rendering failure remains preserved.

## Additional actual CPU results — 23:11–23:23 UTC

T2 r6 compiled under `-std=c++17 -Wall -Wextra -Werror` with an empty warning
log and passed all 50 authored checks. The single CPU12/BelowNormal Job took
1.517 seconds, peaked at 94,818,304 bytes, exited 0 and ended with an empty
tree. The private fixture executable is `a5c6c02c…`. Root checked nine source
inputs, eight executed copies, the fixture/result/logs and known identities;
it did not repeat compilation or the large compiler-library hash sweep.

The new lifecycle keeps an owned pending/displayed frame valid across the
next ordinary capture, while preserving r4's invalidation API. Only the exact
expected buffer flip and matching completion can pass; stale/abandoned frames,
front-buffer writes and unknown write footprints refuse. The tests use fake
policy/hazard hooks and a seqlock smoke test. Actual capture glue, display-hazard
integration, camera/material identity, compositor and GPU synchronization are
still unqualified. These 50 checks do not demonstrate live Remix rendering.

C1 r4 extends the same interior-only correction to three fixed lettering ROIs
on three palette keys. Each successful dry/write invocation passed 14 controls
and G1–G5, with zero centre voids and all 65,536 protected centre classes correct.
The three new private candidates are:

- `1AD90FC9-4315989E`: 12 pixels, SHA256 `2c415f4e9d7d2ac0cc5b6f7833189cc7c1707b998c7734e928c6742851c258e4`.
- `1AD90FC9-02491337`: 422 pixels, SHA256 `8eee400475a66139df38d19989914bf9a205ebf9cf8163e35e56ff70a7eb9eec`.
- `1AD90FC9-79902A90`: 422 pixels, SHA256 `1067cc536c8028c619089b4abff41f228c9d845696eed26f99af9af693355a03`.

Total: 856 pixels across three candidates, **including** the earlier 240-pixel
r3 correction. Inputs always come from the frozen snap-native candidates;
outputs are not chained. The third write was first refused at 71.4% CPU,
exit 3 and no child. That refusal is preserved. A later, separately granted
write succeeded once at 37.5% CPU without repeating its dry run: 1.666 seconds,
251,125,760 bytes peak and empty tree. The other five successful invocations
took 1.431–1.694 seconds each. Root checked the receipts/output hashes and
additional sheets. Rough contours remain; no candidate is installed or accepted
for readability, composed appearance or the distant neon signs.

The ownership/provenance report ran once in 3.114 seconds, 57,597,952 bytes
peak, CPU13/BelowNormal, exit 0 and empty tree. Its key universe remains 2,321
Stage 2 keys and 2,289 Stage 3 keys, combining recorded and predicted scope.
Family labels changed for 21/11 rows, while raw key/source/authored fields and
recorded stage-input hashes match the earlier report. Root did not rehash all
295 scanned manifest inputs. There are still **75 recorded Stage 2 drawn keys
without authored HD**, including four unverified transient-hash correspondences.
Stage 3's zero recorded drawn-unauthored count does not establish completion:
live capture is incomplete. One candidate-ledger-only row per stage now counts
as provenance rather than integration. Every family's admission, live review
and stage E2E remain unestablished.

The corrected cleanup fixture passed 17/17 pure controls in 0.234 seconds;
whole CPU12 Job 0.388 seconds, 20,172,800 bytes peak, exit 0 and empty tree.
It covers retained process aliases, PID reuse, absence errors, a shared cleanup
deadline and cleanup failure evidence. It creates/stops no real process and
does not prove real OS tree absence. A live driver must join its owned-identity
observation with the outer Job's emptiness after the driver exits; it must never
pretend its own still-running Job contains zero processes.

The raw menu/audio driver had two actual failed control attempts. The first
exited 1 after 0.863 seconds with empty captured stdout/stderr; its cause is
unrecorded. A separately granted logged diagnostic exited 1 after 2.168 seconds
and identified a fixture bug: Windows `write_text` produced CRLF settings bytes,
while the test expected an LF hash. The production file check correctly refused.
Both failures and their empty trees are preserved; neither produced final check
counts or ran staging. The corrected exact-byte fixture subsequently passed
61 controls in its exclusive log, including the expected argparse rejection
case. Staging and an owned in-game run still require their own actual receipts;
the control pass is not an audio, adapter or gameplay result.

The first actual raw staging attempt then failed before `prepare()`:
`ModuleNotFoundError: build_facade_ab_candidates` under isolated Python.
Whole Job: exit 1, 0.183 seconds, 22,814,720 bytes peak and empty tree;
no batch directory was created. The import-only followup preserves isolation.
An intermediate R5 proposal was not executed: static review caught a lazy
dependency incorrectly required at module load. R6 corrects that classification
and pins 11 load-time plus four lazy local source files before import. Root
checked those 15 hashes and the static initial import graph without importing
the target. Dynamic/third-party closure and actual staging remain separate.

## Retained stripe fixture failure — 23:28 UTC

S45 r4's one authorized fixture run returned **3, FAILED: 19/23**, including
all 15 expected negative cases and four successful positive cases. Four other
positive cases failed: staircase residual 0.2528 versus 0.15 at scale 8;
0.1644 versus 0.15 at scale 4; four missing crossings on the steep pattern;
and insufficient staircase improvement on the shallow pattern. Whole Job:
1.538 seconds, 84,549,632 bytes peak, CPU15/BelowNormal, exit 3 and empty tree.
No key repair or art installation ran.

The actual run started before root's late hold reached the owner. It supersedes
the earlier source-only/UNRUN description; it is one real execution, not a
retry. Root checked the source/input pins, actual receipts and both recorded
process identities absent. Failing cases retain their messages but lack full
metric arrays. R4 also skips per-chain checks on chains with fewer than eight
second-difference samples and does not gate missing border crossings. No
universal per-chain, zero-missing or visual acceptance follows. The next
immutable source revision must expose measured, excluded and unmeasured
coverage and use the production verifier for its negative cases.

[Additional pinned source, actual receipts, failures and root readbacks](../remaster-audit/cpu-present-lifecycle-actual-20261114/README.md).

## Actual private staging and controlled startup — 23:31–23:35 UTC

Corrected R6 CPU staging succeeded once: exit 0, 17.630 seconds, 63,119,360
bytes peak Job memory, CPU14/BelowNormal and empty tree. Receipt `2710782e…`
binds the copied `37c137e8…` executable, private settings `406643a1…`, closed
card1 seed, disabled absent card2 and initially empty own cache. It verifies
1,701 PNG names/hashes: 1,699 candidate files and two pinned emissive files,
with emissive disabled. Another 688 non-PNG files are recorded by hash but were
not pinned by the original candidate; this is not an immutable-pack claim.
The disc BIN was hashed once during staging, with 653,493,792 bytes recorded.
The eleven load-time and four lazy local imports are pinned separately from
unqualified third-party provenance. Root checked the receipt, local imports,
executable and small input bindings without repeating the full pack/ROM sweep.

The first coordinator-owned run setup then aborted **before game creation**:
another isolated import could not locate `gl_adapter_identity_guard` while
loading the cleanup holder. Outer Job: exit 1, 3.397 seconds, 27,119,616 bytes
peak, Normal/all-16-core child and empty tree. No game identity, holder or game
broker registration existed in that evidence. A narrow R7 import fix added
the canonical path and exact holder-closure pins without restaging the pack.

The next coordinator-owned attempt did start the private game: PID 7116,
creation time `1794699328.160226`, exact executable `37c137e8…`, priority 32
and all 16 cores. The listener appeared after 3.460 seconds. The run then
returned **ABORTED** on the first `skin_material` transaction: connected TCP
peer missing or ambiguous. No menu gate completed and no `audio_stats` result
was recorded. Whole Job: 8.368 seconds and 1,830,989,824 bytes peak Job memory.
That is host Job memory, not measured GPU memory.

The game identity matches its broker registration and cleanup holder exactly.
The holder reported that identity absent; its own tree field remained false
inside the still-running parent, as designed. The outer Job subsequently
reported active 0 and absent tree, completing the cleanup join. Root checked
all three recorded identities absent. The coordinator reports explicit GPU
release; root did not read private fence/token files or change driver settings.
This controlled abort is not evidence of a game crash, resolved stutter or
passing audio/menu behavior.

The failed transaction did not preserve which peer-check phase failed, so a
pre-send visibility delay is unproven. The retained debug-server source
`b50aef2a…`, lines 14964–14989, sends the reply and then closes that client
socket. Requiring an ESTABLISHED server row after receiving a one-shot reply
can therefore reject a legitimate close. The next transport revision must
preserve phase-specific evidence, bind the owned socket before sending, reject
observed foreign/ambiguous peers and distinguish legitimate closure afterward.
It remains a reviewed followup, not a successful raw collection or adapter proof.
