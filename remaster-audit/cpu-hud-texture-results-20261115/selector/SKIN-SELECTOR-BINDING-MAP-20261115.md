# Skin Factory → launcher → in-game selector: binding map and gaps (source-only, 2026-11-15 ~00:25Z)

Read-only grep and reads of the canonical tree. Nothing was compiled, run, decoded or launched.
This builds on `docs/SKIN-FACTORY-MENU-GAPS.md` (45b4e4ce, Nov 13-14) and adds file:line bindings plus the current state.

## 1. The actual binding chain today (canonical files, sha256 prefixes)
| step | what happens | file:line | sha |
|---|---|---|---|
| A. author / select | Browser material lab: 14 finishes plus Stock, separate player and enemy profile and strength, detail maps. Note shown: "Live apply changes player and enemy colors together… Detail and texture-scope changes require a restart." | windows-x64/tools/material_lab.js:12 (note), :613 (save) | b6c78520 |
| B. presets / contract | `PROFILES` (stock + 14) at :50-55. Keys: `PLAYER_KEYS` (5, incl. the shared mechanical sheet `FIGHTER_KEY 5CC44E5F-053D9A00`) at :15-16; default hull-only `DEFAULT_PLAYER_KEYS` (4) at :19; `ENEMY_KEYS` (6 Stage-1 strips, palette 527B28B9) at :20. `selection()` :68, `enemy_selection()` :89, `detail_selection()` :130 | windows-x64/tools/material_profiles.py | 540584cf |
| C. live apply | Debug command `skin_material` (player and enemy together, colour only) | material_profiles.py:381-390 | same |
| D. save | Writes `tools/material-selection.json` atomically: temp file, symlink refused (:392-412). `saved_selection()` reads it (:260-265) | material_profiles.py | same |
| E. launch | `Play-HD.cmd` → `launch_hd.prepare_hd_launch` reuses the saved, validated preset, or stock (:18-50) | windows-x64/tools/launch_hd.py | 08f590ec |
| F. environment | `environment()` emits `PSXRECOMP_SKIN_{PROFILE,KEYS,STRENGTH}`, `_ENEMY_*` and `_DETAIL_*` (:171-189) | material_profiles.py | same |
| G. runtime allowlist | Renderer parses those keys STRICTLY against `hd_skin_player_keys` (:48) and `hd_skin_enemy_keys` (:56). A caller cannot broaden ownership (:90-118). Profiles at :26-42 | psxrecomp/runtime/src/hd_skin_material.h | 59565481 |
| H. runtime state | Startup environment read; live API `gl_renderer_skin_material_get/set/configure` | gpu_gl_renderer.c:4706-4716, :3467-3556 | 92d08057 |
| I. in-game selector (mine, P1) | F6 "Player color": stock + 14, PLAYER channel only. Enemy channel, scopes and accents are passed as unchanged. Private build exe 37c137e8; NOT live-verified (the startup aborted) | proposals/p1-player-color (main d8abf287 / 994af594) | - |
| J. launcher selector (S67 proposal) | ImGui combos for player and enemy colour and strength; "Apply to running game" goes through the debug server; session only, no save | s67/proposals/skins-launcher-selector/launcher-skin-selector.diff (vs launcher_devtools.cpp b90b44fe) | - |
| K. per-target binding (S67 proposal r2) | Catalog of 8 targets: only `player.hull.shared_candidate` (4 hull keys) is BOUND. UNRESOLVED: mechanical_sheet, craft.named, gunpods, enemy.stage1.strips, enemy.stage2.families, boss, weapons.effects. Environment-only `PSXRECOMP_SKIN_TARGETS`; INVALID fails closed | s67/proposals/skin-targets-r2/hd_skin_targets.h:81-107 | (S67-owned; not edited) |

## 2. How generated ship / gun / PBR maps reach real TEX-CLUT targets (source reading)
- **Colour material, which is what all selectors change:** a shader tint applied ONLY to draws whose (texture, CLUT) key is in the strict allowlist (step G). The HD PNGs themselves are not changed.
  - Player: 4 hull keys by default; the 5th, the mechanical sheet, is excluded because its ownership is mixed.
  - Enemy: 6 Stage-1 strip keys.
- **Detail maps:** authored RGB detail textures, from a local asset manifest, are set at launch through `PSXRECOMP_SKIN_*DETAIL*` (B :110-160, F :184-189). They take effect at the next launch only (`detail_changes: next_launch_only`).
- **Generated or replacement art (HD PNGs):** these reach the game ONLY as pack files keyed by native RAW-CLUT under the HD pack root (gpu_gl_renderer.c:2663 / hd_texture_pack.cpp).
  - No Skin Factory action produces those pack files.
  - The devtools "create workspace" makes an uninstalled draft (devtools_service.py, per the gaps doc). Its import enforces dimension and exact-alpha rules.
  - Admission into a selectable library: NONE exists.
- **"PBR":** the runtime has colour material plus an optional RGB detail map. There is no normal, roughness or metal channel in `hd_skin_material.h`. Calling the result PBR would be inventing it.

## 3. Current behaviour vs the 14 presets and the concept images
- All 14 named finishes plus Stock are real runtime profiles (step G :26-42) and are selectable in A (browser), I (my F6, player only) and J (S67 launcher, player and enemy).
- Concept or style images are NOT loaded by the game; S67's selector text says so. A 4K atlas preview is not mapped gameplay art.
- What a preset changes in game: the tint on 4 player hull keys and 6 Stage-1 enemy strips. Nothing else: no named craft, gunpods, bosses, enemy weapons, bullets or effects (S67 catalog UNRESOLVED; gaps doc §2-6).

## 4. Missing names and actor roles (the real blockers)
- 7 of 8 target roles are UNRESOLVED in S67 r2 (see K). The boss evidence is "S2 boss TEX CA05583A/A65BA8AE/4CE48309/986B6314/AC93CD6C: 0 drawn, 0 authored HD images".
- No identity mapping exists for weapons, bullets or effects. These need capture work (owner: S67 / authoring), not UI work.
- There is no persistence of an in-game choice: F6 and S67's launcher selector are both session-only; saving exists only in the browser lab (D).

## 5. Smallest concrete UI + contract patch (independent of S67's header and the renderer)
**P1 r2: add the ENEMY channel to the existing F6 menu.** It surfaces the already-valid enemy profiles in game and uses only the existing live API.
- The menu gets 2 rows, "Player color" and "Enemy color". Up/Down switches the row and Left/Right changes the selection. Enter applies both rows in one configure call: `configure(player_id, player_strength, enemy_id, enemy_strength, NULL, NULL, -1)`. Each strength is kept as read at open, and diagnostic scopes and accents stay unchanged. The apply is atomic: on rejection nothing changes.
- No renderer, host_osd, keymap-enum, S67-file or launcher change. Only proposed main.cpp changes, plus its v69 merge copy.
- Not covered:
  - persistence (the browser lab remains the only save path);
  - target-mode / per-role selection (depends on S67 r2 roles being BOUND);
  - detail maps (next launch only).
- Source prepared next to this file (see `p1r2-enemy-channel/`). Build and live check only under separate grants.
