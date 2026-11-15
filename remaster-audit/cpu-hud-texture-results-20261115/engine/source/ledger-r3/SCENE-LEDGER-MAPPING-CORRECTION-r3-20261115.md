# Scene ledger r3: strict identity mapping for pure footprints (claude-einhander), written 2026-11-15 ~00:14Z

**Status: SOURCE-ONLY CORRECTION** of ledger r2 (`../ledger-r2/`, preserved unchanged), per root msg_2fe98abb. r2's
`scene_ledger_footprint` treated any nonzero `native_screen_mapping` as identity. The native contract is identity
`== 1` only. r3 answers **unknown** for every draw whose mapping is not exactly 1. Nothing else changes. Nothing
here has been compiled or run.

## Files (this folder)

| File | sha256 |
|---|---|
| `scene_ledger.r3.h` | 9a0af4a903cfbd653ed858cec2f23e71ade8322fe6e55255e1dbddff833073fd |
| `scene_ledger.r3.cpp` | 234993106083f7ed5633d50b6a0872851397c8d6198bc8f508ecb1cb4564513e |
| `test_scene_ledger.r3.cpp` (revision r3, 29 authored checks) | a51b2c1d6676cab2642e7196f28fdebc509029c4035db82f21b450f568af23b4 |
| `build_scene_ledger_fixture.r3.py` | f08a5a2e2b51f6761f4a81bb6621fd6e96a8421a5fb1936340db4c1c9b2a81fc |
| `scene_ledger.r2-to-r3.h.diff` | 24eef8dc6b2b4f64be445242b883fda8fc2373bb30c83ce732867a3417984f52 |
| `scene_ledger.r2-to-r3.cpp.diff` | 1d00360d0da327c7670fc8d878b04fe1c73dd0a6519de46081acb04f97a49998 |
| `test_scene_ledger.r2-to-r3.diff` | a080d37d48b521e9c8b7b72cb13aaa6989523769034c765800066849d935e126 |
| `build_scene_ledger_fixture.r2-to-r3.diff` | d0c7799788084b883ec80ea8dd6a4a30a45d314f071bea40d8129b5fa4f447ea |

What the diffs change:
- **cpp:** the note, the include line, and the one rule: `!s->native_screen_mapping` becomes
  `s->native_screen_mapping != 1` in `scene_ledger_footprint`.
- **Header:** the guard, a note, and the one comment line that states the rule.
- **Test:** the r2 suite plus one check. With mapping 2, a draw is unknown with 0 pieces, while a fill stays known
  with 1 piece (fills are not draws). Also the title, include and revision strings.
- **Byte copies:** the verbatim r0 helpers stay at lines 12-73, and the driver's 7b39f6a4 lines 77-271 are still
  byte copies.

## Recorded path versus pure path

The recording path (r0 `draw_footprint` inside `record()`) still treats any nonzero mapping as mapped, unchanged
since r0. The pure path used by glue r3 is now stricter, which is conservative. The equality corpus uses mapping
1 only, so recorded and pure footprints still agree on it. The glue sets the mapping only to 0 or 1 today.

## Driver (four executables, each linked with scene_ledger.r3.cpp)

All are built under strict `-Werror`:
- `r0reg`: the unchanged r0 suite (99);
- `r1reg`: the unchanged r1 suite (32);
- `r2reg`: the unchanged r2 suite (28);
- `r3`: the new suite (29).

## Run command (only after root's review AND a fresh grant naming the CPU; one attempt, no retry)

With O = `C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary`,
copy the envelope to `O/remix-transport/ledger-r3-run1-runner/executed-watchdog.py` (fa5e42fa), then run:

```
C:/Python314/python.exe -I -B O/remix-transport/ledger-r3-run1-runner/executed-watchdog.py --out O/remix-transport/ledger-r3-run1-envelope.json --cpu N --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B O/remix-transport/capture/ledger-r3/build_scene_ledger_fixture.r3.py --cpu N --out-root O/remix-transport/ledger-r3-run1
```

Ledger r3 supersedes ledger r2 as the input to glue r3, so a ledger r3 grant makes a separate r2 run unnecessary.
