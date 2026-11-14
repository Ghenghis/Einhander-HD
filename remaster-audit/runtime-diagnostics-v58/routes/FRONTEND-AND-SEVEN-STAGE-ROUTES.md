# Bounded frontend/title checks for the other material pairs, and seven-stage capture routes

Written by claude-einhander (source-only; nothing launched, nothing changed outside this folder).
Facts are from `windows-x64/psxrecomp/runtime/src/main.cpp`, `tools/launch_material.py`, `tools/material_profiles.py`,
`remaster-audit/fullgame-prep/stage-access/STAGE-ACCESS.md` and `remaster-audit/claude-backlog/capture-checklists/`.

## A. Material pairs on the rebound b287 runtime

### What is and is not proven (as of 03:16Z)
| Launcher | Config | Player / enemy | Live on b287 |
|---|---|---|---|
| Play-Saved-Skin | saved selection | aurora-teal / crimson-red + both detail maps | **yes**: 120 s run, skin_material checks passed before timing and at the end |
| Play-Aurora-Crimson | `aurora-teal-20261112-144639-5807813a` | aurora-teal / crimson-red | receipt `--check` only |
| Play-Aurora-Gold | `aurora-teal-20261112-144639-a5d808a5` | aurora-teal / **gold-obsidian** | receipt `--check` only |
| Play-Neon-Cyberpunk | `neon-circuit-20261112-144639-8852b8b8` | **neon-circuit / ultraviolet-grid** | receipt `--check` only |

### The frontend fact that matters
`launch_material.py` passes `--launcher`, and main.cpp documents `--launcher` as "force the GUI launcher (overrides skip_launcher)"
(main.cpp:10755, parsed at 10787; the decision is made at 11864-11869). So every normal material launch shows the GUI frontend,
even though `build-release/settings.toml` has `[launcher] skip_launcher = true`. Play-HD passes `--no-launcher`. The frontend
persists its settings to the `settings.toml` beside the exe, which is now the shared `build-release/settings.toml`.

### Check 1: title-only skin state per pair (fast, no route, no aid, no RAM writes)
For each untested config:
1. Prepare (CPU only): `prepare_normal_player.py prepare --leg material-b287 --material-config <config>/material.json
   --batch mat-title-<id>`. This is the same private clone, b287 with its own cache, ring 0 and private cards.
2. Run a title-only pass with root's material runner:
   - launch with `--no-launcher`;
   - wait for debug port 4376;
   - wait until the native title is observed (the pacing boot gate);
   - send `{"cmd":"skin_material"}` (GET; no `set`, no op);
   - check it with `material_state_errors(reply, normal_profile.material_expectation)`;
   - optionally take one `screenshot`;
   - quit.
3. Bound: about 30-45 s per pair, with no gameplay timing claim. Then run `verify-after`.
4. Pass:
   - contract `ein-material-v3`;
   - `ready`, `opengl_ready` and `hd_ready` all true;
   - player and enemy profile and `strength_percent` equal to the config;
   - exact key sets and `key_count`;
   - `detail_active` matching the config's detail strength;
   - clean exit with the port closed.

   This proves configured state at the title only. Appearance of gold-obsidian, neon-circuit or ultraviolet-grid in
   gameplay stays unverified unless a gameplay pass is added.

### Check 2: the real frontend path, once (saved pair)
- Do it on a private clone, so the frontend writes only the private `settings.toml`. Pass `--launcher` exactly as
  `launch_material.py` does (do not substitute `--no-launcher`).
- **Open point for root:** the debug server starts after the frontend hands off to the game (`debug_server_init` runs in the game
  start path, main.cpp:13076). So no debug command can press the frontend's Play button. Options:
  1. one UI-automation click on the owned window, disclosed;
  2. observation only: the frontend renders and reads the private settings (screenshot), then close, with the hand-off
     recorded as untested.
- After the hand-off, repeat the Check 1 skin_material read and compare the private `settings.toml` before and after, to
  record whether the frontend rewrote any key.

### Coupling to keep disclosed
- Material and Play-HD now share build-release `settings.toml`, `cache/` and the capture store.
- The receipt sha binds the material launchers to the Play-HD binary's lifecycle.
- `material_profiles.environment()` sets `PSX_DISPLAY_RING` to 0 unconditionally (a normal-only policy). Forensic preparation
  sets 1 explicitly.

