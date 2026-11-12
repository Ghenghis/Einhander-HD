# Einhänder completion plan

Updated 2026-11-12. Status: **in progress; full remaster and full-game E2E are not complete.**

Public showcase update: the current reviewed UI/title composition has 1,194 keys; isolated facade experiments add one exact region. All 324 known mixed-family palette keys are present in that composition. These are texture-key counts, not accepted buildings or completion percentages. The older session counts below are retained as historical planning evidence. Local process/evidence resume state is kept separately from the public source snapshot. See [the gallery](../docs/GALLERY.md) and [comparison notes](../docs/COMPARISONS.md) for the status of published imagery.

## Objective and scope

Finish the remaster with a traceable source map and actual in-game acceptance for every component. Include every player hull, small and large enemy, boss and boss phase, weapon, Gunpod, projectile, effect, sign, building, background layer, window, light, palette cycle, animation, HUD element, menu, result screen, and available unlock/end state. No category is silently excluded. Unknown ownership or an unsupported path becomes an explicit remaining item.

2160p rendering, a large PNG, a neural upscale, an authored restoration, and live verification are different milestones. Preserve the original 4:3 composition; the current isolated 9x gameplay surface is 2880×2160.

## Historical session evidence and remaining scope

- The installed base has 964 files: 311 neural RGB upscale origins and 653 nearest-only origins. These are processing origins, not 964 accepted remastered components.
- The current UI composition has 1,011 texture keys. Its 130 overlay inputs resolve to 118 unique overlay keys: 71 base replacements and 47 additions; 893 base files remain unchanged. Texture keys are not object counts or completion percentages.
- A separate 1,522-file expanded candidate contains a 558-file cached/local UltraSharp batch. It has not become comprehensive authored background/sign acceptance. Its families also include enemies; it must be reconciled with the current UI candidate instead of being counted as 558 background components.
- The existing fleet catalog lists five playable hull identities (three starters and two reported secrets), 12 Gunpods, and 40 conservative enemy model groups, including 12 bosses/midbosses. These are a starting inventory, not exhaustive runtime mappings or completed skins.
- Current permanent material work covers specific player keys and strips of one observed Stage 1 enemy family. It does not establish all small enemies, large enemies, bosses, weapons, model parts, poses, or stages as skinned.
- The copyright/SQUARE strip has been rebuilt and independently reviewed in a fresh live v5 title capture after actual replacement submissions. Native PILOT creation and restart/load were verified on private test cards.
- Font48, menu8, banner2, blueprint11, diagram6, title2, footer3, Results typography and Results art5 pass source/composition checks. The newly prepared v6 pack still needs its final live replay. Do not transfer v5 visual acceptance automatically to changed v6 files.
- Some city sign/glyph regions remain protected nearest-source content. Their protection prevented accidental corruption; it is not completion. The distinct sign count is not established, and “about 50” is not an audited count.
- The Stage 1 world audit independently verifies all324 queue palette sources in ten historically grouped mixed page families. The UI candidate inherits184 at2048² from the base and lacks140 known variants. The separate expanded candidate has322 of these at4096² and two fallback2048² outputs; dimensions alone do not pass authored detail or animation acceptance. Six protected native UV rectangles span four families. These are page/palette counts, not counts of signs, buildings or complete animation loops; those semantic totals remain unknown.
- Gallery/unlock/endgame coverage is not established by the blank/new native PILOT profile. The scoped fixture search found no documented progressed Gallery fixture.

## Completion register

Create one record per semantic component and per meaningful state, with links between shared sources and placements. A texture shared by an enemy and a building cannot be assigned wholly to one owner without proof.

Each record must contain, where applicable:

- Stable component ID, name, category, model/part, stage, placement, and confidence in ownership.
- Disc/archive/source location; observed guest upload address or producer PC when established; VRAM page, word rectangle, depth, texture CRC, CLUT coordinates/CRC, UV bounds, blend mode, and transparency classes.
- Native reference frame and source proof. Raw-word, CLUT, validity and decoded-pixel checks must agree. A raw row alias requires actual byte equality and its actual palette.
- Animation/palette/frame sequence, lighting states, damage states, camera/pose conditions and other contexts that expose it.
- Authored asset/version, source/authoring dimensions, protected bounds, changed coverage, hash and composition lineage.
- In-game replacement admission and visual evidence, readable motion samples, acceptance checks and remaining defects.

