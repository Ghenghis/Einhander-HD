# Artwork produced, verified and still required

November 14 continuation: the [green/pink sign audit](STAGE1-SIGN-QUALITY-20261114.md) now includes a private live five-sign run and [broader world census](../remaster-audit/world-sign-census-20261114/WORLD-SIGN-CENSUS.md). The inspected distant green/pink panels are city window-light atlas regions with soft/grainy replacements. Twenty-one drawn keys are absent from the tested pack, and126 drawn legacy keys have unused deliverable candidates in sampled earlier routes. These are texture-key counts, not full-game coverage. No revised art is accepted or installed. The [RTX Remix direct SDK](RTX-REMIX-SETUP-20261114.md) now initializes successfully, while scene transport and real gameplay capture/rendering remain unfinished. [Full4K implementation scope](4K-REMIX-IMPLEMENTATION-PLAN.md).

Snapshot: November 13, 2026 (America/Phoenix). The art pipeline has produced substantial Stage 1 work and candidate exports for every later stage. **Full-game artwork, Stage 1 release acceptance and seven-stage E2E are incomplete. There is no verified whole-project completion percentage.**

The installed Stage 1 pack has **964 PNGs**. The larger private Stage 1 composition has **1,669 color PNGs**, including **837 authored entry records**, plus **two emissive masks**. Its **226 native-region verification records report zero failures**. It is explicitly uninstalled and not accepted as a complete visual candidate. A PNG, palette key, sprite frame, authored entry, object, frozen revision and accepted gameplay state are different units.

[Machine-readable inventory and evidence hashes](media/gallery/artwork-inventory-results.json) · [Runtime and E2E handoff](RUNTIME-CONTINUATION-20261113.md) · [Exact seven-stage capture requirements](../remaster-audit/runtime-diagnostics-v58/capture-checklists/INDEX.md)

## How much production is retained

The [bounded frozen-folder census](media/gallery/artwork-frozen-inventory-snapshot.json) records **33 authoring lanes, 263 retained sets and 11,106 PNG file paths**, with **1,764 distinct keys parsed from filenames**. It counts all retained versions, resolutions, alternatives, masters and previews. **954 keys occur in multiple sets. This is production volume, not 11,106 completed assets.**

The lane grouping records 213 Stage 1/shared sets with 9,891 PNGs; Stage 2 12/332; Stage 3 3/156; Stage 4 9/138; Stage 5 7/97; Stage 6 11/394; Stage 7 8/98 (sets/PNGs). The “Stage 1” grouping assigns every non-w7 lane there by name, including cross-stage HUD and menus. It does not prove stage residency. Three retained sets lack manifest.json: two facade sets and one player set; their names are in the census. This metadata scan did not decode or hash each PNG. The current-version export counts below are deliberately smaller.

## What the RTX 3090 Ti work means

Claude's project ComfyUI uses port 8188 on GPU0, the RTX 3090 Ti. The local GPU queue log records 85 owner/start/end slot records in this snapshot. It does not map every final PNG to a successful device job, a model, a retained output, or accepted quality. Therefore an exact count of final assets created specifically by that GPU remains unknown.

The delivered work mixes neural generation/upscaling with CPU vector reconstruction, categorical alpha repair, palette variants, atlas composition, material layers and reuse. The 964-PNG baseline's historical manifest classifies 311 neural-upscale origins and 653 nearest-only origins. The latter are useful preserved source pixels; they are not 653 newly painted objects. Retained versions and preview folders are not additional completed assets.

## What has to be created

- Source-backed color PNG replacements for backgrounds, facades, roads, sky, signs, player hulls, enemies, bosses and Gunpods. Full atlas pages and bounded regions must retain their original ownership and UV layout.
- Sprite and effect textures for muzzle flashes, projectiles, impacts, smoke, fire, electricity, explosions, pickups, damage and destruction. A single image is insufficient where ordered frames, palette phases or different states are used.
- Exact transparency/STP/opaque classes, emissive masks and mapped material/detail layers; room/window content and lighting where appropriate.
- Legible sign lettering, font strips, HUD digits and labels, weapon logos, craft diagrams and title/menu/results/evaluation/Continue/Game Over/unlock/ending/credits states.
- Source identity, CLUT/palette evidence, draw/UV mapping, animation order and shared-page composites. Unknown sources must be captured before an invented identity or palette is admitted.

The existing game geometry and animation code are retained. The plan does not establish a requirement to replace every model with a newly authored mesh. FMV and enhanced music/voice/SFX are separate media workstreams; they are not included in these PNG totals.

## Stage 1: installed baseline and private authored composition

The frozen composition's 837 authored entry records are grouped as: player/Gunpods 78; enemies 279; sky/facades/green lighting/canyon 84; signs 42; effects 65; HUD 187; title/menus 10; polish 92. These groups sum to 837 entries and include strip, palette and state variants. They are not counts of unique pictures or models.

Bounded in-game evidence is stronger than mere file production but narrower than complete acceptance: the Astraea run observed 448 authored entries, all five new hull bindings and all 32 canopy phases; the lighting run submitted all ten delivered building tiles; other runs observed nine font bindings and evaluation screens. See [Stage 1 status](STAGE1-COMPLETION-STATUS.md), [wave 3](STAGE1-WAVE3-RESULTS.md), [emissive results](STAGE1-EMISSIVE-RESULTS.md) and [UI results](STAGE1-UI-RESULTS.md).

The current Drache ledger reports 195 of 218 known keys delivered. The remaining 23 death-flash keys require exact live CLUT capture. This is a finite known-key gap, not the entire remaining Stage 1 workload. Shared-page ownership, native-source gaps, HUD fades, weapon/ship states, look choices and final combined motion review remain open.