## B. Seven-stage capture routes without stage select or RAM stage jumps

### What the game allows (STAGE-ACCESS.md §0, §2.2, §3)
- No pad-only shortcut to a later stage exists in the US build.
- No mid-game save exists: the data file holds configuration, bonus mask, gallery and scores, never a stage number.
- The hidden stage select needs RAM writes (Japanese-only Free difficulty gate).
- **The only route that involves no jump is continuous play from boot.**

### Routes, ranked (STAGE-ACCESS.md §7)
| Route | RAM writes | Use |
|---|---|---|
| Continuous chain, Stage 1 → 7 in one session, with the disclosed **invincibility-countdown aid only** (`0x80085718`, renewed; the same aid used in tonight's boss runs). No lives lock, because a lock hides the gate-L Continue and Game Over legs | the aid only, disclosed; **no stage jump** | **capture** (`acceptance_eligible:false`) |
| Same chain, then the deterministic replay layer (`input_route_append`, guest-synchronous; RAM-hash checkpoints at stage start, Greif first draw and the `0x80081380` 1→2 load) | none beyond the original aid | re-enter any stage on demand without a pilot, if the hashes match |
| Robin pad-only, stage by stage | none | **acceptance** (not ready: Greif kill, Drache families and later-stage policies are missing) |

### Chain plan (one continuous owned session; Codex runs it; segment windows rotate)
1. **Stage 1** (boot → Drache → Stage 2 load). Reference: about 34,000 frames, about 13 min. The Stage 2 load shows
   as `0x80081376`/`0x80081380` going 1→2, with section `0x80081382` going 31→1, at about frame 40,622 in the Nov 12 reference.
   - Decide the Greif branch deliberately and record it: a lower-section kill gives the Angler path, otherwise Fledermaus.
   - Work items: S1 checklist (23 Drache flash keys, and so on).
2. **Stages 2, 3, 4, 5, 6, 7**: straight play, with a 15-30 min runtime budget per stage (a budget, not a measurement).
   - The Stage 6 timer must be failed once deliberately for the second ending (AQ-13), on a separate pass.
   - Work items: S2-S7 and the S6 appendix checklists (shared items X-05E1881C and X-704256 are captured once).
3. **Marks:** a 1 Hz read of `0x80081380`, `0x80081382` and `0x80081384` (stage, section, sub-state) for marks only. Recorder
   windows are rotated per segment (≤ 256 sources each).
4. **Stop rule:** if a stage cannot be cleared, record the frame and the reason, and keep everything captured so far.

### Two runtime choices that change what the chain proves
- **Display ring:** use `PSX_DISPLAY_RING=0` for the long chain. The ring cost about 26% of main-thread CPU in the boss
  profile, and it is read once at launch, so it cannot be toggled mid-run. Items that need frame-exact VRAM
  (`display_ring_get` / `display_ring_aux`) belong in short separate runs with ring 1.
- **Native code beyond Stage 1 (smoothness):**
  - b287's 4,405-shard cache was compiled from development captures. Stage 1 is proven smooth with it. Whether it holds
    shards for Stage 2-7 overlays is UNKNOWN, and the normal packaging cannot self-warm (no compile command).
  - So the chain should also request `{"cmd":"overlay_capture_dump"}` at each stage start, mid-stage and boss end, and copy
    `runtime/overlay_captures.json` each time. That is the run_stage1_code_capture.py pattern; it needs
    `PSX_OVERLAY_AUTOCOMPILE_OFF=1`, which is behaviour-neutral here.
  - Then compare the dumped load addresses and CRCs against the b287 cache's shard names. Missing pages become the
    option (a) pipeline: compile_overlays.py with the current framework (tag a4ce4ce4 / ABI 21 / CPS, which equals b287
    and f018), then shadow-qualify on b287 and stage only the qualified shards.
  - Until then, Stage 2-7 smoothness on the normal packaging is unmeasured.

### What each stage run unblocks
See `remaster-audit/claude-backlog/capture-checklists/INDEX.md`:
- S1: 23 keys + an A/B of 195;
- S2: 39 + 60 + 119 + 16;
- S3: 39;
- S4: 11 + 233;
- S5: 12 + 245;
- S6: 101;
- S7: 26.
