# Reaching Stages 2-7 for native-source capture (W5 stage-access study)

Read-only analysis, 2026-11-13 (Claude).

- Nothing was launched.
- No runtime file, user card or Codex file was modified.
- Writes are confined to this folder.
- Inputs, hashes and the CPU-QUIET log are in `LEDGER.md`.

This revision folds in the coordinator's two leads from `../secrets/CATALOGUE.md`: the debug menu or hidden stage select, and the AQ-02 syscall hypothesis.

**Labels:**
- PRIMARY-DISC: code or data read from the disc, with an address;
- RUN: RAM or draw evidence from a recorded run;
- SECONDARY: FAQ or cheat list;
- UNVERIFIED.

**Static tools** (single-threaded, read-only):

| Tool | Purpose |
|---|---|
| `xref_state_vars.py` → `xref-state-vars.json` | absolute-address cross-references in `SYS.EXE` and BINPACK0-4 |
| `ea_search.py` | fast reference search for any address |
| `dis.py` | window disassembler |
| `aq02_overlay_check.py` → `aq02-overlay-check.json` | the AQ-02 page images |
| `page_provenance.py` → `aq02-page-provenance.json` | the AQ-02 page images |

---

## 0. Bottom line

1. **Stage 2 has already been entered once, in an assisted run.** The Nov 12 session `level1-live-d59b8e1c` (`verified-pass`, then `boss-pass`; research runs 152726 → 153038 → 153406 → 155355) did it.
   - **The game's own stage fields change exactly as the engine code says they should.** At frame **40,622**, `0x80081376` goes 1→2, `0x80081380` goes 1→2 and the section counter `0x80081382` goes 31→1 (`research-20261112-153406-11eebc24/samples.jsonl` line 208).
     - `SYS.EXE` 0x800489E4-0x80048A04 increments `0x80081376` on stage advance.
     - 0x800254D8-0x800254E8 copies it into `0x80081380` and loads the section from `0x80081D8E`.
   - The session was still in Stage 2, section 2, at f97,624 (155355 snapshot).
   - The census bucket "post-Drache, 128 keys" (frames ≥ 40,622) is therefore **Stage 2 opening content**. Gate E still wants visible identity.
2. **That run was assisted.** The dev-center held the invincibility countdown `0x80085718`=165 and lives `0x800813C4`=3:
   - `verified-pass/assisted-pilot.jsonl` line 1 (`hold_fields ["invincibility","lives"]`);
   - `boss-pass/probes/153739777950.json` and `153740709025.json`.

   `DRACHE-GUIDANCE.md`'s "no RAM writes" refers only to the recorder. Stage 1 start to Stage 2 took about 34,000 frames, about 13 min of wall time, with a trivial scripted pilot.
3. **There is no pad-only shortcut to a later stage in the US game** (§3).
   - The DEBUG OPTION screen is a "Sorry, Under Construction!" stub.
   - The title's debug entry is unreachable by cursor wrap.
   - The hidden Configuration stage select is gated behind the Japanese-only Free difficulty. The US code forces Free back to Normal in three places, and one prerequisite flag (`0x8008595E`) is zeroed at init and has no direct writer in any code.
   - There is no mid-game save (FAQ; and statically, the data file holds configuration, the bonus mask, the gallery and scores, never a stage number).
   - **Later stages need a continuous run.**
4. **AQ-02 (the syscall hypothesis).**
   - **The mechanism is real:** while the engine overlay is resident, `0x800ADAA4` holds `0x96AE000C` (`lhu t6,12(s5)`), and writing `0x0001` to `0x800ADAA6` turns it into `0x0001000C` (`syscall`).
   - **It did not happen in the AQ-02 run.** Both engine images captured before an overwrite still hold the disc bytes at `0x800ADAA6` (§1.2).
   - In addition, the one-shot pokes could not have opened stage select, and they touch no display state.
   - The black screen is most likely a runtime or presentation fault of the unverified 03:41 build, or of the capture path. Next test: a no-poke control (§1.4).