Use separate states: **unmapped → mapped → rebuilt → integrated → live-verified**. Add defect flags and unsupported states. “Mapped” is not “rebuilt”; “integrated” is not “live-verified.” Procedural geometry/lights need producer/draw evidence rather than an invented texture address.

## Work order

### 1. Freeze and reconcile existing work

Keep source ROM, native references, private test cards, all original files and rollback receipts intact. Reconcile installed base964, expanded1522, UI1011, material profiles and all authored artwork manifests into one composition ledger. Classify each input as source, nearest enlargement, neural upscale, authored restoration, or unaccepted experiment. Merge only verified current-source work and make every omitted candidate explicit.

First finish live verification of the prepared UI candidate: solid fighter/ARM descriptions, large Ranking digits, all menu colors, copyright, controller/slot diagrams, blueprints, and the five-strip Results aircraft image. Check text transitions, cold loading, transparency and strip seams. Keep the proposed indexed-palette runtime experiment unaccepted and out of the release; the validated runtime is unchanged.

### 2. Complete source and ownership mapping

Map all starter and secret player hulls, all parts, all 12 known Gunpods, and each enemy/model group. Include tiny drones, transports, turrets, ground machines, large ships, bosses and transformation/damage phases. Expand the inventory whenever a new family appears.

Map the full scene: sky and distant skyline, every building type and facade, foreground/occluding geometry, signs and lettering, windows, rooftop beacons, reflections, fog/glow, background movement and animated palette/upload sequences. Track unique designs and every placement separately. Do not count one atlas or one color variant as all buildings/signs.

Map effects and UI states too: muzzle flashes, projectiles, beams, trails, impacts, explosions, pickups, weapon loss/durability, ammo counters, results graphs/grades, Game Over, continue, saves, Gallery, endings and credits. Classify intro/video content separately so 240p video is not misreported as restored texture detail.

Deliverable: source/ownership map with captured evidence and an explicit unmapped queue.

### 3. Run multiple independent sweeps

1. **Inventory sweep:** record full stages and routes, every visible draw/source family, uploads, CLUT variants, UV regions and timed events. Include alternative branches and boss phases.
2. **Fleet and equipment sweep:** repeat with every player hull/loadout, every enemy type, both arms, all known weapons, pickups, ammo extremes, switching, damage/destruction and material profiles. Verify shared texture ownership and accents.
3. **World sweep:** repeat camera/movement paths that expose foreground, middle and distant layers, all sign placements, rooftops, window patterns and different building surfaces. Dedicated lettering review must preserve the actual wording/glyphs.
4. **Animation sweep:** capture complete loops and transitions—neon/palette cycling, blinking beacons, lit/unlit windows, streamed signs, glow, scrolling layers, weapon/effect animation and boss transformations. A single still does not pass an animation.
5. **Independent omission sweep:** compare raw draw/upload inventories against the completion register and the assembled pack. Review small, distant, obscured, shared-page and newly encountered assets deliberately.

Repeat after repairs. Require both full registered inventory coverage and two complete repeated sweeps with no newly unclassified component. Repeating an incomplete route twice is not full-game coverage.

### 4. Rebuild the remaining components

Prioritize visible original content and mismatched quality: city lettering/signs, window/light cycles, building surfaces and distant layers, uncovered ship/part families and weapons, then effects and remaining menus/results art. Work in bounded source regions so improving a ship does not repaint neighboring signs or unrelated atlas content.

Use coherent contours, readable lettering, deliberate outlines/depth and source-faithful mechanical detail. Preserve source geometry, wording and intended color/material identity. A generic upscale or recolor alone does not pass. Preserve or deliberately reconstruct PSX categorical coverage/STP behavior; forcing the old pixel-shaped alpha footprint can defeat smoothing and must not be an automatic main-output requirement. Keep strict source-footprint comparisons separate.

Deliverable: reproducible authored assets with source, region, palette/animation, alpha and protected-pixel proofs.

### 5. Integrate one isolated candidate

