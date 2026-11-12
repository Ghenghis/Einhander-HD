# Einhander Recompiled — Debug Findings

Build: `build-ss8c` (debug). Game: SCUS-94243 (US).
Evidence-first rule: every claim below has a runtime artifact; absence of evidence is stated as unverified, not assumed.

## 1. HD texture pipeline

### Root bug (fixed)
`gpu_gl_renderer.c` dump mode ended in an early `return 0` after `hd_dump_upload`, so the
replacement decode/draw path below never ran while dumping was enabled.
Fix: dump once, then fall through into replacement drawing (line ~2614).

### Verification evidence
- `hd_err.log` — temporary `[hd_tex] drew %08X-%08X %ux%u` diagnostic produced 32 lines of
  `[hd_tex] drew D0948A15-B20FDBC4 320x480`, proving a replacement reached the GL draw path.
  Diagnostic was removed after confirmation; final source is clean.
- `[hd_tex] pack active: .../hd_dump_rgba (dumping)` proves pack init only — it is NOT proof
  of any individual draw. Do not treat the pack line as replacement evidence.
- Visual smoothness alone cannot distinguish replacement pixels from SSAA4 upscaling.
  Use the draw diagnostic if more proof is ever needed.

### Upscale verification
- Compared IHDR dimensions of all 432 `.png` vs their `.png.orig` backups:
  **432/432 resized, 0 unchanged** — the earlier batch did complete despite its tool timeout.
- 5 newer `A40D25FE-*` strips (256x8, dumped after the batch) upscaled 4x to 1024x32
  with `.orig` backups, matching their 1024x32 siblings.
- Bicubic enlargement adds no source detail; it exists so the pack renders at higher
  texel density under SSAA. Real detail gains require edited/AI-upscaled content.

### Dump-probe syscall cost (fixed)
`hd_dump_upload` probed `fopen(path,"rb")` per textured primitive per frame.
Added `s_hd_dumped_set` (16384-entry open-addressed set over tex|pal 64-bit keys,
`gpu_gl_renderer.c` ~line 2389): each unique texture now pays one filesystem probe
per process. Table-full falls back to the filesystem probe. Rebuilt clean.

## 2. Starvation abort (organic hang — diagnosed, not yet root-fixed)

`starvation_watchdog: 8805955 us without heartbeat — ring dumped to starvation_dump.jsonl`

### What the evidence shows
- `psx_freeze_dump_psx-runtime_*.json`: `wedge_kind = 3 ("slow_frames")`,
  `frame_count` advancing ~4-5 fps, `dirty_insns` still retiring, `store_pc`
  alternating between `0x80013070`/`0x80017368`/`0x800B6210` (NOT pinned —
  mode-D spin ruled out). `i_stat` flapped 0↔1, so interrupts were servicing.
- `exception_reentry_blocks = 2420` is *normal* — `freeze_heartbeat.c` documents
  ~2K/frame as the chronic baseline (VSync callback chain runs in exception
  context); wedge threshold is 20K/frame.
- `main_stack_samples` (the smoking gun): main thread blocked inside
  `wglSwapLayerBuffers` → `NtUserPeekMessage`/`SendMessageW` → dispatched window
  proc → `GetICMProfileW` / `WcsGetDefaultColorProfileSize` /
  `GetFileAttributesW` / `CreateDIBSection`. Windows ICM color-profile + DIB
  work was serviced inside the GL present's message pump for >8s.
- `starvation_dump.jsonl` tail: `SELECT_DEASSERT` mid pad-poll — SIO traffic
  just slowed with the frames, it did not deadlock.
- `generated/SCUS_942.43_full_00.c` `func_80012F10` block `0x80013060`: the
  frequent `store_pc` sample is a normal guest poll loop, only repeatedly
  sampled BECAUSE frames were running slowly.

### Diagnosis
Mode-C slow-frames wedge: host-side wall clock eaten by Windows/GDI/driver work
inside `wglSwapLayerBuffers` (same documented class as the NVIDIA
SwapBuffers ~1.5s stall in `freeze_heartbeat.c`). Emulation wasn't dead — it
crawled at ~4 fps, so the main loop never reached the idle heartbeat site in
`main.cpp:5356` within the timeout and the watchdog aborted, as designed.
Caused by a transient OS/driver event during present — not the RAM freeze
writes (second identical run survived), not the dump path, not an IRQ deadlock.

### Why no code fix
The stall lives in the Windows message pump / ICM / GDI layer invoked during
GL present, outside emulation logic. If it recurs, compare `main_stack_samples`
across dumps; a repeated wglSwap→ICM signature would justify draining the
window message queue differently or deferring present, but a single transient
sample doesn't warrant touching the render path.

## 3. Runtime RAM access (verified)

Debug server on TCP 4370, one request per connection (`dbg.py` reconnects per command).

- `read_ram`/`write_ram` verified: write `0x03` to `0x800813C4` reads back `03`.
- `0x80085718` (invuln) is a countdown timer decremented ~30x/sec by the game —
  GameShark codes must rewrite constantly; one-shot writes cannot hold it.
- `dbg.py --freeze <addr_hex> <val_hex> <secs> <interval_ms>` pins countdown bytes.
- Second identical 75s freeze run: game survived — freeze flood does NOT cause the
  starvation abort (correlation excluded by experiment).

### Still unverified (needs real gameplay)
- Lives pinned at 03 held during demo, but no death occurred. True proof: ship dies
  while lives reads 03 after the death animation.

## 4. Known non-issues (checked)

- `Hashes.ini` empty: not a defect — pack scans the replacement dir directly.
- No ImGui launcher exists in searched sources — HD toggle lives in `settings.toml`
  `[video]` (`hd_textures`, `hd_texture_root`, `hd_dump_root`), wired through
  `config_loader` -> `main.cpp` -> `gpu_hd_texture_config`.
- Launcher-less run requires `--no-launcher`; without it the process sits in the
  launcher UI (alive, CPU ticking, no port 4370, stderr stops at `main() entered`).

## 5. Maintenance notes

- While dump mode is on, every newly seen texture is dumped once into
  `<hd_dump_root>` and, when no explicit texture root is configured,
  `<root>/einhander-texture-replacements` doubles as both dump target and pack source:
  a fresh 1x dump immediately counts as a "replacement" (visually identical — harmless,
  intended dump->edit->draw workflow).
- `.orig` files are pre-upscale backups; restore by copying over the `.png`.
- Rebuild: `ninja -C build-ss8c` — stop `Einhander_Recompiled` first (exe lock).
- Launch for automation: `--no-launcher`, stderr -> `hd_err.log`.