5. **Fastest legitimate route** (rank 1, §7): rerun the proven assisted route as a proper acquisition run, with a disclosed invincibility-timer aid only, and continue in the same session through Stage 7. Expected cost is about 15-30 min of runtime per stage plus setup.
   - **Optional capture-only fixture** (rank 3): the game's own stage-select step can be opened with three one-shot writes to `SYS.EXE` BSS **data** (never overlay addresses) while the front end is resident.
   - It is useful for reconnaissance and supplementary re-captures. It fails gate R and is never acceptance.

---

## 1. AQ-02: what happened, and the verdict on the syscall hypothesis

### 1.1 Run evidence (`C:/github/REMASTER_STAGING/hd-expansion/capture-stage2/`)

| Item | Finding |
|---|---|
| `evidence/stage-select-writes.json` | `0x800ADAA6`=01, `0x800ADAA7`=00, `0x80085960/61`=FF FF, `0x8008593C/3D`=00 00 (the almarsguides "Enable Stage Select" code `800ADAA6 0001 / 80085960 FFFF / 8008593C 0000`, a constant-write cheat). Scope: "Isolated runtime RAM only". **No timestamp, frame or input log** |
| `runtime/settings.toml` | memcards disabled. `captures/card-or-title.png` (03:55, `10c29e30...`) shows the game's "Memory card not inserted. X Check" dialog |
| Black captures | `initial-menu.png` (03:54, the **first** capture), `stage-unlock-title.png` (03:55) and `now-menu.png` (03:59) are identical, sha256 `489cf39e...`, mean 0 and max 0. **No non-black title frame exists in this run** |
| `evidence/draws.jsonl` | Boot f69-1462. Front end f8,740-9,414. Stage 1 keys from f11,327: Mk.III hull, fighters, Uhu, night sky, neon at f13,576. From f20,390: Mk.II hull `7E3ADD56/B16492B1` with menu-text atlas `E6B65424`. All 659 keys are Stage 1 or menu. These are consistent with title attract demos (TRIAGE §1) |
| `draws.jsonl.stats.json` | 3,317,788 replacement draws through f22,948: the guest and the renderer kept running |
| `runtime.stderr.log` | dump lines only; no guard or overlay message |
| Binary | `runtime/Einhander_Recompiled.exe` sha256 `8d5ffa4c...`, built 03:41, no `build.json`. It is not the installed post-polyline-fix build (`05c69984...`). **AQ-02(a): an unverified dev build** |

### 1.2 Which code occupied `0x800ADAA6`, and when (`aq02-page-provenance.json`, `aq02-overlay-check.json`)

The run's own pre-overwrite page captures (`runtime/overlay_captures.json.d`, 173 pages) were located byte-exactly on the disc:

| Local time | Pages overwritten | Disc source | Meaning |
|---|---|---|---|
| 03:57:23 | `0x8008E000-0x800A5000` | BINPACK0 entry 10 (front end; file offset + `0x7FFCE800` = RAM, i.e. entry offset 0 ↔ `0x8008C800`) | front end replaced by the engine: the first demo or game start |
| 03:58:57-59 | `0x8008D000-0x800E3000`, **including `0x800AD000`** (`D65811353BCAA437.json`) | BINPACK1 entry 0 (engine; offset 0 ↔ `0x8008C800`) | engine replaced: back to the title |
| 04:00:31 | front-end pages | BINPACK0 entry 10 | front end replaced again |
| 04:00:33-37 | engine `0x800E6000-0x800F9000`; stage module BINPACK1 entry 3 at `0x80146000+` | BINPACK1 entries 0 and 3 | engine pages and the Stage 1 module |
| 04:02:00 | `0x8008D000` and **`0x800AD000`** (`5C631C39356BBC67.json`) | BINPACK1 entry 0 | engine replaced (end of run) |

