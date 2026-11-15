# Region-only composition and menu defects — actual results

Two far-building texture corrections are now composed into a new private comparison pack. The composer overlays only the approved region onto the latest parent, preserving newer artwork elsewhere. This is CPU integration proof, not an installed release or accepted in-game appearance.

## Actual region-O composition

The exact reviewed composer ran on CPU15, BelowNormal, with a Job Object deadline of 120 seconds. It completed at 17:00:30 UTC: child exit 0 in 9.36 seconds, outer exit 0 in 10.582 seconds, child and Job Object tree absent. The resource gate measured 40.2% CPU and 72.21 GiB free. No GPU, game, audio or installation ran. Root explicitly returned CPU15 after independent readback.

Independent verification checks all 1,699 PNG hashes and unchanged parent inputs. Exactly 1,697 PNGs remain byte-identical. The other two remain 2048×2048, with identical whole-page alpha and every outside-region RGBA pixel unchanged. Their approved region matches the frozen artwork exactly:

- 95A3BCF8-07A9568D: PNG SHA256 `52b92c145f051c01e56a596fbce35af4bda0ef3fca201c2c3421f89fe0396e7f`; 184,153 RGB pixels changed.
- 95A3BCF8-60245B3A: PNG SHA256 `6b8aa13e2590d14b11b9c4a1abaf05369684c790341b002e3a2e143fe9b8b859`; 193,636 RGB pixels changed.

Candidate receipt SHA256 `3a83b481010f1c27c99e51eca13a62240c6e6e74684c723dbb0169f35f22a25c`. The native half-open region is [176,112]–[240,176], at scale 8. Captured source words/CLUT CRCs and all-valid word masks are bound in the plan. Full runtime native admission was not rerun for this candidate; motion, shimmer, distant readability and live visual acceptance remain open. Unchanged pages retain their earlier defects, including other background regions.

## Composer behavior and checks

An optional `roi_overlay` contains `native_size` and a half-open `uv` rectangle. The composer requires identical RGBA page dimensions and one integer scale, refuses malformed/outside/fractional coordinates and performs a direct slice copy without resampling. A frozen manifest's region must match the plan. Its pinned original baseline must match every authored pixel outside that region. The overlay then preserves the latest parent's outside pixels, which may contain newer artwork than the artifact's original baseline.

The composer refuses combining this mode with exact-region cropping, an alpha/mask replacement or whole-page cutout RGB fill. Existing companion masks fail closed when a changed page has no explicit compatible replacement. Parent hardlinks are broken by atomic file replacement. Final alpha must remain categorical. The prior non-ROI composition routes are retained.

Root's actual CPU run passes seven unit cases, twenty invalid-geometry/binding cases and a real CLI synthetic composition in 1.066 seconds. The CLI verifies parent preservation, an unchanged second PNG, a replaced ROI and an uninstalled candidate receipt. An independent native Claude review also runs seven cases and checks both real O artifacts against the binder, including rejecting a shifted rectangle. These are component checks; main-level mixed-option/mask rejection is source-reviewed rather than separately exercised by the new test suite.

## Window previews and further defects

Root viewed all six M/I/J preview sheets. They restore native layout, brightness variation and class boundaries instead of the previous invented repeated window grid. The rounded per-cell mean error is at most 0.4375; walls are exact and new alpha center/uniformity errors are zero. The current I pages have 45 center and 828 mixed-block errors; J has 571 and 1,485. The corrected previews still look coarse or soft when enlarged. They are correctness candidates, not finished realistic glass or live acceptance. Their three immutable freezes are now verified; integration into the newer O parent remains pending at this packet checkpoint. The continuous-glass alternative is still a source proposal. P/Q native cutout correction has actual frozen outputs, as recorded below.

The P/Q source investigation identifies real filled-in native cutouts. The two P/Q repairs are built and pinned; they are not installed or live-accepted. Root preserved exact reviewed builder copies when two native sessions reported a weekly limit; these copies were not executed at this checkpoint. Later source review found the original M freeze had already completed while its separate observer lingered; all original native results are used instead of rerunning the copies.

## Actual menu/HUD audit and repair limits

The UI worker's three bounded jobs return exit 0 with no remaining child processes: representative repairs (16.2 seconds, sampled peak 343.4 MiB), gauge class-aware mips (5.19 seconds, 84.2 MiB) and the remaining menu audit (46.36 seconds, 395.3 MiB). These are author receipts preserved here, not tests replayed by root.

