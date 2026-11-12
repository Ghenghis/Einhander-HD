# EINHÄNDER 2026 — SOTA Launcher & Menu Modernization Plan

Status: **Phase 0 complete (audit)** · Owner: Cascade + USER · Target: 4K-ready launcher, dev-tools suite, smooth gameplay/FMV

---

## 0. Verified Current State (audit, 2026-11-11)

### Launcher (`recomp-ui/`)
- `src/common/backends/imgui/launcher_imgui.cpp` (~460 KB) — shared Dear-ImGui launcher; **panel-composition model**: each `SystemProfile` lists panel ids per view; panels are game-agnostic and read capability from `LauncherModel`.
- Views present: `dashboard`, `settings`, `controller`, `assist_tools`, `credits` (see `launcher_debug.h` view names).
- Registered panels (dashboard): `"game"` (MAIN), `"controller"` (SIDE), `"save"` (WIDE, PSX-only).
- Settings panels: `video`, `audio`, `input`, `system`, `hotkeys`.
- PSX unit: `src/consoles/psx/psx_profile.h` — 24-button vocabulary, DualShock art (`pad.tga`, `pad_analog.tga`, `pad_digital.tga`), `brand_psx.tga`, theme `"psx"` (PlayStation blue), dual-slot memcard 15-block grid, disc filters `.cue/.bin/.car`.
- Assets: `assets/common/img/*.tga` + fonts (`LatoLatin`, `NotoSansSymbols2`, `OpenMoji`); per-console `assets/consoles/<sys>/img/`.
- Automation: `launcher_debug.h` — `LNG_SCRIPT` env var drives `view:`, `player:`, `size:`, `click:`, `key:`, `screenshot:` commands — **CI-driving every launcher change is already possible**.
- Remote surface: `launcher_udp_port.c` — external control/query port.
- In-game overlay: `recomp_runtime_ui.c` + `runtime_ui_imgui.cpp` — host-drawn sections/items overlay (currently settings-shaped; extensible to full dev menu).

### Runtime (`psxrecomp/runtime/`)
- Debug server `127.0.0.1:4370` — `get_registers`, `phase_profile`, `cdrom_state`, `vblank_rate`, `dirty_ram_stats`, savestate commands, overlay toggles.
- **FMV stutter root cause (confirmed 2026-11-11):** a 16-byte runtime patch at `0x1887C` (game installs `B0(0x17)`/`B0(0x18)` exception-return stubs over its own text) diverges the page → `text_native_blocked=640M`, `interp_share≈0.96` → guest can't drain the 8-slot CD ring at 2× cadence → `ring_dropped` climbs ~51/sec → dropped STR/XA sectors = stuttery video **and** audio. Fix direction: bless intentional kernel patches / per-function granularity so only truly-divergent code interprets.
- HD texture pack enabled in `build-release/settings.toml`.
- Retail BIOS `SCPH1001.BIN` boots the game (currently verified under `PSX_KERNEL_BLESS=0`).

---

## 1. Design Pillars

1. **Mirror the stock menus — don't invent new ones.** Every Einhänder menu page gets a modern twin that preserves information hierarchy and terminology, upgraded in fidelity.
2. **Smoothness is a prerequisite, not a feature.** The interp/dispatch fix ships first; no UI work can compensate for a 96%-interpreted guest.
3. **Art by generation, chrome by code.** Hero art, backgrounds, emblem/keyart, panel backplates are AI-generated (image tool) at 4K; widgets, layout, focus/indication and motion stay deterministic ImGui.
4. **Everything verifiable.** Every screen ships with `LNG_SCRIPT` coverage + screenshot diffs; every perf claim ships with a debug-server counter reading.

---

## 2. Menu Surface Map (stock → modernized)

### 2a. Launcher views (host-side, ImGui)
| Stock area | Current panel/view | 2026 treatment |
|---|---|---|
| Game card | `panel_game` | Hero keyart backdrop (generated), animated scanline-sweep accent, verdict checklist → capsule badges, meta table → info chips |
| Controller card | `panel_controller` | Live DualShock diagram (generated pad art, per-button glow on input test), pad-mode switcher with device preview |
| Save/memcard | `panel_save` | Card-as-object render (generated MC art), per-block occupancy heat map, label editing inline |
| Video/Audio/Input/System/Hotkeys | settings panels | Grouped section cards, live preview (CRT filter swatch, renderer note, latency estimate row), search-filter box |
| Library (NEW) | new `panels_dashboard` entry | Disc/save-state/browser picker with generated shelf/backplate art |
| Dev Console (NEW) | new view + panel ids | Debug-server cockpit (§5) |
| Boot/branding | window chrome | Generated splash sequence, Einhänder emblem wordmark, 4K-safe layout (`px()` scale pass) |

