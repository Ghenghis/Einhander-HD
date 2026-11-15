# Actual private audio build and Remix CPU probe — November 14, 2026

Latest actual CPU results: [private menu build, transport checks and retained diagnostic limits](CPU-TRANSPORT-ACTUAL-20261114.md). P1+v69 compiled/linked37c137e8, not launched/installed; T1 36 and T2 55+21 checks passed. Loopback probe5 remains inconclusive. Earlier entries below preserve their dated scope.

The proposed audio telemetry is now compiled and linked into a **private v69
executable**. The corrected Remix probe also builds and passes its CPU controls.
Neither result establishes working in-game audio, Remix rendering or an installed
release. This continuation used no Einhander GPU or game launch.

[Pinned results, source and independent readbacks](../remaster-audit/cpu-engine-builds-20261114/README.md).
[Earlier actual audio/collector results](CPU-AUDIO-ACTUAL-20261114.md).

## Audio: fixtures, baseline reproduction and actual integration

The current combined header c84258e1 passed seven host PCM cases against the
original70cb5acd: **all14PCM file hashes independently checked; seven pairs are
bit-identical and legacy underrun-counter marks match**. The cases include
starvation, recovery, multiple gaps, split callbacks, mute/reset and reinit.
The Dr5 Job took1.391s/93,261,824Bpeak, CPU15/BelowNormal/1GiB. It ran once under
direct grant b2b1; the later35c1relay described the same slot, not another run.
This complements the previously published200,000-read coherent-getter fixture
and four-event pump fixture. No listening or performance improvement is inferred.

Unmodified main.cpp and debug_server.c were then recompiled with their recorded
arguments. Both objects reproduced the v68-linked911b117a/1947bca3 byte-for-byte.
The repro Job took9.324s/200,278,016Bpeak. It measured main's O3compile at5.396s
and debug at2.896s. An independent peer rehashed1201unique dependency files
(17,958,336bytes), five compiler components and153retained link inputs with no
mismatch. Root read that complete review, independently verified both object and
depfile hashes and four known process identities absent, and did not repeat the
entire dependency sweep.

The separately granted BUILD then compiled the complete changed main/debug
translation units and linked v69. The actual main/header/debug copies match
8022b148/c84258e1/b50aef2a. Their dependency dictionaries match repro exactly
except the explicitly changed source/header paths. Main consumed the copied
combined header; debug did not unexpectedly include it. Root independently
checked the copied files, new objects/depfiles and the closure comparison.

Exactly two object paths change in the pinned parent response file; root
compared its actual bytes and the actual link argv/cwd. The other153link inputs
remain hash-checked by the driver. A second independent post-build review also
rehashed1201current dependencies and153retained inputs, with no mismatch.
Main compile5.743s, debug2.702s, link.364s;
whole Job9.884s/199,749,632Bpeak, CPU15/BelowNormal/120s/1GiB, child/wrapper0,
Jobactive0/treeabsent. Five recorded PID/creation identities were absent at
root's22:08:47readback. The actual copied fa5 wrapper matches its full pin.

Private executable: `remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206/Einhander_Recompiled.exe`,
21,468,672bytes, SHA256 `f1ccb34dc0d06ba945fd822c9e807fe14b452b0d61584b731dcd4163f27759e5`.
It has **not launched, opened an audio device or been installed**. This is an
incremental two-object build, not a full-source rebuild. Real SDL locking and
ready/callback lifecycle, audio_stats/trace behavior, audible quality/listening,
mini-boss frame pacing and performance still need runtime acceptance.

Repro provenance deviation remains explicit: its fa5 wrapper executed in place
after prehash instead of from the requested copied file. That run was not
repeated to alter history. BUILD used the required literal verified copy.
Both compiles retain the inherited pgxp.h comment warning.

## Remix probe and retained geometry failure

Corrected PR7 builder b0e08a6a actually ran at22:03:09–12UTC. Syntax, object and
link succeeded; **65CPU contract checks passed**, and the no-lease guard returned
the expected77 with GPU/DLL/GL flagsfalse. Whole Job3.158s/118,841,344Bpeak,
CPU13/BelowNormal/1GiB, Jobempty/treeabsent. Root independently checked the
source/header/wrapper/archive pins, object and EXE hashes and both recorded
wrapper/driver creation identities absent. The probe EXE is eb28476c; binaries
and SDK payloads remain private.

Actual compiler argv used the **original pinned source path**. The run directory's
executed-source.cpp is an archived matching copy, not the compiler input. The
builder did not record subchild creation times; those remain unavailable. Prior
resource refusals66.1/78.6/64.6% and the earlier object-path failure are preserved.
9d012821 is the66.1%refusal; the object failure has separate97a2738c/9391f12c receipts.
No Remix DLL loaded or rendering/lifecycle/RT/DLSS passed in this CPU run.