The remaining audit checks 133 files and reuses 128 earlier checks, covering its selected 261-file gate set. Only 19 pass its stricter primary center/shape rule. Eight of the new 133 pass; 82 are center-exact but fail the primary rule. This is a scoped asset census, not every game menu or interaction. The selected folders, source hashes, reused records and per-file failures are in the raw report.

Representative class repair passes numeric checks but exposes a major visual failure: 1AD90FC9's authored labels had incorrectly removed the native visible background. Restoring alpha with authored white creates jagged white blotches. That candidate is rejected for usable appearance even though its class checks pass. The smaller BDAE4156 repair remains a separate candidate. A native-color restoration proposal is the next step, pending its own execution and look review. The actual CPU renderer's `conv_1555_to_rgba8` uses 5-bit components shifted left by 3, consistent with the current audit convention; other shader/material paths still need live color comparison.

The gauge mip proposal passes primary and s/2 at both 2048 and 1024 for all 11 keys and both variants, reducing the measured 1024 aliasing. It is not look-accepted or installed. Numeric shape/class success does not finish the modern HUD.

## Timeout evidence validation

The Stage 6 timeout-profile validator has an author pass and an independent support replay: 72/72 cases, matching per-case outcomes, identical pinned source. The independent replay reports exit 0 in 24.122 seconds and a Job Object total of 73 processes, all absent at the end. The author's earlier polling counts of 59/60 children were sampled lower bounds, not exact process totals; the correction is preserved.

The normal stage-clear validator continues to reject a timeout as a clear. This validates a private evidence profile, not a Stage 6 clear or a completed live acquisition. The actual AQ-13 capture is still missing. A separate source-review concern about preserving future mark-record slots is not reproduced or fixed here.

## Unfinished project and payload scope

The previously published modern Remix GPU attempt failed blank geometry and clean shutdown; it remains a failure. No new GPU test occurs in this checkpoint. Full geometry/camera/material transport and accepted RT/DLSS gameplay, all background/palette coverage, actor/gun/boss skins and selectors, native HUD/menu interactions, audio remaster/listening and smooth full gameplay across seven stages remain unfinished. No whole-project percentage, final 4K acceptance or installed experimental release is claimed.

Only reviewed source and reports are published. Generated PNGs, executable/DLL/SDK packages, ROM/BIOS, native binary captures, cards, user state and fenced tokens remain local. SHA256SUMS binds the immutable packet, and SOURCE-MAP records copied inputs. Historical packets are unchanged. Dated monitoring/session metadata is not proof of an active model turn or uninterrupted future work.

## Later actual results and preserved scheduling failure

Root independently verifies all 39 frozen file pins across M/I/J/P/Q, all five READY/manifest/SUMS bindings and original worker/wrapper absence. M ran in its window: child/outer exit 0, 64.786 seconds, sampled peak 0.765 GiB. Its companion observer matched its own command and delayed the shell. P/Q subsequently ran for 2.415 seconds and passed functionally, but started about 87 seconds outside the granted batch bound. That is a scheduling violation, not an overall compliant PASS. The author disclosed stopping only its own second observer. Receipts, sampled memory data and the disclosure remain preserved. No successful freeze was rerun by root.

Root viewed the P/Q sheets: native holes are restored around the antenna/ladder/tank, retaining authored visible surface colors. Edges remain native-cell shaped; this is private correctness review, not final fidelity or in-game acceptance. An eight-entry ROI plan binds those frozen inputs to the newer O parent. Its first integration attempt refused a changed shared runner hash before Popen, so no composition child or candidate was created. The failure is preserved. A fresh run requires a new grant and the already preserved exact reviewed runner; no retry under an expired or consumed grant.

UI follow-up runs fix the white background blotches using exact native colors on newly visible pixels. The author reports remaining stair-steps and pinholes; root has not live-accepted the labels. Two chunks process all 72 near-pass runtime representative units with primary passes, with separate source hashes and resume records. These units are not a new count of accepted menus. Remaining at that checkpoint: 46 palette twins, 41 higher-resolution pack units, 51 substantial-error units requiring look review, and about 1,400 PNGs outside the selected audit. All interaction/live gates remain open.

The initial S2 actor map missed existing candidate indexes. Its corrected map is included: three previously labelled missing enemy keys and eleven Stage-2 HUD palette keys already have candidate assets. Do not author duplicates from the superseded map. Two other shared-file keys have complete source but draw only tiny flat gray slivers; the support source review does not prove a pod identity or a skin-selector mapping. Native-equivalent coverage is not a new realistic skin.

The initial unpublished packet preparation is preserved locally with its outdated pending-state text. This final packet corrects that text before GitHub publication and preserves the raw old/new reports with their dates.
