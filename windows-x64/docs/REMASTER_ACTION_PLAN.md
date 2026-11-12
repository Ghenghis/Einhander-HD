# Einhänder 4K implementation plan

Current milestone: finish Stage 1 and its boot/title, menu, HUD and demo-play
visuals. Later stages extend the same pipeline after this milestone passes.
Keep the layout, wording, glyph identity, animation, palette behaviour and
gameplay intact. Restore visual quality for a 3840x2160 output; retain 4:3
composition where the original uses it.

## Current delivery phases — November 12

The requested quality target is a substantial visible improvement in contour
quality, layered lettering, color, surface detail and depth. Enlarged images
alone are not an acceptance result. Each component follows the phases below;
components with verified mappings proceed to authoring while other mappings
are still being collected.

1. **Inventory and exact mapping.** Track title art and logo tiles, loading and
   card prompts, mode/configuration screens, fighter and arm selection, in-game
   HUD, pause, death/continue and results. Record source CRC and palette CRC,
   native dimensions, UV rectangle, sprite bounds, blend/STP class, wording,
   scene and a directly reviewed frame. Distinguish weapon inventory slots,
   ammunition, score/multiplier indicators and other meters using the native
   manual and observed behavior; do not invent health bars or labels.
2. **High-resolution authoring.** Reconstruct the original glyph contours at
   high resolution, preserving character identity, spacing, baseline and atlas
   positions. Use controlled inner faces, borders, highlights and shadow depth;
   remove stair-step edges and clipped corners. Restore plates, slot frames,
   weapon indicators and numerical overlays consistently. Preserve original
   transparency/STP semantics. Authored edge coverage changes are tracked
   separately from the exact-mask reference so the old jagged silhouette is
   not accidentally treated as a quality requirement. Illustrated background
   masters, the game logo and interactive text are separate assets.
3. **Candidate integration.** Compose verified artwork with the existing pack
   in an isolated candidate. Replace candidate files atomically because base
   files may be immutable hardlinks. Retain source files, authoring scripts,
   hashes and rollback. Register every exact required palette variant. A source
   admission PNG or concept master remains explicitly distinct from completed
   high-resolution artwork.
4. **Visual and runtime verification.** Capture real boot, title, loading,
   selection, configuration, gameplay, pickup/equip/fire, pause, death,
   continue, restart and result states. Check glyph spelling and contours,
   corners, alignment, atlas seams, UV bounds, alpha/STP blending, palette
   animation, clipping, bright/dark readability, and motion stability. Require
   actual replacement draw receipts as well as directly reviewed images.
   Test the 2160-line 4:3 viewport with private render settings; record actual
   capture dimensions and frame pacing. UHD presentation must preserve the
   original composition rather than stretch it.
5. **Verified delivery.** Install only components that pass their asset, GPU
   and in-game checks, retain rollback, and publish the remaining component
   list. A single passing screen does not complete the HUD/menu milestone.

### Current verified anchors and implementation work

- `DD0B6963-4C1DD349`: validated reusable 256×128 UI glyph atlas; includes
  pause, continue, start, countdown, digits and prompts. HUD contour/edge
  authoring is in progress in an isolated supplement.
- `323B5FB0-1C7962B3`: actual GAME START draw, native UV `[0,43,88,55]`;
  other menu words share its native page and need bounds-preserving packing.
- `282438F3-00000000`: validated 16bpp title tile at VRAM
  `[704,0,256,256]`, drawn through UV `[0,0,254,239]`. The hand artwork and
  part of the logo are baked together; the complementary right-hand title
  draw must be accounted for before the complete title is accepted.
- Current player stock/gold/neon comparison has directly reviewed solid-hull
  frames and matching submissions for all five selected keys. Warm markings
  remain visible. This verifies that local material change, not finished
  surface artwork or every ship pose.
- Cannon Cross-only tests repeat HUD `15 → 14 → 13`. Ammunition RAM
  correlations remain candidates; the late GP0 window does not prove the
  projectile lifetime and is excluded from that acceptance claim.
