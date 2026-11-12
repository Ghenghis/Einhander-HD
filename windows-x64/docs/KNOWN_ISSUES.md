# Einhander Recompiled — Known Issues & Diagnostic Notes

_Last updated: Nov 12, 2026 — verified via debug-server captures, renderer regressions, and live navigation._

### Nov 12 renderer investigation

Stage 1's black/missing-texture scene was reproduced in a fresh isolated run
with `hd_textures=false`, dumping disabled, and
`PSXRECOMP_HD_CPU_AUTHORITY=1`. The native-CPU experiment alone does **not**
fix it. Six sampled CLUT rows were populated at frame 7209 and all zero by
frame 12027; no observed A0 upload covered those rows in between. The upload
observations are deduplicated recent-history samples, not a complete event log.
The subsequent trigger capture identified a malformed GP0 fill at frame 8990:
`02000000 FFDAFFE6 55555555`. It cleared a wrapped 352x341 rectangle starting
at (992,474), including the CLUTs at x=0..319, y=480..511.

The fill came from prematurely ending a shaded polyline. The parser accepted
the terminator pattern before consuming two vertices and at vertex positions.
Later colour/vertex words were then interpreted as new commands. The parser
now consumes the initial two vertices unconditionally and recognizes shaded
polyline termination only at a subsequent colour position, matching
[DuckStation's parser](https://github.com/stenzek/duckstation/blob/master/src/core/gpu.cpp).
The mono-polyline initial two vertices follow the same minimum-length rule.

Also fixed two defects in the diagnostic used for this investigation:
`gl_fbo_peek`/`gl_vram_diff` now drain queued draws before reading, and they
read actual GPU pixels even when native CPU authority is enabled. After a
diagnostic read, native texture sampling is restored to its CPU source. Older
CPU-authority FBO comparisons could silently compare the CPU mirror to itself;
they do not establish GPU agreement.

`python remaster-audit/run_vram_coherence.py` from the workspace root builds
the current renderer with a hidden real-OpenGL fixture. All 24 checks pass
(10 normal, 14 native-authority). The pre-polyline-fix build fails ten
assertions across the two modes; the pre-diagnostic-fix renderer fails three
of the earlier 14 diagnostic checks.
Artifacts: `C:/github/REMASTER_STAGING/renderer-validation/coherence/`.
Gameplay captures and palette/upload observations:
`C:/github/REMASTER_STAGING/renderer-validation/palette-trace/`.
The exact transition capture is in
`C:/github/REMASTER_STAGING/renderer-validation/palette-loss-trigger/evidence/palette-loss-trigger.json`.
Normal-renderer gameplay validation completed a 210-second Stage 1 route
through the helicopter fight, with 14 periodic captures and no zero rows in
198 palette samples taken after visual confirmation. This is a bounded route,
not a full-game playthrough. Evidence is under
`renderer-validation/polyline-fixed-default/`. The verified executable is
installed at `windows-x64/build-release/Einhander_Recompiled.exe`; the previous
executable is preserved under `build-release/backups/20261112-polyline-fix/`.

---

## 1. Missing / untextured 3D models on some stages

**Nov 12 status:** the reproduced Stage 1 failure is caused by polyline-parser
desynchronization, as documented above. The parser fix passes the renderer
regressions and the 210-second normal-renderer gameplay run, with populated
CLUTs and textured scenery past the old failure point. Reports from later stages and
continue/respawn still need separate regression runs. The Nov 11 hypotheses
below are retained as historical observations, not the current root cause.

**Symptom:** On certain stages and after continue/respawn, the 3D world renders as
flat gray or flat-colored polygons. HUD, menus, and 2D elements still render correctly.

**What is confirmed:**

- A fresh boot renders **fully textured** gameplay — stage-1 city, enemies, and
  world all correct (verified capture `ingame.png`, Nov 11 ~21:50).
- The flat/untextured appearance shows up later — stage transitions, continue/respawn
  after death, and on some stages (per user report).
- **CPU-side VRAM and GPU-side FBO match exactly** in sampled texture pages
  (`vram_peek` vs `gl_fbo_peek`, 5 regions, Nov 11 ~22:07). The renderer is
  faithfully sampling what the CPU VRAM contains — this is **not** a GPU-side
  sync/desync bug.
- Texture pages at (512,256), (640,256), (384,320) contain valid data on both
  sides; pages at (320,256) and (0,320) are zero in **both** CPU and FBO —
  meaning the game never populated those pages for this scene, or the scene's
  texture-page table points elsewhere.

**Where the fault sits (evidence-limited):** CPU-VRAM and FBO contents matched at
five **arbitrary** sampled regions — but those regions were not proven to be the
texture pages referenced by the missing models. So this is *consistent with* a
game-side VRAM upload problem, **not proof** of one. The renderer vs. game-side
question is still open. Two open hypotheses:

- **(a)** On continue/level-load, texture `LoadImage`/VRAM-copy writes for some
  stages are dropped or misdirected — the texture pages the scene's `tpage` bits
  reference stay empty.
- **(b)** Some stages are genuinely dark/flat-shaded sections (stage-2 tunnel
  area) and read as "missing textures" — partially supported by the quad
  capture showing only flat-shaded primitives in the dark scene.

**Not yet done:** per-frame textured-draw counter diff (sample `gpu_opcodes`
0x2C/0x2E across a flat-scene frame — if they increment while the screen is
flat, textured prims are being submitted against empty pages = confirms (a)).

**Workaround:** none in-game. A fresh reboot restores correct rendering.

---

## 2. Savestate load corrupts VRAM (noise screen / texture corruption)

**Symptom:** After `savestate` load, the presented frame is pure noise or a
texture-corrupted scene.

**What is confirmed:**

- `savestate load` can leave the display as VRAM garbage (`ss_post` captures).
- `boot_state.c` restores VRAM through `gr_vram_transfer_in`; whether that
  re-synchronizes the renderer's texture pages/dirty tracking is **unverified**.
- Failed loads also log `Load failed slot N` and leave broken state.

**Status:** real defect, treat savestate load as unreliable. Save is fine to
write; do not trust restore until the VRAM-resync path is verified.

---

## 3. Memory-card save: "Game cannot be saved without entering a name"

**Symptom:** Game reports `No game data` at boot; attempting to save shows
`Game cannot be saved without entering a name` — but the user reports no
reachable name-entry screen.

**What is confirmed:**

- Both configured cards are **present, 128 KiB, `MC`-signed, all-empty** —
  structurally valid blank PSX cards (`memorycard1.mcd`, `saves/card2.mcd`).
- `memcard.c` correctly formats, writes sectors, marks dirty, and flushes.
- The card files are **not** the problem — the blocker is the game's own
  save-flow gating on a pilot name.
- Menu navigation works (Start → GAME START → Fighter Selection → ARM Selection
  → in-game), so controller input path is functional.
- **Not yet verified:** whether Einhander's name-entry screen exists in this
  build / how it is reached. On stock PSX, name entry is part of the save
  screen (appears on first save at Game Over / stage end).

**Partial workaround (unverified):** `tools/save_editor.py` can inject a
structurally valid named save block into the `.mcd` (correct dir entry +
checksum + SC header). **Not yet proven:** whether the game recognizes the
injected block as a usable Einhander save — the save payload format has not
been decoded, so injected blocks may still fail the game's own checks.

---

## 4. Full "what else is broken" inventory

| Feature | Status | Evidence |
|---|---|---|
| Stage-dependent flat/untextured models | **Stage 1 cause fixed; broader regression pending** | polyline parser generated a wrapping black fill; later-stage/continue cases need rechecking |
| Savestate load | **Broken/unreliable** | noise/corrupted VRAM after restore; renderer resync unverified |
| In-game save / name entry | **Blocked** | name-entry screen unreachable for user; cards are structurally fine |
| `save_editor.py` inject | **Writes entry, game recognition unproven** | dir entry + checksum valid; payload format undecoded |
| `ein_bridge.py` + `dev_menu.html` | **Written, not run E2E** | bridge compiles; no live session yet |
| Robin autoplay bot | **Written, not live-tested** | addresses/config plausible, unproven |
| `post_degrain` shader path | **Compiled, A/B unverified** | compiles; no visual comparison done |
| Launcher **DEV TOOLS** panel (Settings) | **New — syntax-checked, not run in-app** | native ImGui panel wired into PSX Settings; connects to :4370, edits `.mcd` cards natively |
| Savestate x/y sign-extension fix (older) | **Unverified** | fix landed earlier; no regression capture |
| 24-bit FMV post path vs VRAM path | **Working assumption** | separate paths confirmed in code; visual OK |

## 5. Diagnostic commands (debug server 127.0.0.1:4370)

| Command | Use |
|---|---|
| `present_shot` + `present_shot_seq` | capture presented frame |
| `vram_peek` | read CPU-side VRAM rect |
| `gl_fbo_peek` | read GPU/FBO-side VRAM rect (diff against `vram_peek`) |
| `gpu_opcodes` | per-opcode draw counters (0x2C/0x2E = textured) |
| `gpu_state` | display timing, draw area, GTE/dirty counters |
| `capture_quads` + `get_quads` | last drawn primitives w/ colors |
| `pad_status`, `press`, `set_input` | controller state / inject input |
| `read_ram`, `write_ram`, `vram_peek` | memory access |
| `memcard_status` | card presence summary |
| `savestate`, `savestate_status` | savestate slots |

## 6. Decoded game addresses (US SCUS-94243)

See `docs/MODS_AND_TOOLS.md` for the full cheat/address table and tooling.

## 7. Next verification steps (ordered)

**HD coverage update (Nov 12):** native-page fallback plus independent GPU-cache
reuse reached 87.91% replacement queries in a 120-second Stage 1 route, versus
19.37% upload-only. The 964-file local pack includes 311 neural restorations
and 653 conservative pixel-preserving entries; the percentage is not screen
area or neural-detail coverage. All 385 page sources, 91 protected lettering
regions, 18 HD cache regressions, 24 native renderer regressions and 61 page
coherence checks passed. Run `Play-HD.cmd` for the opt-in local pack. Details,
performance limits and the remaining asset gaps are in
`docs/HD_TEXTURE_COVERAGE.md`.

1. Start fresh with the patched executable; do not use an old savestate whose
   VRAM already contains the palette corruption. Recheck continue/respawn and
   later-stage cases separately.
2. Fill the remaining page/palette identities observed by the HD coverage pass;
   replacement decode eviction is fixed. Continue boss and later-stage review.
3. Extend temporal review of Stage 1 replacements (palette changes, text, alpha,
   seams) beyond the bounded route already captured.
4. Fix or gate savestate restoration, then verify the real name-entry/save flow.
5. If a new missing-texture scene remains, use `probe_scene_textures.py` to
   decode its actual page/CLUT references and the corrected GPU peek/diff.
