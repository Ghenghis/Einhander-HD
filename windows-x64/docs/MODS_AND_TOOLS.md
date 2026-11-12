# Einhander Recompiled — Mods, Tools & Feasibility (2026)

Tools live in `tools/` at the workspace root. Everything talks to the game's
debug server at `127.0.0.1:4370` (active-low pad words, line-JSON commands).

---

## Launcher DEV TOOLS panel — native (NEW)

The launcher now ships a **DEV TOOLS** card in PSX Settings
(`recomp-ui/src/common/backends/imgui/launcher_devtools.cpp`, registered as
panel `"devtools"` in `launcher_imgui.cpp`, composed by
`src/consoles/psx/psx_profile.h`). It is the in-launcher equivalent of the web
panel — no Python, no browser:

- **CONNECTION**: live status of `127.0.0.1:4370` + ping.
- **CHEATS**: one-click `write_ram` presets (lives, invincible, hyper, ammo,
  invincible pods, score x40, gallery unlock).
- **PAD**: virtual pad buttons → `press` commands (active-low words, real
  PS1 bit order).
- **SAVESTATES**: slot save/load, with an in-UI warning that load is unreliable.
- **MEMORY CARD EDITOR**: native `.mcd` block list / inject / delete against the
  card paths configured in the launcher (`m->s.memcard_path[]`). Same format
  logic as `tools/save_editor.py` — injects `BASCUS-94243<name>` dir entries
  with correct XOR checksums and `SC` block headers.
- **AUTOPLAY BOT**: Robin — name + autofire/weave/dodge toggles; drives `press`
  loops while the panel is open.
- **DIAGNOSTICS**: one-click preset probes (gpu_state, gpu_opcodes, vram_peek,
  gl_fbo_peek, memcard_status, traces, ring stats) that fill the raw console;
  a **VRAM cpu/fbo diff** button that runs the 5-region CPU-vs-FBO comparison
  used to diagnose the texture bug.
- **DEBUG CONSOLE**: raw JSON command line for every other server command.

Status: syntax-checked against clang++17; first in-app run pending.

## Dev Control panel — `tools/ein_bridge.py` + `tools/dev_menu.html`

```powershell
python tools\ein_bridge.py        # serves http://127.0.0.1:8090/
```

Browser panel with: RAM cheat writes, virtual pad, savestate slots,
screenshot capture, GPU/geom diagnostics, raw debug console, and Robin bot
controls. The bridge also hosts the bot in-process (`POST /bot`).

## Robin — autoplay bot

Configurable in-game player driven via `press`/`input_route` + `read_ram`.

- **Name**: configurable (default `Robin`) — set in dev menu.
- **Toggles**: `autofire`, `weave`, `dodge`, `revive` (auto-continue),
  `invincible` (top-ups invincibility timer), `tick` (decision rate).
- API: `POST /bot {"action":"start|stop|config",...}` — see `ein_bridge.py`.

## Save editor — `tools/save_editor.py`

Direct `.mcd` (PSX memory card) editing:

```powershell
python tools\save_editor.py list   D:\Games\Einhander\ROM\memorycard1.mcd
python tools\save_editor.py inject saves\card2.mcd 0 PILOT01
python tools\save_editor.py rename saves\card2.mcd 0 DAVE
python tools\save_editor.py delete saves\card2.mcd 0
```

Writes valid directory entries (status + product code `BASCUS-94243` + XOR
checksum) and `SC`/`SCUS-94243` block headers — bypasses the broken in-game
name-entry step for future saves.

## Decoded addresses (US Einhander, SCUS-94243)

| Address | Field | Notes |
|---|---|---|
| `0x800813C4` | lives (u8) | freeze 0x03 |
| `0x80085718` | invincibility timer (u8/u16) | nonzero = invulnerable |
| `0x80085710` | hits counter (u8) | GameShark 0xFF |
| `0x80085709` | hyper mode (u8) | 0xFF on |
| `0x80083E2C` | pad input bitfield | Triangle=0x0010 |
| `0x80084832` | active gunpod ammo (u16) | |
| `0x80084834` | ammo counter (u16) | |
| `0x80084830` / `0x80084980` | pod durability top/bottom | 0x03C0 = invincible pod |
| `0x80084B62` / `0x80084CB2` | secondary integrity top/bottom | 0x03C0 |
| `0x80081326` | score multiplier (u8/u16) | 0x28 = x40 |
| `0x801FEC9C` / `0x801FEC9E` | gallery unlock all | 0xFFFF each |
| `0x800ADA40-0x800ADA53` | config / stage-select region | 4/5 |

## What's feasible to mod (from decoded state)

- **Cheats/tweaks**: everything above via `write_ram`.
- **Autoplay**: Robin bot (RAM-driven now; vision-assisted possible later via
  `present_shot` frames).
- **Ghost/replay**: `input_route_append` + `input_route_start` can replay a
  recorded pad segment — building blocks for replay/ghost.
- **Save engineering**: `save_editor.py` + `read_ram` on save-state vars
  (score, kills, mission) to edit in-memory and let the game save.
- **Debug overlays**: `get_quads`, `gpu_opcodes`, `geom_correction`,
  `wtrace_*`, `fntrace_*` for instrumentation-style mods.
- **Not feasible today**: true model/texture swapping (no asset pipeline),
  netplay (not wired), Lua-style scripting inside the recompiled core.

## 2026 SOTA framing (docs/user-facing)

- Bot named/configurable; autopilot + assist modes.
- Dev menu = single control plane for cheats, input, savestates, capture.
- Save editor as the canonical fix for the name-entry blocker.
