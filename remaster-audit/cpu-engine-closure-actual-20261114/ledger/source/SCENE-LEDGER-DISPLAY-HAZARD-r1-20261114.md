# Scene ledger r1: display hazard (claude-einhander), written 2026-11-14 ~23:38Z

**Status: SOURCE-ONLY PROPOSAL.** Nothing here has been compiled or run. It is an additive revision of ledger r0
(`../ledger-r0/`, all files preserved unchanged). It supplies the `DisplayHazardHook` that T2 r5 and r6 require:
`build()` returns `T2S_HAZARD_MISSING` without one. It enables no live gate. Using it needs glue r3, which is not
written yet.

## Files (this folder)

| File | sha256 |
|---|---|
| `scene_ledger.r1.h` | f080658b11c2692de5d47c88989d203cd78bb2b058b128012ff45a394b62f15c |
| `scene_ledger.r1.cpp` | f39a436311a401873276c3f9ad58d3e5bb2117dcb9d0e858cdb73f9c0fc755fb |
| `test_scene_ledger.r1.cpp` (fixture scene_ledger, revision r1, 32 authored checks, none in loops or helpers) | eb4655ec65a65599b1cf1fbbe5a3cf48eced5ee847a599a9930eabfc7d468cc2 |
| `build_scene_ledger_fixture.r1.py` | 5430020d4ad710f3f400ea2da958e6c209f8244ca4676edbf5c446d443879f65 |
| `scene_ledger.r0-to-r1.h.diff` | fbb074c5964271084fa618c740a23fbc73e681d6936024dfdd885d29ac5b22ab |
| `scene_ledger.r0-to-r1.cpp.diff` | c2635a3037a0b72269f941a10ac1798987541cb2dd0e423aa6e36ecb8548b2a5 |

The diffs contain additions only, apart from the include guard (`R0` → `R1`) and the include line of the cpp.
Everything else is byte-identical to r0 (header 220d1a5e, cpp 9614a6a8).

Two pieces are byte copies, both checked with diff:
- The test's lines 12-73 copy the r0 suite's helpers (`test_scene_ledger.r0.cpp` c1d389f1 lines 12-73).
- The driver's lines 77-271 copy `build_t2_fixture.r4.py` 7b39f6a4 lines 77-271.

## API

```
int scene_ledger_display_hazard(uint32_t token, uint32_t generation, const uint32_t *transported, uint32_t count,
                                const int32_t rect[4], SceneLedgerVerdict *out);
```

- **Inputs.** The owner token; the sealed generation; the exact transported capture ordinals; and the frame's target
  rect `{x, y, w, h}` in VRAM halfwords (the buffer the expected flip will display, as in the T2 r6 `SealedScanout`
  target rect). A rect that wraps is split like every other native area.
- **Arguments.** These return `LEDGER_BAD_ARGUMENT`:
  - a null `out` or `rect`;
  - `count > 0` with a null list;
  - `w <= 0` or `h <= 0`.

  A foreign token returns `LEDGER_WRONG_THREAD`. A read never counts as a foreign mutation.
- **Verdicts.**
  - **`LP_NATIVE_INCOMPLETE`** (the default): the ledger is not sealed, not complete, or a different generation.
  - **`LP_NATIVE_BAD_REF`**: the same reference rules as `scene_ledger_policy`, plus `count > capacity`.
  - **`LP_NATIVE_DISPLAY`** with entry and ref both 0xFFFFFFFF: the target overlaps an area that was displayed
    during the interval. The frame did not draw into a hidden buffer, which covers single-buffer frames and
    partially overlapping buffers.
  - **`LP_NATIVE_DISPLAY`** with entry and ref set: a transported page or CLUT overlaps the target. Its texels
    would be the very image that suppression replaces.
  - **`LP_TRANSPORT_OK`** otherwise.

  The `count == 0` case still runs the displayed-area check.
- **It is not a replacement for `scene_ledger_policy`.** T2 r4 still requires that policy to return
  `LP_TRANSPORT_OK`. That covers mutation of displayed areas, page/CLUT mutation, draw-destination feedback and
  readback after a transported polygon. Fills and other draws into the target buffer are excluded upstream: T2 r3
  requires `geometry_types_complete` (no fills), plus its coverage and interleave rules.
- **Glue r3 adapter** (not written): `DisplayHazardHook.fn(ctx, frame, generation, ordinals, count, rect)` checks the
  sealed header still names that frame and generation, then calls `scene_ledger_display_hazard` with the owner
  token and returns `verdict` (`LP_TRANSPORT_OK == kPolicyTransportOk == 0`).

## Fixture coverage (32 authored checks)

| Group | Checks |
|---|---|
| Z | Owner unbound; init; helper sanity; a recording (not sealed) ledger is INCOMPLETE; after the seal the header is sealed and complete with one displayed area (0,0,320,240) and the entry is captured-textured at index 0; null rect, null out, null list, zero width, foreign token, wrong generation. |
| H | Target B (0,256,320,240): OK, both with the transported set and with an empty set. A target overlapping displayed A is DISPLAY (no entry), with and without refs. A target over the 4 bpp page (512,0) is DISPLAY (entry 0, ref 0), and so is one over CLUT row 500. Absent and repeated refs are BAD_REF. |
| W | A target wrapping past x = 1024 at y 256 is OK. One wrapping into (0..40, 0..240) is DISPLAY. One wrapping past y = 512 into 0..128 is DISPLAY. |
| P | The r0 `scene_ledger_policy` of the same interval is `LP_TRANSPORT_OK` (consistency). |
| X | A 15 bpp page (512..768) is DISPLAY when overlapped, and has no CLUT, so CLUT row 500 is OK. INCOMPLETE after an external VRAM write, an unknown display area, or a foreign-token mutation. |

## Driver (two executables, both must pass)

- **`r0reg`:** the UNCHANGED r0 suite, `test_scene_ledger.r0.cpp` c1d389f1 (99 checks, revision r0), compiled with
  `scene_ledger.r0.h` and linked with `scene_ledger.r1.cpp`. This is the regression check that r1 keeps every r0
  behaviour.
- **`r1`:** the new suite, `test_scene_ledger.r1.cpp` (32 checks).
- Both are built under `-std=c++17 -Wall -Wextra -Werror`. The `.inc` comes from the raw-pinned v66-r3 BLOCKS. The
  compilers are pinned.

## Run request (only after root's review AND a fresh grant naming the CPU; one attempt, no retry)

O = `C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary`.

1. Copy the envelope to `O/remix-transport/ledger-r1-run1-runner/executed-watchdog.py` and verify fa5e42fa.
2. Set OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1.
3. Run:

```
C:/Python314/python.exe -I -B O/remix-transport/ledger-r1-run1-runner/executed-watchdog.py --out O/remix-transport/ledger-r1-run1-envelope.json --cpu N --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B O/remix-transport/capture/ledger-r1/build_scene_ledger_fixture.r1.py --cpu N --out-root O/remix-transport/ledger-r1-run1
```

## Not claimed

- Compile success.
- Glue r3 wiring.
- Correct display rects for 24-bit or interlaced modes (the glue must compute them in halfwords).
- Material identity (G4).
- Any live suppression.