- Greif's 60 missing native-page replacement entries were recovered as two
  indexed texture families plus palette variants. Their isolated 256×256
  source admission proofs pass loader/GPU checks; they are not finished 4K
  artwork. Full gameplay admission and part/motion checks remain required.

### Collection fixes and remaining coverage gates

- Short runs can request exact missing source keys. Successful source queries,
  GL submissions, material generation/profile and temporary diagnostic scope
  are recorded separately. Source filtering does not imply exhaustive capture.
- Preserve the bounded original-upload cache between short runs on the next
  research launch. Previously disabled inter-run caching could leave only
  surviving fragments after a texture upload was partially overwritten.
- Let the game's invulnerability countdown expire naturally for clear hull
  captures. Direct zero writes can skip its model-visibility clear branch.
- Whole-stage acceptance still requires the remaining boss phases/destruction,
  applicable route actors, other selected craft/loadouts, effect lifetimes,
  equipment transitions, results and persistence checks. No whole-game or
  whole-Stage-1 completion percentage is inferred from texture counts.

## Completion checklist

- [x] Re-extract the original disc read-only: 20 files, 229 archive entries,
  100 validated TIM images. Originals and extraction manifests retained.
- [x] Inventory available runtime sources: 1,501 independently verified
  texture/palette keys; 57 older original backups remain unverified.
- [x] Fix palette corruption and independent GPU texture cache reuse.
- [x] Begin the local RTX 3090 Ti world/machinery batch: 558 selected entries,
  two UltraSharp 4x passes, original transparency/STP classes, per-file hashes
  and resumable checkpoints. Outputs are candidates until tested in game.
- [x] Generate a transparent WAIT / DEMO PLAY UI master with the image tool.
- [x] Export category-specific ComfyUI API graphs under
  `remaster-audit/workflows/`.
- [ ] Capture each boot/menu/HUD state and record the asset key, UV rectangle,
  text content, palette identities and a native screenshot.
- [x] Expose native demo play in the web and in-app dev controls, with clear
  state feedback and an exit/release control. Do not call synthetic bot play
  a native demo.
- [ ] Build UI sprite sheets in the game's original atlas layout. Include WAIT,
  DEMO PLAY, countdown, start, pause, continue, fighter/weapon selection,
  configuration, loading/error prompts, status messages and score/result text.
  Capture actual wording before creating additional labels.
- [ ] Create faithful high-resolution logo/background masters. The previous
  title-image proof changed details and remains rejected/uninstalled.
- [ ] Restore HUD plates, counters, weapon/ammo indicators, lives and status
  graphics. Use the same native glyph positions and animations.
- [ ] Integrate the completed assets into an isolated 4K candidate pack and
  runtime. Preserve the installed Stage 1 pack and executable rollback.
- [ ] Compare stock, existing enhancement and new 4K output using native demo
  sequences and the same scene checkpoints. Record differences in rendering
  between DuckStation and the recomp rather than presenting them as identical.
- [ ] Complete Stage 1 through the boss/results flow; test pause, death,
  continue and restart. Verify text, palette cycling, STP effects, seams and
  frame pacing. Run real-GPU regressions for renderer changes.
- [ ] Install the tested milestone build and pack, retaining rollback files.

## Asset accounting

The complete disc-file extraction is not a complete texture dump. Streamed
pages, CLUT variants, glyph atlases and framebuffer uploads require observed
runtime mapping. Track each item through:

`observed -> source verified -> category assigned -> restored master -> atlas
packed -> replacement draw observed -> visual/motion checked -> installed`.

An asset is complete only at the last step. File count, PNG dimensions or a
successful model run do not establish visual completion. Unknown keys and
uncaptured screens remain explicitly open in the manifest.

## Workflows and safeguards

1. **World, ships and machinery:** native raw/CLUT decode, source verification,
   UltraSharp RGB restoration, 16x dimensions capped at 4096 per axis, exact
   native class mask, then UV/seam and temporal palette checks. Preserve glyph
   regions in mixed pages until their dedicated masters are ready.
