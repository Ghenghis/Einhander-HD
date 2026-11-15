# HUD, distant textures and player/enemy selector: actual CPU results

This checkpoint records completed CPU work with Claude from C:. The project remains active and incomplete. No game or GPU was launched for these results, and no private candidate was installed or accepted in a release.

## What actually ran

The private player/enemy colour selector compiled and linked successfully. All 12 build steps passed in one CPU13 Job: 10.478 seconds and 275,169,280 bytes peak host Job memory. The outer Job ended empty, and root checked both recorded process identities were absent. The new executable is `34e5d8f50ee013749bdd53eb139796ca15adea684d1a93bb8335b6127bcd3be2`; its reviewed merged main source is `fe85c7e4caf7be4f76ce3a8528ba08868e9468113940ea44e716aa68a2ae6dd3`.

The builder recorded equality with the 1,142-entry v69 main dependency closure, a complete 118-entry C:-only keymap closure, 155 input files and exactly two replaced objects. Root independently verified six artifact pins, the recorded closure comparisons and cleanup; it did not rehash the entire compiler library/dependency tree or rebuild. The historical D: keymap closure remains unknown. The older private 37c gameplay baseline was not replaced by this build.

This selector exposes separate player and enemy **colour profiles** through an incremental F6 overlay. It preserves both channels and applies them together. It is not a realistic ship-skin system. Live keyboard/controller cases, rejection behaviour, zero-strength usability, persistence and composed appearance remain untested. No normal, roughness or metallic material maps are delivered by this selector. The source binding map records one shared player-hull role and seven unresolved actor roles; named weapons, enemies and bosses still need verified bindings. The browser factory draft/generation, texture admission, saved library and in-game selection chain is not complete end to end.

The four existing coherent-v4 HUD candidates were measured in one CPU13 Job: 4.518 seconds and 547,622,912 bytes peak host Job memory, with six diagnostic toy controls passing. Exit zero means the measurement completed. It does not mean all four candidates passed.

- `44C16454-72FBA1C5`: R1/connectivity **FAIL**, 2,028 flagged pixels. All flags are on HD image rows 0 and 127. This is a mixed numeral/icon strip, not a glyph-only image.
- `8BA3BB4D-E0AE221F`: R1/connectivity **FAIL**, 932 flagged pixels on the region's top HD row 1024.
- `8BA3BB4D-36D62A31`: R1/connectivity **PASS**, zero connectivity flags. It looks coherent in the static sheet; this is not live acceptance.
- `8BA3BB4D-190A55AD`: R1/connectivity **PASS**, but its native CLUT is entirely zero and the region is blank/transparent. This gives no evidence of readable HUD artwork.

All four measured regions had correct native-cell centres, zero nonclass alpha and agreement between the two region metrics. The stricter half-texel displacement diagnostic still reports 2,031, 933, one and zero flags respectively; it is not interchangeable with connectivity. Root checked 16 artifact pins, both known process identities and all four existing review sheets. Four candidate hashes already match the private 37c staged bytes; pack membership did not prevent these defects.

Two narrow rim-correction recipes have been reviewed but have not run at this checkpoint. E0 corrects exactly the 932 top-row pixels; 44C targets exactly the 2,028 outer-row pixels. Each copies a verified adjacent inner pixel in the same native cell and corrects defective alpha toward the native class. They preserve cell centres and all untargeted pixels. Outside-region preservation is vacuous for the 44C whole-strip region. Each requires its own fresh bounded CPU grant and private output. Neither is installed, admitted or visually accepted in-game.

The stripe-repair r5 diagnostic actually **failed: 21 of 24 cases passed**, including all 16 negative cases. Its one CPU15 Job took 1.773 seconds, peaked at 87,171,072 bytes and ended empty. Three positive cases remain: the actual S8 border exceeds the strict displacement threshold, a steep stripe has missing crossings at a closing sliver, and a shallow reference has incomplete rows/edge discontinuity. The preceding resource-only CPU85% refusal and earlier r4 failure are preserved. Proposed r6 changes metrics/gates while leaving candidate pixels unchanged; a green result under those altered gates would not establish repaired artwork. The next useful step is a private real-key diagnostic preview that preserves strict failures and before/after crops.