The older W4 import-v3 receipt reports 635 rows, 1,769 files and zero mismatches. It is a separate delivery census containing revisions and variant files; do not add it to the 1,669-PNG candidate. Import-plan-v5's 202 file rows predate later Stage 3/5 work and are stale as a current total.

The separate W4 v4 addendum proposes 330 keys/rows after v3: 104 additions, 220 replacements and six no-ops. It records 729 export-file checks, zero reported class mismatches and zero composite-class mismatches. However, 83 keys still need proof pinning and nine file comparisons were not comparable. These are source/merge gates, so this proposal is not an installed or fully verified combined pack.

## Stages 2–7: current selected candidate exports

These counts select current versions and exclude superseded alternatives. They were reconciled from existing manifest/ledger metadata, without new GPU work or decoding/hashing all PNGs. Existing class-check reports record zero mismatches for the selected passing sets. **None of these later-stage sets has completed live key/CLUT confirmation, in-game visual acceptance or installation.**

- **Stage 2: 39 keys / 78 runtime PNGs.** Eight cycling-phase keys; four sky/ground; twenty train-car; seven opening FX. Current selection combines prep-v2, one retained sky-ground-v2 key, three sky-ground-v3 keys, train-cars-v4, and selected FX v1/v2/v3 keys. Remaining: live key/CLUT confirmation, full-rate draw/UV logs, train/ground motion and shimmer review, mechanical edge quality and integration.
- **Stage 3: 39 keys / 78 runtime PNGs.** Twenty-five machinery/wall keys and fourteen signage/props. A 25-key material alternative replaces those wall keys and adds no unique keys. Remaining: live UV, palette, motion and look acceptance; final selection and integration.
- **Stage 4: 11 keys / 22 runtime PNGs.** Six world, three enemy and two effect keys. Effects v2/v3 are alternatives. The shared Stage 4/5 panorama 05E1881C is not built. Another 233 static keys are classified as renderable later; that is a deferred source scope, not a verified count of required new paintings.
- **Stage 5: 12 keys / 24 runtime PNGs.** Five world, five Dürer armour and two effect keys. Remaining: three unresolved 8bpp Dürer regions, shared panorama, live palette/UV/motion review and integration. Another 245 static keys are classified as renderable later.
- **Stage 6: 101 current keys / 202 runtime PNGs.** Eighty-three batch2 keys plus eighteen initial keys: explosion 5, bolts 3, camouflage 6 and smoke 4. Later smoke/FX passes replace existing keys and add zero. The ledger prose “83+21” is inconsistent with the manifests; the supported total is 101, not 104. A 43C26C42 FX revision failed and stays excluded. Hull material work needs GP0 part masks; residency/animation and the separate timer-failure outcome still need live evidence.
- **Stage 7: 26 exported candidate keys / 52 runtime PNGs.** Twenty-two fleet-part, two backdrop and two planet pairings. One planet pairing, C4FDEDD2-EAD968A1, is unlisted and inferred from the other limb's CLUT slot; it needs live proof. Explosion, transmission and hull masters/previews have no runtime key exports and are not included as completed runtime assets. Fourteen dense kanji retain fallback. Remaining: source/CLUT confirmation, keyed exports, motion, destruction/transmission states and integration.

The per-lane PNG counts include multiple resolutions. Do not add their keys to Stage 1 or infer a global unique-object total: stages can share sources, and the complete dynamic-state denominator is unknown. Zero completed later-stage acceptance is different from zero produced artwork.

## Where the remaining work lives

All paths below are local-only locations beneath C:/github/Einhander/remaster-audit. Selected source-receipt hashes are in the inventory JSON.

- Stage 1 composition: dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/; candidate.json, native-verification.json, input-manifests/ and pack/.
- Stage 1 revisions and missing sources: comfy-authoring/w6-drache/STATE.md and CAPTURE-REQUESTS.md; comfy-authoring/w6-native-gaps/LEDGER.md, F44-OWNER-CONFLICT.md and CAPTURE-REQUESTS.md; earlier t1–t9 and w2–w6 lane ledgers.
- Stages 2 and 3: comfy-authoring/w7-stage2/LEDGER.md and w7-stage3/LEDGER.md; each lane's frozen/ directory and capture requests.
- Stages 4 and 5: comfy-authoring/w7-stage4/STATE.md and w7-stage5/STATE.md; shared-panorama and 8bpp decisions are still open.
- Stage 6: comfy-authoring/w7-stage6/LEDGER.json, GPU-RESUME.json, frozen/ and failed/.
- Stage 7: comfy-authoring/w7-stage7/LEDGER.md and frozen/stage7-planet-limb-v1/manifest.json.
- Cross-stage source acquisition: fullgame-prep/static-extraction/stages-v4/FREEZE.json; claude-backlog/capture-checklists/. The [published checklists](../remaster-audit/runtime-diagnostics-v58/capture-checklists/INDEX.md) contain the exact missing-key lists and route gates.
- Global ships, Gunpods, effects, signs, HUD transitions, menus and end states: [Claude work queue](../coordination/CLAUDE-WORK-QUEUE.md) and the [full restoration plan](../remaster-audit/REMASTER_COMPLETION_PLAN.md).
- Per-job GPU scheduling provenance: comfy-authoring/gpu-log.jsonl. It is a scheduling log, not a completed-asset ledger.

## What counts as complete next

For each selected candidate: confirm the real runtime source and CLUT, check categorical classes and owned regions, integrate into a fresh hash-pinned composition, observe the actual mapped draws and all required states in motion, then pass normal gameplay/audio and release/install checks. Retain failures and alternatives separately. Until those gates pass, the honest status is produced or source-checked candidate, not a finished stage or remaster.