2. **Dithered art:** compare the installed 1x DitherDeleter and PBRify models
   against UltraSharp on representative crops. Cleanup is selective, not a
   mandatory pass over all textures.
3. **Menus and splash art:** image-tool masters referenced to native artwork;
   retain layout and animated layers. Verify logo geometry and wording. Do not
   replace a whole interactive screen with a flattened screenshot.
4. **Text and HUD:** account for word strips versus reusable glyph atlases;
   recreate exact spelling and glyph positions, pack into the native UV layout,
   preserve palette/STP behaviour, and check every reconstructed label in game.
5. **Effects:** preserve transparency, black STP texels and palette cycles;
   enhancement must not make effects opaque or flicker between palettes.
6. **FMV:** six extracted movie streams have their own inventory. They are
   separate from this Stage 1/menu texture milestone and require a verified
   video replacement path before integration.

## Current work and evidence locations

- Source inventory: `C:/github/REMASTER_STAGING/full-remaster/queue.json`
- GPU checkpoints: `C:/github/REMASTER_STAGING/full-remaster/world-machines/`
- UI masters: `C:/github/Einhander/remaster-audit/assets/ui/`
- Native demo capture: `C:/github/REMASTER_STAGING/full-remaster/ui-demo/`
- Existing validated pack: `windows-x64/hd-textures/stage1-v1/`
- Existing renderer checks: `C:/github/REMASTER_STAGING/hd-coverage/`

The attempted stage-select RAM shortcut produced a black display in an
isolated session and is not accepted as later-stage coverage. Native menu
navigation/demo capture is the next verified path; no user cards were used.

## Resumed work, November 12

The previous chat ended with a tool-level `Bad Request`. Its on-disk outputs
were retained. The GPU worker had also exited during a progress checkpoint:
Windows denied replacing a JSON file while a reader held it open. Checkpoint
writes now retry brief sharing locks. A real Windows file-handle regression
check passed, and the UltraSharp batch resumed from verified completed files.

Native attract controls now work in both developer interfaces: release input
at the title and wait for the game's own attract sequence, send a short Start
press, or release all input. Status explicitly says when it is waiting; it
does not claim that the game has entered a demo. Browser button/status checks
and real in-app button captures are in `remaster-audit/verification/`.
The launcher registry adapter, wide-panel rendering, and duplicated source
tail were repaired so the current sources compile. The rebuilt executable
is installed, with rollback under
`build-release/backups/20261112-resume-devtools/`. Stale relocated BIOS/disc
paths are corrected. `Play-HD.cmd --check` passes.

One resumed 12-second cached FMV sample sustained about 60 fps with zero audio
underruns and GL errors. That sample used no HD pack, dumping or rewind;
it does not establish normal-launcher or full-game performance. Further HD
playback evidence is stored in
`C:/github/REMASTER_STAGING/full-remaster/validation-cached-hd/evidence/`.
The installed rebuild with the existing HD pack also passed an active
15-second FMV sample: about 60 fps, 459 decoded movie frames, zero audio
underruns, and zero GL errors. Authoring workers were suspended during that
sample and resumed afterward; dumping and rewind were disabled. The report
is `installed-cached-hd-active-fmv-av.json`. Combat, rewind-enabled normal
playback, and the expanded pack still require separate checks.

`build_expanded_pack.py` assembles an isolated pack from verified sources and
the GPU batch. It protects lettering rectangles in mixed texture pages and
retains native fallbacks for UI assets awaiting faithful redraws. Its output
is `C:/github/REMASTER_STAGING/full-remaster/stage1-expanded/`; the installed
`stage1-v1` pack remains the reference. An image-tool whole-atlas attempt is
retained under `remaster-audit/assets/ui/` as rejected because it changed
glyphs/layout. It was not installed.

The new card-enabled capture recognizes an empty card and reaches the native
"No game data" prompt, then the FMV, title, configuration and fighter screens.
Name registration and restart persistence still need verification. Captures
and raw/CLUT sidecars are in
`C:/github/REMASTER_STAGING/full-remaster/ui-capture-v2/`.
