# In-game menu and Skin Factory gaps

November 13, 2026. Static source audit following the requested player/enemy ship, gun, bullet and effect customization. These are implementation and acceptance gaps, not a claim that new controls have shipped.

## What exists now

The native launcher links to a browser material laboratory. Its current controls select fourteen colored finishes plus Stock, six reusable detail maps, and separate player/enemy material channels. It can save or stage a preset, export an atlas preview and send color changes to a running game. Detail layers and texture-scope changes require restart.

Saved presets can launch through Play-Saved-Skin.cmd and launch_material.py. The earlier published tests establish bounded saved-material/frontend behavior, not complete customization coverage. See [actual results](media/gallery/stage1-display-history-results.json) and [runtime handoff](RUNTIME-CONTINUATION-20261113.md).

The renderer targets exact texture-plus-CLUT keys. The current material allowlist has five player atlas keys, with four hull keys selected by default and one shared mechanical sheet excluded, plus six observed Stage 1 enemy strips. These are texture channels, not independent named-ship or weapon identities.

The skin workspace supports create/import/inspect/set-style. Creating a workspace makes an uninstalled draft; it does not generate art. Imported images have dimension and exact-alpha constraints. A style/concept image and a 4K atlas preview do not establish mapped gameplay art.

Source evidence:

- [Native launcher material-lab link and authoring explanation](../windows-x64/recomp-ui/src/common/backends/imgui/launcher_devtools.cpp)
- [Browser material controls and restart limits](../windows-x64/tools/material_lab.js)
- [Preset defaults, scope checks and live-apply contract](../windows-x64/tools/material_profiles.py)
- [Runtime material profiles and exact-key allowlists](../windows-x64/psxrecomp/runtime/src/hd_skin_material.h)
- [Draft creation and research-required capability metadata](../windows-x64/tools/devtools_service.py)
- [Saved-preset launch preparation](../windows-x64/tools/launch_material.py)

## Confirmed missing from the requested complete system

1. **An in-game skin library and selector.** The inspected implementation provides the external browser lab; a controller-operated in-game customization screen with an owned selection state has not been established.
2. **Independent player-craft selection.** Each named craft needs its own hull/component assignment. The current shared player channel does not prove craft-specific body, wing, mechanical and built-in-gun isolation.
3. **Independent player weapon skins.** Each Gunpod/built-in weapon needs separate visual assignment, including upper/lower and spare/dropped/pickup states where applicable. Ammunition editing is not a weapon identity or skin selector.
4. **Enemy and boss ship skins.** Per-family/per-boss choices, including palette, damage and destruction states, need mapped identities. Six fighter strip keys do not cover all enemies or stages.
5. **Enemy weapon skins.** Enemy/boss guns and their attacks need independent assignment rather than inheriting a shared enemy hull material.
6. **Bullet and effect selectors.** Projectiles, muzzle flashes, impacts, explosions, smoke, fire and electricity require keyed category/sequence coverage and state-safe replacement. Existing effect PNG deliveries are candidate content, not a user-facing effects selector.
7. **The integrated Skin Factory generation workflow.** No all-asset generation action was found in the inspected launcher/tool path. The complete workflow still needs target selection, style/reference input, a bounded generation job, progress/cancel/failure handling, retained candidate provenance, source/alpha/palette/region validation, preview and explicit admission to the selectable library.
8. **Complete in-game preset management.** Named per-target presets, previews, saving/loading, Stock/reset behavior, persistence and clear apply/restart behavior must be connected to the in-game selector. External preset save/apply exists; this gap concerns the requested in-game workflow and independent target scope.
9. **Complete live application.** Colors can change through the current bridge, but texture scope and detail changes still require restart. A broader live-change feature needs its own implementation and validation before the menu promises it.

This list covers the requested customization system. It does not assert that every unrelated menu control is absent.

## Other development controls still marked research-required

The existing Dev Center capability metadata explicitly leaves these unverified: upper/lower Gunpod durability and secondary integrity; gun type/slot ownership/equipment retention; pickup lifetime; mission/stage selection; boss practice/checkpoints; enemy/boss shields and health; semantic ship/gun/effect skin assignment. See RESEARCH in [devtools_service.py](../windows-x64/tools/devtools_service.py).

These are development/practice features. They must not be presented as working gameplay controls merely because a button or a legacy RAM address exists. Native progression and ordinary player loadout choices are separate from developer equipment writes.

## Existing menu infrastructure is not a complete installed-menu audit

The framework has standard Display, Graphics, Audio and System menu helpers, including volume, resume, save/load and reset definitions in [recomp_runtime_settings.c](../windows-x64/recomp-ui/src/common/recomp_runtime_settings.c). Options are feature-gated by the caller. This source alone does not prove which are registered in the delivered Einhander executable.

The runtime also has [save-state slot-browser code](../windows-x64/psxrecomp/runtime/src/psx_savestate_menu.c), [volume/rewind OSD integration](../windows-x64/psxrecomp/runtime/src/host_osd.c) and the existing rewind implementation. Their complete current keyboard/controller journeys, persistence, cancellation and restore behavior still need a separate bounded installed-menu test. This audit did not launch the game or declare those features missing.

## Concrete completion order and acceptance

First establish verified target identities and shared-atlas ownership for craft, Gunpods, enemy weapons and effect sequences. Extend the selection/preset model so each target can own a selection. Then expose it through the in-game menu and connect the launcher factory's validated outputs to that library.

For each admitted target, verify actual mapped draws and every required palette/animation/damage state, absence of changes to unrelated shared pages, Stock restoration, saved selection after relaunch, and controller/mouse/keyboard operation. Test unsupported targets and failed/cancelled generation without modifying an installed pack. Measure gameplay/audio separately from generation; GPU authoring and timing runs need separate coordinated windows.

“SOTA” is a requested quality goal, not a currently verified property. Acceptance requires source-faithful readable material detail, consistent art direction, stable motion and no introduced frame/audio stalls. Higher dimensions or more presets alone do not satisfy it.

Required assets, produced counts, remaining capture locations and their evidence scopes are recorded in [artwork status](ARTWORK-STATUS-20261113.md). Full-game E2E and final release acceptance remain open.
