# Menu/HUD + skin-selector integration map (claude-einhander-ui, source-only, 2026-11-14 ~22:00Z)

Read-only grep/inspection of the canonical C:/github/Einhander working tree. Nothing was compiled, run or decoded.
Hashes are sha256 prefixes of the files as they are on disk now (the working tree may differ from Git HEAD).

## 1. What exists today

### HD skin/material (ship skins)
| piece | file:line | sha256 (prefix) |
|---|---|---|
| 14 named profiles (aurora-teal … reactor-lime) plus "stock" | runtime/src/hd_skin_material.h:26-42 | 59565481657298ff |
| Startup selection from env `PSXRECOMP_SKIN_PROFILE` / `_KEYS` / `_STRENGTH` and `PSXRECOMP_SKIN_ENEMY_*` | runtime/src/gpu_gl_renderer.c:4706-4716 (init_gpu_raster) | 92d080578d2a3d73 |
| Player/enemy material state | gpu_gl_renderer.c:2537-2538 (`s_hd_skin`, `s_hd_skin_enemy`) | same |
| Public live API: `gl_renderer_skin_material_get/set/configure`, `gl_renderer_skin_profile_count` (includes stock) / `_id` | runtime/include/gpu_gl_renderer.h:108-117; implementation gpu_gl_renderer.c:3467-3511 | 850b7c4ae5fedf0f (.h) |
| Validated all-or-nothing live commit, colour applied on the next draw | runtime/src/hd_skin_live.h:40-56 (`hd_skin_live_commit`) | e003bfafe0db9325 |
| Only live caller: debug-server JSON command `handle_skin_material` | runtime/src/hd_skin_live_debug.h:8 (included at debug_server.c:4930) | 2e33d6a92dd6a09c / 86ce765bab0ef633 |
| Saved preset at launch | tools/launch_hd.py, via Play-HD.cmd (root-owned; receipts per RUNTIME-CONTINUATION) | not read here |

### In-game overlays and menus
| piece | file:line | sha256 (prefix) |
|---|---|---|
| Host hotkey actions: FULLSCREEN, TURBO, VOLUME±, DISPLAY_PERF, REWIND (F8), SAVE_STATE_MENU (F7) | runtime/include/host_keymap.h:17-24 | c1924f1129bfb939 |
| F7 save-state overlay: a software-rasterised panel (draw_text/fill_rect) composited over the game | runtime/src/psx_savestate_menu.c (326 lines); main.cpp:5803-5905 open/move/submit/key handling | c61218c3b4c3033d / f4ecc89c69b394ca |
| Pre-boot ImGui launcher (shader presets etc.) | recomp-ui/src/common/backends/imgui/launcher_imgui.cpp:87-150 (ShaderPresetEntry, refresh_shader_presets); main.cpp:87 includes recomp_launcher.h | not hashed |
| Generic in-game settings menu, data-driven (BOOL/INT/CHOICE/ACTION/TEXT items with callbacks; `extra_items` for game-specific rows) | recomp-ui/src/recomp_runtime_ui.h:22-140; builder recomp_runtime_settings.c:42-178 | 3fe582cd49065fcd / 61e986d6466c2c82 |
| ...but the PSX runtime never creates it: the only caller of `recomp_runtime_ui_create_standard` is recomp-ui/tests/runtime_ui_test.c:113 | grep over runtime/src and recomp-ui/src | |

### Menu/HUD artwork path
- HD replacement art is loaded from the pack root `PSXRECOMP_HD_TEXTURE_ROOT` (gpu_gl_renderer.c:2663), keyed by native `RAW-CLUT`, through runtime/src/hd_texture_pack.cpp.
- Menu/HUD art reaches the game ONLY if its files are in the pack the launcher points at. I have NOT determined which pack folders are installed or private: UNKNOWN.

## 2. Accepted art vs proposals (strict)
- **Accepted menu/HUD art from this lane: none.**
- The v5 runtime summary e124d0e8 holds 118 generated PROPOSAL files (72 units). "118/118" is a replay of reported class metrics (root r3 readback PASS). It is not look acceptance or admission.
- Prompt keys (BDAE4156 ×2, DD0B6963): root provisionally prefers w5 prompt-sheet snap-native, on atlas only.
- 1AD90FC9 spec-text: unresolved; neither folder is accepted; the r6 measure is pending.
- 60 R1>0 files and 64 R1=0 pack files: no output; hard class defects remain.
- s45 frozen folders: authored candidates, not accepted. J-K3 gauge mips: class-valid proposal, not look-accepted.

## 3. Missing implementation (user-visible gaps)
1. No in-game way to change ship skin. It is env-at-launch or the debug-server JSON only. The validated live API already exists, but no hotkey or menu calls it.
2. No in-game settings menu in the PSX runtime. The generic recomp-ui runtime menu, with CHOICE rows and extra_items, is unwired.
3. No menu/HUD proposal art is in any pack. That integration needs main's conflict choices, look acceptance and a private pack copy.

## 4. Proposed next small user-visible step (P1). Proposal only; main owns these shared files.
**In-game skin-cycle hotkey (default F6), reusing the validated live API. No new renderer code.**
- host_keymap.h: add `HOST_KEYMAP_SKIN_CYCLE` before `HOST_KEYMAP_ACTION_COUNT`, with default label "F6" in its .c table. F6 is not taken by the listed actions; to be verified against host_keymap.c.
- main.cpp: in the same key path as `savestate_menu_handle_key` (~5885), on F6:
  - read `gl_renderer_skin_material_get(&st)`;
  - pick the next player profile index modulo `gl_renderer_skin_profile_count()`, where 0 is stock;
  - call `gl_renderer_skin_material_set(next_id, st.player strength or 100, enemy unchanged...)`.
  - This runs on the emulation/main thread between frames, which is where the debug server already applies it, so it is the same contract.
- Feedback: set the window title to "Einhänder — Skin: crimson-red 100%" (SDL_SetWindowTitle), or "Skin: unavailable (keys not configured)" when `configure` reports that the material keys are not initialised. A small on-screen toast through the F7 overlay rasteriser could come later.
- Scope it does NOT cover: persistence (the next launch still uses the saved preset from launch_hd.py), enemy channel cycling, and detail layers (`detail_changes: next_launch_only`).
- Tests (when granted):
  - a host unit test of the pure next-index function (wrap, stock in the cycle);
  - the existing hd_skin_live contract tests unchanged;
  - then one root-run private live check: press F6 three times, verify the title text plus the debug `skin_material` get, no RAM writes.
- Alternative P1b: a "Ship skin" combo in the pre-boot ImGui launcher, setting `PSXRECOMP_SKIN_PROFILE` for the spawned runtime (the same pattern as ShaderPreset). That only helps if Einhander launches through this launcher rather than Play-HD/launch_hd.py, which main should confirm.