Compose all verified work with exact keys/manifests, scoped conflict resolution and provenance. Verify full PNG decodes, hashes, dimensions, source/CLUT mapping, animation variants, alpha classes and untouched regions. Treat missing/rejected replacements as defects, not silent exclusions.

Do not accept a first screenshot before asynchronous replacement decoding/submission. Require actual draw evidence and a fresh visible frame after readiness. Recheck cold starts, scene re-entry, palette changes and cache eviction.

### 6. Full E2E and quality regression

Run native boot/profile creation/restart/load; all settings; fighter and weapon selection; gameplay with all registered craft/enemy/weapon/world states; pause/resume/quit; death/continue/Game Over; results and all graph modes; rankings; save/load/discard-cancel; stage/unlock/Gallery/end states.

Use documented isolated fixtures for otherwise locked states. Never guess unlock bits or treat a locked screen as passed. Separate natural gameplay proof from RAM-assisted art/state fixtures. Do not use test-fixture outcomes as survival, difficulty or balance proof.

Check readable contours at actual display scale, atlas seams, clipping, palette/STP changes, transparency, flicker, missing animation frames, lighting consistency, layer ordering and motion. Compare native and candidate using matching routes/poses. Measure representative steady gameplay without screenshot/readback load and competing renderers; a good settings-screen average is not a full-game performance pass.

Deliverable: per-component and per-journey acceptance ledger with exact captures, motion, source/draw brackets, results and remaining failures.

### 7. Release gate and delivery

Mark complete only when every in-scope register item is live-verified, all required states are covered, no unresolved omission/defect remains, and the final assembled build—not a prior candidate—passes replay and pacing checks. Explicitly resolve missing scenes/content; do not quietly remove them from the denominator.

Deliver one versioned build/pack, source and composition manifests, source/ownership map, accepted before/after captures and motion, complete E2E ledger, reproducible launch/check commands, and tested rollback. Preserve user saves and original settings/files. The report must distinguish processing resolution from authored detail and actual rendered output.

## Previous session handoff (superseded by RESUME_STATE.json)

- Current running isolated candidate: v5, PID8760, port4371, private test state. Continued from its Pause menu with Cross; newest draw frame advanced104891→104920 in0.7s and pad returned0xFFFF. The composed `handoff-after-continue.png` visibly shows gameplay. Later natural progression may change that state.
- v5 RAM was used for a bounded Game Over repeat fixture. Writing lives0 underflowed on the next loss; this was corrected to1 and recorded. Those fixture captures are not natural-life-count/balance proof. Several filenames predate visual confirmation; use the explicit ledger, not filenames as state assertions.
- Prepared but not launched: `dev-center-evidence/hud-4k-candidate-20261112-v6/candidate.json`. Composition is1,011 keys. Independent `preparation-revalidation.json` passes final launcher provenance, all1,011 PNG hashes, and both candidate/rollback executables and settings. A known valid private PILOT card was seeded from the closed v4 test session; `private-card-seed.json` records its hash. No user cards are mounted.
- Runtime: `C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112-v3/Einhander_Recompiled.exe`, SHA256 `0b746a7f10d8db0f5b2481b6c5859913e4b209468ef40cb45928a21f3027942e`. BIOS save, title-edge clipping and real GL hi-res capture fixes remain included. No indexed-palette runtime feature was integrated.
- Next: verify the existing v5 PID/path against its launch receipt, close only that owned candidate, and confirm port4371 is free. Then launch v6 through its prepared `launch-candidate.cmd`, verify its private PILOT load, and replay changed UI/art states. The launcher intentionally refuses an occupied candidate port. Map the actual Game Over wordmark using an observed GP0/VRAM bracket; the animated8E footer queries were not proof of Game Over ownership.
- Then execute fleet/world mapping sweeps and integrate the remaining verified work under the release gate above. No assertion of complete ship, background, sign, lighting or animation remastering is supported yet.

Supporting records: `overall-remaster-coverage.json`, `hud-restoration/e2e-coverage.json`, `hud-restoration/final-composition-check.json`, `hud-restoration/native-card-fixture-inventory.json`, `hud-restoration/fleet-weapon-skin-gap-audit-20261112.json`, `background-audit-20261112/stage1-background-gap-inventory.json`, v5 capture/command evidence, and all individual restoration manifests.