- **Both engine images of page `0x800AD000` hold the disc bytes at `0x800ADAA6` (`AE 96`).** The word at `0x800ADAA4` is `0x96AE000C` = `lhu t6,12(s5)`, inside a GTE vertex-load sequence (`mtc2` follows).
- So no poke was present during either engine residency (03:57:23-03:58:57 and 04:00:33-04:02:00). **The syscall corruption did not occur in this run.**
- The pokes were made while the front end was resident (03:55). In the front end, `0x800ADA40-0x800ADAAF` is zero-filled data at the tail of BINPACK0 entry 10 (`BINPACK0.BIN` offsets `0xDF240+` are `00`).
- **The hazard is still real for any constant (cheat-device-style) application:** once the engine loads, the write converts that `lhu` into `syscall`.

### 1.3 What the three writes actually do (PRIMARY-DISC)

| Write | Location | Meaning from code | Effect as applied (one-shot, front end) |
|---|---|---|---|
| `0x800ADAA6` = 1 | front-end data | Working variable of the Configuration screen. 0x800A2128-0x800A2168 copies save `+0x1C90/92/94/96/9A` to `0x800ADA9C-A4` and **zeroes `0x800ADAA6`** when the screen opens. It is read by six menu routines and reset at 0x800A30FC | Overwritten by the game's own code on the next Configuration entry. Harmless in the front end; **becomes a `syscall` patch if it is still applied after the engine loads** |
| `0x80085960` = FFFF | `SYS.EXE` BSS | Copy of save `+0x1C98`: the **7-bit "stage with all 3 secret bonuses" mask** (front end 0x8008F488-0x8008F588 sets bit k when group k of the bonus word `0x80081B54` is complete) | Inert unless `0x8008595E` ≠ 0 |
| `0x8008593C` = 0 | `SYS.EXE` BSS | Copy of save `+0x1C90` = **difficulty**; 0 = Free (JP) | **Reset to 2 (Normal)** by `SYS.EXE` 0x80038954-0x80038970, step 0 of every top-level sequence, and by the front end at 0x8008E55C-0x8008E570 and 0x8009DA04-0x8009DA14 |
| (not written) `0x8008595E` | `SYS.EXE` BSS | Copy of save `+0x1C9A`. **Required ≠ 0** by the stage-select gate (§3.2). `SYS.EXE` zeroes `0x80085918-0x80085977` at boot (0x8001A4F8-0x8001A508). No direct writer was found except the save↔RAM copies (absolute and struct-relative scans; a block copy cannot be excluded). With no card it is 0 | the gate stays closed |

**Verdict.**
- The pokes, as applied, could not open stage select, and none of them is display state.
- With the engine bytes proven intact and the first capture already black, the leading explanation is:
  - a presentation or runtime fault of the unverified 03:41 build with this configuration (HD on, `page_fallback 1`, dumping, cards disabled);
  - or a capture-path fault.
- This is UNVERIFIED until the control below runs.

### 1.4 Next test (one short isolated run; no pokes first)

1. **No-poke control.**
   - Same isolated arguments as `session.json`, cards disabled, HD on, `page_fallback 1`, dumping on, on the **current baseline build**.
   - Boot → card dialog → X → title. Capture title, demo and menu. Log `gp1_dump`/`gpu_state` (display enable and display area) once a second.
   - Black ⇒ a runtime/presentation bug unrelated to stage select. Report it to the runtime owner; it matters for any cards-disabled acquisition.
   - Not black ⇒ repeat once with the same one-shot writes at the title, to reproduce or clear AQ-02.
2. **Close AQ-02** with that receipt. Do not spend more on cheat codes; §3 shows the published code is incomplete for the US game (it lacks `0x8008595E`).

---

## 2. Game state: stage, progress and unlocks

### 2.1 Stage and section variables (PRIMARY-DISC semantics + RUN values)