### 2b. In-game menus (guest-drawn — mirrored via HD pack + overlay)
Einhänder stock screens to modernize **without changing gameplay behavior**:
- Title / Press Start / main menu (Game Start, Load, Options, Ranking?)
- Options page (difficulty, controller config, sound mode, pad settings)
- Pause screen
- Mission briefing / weapon-select / loadout pages
- Score/ranking and game-over/continue pages
- Memory-card / file screens
- FMV letterbox chrome (frame + letterbox treatment while MDEC plays)

**Mechanism (two lanes, chosen per asset):**
- **Lane A — HD texture replacement (preferred):** upscale/recreate each menu's TIM/VRAM assets into the existing HD pack; zero guest-code risk; per-screen art generated then composited to the pack layout.
- **Lane B — Host overlay mirror:** runtime detects the menu screen (screen-id hook or VRAM signature) and draws a modern ImGui twin over it; guest menu still runs beneath for input. Use only where Lane A can't reach fidelity (e.g. animated transitions we want to redesign). Deferred — needs a screen-detection hook that doesn't exist yet.

### 2c. Runtime overlay (in-game)
- Extend `recomp_runtime_ui.c` sections: `Settings` (exists), plus `Dev`, `Cheats`, `Capture`, `State`.
- Style parity with launcher theme (shared `launcher_theme.h` tokens).

---

## 3. Phase Plan

### Phase 1 — Smoothness foundation *(pre-requisite, already root-caused)*
- [ ] Bless intentional kernel patches: the `B0`-stub install writes (`SetCustomExitFromException`-class) must be recognized as intentional so `dirty_ram_text_native_ok` stops blocking the page — or convert `native_ok` to emitted-range granularity so only patched functions interpret.
- [ ] Rebuild → verify `phase_profile` native share ≫ 0.9, `cdrom_state.ring_dropped` stops growing during FMV, `vblank` delivery stays ~60 Hz.
- [ ] Kernel-bless: proper fix so retail BIOS works without `PSX_KERNEL_BLESS=0`.
- [ ] FMV: verify smooth intro + inter-level cutscenes (video and XA audio) on retail BIOS.
- **Gate:** FMV plays without audible/visual dropouts; `ring_dropped` flat.

### Phase 2 — Visual identity system
- [ ] Design tokens in `launcher_theme.h`: Einhänder palette (gunmetal, HUD-cyan, warning-amber, deep space blues), type ramp (UI/display/mono), radii, spacing, motion timings.
- [ ] Asset spec: per-screen art list (hero keyart, panel backplates, pad renders, memcard art, emblem wordmark, splash, icon set, save-state frames).
- [ ] Image-tool generation pass (see §4 manifest) → composited to TGA atlases under `assets/consoles/psx/img/` (or a new `assets/einhander/` tree).
- [ ] 4K layout pass: audit all `px()` usage + window min-sizes; add `size:`-driven reflow checks via `LNG_SCRIPT`.

### Phase 3 — Launcher views
- [ ] Dashboard: hero panel (keyart + emblem), game card restyle, controller card with generated pad render + input-test glow, save panel card-object treatment.
- [ ] Settings: section cards, per-row live preview/footprint note, search filter, preset row (Recommended / Faithful / Max).
- [ ] New `Library` panel: disc + save-state browser with generated shelf art.
- [ ] Boot/branding: generated splash → fade to dashboard; Einhänder wordmark replaces `brand_psx.tga` (keep system brand as fallback for non-Einhänder discs).
- [ ] Per-view `LNG_SCRIPT` screenshot set at 1080p/1440p/2160p.

