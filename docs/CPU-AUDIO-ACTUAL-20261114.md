# Actual CPU audio and collector results — November 14, 2026

Two combined audio fixtures **compiled and passed** at21:40:30–21:40:36UTC.
This is CPU-only logic validation. Integrated game audio, audible quality,
mini-boss pacing, PCM identity and real SDL locking remain unqualified.

[Pinned source, original receipts and independent readback](../remaster-audit/cpu-audio-actual-20261114/README.md).
[Previous dated source review](CPU-INTEGRATION-REVIEW-20261114.md).

## Audio: what actually ran

One fresh grant806b9f6d was consumed once, without retry. The immediate gate
measured22.5%systemCPU and60.46GiB free. Whole-Job limits were assigned before
child resume and read back: CPU15, BelowNormal,120seconds and1GiB. The complete
job took6.723seconds and peaked at93,515,776bytes (89.2MiB), with child/wrapper
exit0, no timeout, Jobactive0 and no descendants remaining. Job accounting
reports16processes; the sampled descendant list sees11 and is not a census.

The pinned clang++ launcher and three backend files matched their expected
hashes. Compilation of each exact extracted helper succeeded. Both helpers were
re-extracted byte-for-byte from the copied proposed main.cpp before compilation.
The getter fixture ran4.922seconds:200,000concurrent reads, zero modulus,
coherence or gap violations,196distinct snapshots and all3deterministic negative
controls fired. The pump fixture passed4event cases. The fixture lock is a
checked nonrecursive stub, not SDL. The checks cover coherent locked snapshots,
legacy/no-device/reset/epoch-baseline semantics and pump generation/resync logic.

Root independently rehashed both original receipts and12original/copied source
inputs and verified the six recorded PID/creation identities absent at21:45:27.
This metadata readback did not replay the tests or independently repeat helper
extraction. Exact executable hashes remain in the manifest; binaries are omitted
from this packet. Compiler availability and private pinned inputs are required
to reproduce the recipes; this packet is not an installed game build.

The proposal remains unapplied to the live game. Current-header PCM comparison
Dr5, integrated main/debug build/link, real SDL3 lock and callback lifecycle,
post-unlock tracing, audible gap/listening checks and performance measurements
are still required. No measured frame-time improvement or remastered sound is
claimed from these fixture timings.

## Collector: preserve both the pass and the launcher failure

The separately granted21:21run passed74/74synthetic collector controls in.083s.
The10second/128MiB/CPU11/BelowNormal Job exited0 in.249s and peaked at23,293,952
bytes, with Jobactive0/treeabsent. These controls use fake process/listener/
connection data; they do not qualify Windows accepted-peer visibility or a game.

The original parent launcher949d **failed**, exit1/passedfalse: its retained
wrapper handle had exited, but its wrapper identity-absence check returnedfalse.
The exact original launcher/receipt/stdout/stderr are preserved. Empty logs are
empty evidence, not invented console output. A later independent21:22:12
metadata readback verified both known identities absent, the executed sources,
74records and resource limits. That later cleanup observation does not rewrite
the original launcher failure. The current14317586launcher source releases its
exited handle before polling; it is reviewed but unrun. No74test replay was used
to obtain a green wrapper. A focused Win32 handle/PID lifetime probe is authored,
unrun and awaiting review/a fresh resource grant; the retained-handle cause is
still a hypothesis.

Canonical collectorc457 and guardc783 are unchanged and unwired. Audited binding
r0 is source-blocked: the disk audit needs exact in-memory intent-ID binding,
post-fsync deadline/identity rechecks, strict transport types and an explicit
successful owned-cleanup contract. The corrected owned-stub r1 is authored and
awaits full source review; no real socket probe has run.

## Engine, skins and remaining graphics acceptance

The latest corrected Remix-builder attempt at21:01:53measured64.6%CPU and59.7GiB
free and refused before a child, exit3. Earlier78.6%and66.1%refusals and the
earlier syntax-pass/object-path-failure remain preserved. The output-path fix
has not executed. No link,65controls, guard77 or new GPU image is accepted.

T2r3 source fixes the two-writer reservation-underflow counter and modular-age
boundaries; its82checks are authored/unrun. T1's36checks and observer/GLidentity
fixtures remain unrun. Native Claude delivered a first ordered capture-ledger
and private integration-glue proposal; both are source-only and still under
review. Full command coverage, late owner invalidation, actual material content,
camera transport, composition and SDK lifecycle still block native suppression.
No ray tracing or DLSS integration is verified. OpenGL color output alone does
not supply the geometry/material/motion/depth/HUD-separated inputs those paths
need; no unqualified runtime DLL was injected.

Skin-target r1 is a source proposal, not a visible skin release. It distinguishes
unset/invalid/valid selection, rejects invalid nonempty selections to stock and
uses observed per-key UV rectangles for a generic shared hull candidate. Trusted
pack-entry admission, native-alpha identity, named-craft ownership, live material
generation recommit and a runtime selector are still open. Seven other role
groups remain unresolved. Tint/detail is not realistic4K/PBR artwork. Player,
enemy, miniboss/boss, gunpod/weapon, bullet and effect coverage is incomplete.

The texture stipple draft corrected its positive key to87F01A0F-D9554B55 and
control to28127931-7C2D834A. The earlier cited D1B4140B did not draw the proposed
window. Allowed/protected masks require review before preview; no new repair or
admission is accepted. Distant green/pink signs, buildings/backgrounds, HUD/body
text, menus, skins/selectors and all-seven-stage gameplay/audio/outcome/install
acceptance remain open. 118/118metric replay is not118accepted artworks.

All work here used C:. No Einhander GPU/game/Comfy job or driver/power/security
change occurred. Shared resource grants remain mandatory. Metadata monitor32088
was observed at21:44:17and is bounded to22:14:16UTC; it is not model activity or
an uninterrupted-availability guarantee. Historical monitor gaps remain intact.