| Address | Code evidence | Run evidence |
|---|---|---|
| `0x80081376` stage to load (1-based) | Set to 1 by the new-game path (BINPACK0 entry 14, function 0x801CF7BC; `[0x800812F8+0x7E]`=1). Incremented on stage advance (`SYS.EXE` 0x800489E4-0x80048A04, which also sets `0x80081D8E`=1) | 0→1 at the front end (145827 line 67); 1→2 at f40,622 |
| `0x80081380` current stage | `= 0x80081376` at stage load (`SYS.EXE` 0x800253BC / 0x800254DC / 0x80025528) | 0→1 at Stage 1 start; 1→2 at f40,622 |
| `0x80081382` current section | `= 0x80081D8E` at load; indexes `*(0x8005296C + stage*4)` → section script pointer → `0x80081300` | 9 at the Greif, 30 at the Drache, 31→1 at Stage 2, 2 at f97,624 |
| `0x80081D8E` start section | 1 at new game and at each stage clear (restart point) | — |
| `0x80081374` | 0 at new game (`[0x800812F8+0x7C]`); written by the engine in 4 places (BINPACK1 entry 0 `+0xCCF0`, `+0xEE28`, `+0xF3AC`, `+0xF720`) | 0→1 at f40,622 (meaning UNVERIFIED) |
| `0x8005296C` | Per-stage section tables: index 0 NULL, **indices 1-7 non-NULL**, 36 words each. This is code-level confirmation of **seven stages** | — |
| `0x80081384` | boss/event flag (CANDIDATE) | 1 during bosses; 4 at f97,624 |

All of these are **read-only phase detectors** for acquisition marks. Gate E still needs visible identity.

### 2.2 Save image and persistence (PRIMARY-DISC)

**Save buffer.** The pointer `*(0x80085918)` is very likely `0x801FD000`, one 8 KB card block. The gallery cheat `0x801FEC9C` equals buffer `+0x1C9C`.

**Load path.** Front end 0x8008DDE8-0x8008DF0C copies the save into RAM:

| Save offset | RAM | Meaning |
|---|---|---|
| `+0x1C90` | `0x8008593C` | difficulty |
| `+0x1C92` | `0x80085944` | stereo/mono branch at 0x8008DE8C |
| `+0x1C94` | `0x8008594E` | — |
| `+0x1C96` | `0x80085950` | — |
| `+0x1C9A` | `0x8008595E` | stage-select prerequisite |
| `+0x1C98` | `0x80085960` | bonus-complete stage mask |
| `+0x1C70..8E` | `0x8008591C..` | 16 words, controller map |
| `+0x19F0..` | `0x80081854..` | score and ranking tables |

**Save path.** The reverse copy is at 0x8008E104 and 0x8008F2E0.

**Secret bonuses.**
- Stage modules OR bits into `0x80081B54`, 3 bits per stage:
  - BINPACK1 entry 3 at 0x8014CA08-0x8014CA20, after 16 counted hits in `0x80081DD2`;
  - BINPACK1 entry 15, BINPACK3 entry 2 and BINPACK4 entry 7.
- Each also bumps the S.Bonus count `0x80081B5A` and sets the 120-frame notice timer `0x80085741`=0x78.

**No stage number or resume point is saved.** This matches the FAQ: "Saving isn't possible. You can restart only from the first level." So `natural_save_then_next_stage_entry` does not exist.

---

## 3. Debug menu and hidden stage select: how each is reached (lead 1)

### 3.1 DEBUG OPTION: no pad route; the US screen is a stub

1. **Title menu.**
   - The title handler (front end 0x80091740) keeps its cursor in `0x800AD29C`.
   - Left/Right change it and wrap at 3, or at 4 when `0x800AD2C4` is non-zero (0x800917F8-0x800918DC). `0x800AD2C4` is set from 0x800929A8 at title init, probably meaning a data file is present.
   - The string "DEBUG OPTION" (0x8008C930) is drawn only when the cursor is **≥ 4** (0x80091D94-0x80091DF8), so the pad can never reach it.
   - No button-sequence table exists (catalogue §8, confirmed).