### Phase 4 — In-game menu modernization
- [ ] Inventory menu assets: identify TIM/VRAM signatures for every stock screen (title, options, briefing, loadout, pause, score, memcard).
- [ ] Lane A HD pack: generate + wire replacements for static menu surfaces first (title, options, briefing backplates), then HUD chrome.
- [ ] Typographic pass: menu font → generated hi-res glyphs or SDF path if pack supports it; keep original strings.
- [ ] Transitions: add fade/slide where the stock screen had hard cuts (only via overlay lane if needed — else keep stock timing).
- [ ] Verify each screen against the stock one (side-by-side captures).

### Phase 5 — Dev menu area (the "complete dev" ask)
New `Dev Console` view + runtime `Dev` overlay section, all backed by the existing debug server (no new protocol needed):
- [ ] **State:** save-state slots grid (screenshot thumbs), rewind depth, save/load actions.
- [ ] **Cheats:** level select (validated entry points only), god-mode/weapon flags — each option gated on a verified runtime hook, hidden when unverified.
- [ ] **Capture:** frame capture → PNG, FMV dump toggle, screenshot on demand.
- [ ] **Telemetry:** live `phase_profile`/`cdrom_state`/`vblank` graphs; interp-vs-native share bar (already the key health signal).
- [ ] **BIOS/Disc:** backend selector (HLE/OpenBIOS/SCPH1001), disc info, kernel-bless status.
- [ ] **Demo/bot:** only after a safe runtime input-injection surface exists (currently none — do not fake it).

### Phase 6 — Media & packaging
- [ ] Asset pipeline doc + regeneration script (prompt → file → atlas → hash).
- [ ] Installer/packaging pass so `build-release` ships assets + fonts + theme.
- [ ] README + controls page (existing `keybinds.ini` surfaced in launcher).

### Phase 7 — Verification harness
- [ ] `LNG_SCRIPT` journey suite: dashboard→settings→controller→save→dev console→launch.
- [ ] Screenshot-diff baselines per view at 3 resolutions.
- [ ] Perf gate script: `phase_profile` + `ring_dropped` + `vblank` assertions during a scripted FMV play.
- [ ] UI event-handling audit (global rule): every clickable has focus/hover/active states; keyboard+pad navigation passes on every view.

---

## 4. Image-Generation Asset Manifest (Phase 2)

| Asset | Prompt direction | Size | Dest |
|---|---|---|---|
| `hero_keyart` | Einhänder-style mecha over neon city, cinematic, dark | 3840×2160 | `assets/einhander/hero.tga` |
| `wordmark` | EINHÄNDER stencil HUD wordmark, cyan glow | 2048×512 | `assets/einhander/wordmark.tga` |
| `panel_backplate` | brushed gunmetal + hex tech pattern, subtle | 1600×900 | `assets/einhander/backplate.tga` |
| `pad_render` | DualShock front/3-quarter, dark studio | 1200×800 | `assets/einhander/pad.tga` |
| `memcard_art` | PS1-style memory card product shot | 800×800 | `assets/einhander/memcard.tga` |
| `splash` | boot splash — emblem + starfield | 3840×2160 | `assets/einhander/splash.tga` |
| `icon_set` | 16 icon set, HUD-cyan line style | 256×256 ea | `assets/einhander/icons/` |
| Menu TIMs (Lane A) | per-screen modernized versions of stock menu art | native×4 | HD pack tree |

---

## 5. Risks / Explicit Non-Claims

- FMV smoothness is **root-caused but not yet fixed/verified** — Phase 1 gate must pass before menu work is called "done".
- Lane B menu overlay needs a screen-detection hook that doesn't exist; keep Lane B off until then.
- Cheats/level-select/demo-play ship only behind verified runtime hooks; unverified entries are hidden, never stubbed.
- The 321 heuristic BIOS seeds are unvalidated; do not build features on them.
- Generated art is direction-of-travel, not final keyart — each asset goes through a review pass before it ships.

## 6. Done Definition (2026 bar)
- Launcher: all views restyled, 4K-clean, script-verified at 3 resolutions.
- In-game: every stock menu screen has a modern twin (HD pack), verified side-by-side.
- FMV + gameplay: native-share healthy, `ring_dropped` flat, no audible dropout in intro + one inter-level FMV.
- Dev Console: savestates + telemetry + BIOS/disc controls live; cheats only where hooks are proven.
- All of it reproducible from a fresh `build-release` package.