T1's separate36-check fixture **did not compile**: native pgxp.h:85 contains a
nested comment delimiter, rejected by -Wcomment under -Werror. Extraction passed,
but0/36checks ran. Original failure, source copies and compile log remain intact;
its Job exited1/.536s/94,826,496Bpeak and cleaned up. A precise private comment-only
derived header/driver r3 is source-reviewed but unrun, not a broad warning suppression or a
retry on the consumed grant. T2/ledger fixtures remain unrun. Full ordered capture,
VRAM policy, late ownership/invalidation, material content and composition remain
required before native suppression.

The native owner separately disclosed an accidental empty python3 stdin invocation
outside the PR7 Job during receipt reads. TaskStop and a later image-name listing
were reported; its PID/creation/exit are unknown. The preserved incident note
does not treat that invocation as part of the accepted Job cleanup, and no
unrelated process cleanup is inferred.

## Actual texture/UI results and decisions

J10's two-key corner preview passed its class/R5 checks, with0/3208corner-quadrant
differences. Its Job took7.559s/307,908,608Bpeak. The coordinator viewed comparison
and fixture images: square block corners improve, diagonal smoothing remains,
checker/bead restructuring is unresolved. This is a provisional two-key method,
not admission or live acceptance. S2alpha differs at6515pixels from J9; do not
claim unchanged old alpha.

S45stripe r2 passed its fixtures and two-key preservation checks, but the
coordinator and owner saw conspicuous stepped diagonals without a clear quality
improvement. **Visual decision: reject for admission.** Original artwork and
failed candidates are preserved; no batch/install follows from those passes.

UIr6 measured three text keys once,7.043s/214,695,936Bpeak. In the measured ROIs,
native strokes are one texel thin with an empty native interior; HD interiors are
mostly bright. Snap-native did not increase dark stroke pixels: its major new
dark-visible counts came from previously transparent counters/background. Small
alpha holes remain. The coordinator viewed representative1:1body crops, but did
not accept the font pack or authorize global RGB smoothing/alpha filling. No
repair or v5pack pilot ran. Final readability needs the composed game background.

The drawn D9554B55crop window is mostly transparent and contains a ragged
silhouette, not a proven checker-dither positive. The earlier D1B4140Blook used a
different CLUT and did not draw that window. Preserve this correction; keep the
silhouette case separate, and find genuine drawn checker patterns before repair.

Skin-target r1's header/caller/catalog/controls are source-reviewed for future
pure controls, not compiled/live accepted. Admission/alpha identity, named craft
ownership, live generations and seven other role groups remain open. A private
player-color menu proposal is being implemented; no in-game selector is delivered
by this packet. Tint is not authored realistic4K/PBRship/enemy/boss/gun/effect art.

## Reuse existing rendering foundations

The prepared v68 settings choose OpenGL. Its pinned main requests3.3Core and the
renderer creates an SDL GL context with existing swap-phase hooks. Root statically
parsed the exact prepared EXE imports and source/config hooks without execution.
An import or a source request is not an observed running context/profile/GPU.
The requested API fits RenderDoc's documented Core support; an owned actual
context and capture still need qualification. [RenderDoc API matrix](https://github.com/baldurk/renderdoc/blob/v1.x/README.md).

The repository also has a real Vulkan backend behind PSX_HAVE_VULKAN, with runtime
loading, geometry and swapchain code. Its header's old 'geometry later/abort'
comment is obsolete. Its depth test/write are disabled; the attachment mirrors
PSX mask stencil, not qualified3Ddepth. HD replacement/material/UI parity remains
unaudited, so switching backends is not accepted as a seamless enhancement.

Streamline SR needs correct color/depth/motion buffers and frame constants;
frame generation also needs correct UI/HUD resources and presentation lifetime.
Those exports/integration are not implemented here. Existing Vulkan infrastructure
is a reuse candidate after parity and correctness work. Downloaded mod archives
do not create these inputs. [NVIDIA SR integration](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS.md),
[NVIDIA frame-generation integration](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md).

Both GPUs stayed unused by this Einhander continuation. C:only; no driver/profile/
power/BIOS changes. Remaining acceptance includes normal-game owned adapter/focus/
progression, mini-boss audio/pacing/listening, all seven stages/options/outcomes,
distant signs/buildings/backgrounds, modern readable HUD/menus, realistic skins/
selectors, actual Remix rendering/lifecycle/RT/DLSS and installed release/rollback.