2. **Front-end screen table.**
   - It sits at 0x800AB1EC: records of 0x24 bytes, handler then name. The dispatcher at 0x8009BA04-0x8009BA28 indexes it by `[0x800ADA2C+0x14]` = **`0x800ADA40`**.
   - Screen 7 "DEBUG OPTION" has handler **0x8009A314**, which prints "Sorry, Under Construction!". Circle steps to the next screen index (wrapping at 16) and Cross jumps to screen 8 (Configuration).
   - DATA LOAD and DUMMY 011/012 use the same stub. The "Debug Option" cheat (`800ADA40` = 7 on Select) therefore lands on this stub.
3. **Debug item labels.** STAGE NO, AREA NO, STAGE SELECT, BIGINNER and the rest at 0x800A7128 have **no table or pointer reference** (one stray string use at 0x8008D810).
   - They are residue: **no working STAGE NO / AREA NO selector exists in the US code.**

### 3.2 Hidden stage select: only with RAM writes in the US build

- **The gate** is the first function of BINPACK0 entry 14 (loaded at 0x801CF000), **0x801CF7BC**:
  - if `0x8008595E` ≠ 0 **and** `0x8008593C` == 0 (Free) **and** `0x80085960` ≠ 0, it sets `0x801FBE78`=1 and goes to the next step, the stage-select step;
  - otherwise it sets `0x80081374`=0, `0x80081376`=1 and `0x80081D8E`=1, and skips 6 steps (new game at Stage 1, section 1).
- **`SYS.EXE` also switches top-level sequence tables on the same two conditions:** the extended `0x80056EA0` (9 steps) versus the normal `0x80056EC4` (6 steps), at 0x800388BC.
- **Natural US reachability: none found.**
  - Free is forced to Normal in three places.
  - `0x8008595E` is cleared at init and has no direct writer.
  - This matches the FAQ and Wikipedia statement that Free mode is disabled in the US release.
