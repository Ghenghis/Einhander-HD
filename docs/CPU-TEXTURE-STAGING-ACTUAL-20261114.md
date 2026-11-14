# CPU texture correction, pilot staging and scheduling — November 14, 2026

One private weapon-menu lettering correction passed its CPU checks and was
written to a new candidate. A separate Stage 2 one-key texture pilot was copied
to isolated storage. A scheduling probe confirmed that a future game can retain
all 16 CPU cores and Normal priority while its watcher runs BelowNormal.
No game, GPU, audio device or Remix renderer was launched for these results.

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