## Distant signs and buildings

The Stage 1 far-background audit and its required erratum distinguish missing source evidence from measured defects. Root checked three current staged green/pink/K texture hashes and confirmed `95A3BCF8-7589E98F` is absent from the pinned staging map. Its four recorded draws and missing source CLUT are reported by the lane, not independently recaptured here. The missing CLUT blocks offline HD authoring/class auditing for that key; it does not prevent the native game from rendering it.

Some distant green/pink features may be city-window dot grids on the `95A3BCF8` page. Screenshots and draw logs from different runs cannot identify the user's exact sign atomically. Whole-page class failures on C/D/F/L/T/U/X do not prove that every named region is defective. The K staged/authored hash difference is consistent with a stale input field followed by PNG re-encoding; pixel equality is still unproved. Previous stronger claims were withdrawn in the preserved erratum.

The E exact-region crops do have region-specific evidence: all 61 measured palette cases report the same 30 bad cells and 11 pinhole cells. The next source work measures whole-page flags inside each region without changing its edge context, and produces one private native-fill E candidate. Review found that the page measurement must bind CLUT identity and verify its local helper before import; the repair must also check C API return codes and PNG readback. Those revisions are pending. There is no defensible total count of all remaining in-game sign/building defects from this audit, and no full-coverage or accepted-look claim.

## Engine and Remix integration

Previously published actual checks remain valid: 99 unchanged ledger regression checks plus 32 display-hazard checks, and 79 pure transport controls. The next ledger R3 source adds conservative native write footprints and requires an exact known mapping. Its authored suites overlap; they must not be summed as unique new checks. It has not been compiled at this checkpoint.

The reviewed glue R3 source tracks writes after sealing and through idle/armed phases, refuses an open GP0 body at seal, preserves immutable pending/displayed frame ownership and binds the first expected target flip. The corrected CPU fixture keeps the same 19 authored checks, makes failed takes null-safe and retains producer/PresentState diagnostics on failure. Root verified 11 source pins and the unchanged helper/check lines. The current build recipe is `11c26259ac40c3db1d9cba06d90e5fd6f54629e90dd0279a05fec6904921157c`; the earlier closure r2 is superseded and unrun. No actual compile/link/fixture pass is claimed yet.

This bridge does not suppress native drawing. Its consumer contract requires an owned taken frame, gating before release, one release and one consumer. Continuous opt-in capture scheduling, G4 material identity, camera/depth/motion, an actual SDK consumer and compositor remain implementation/qualification work. The last actual modern Remix GPU probe still produced black/identical outputs and a shutdown timeout. Mesh indices and lifecycle are being diagnosed from source; no repair or cause is established. Ray tracing and DLSS are not working in-game merely because capabilities or CPU fixtures exist.

The input recorder R3 is also source only. It proposes a durable journal, separate read-only observer profile and owned endpoint/deadline checks. Its new controls have not run, and no ordinary-input stage clear, replay determinism or Drache kill is proved by the existing assisted family data.

## Remaining acceptance

The mini-boss pacing/audio problem still requires an actual qualified gameplay run, SDL/device/listening evidence and measured frame intervals. No new result above resolves it. All seven stage journeys, distant sign/building visual coverage, realistic player/enemy/gun/boss/bullet/explosion skins, modern HUD/menu flows, skin generation/admission/persistence, Remix/G4/compositor rendering, RT/DLSS, installed release and rollback remain open.

[Exact source snapshots, actual CPU receipts, retained failures and independent readbacks](../remaster-audit/cpu-hud-texture-results-20261115/README.md). [Previous engine/transport results](CPU-ENGINE-CLOSURE-ACTUAL-20261114.md). [Full runtime scope](RUNTIME-CONTINUATION-20261113.md).