- **Natural unlock of the bonus mask:**
  - Bit k of `0x80085960` requires all 3 secret bonuses of stage k+1 (JP behaviour: stage select once a stage's 3 bonuses are earned).
  - In the US build the mask is recorded but never consumed without Free.

### 3.3 Can a capture-only run use the game's own stage select?

Not without RAM writes. The **minimal, safe fixture** follows.

1. **Card.** A private formatted card (or none). Boot to the title.
2. **Writes.** While **the front end is resident** (title or menu, after the sequence's step 0 has run), write once:
   - `0x8008595E` = 1;
   - `0x8008593C` = 0;
   - `0x80085960` = the bit for the target stage, or 0x7F.

   All three are `SYS.EXE` BSS **data**.
3. **Never write any `0x800ADAxx` address.** Those are front-end variables in the shared slot `0x8008C800-0x800AE000` and engine code after it loads; `0x800ADAA6` becomes a `syscall`.
4. **Then:** Game Start → the gate at 0x801CF7BC → the game's own stage-select step → the engine's own loader (0x800254D8). After the selection, no write remains active.
5. **Record.**
   - Read `0x80081380` back for the stage entered.
   - Check the page bytes at `0x800ADAA4` against the disc after the engine loads (`overlay_captures`).
   - Label the receipt `fixture: ram_writes (3 one-shot, SYS BSS data)`.

**Contract status:**
- It fails gate R (`ram_writes`, `stage_select_used`), so it **never feeds `stageN-source` and is never acceptance**.
- It is legitimate as **reconnaissance**: confirming a stage's look and threats before the continuous run, and pre-building Robin families.
- It is also legitimate as **supplementary re-capture** (animation holds, loadouts, Continue legs) **if the coordinator amends the contract**.
- The Free path is not US behaviour: difficulty-scaled content (FAQ: Free has unlimited continues and no score) must be re-captured on Normal in the continuous run.
- The FAQ's Hard-only units (Stage 2 Libelle) need Hard in any case.

---

## 4. Which progressed-state starts are legitimate

| Start state | Capture-only | Acceptance | Contract today |
|---|---|---|---|
| Continuous play from boot with a disclosed invincibility-timer hold | **yes** (ACQUISITION §1.4) | never | `assist.used=true`, `acceptance_eligible=false`; needs the §7 clarification on `route.ram_writes` |
| Game-written save, then resume | does not exist (§2.2) | — | — |
| Game's own stage select, unlocked naturally | not possible in the US build (§3.2) | — | — |
| Stage select via the §3.3 fixture | reconnaissance; supplementary only if the contract is amended | never | fails gate R |
| Debug STAGE NO / AREA NO | does not exist in the US code (§3.1) | — | — |
| Recompiler savestate (`debug_server.c:8129`, HLE only) taken inside a valid chained run | supplementary only if the contract is amended | never | fails gate R (`state_loads`) |
| DuckStation savestates (AQ-03b) | pre-acquisition only; keys differ (R13) | never | separate fallback |

---

## 5. Robin

**Stage 1 (pad-only clear):**
1. **Greif.**
   - 18 deaths in volleys 1-2, never killed (ROBIN-DEATHS §4).
   - `robin_combat_policy.py` lines 56-61 now prefer `greif_arm`, then `greif_mount`. Those families ship in `sampling-build-v38-greif-parts` (11:13Z), but no live run with them exists.
   - Gate: T1-T4 plus one kill.
2. **Neon and the Uhu sweep:** threat evasion exists but is unqualified (T3).
3. **Drache.**
   - No Drache family exists (allowed families, line 28: fighter, uhu, greif, greif_arm, greif_mount, tracer).
   - The beams are untextured (CAPTURE-REQUESTS C4).
   - The only pass was invulnerable, so DRACHE-GUIDANCE's "safe line" is a hypothesis. Its timings and part groups stand.
   - Needed:
     - `drache_head`, `drache_core` and `drache_gun` families;
     - phase detection from the 30-CLUT trim or from `0x80081382`/`0x80081384` reads;
     - Vulcan time-to-kill.
4. **Branch.** The Stage 1 route depends on how the Greif dies: the lower section gives the Angler path, otherwise the Fledermaus path (FAQ). Robin and the capture must pick one deliberately and record which.

**Stages 2-7:**
- `robin_stage_policy.py` is a Stage 1 frame clock (CPA 1733, CP1 3882, Greif 5130).
- Each later stage first needs its own capture: keys for threat families, section timing (now readable as `0x80081382`), boss weak points and untextured hazards.
- Order per stage: assisted capture → census → Robin families and schedule → pad-only qualification. Final acceptance is one continuous pad-only Stage 1-7 run.
- Stage 1 remains the long pole.

---

## 6. Determinism

- **Live inputs are wall-clock.** Dev-center pulses (`assisted-pilot.jsonl`, 60-frame commands about every 0.5 s) and Robin ticks repeat only to about ±6 frames.
- **Route replay is guest-synchronous.** `input_route_append`/`_start` (`debug_server.c:7685-7723`, consumed per pad poll at `:14619-14633`, ≤ 4,096 steps) counts guest pad polls; only its start is wall-clock (`start_frame` is returned; `pause`/`run_to_frame` were removed at `:8199-8239`).
- **Test:** start a route at boot whose first step is a long no-button hold, replay the recorded pad words of a rank-1 run, and compare whole-RAM hashes at:
  - stage start;
  - the Greif first draw;
  - the Stage 2 load (`0x80081380` 1→2).

  If they match, any stage entry can be re-reached on demand. The aid is still needed while the route contains assisted fights.

---

## 7. Ranked plan

| Rank | Route | Gives | Effort | Main risks | Class |
|---|---|---|---|---|---|
| **1** | **Assisted continuous acquisition chain** (AQ-01 rerun, then AQ-03 in the same session) | Every stage, tallies, FMV placement, boss phases, stage identity | Stage 1→2 proven at about 34k frames (13 min); budget 15-30 min of runtime per later stage plus marks and captures | Recorder cap ≤ 256 sources per window (rotate windows per segment); bosses may need real damage; the hold blinks the hull (take hull sources elsewhere); later-stage runtime faults (R03); the Stage 6 timer (fail it once deliberately for the second ending, AQ-13) | capture only |
| 2 | Deterministic replay layer (§6) | Re-entry to any stage without a pilot | 1 short test | The game may draw RNG from timing | capture only |
| 3 | §3.3 stage-select fixture plus the §1.4 no-poke control | Reconnaissance; closes AQ-02 | 1 short session each | contract scope | fixture / diagnostic |
| 4 | AQ-03b DuckStation savestates | Fallback if the recompiler faults in a stage | medium | keys ≠ recompiler keys | pre-acquisition |
| 5 | Robin pad-only, stage by stage (§5) | **Acceptance** | days per stage at the current pace | untextured threats, per-stage policy | acceptance |
| 6 | AQ-08 natural clears on a private card | Gallery, secret craft and pods, endings | after rank 1 or 5 | conditions SECONDARY | unlock evidence |

### Exact first actions for Codex

1. **Correct the record.** The Nov 12 Greif, Drache and post-Drache pass was **assisted** (§0.2). Census "post-Drache" keys at frames ≥ 40,622 are **Stage 2** (§0.1).
2. **Coordinator decision on the aid:**
   - allow an **invincibility-timer hold only** (`0x80085718`, renewed), recorded as `route.assist = {used: true, kind: "invincibility_timer_hold", address, value, frame_ranges}`;
   - `acceptance_eligible: false`;
   - `route.ram_writes: false`, defined as "no writes other than the disclosed aid";
   - **no lives lock**, because it hides the gate-L Continue and Game Over legs.

   `validate_acquisition.py` lines 346-359 would gain an explicit `assist.writes` list (not changed here; read-only task).
3. **Launch** when GPU-RESERVED and CPU-QUIET allow:
   - an isolated owned instance of the current baseline build;
   - a private blank-profile card in slot 1 (avoids the "not inserted" path and lets the end-of-game save appear);
   - HD dumping stock-first to `<run>/stage1-source/`;
   - the recorder armed with a fresh window per segment;
   - 2880x2160 captures;
   - one read per second of `0x80081380`/`0x80081382`/`0x80081384`, for marks only.
4. **Stage 1:**
   - New game, Normal, Mk.II.
   - Arm the hold and log every renewal with its guest frame.
   - Pilot: Square fire plus short vertical sweeps (the `verified-pass/assisted-pilot.jsonl` pattern). Take the WASP pod in the late city.
   - Record which Greif kill gives which branch (Angler or Fledermaus).
5. **Tally and Stage 2 entry:**
   - Window: Drache last draw → section reset, about f39,125-40,622 in the reference run.
   - Marks `tally:stage1` and `stage:2:entry` when `0x80081380` reads 2.
   - Capture the tally text, the first Stage 2 frame and any title card.
6. **Per stage N ≥ 2:**
   - `stageN-source/`, segment marks keyed on `0x80081382`, every boss phase and its destruction;
   - one deliberate death and Continue with the hold released;
   - re-arm the hold;
   - `make_manifest_skeleton.py`, chained `previous_stage_run`.
7. **Stage 6:** do the thrusters run normally (MOV04 → Stage 7). The timeout or second-ending leg (AQ-13) is a separate later run.
8. **Stop rule:** if a stage cannot be cleared even with the hold, record the frame and the reason. Use the §3.3 fixture for reconnaissance of the next stage and AQ-03b for its sources.
