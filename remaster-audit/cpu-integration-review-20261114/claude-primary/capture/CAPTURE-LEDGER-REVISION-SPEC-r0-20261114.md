# Scene capture: full GP0 command ledger, revision spec r0 (claude-einhander). Tool clock 2026-11-14 20:44Z

Status: SOURCE-ONLY SPECIFICATION. No code, build or run. This is the capture revision T2 r0 (ba059e13) needs before
any frame can be live-eligible (root msg_15415729).

The current capture is v66-r3 `src/scene_capture.cpp`: 78c4158d6428b57e5c1312b61637af4cfebd0c8a484860294ae13ce140c9eff8,
172 lines, LF. This is the file the v68 build links (build.json → v66-r3 `scene_capture.cpp.obj`).

## What the current capture does (read in source)

- `scene_capture_command` (:87-115) records **only textured polygons** (GP0 0x20-0x3F with bit 2).
  - Every other class is a counter only: untextured polygons, textured sprites, untextured rects, lines, VRAM fills
    and `other_commands` (:93-99).
- `ordinal = textured_seen - 1` (:110) is the textured-polygon index, not a global GP0 position.
- `geometry_types_complete` (:83) is true only when no untextured polygon, sprite, rect, line or fill occurred.
  Einhänder's HUD alone makes that false in gameplay frames.
- **Every recorded primitive gets `qualified = 1`** (:114), so it is not a quality gate. T2 uses it only
  conservatively.
- **Not counted as geometry at all:** VRAM transfers (0x80 copy, 0xA0 CPU→VRAM, 0xC0 VRAM→CPU) and state commands
  (0xE1-0xE6). These fall under `other_commands` and do not affect `geometry_types_complete`, yet a mid-frame VRAM
  write or copy can change a texture or the framebuffer between two draws.

## Required revision: a bounded per-frame command ledger

**1. One ledger entry per GP0 command** processed while RECORDING, in submission order, including commands that
are not recorded as primitives:

| Field | Meaning |
|---|---|
| `global_index` | u32, 0-based within the sealed frame |
| `op` | GP0 opcode |
| `class` | textured_poly, untextured_poly, sprite, rect, line, fill, vram_copy, vram_write, vram_read, state, other |
| `textured_index` | `records[]` index for a recorded textured polygon; UINT32_MAX otherwise (also UINT32_MAX after record overflow) |
| `bbox` | screen-space i16 x0,y0,x1,y1 (see 2) |
| `vram_rect` | destination VRAM rect for fill, copy and write; source rect for copy and read |
| `state_hash` | hash of the draw state in force (drawing area, offset, mask bits, texture window, tpage) |
| `flags` | mask set/check, semi, raw, textured |

**2. Exact bbox rules** (draw offset applied, clamped to the drawing area):
- polygons and lines: min and max of the vertex xy;
- sprites and rects: xy plus the size (variable for 0x60/0x64 and their variants; fixed 1x1, 8x8 and 16x16 for the
  others);
- fills: the fill rect, unclamped by the drawing area, per hardware behaviour;
- state, transfer and other commands: no screen bbox, but they are **ordering barriers** (section 4).

**3. Bounds:**
- the ledger capacity is fixed (proposed 8192 entries per frame);
- an overflow sets a new `info.ledger_overflow`, and then `info.ledger_complete = 0`;
- no allocation in the command path; the capacity is reserved once at arm.

**4. Completeness, replacing the geometry-type requirement for live use.** A new field
`info.ledger_complete = complete && !ledger_overflow && !malformed && (ledger_count == commands seen in the sealed interval)`.

T2 live eligibility becomes:
- `ledger_complete`;
- and no VRAM write, copy or fill whose `vram_rect` overlaps the texture page or CLUT of any transported polygon
  **after the first and before the last** transported use of that page. Otherwise the material content may differ
  within the frame, and the pilot keeps the frame native. Per-material content generations are a later refinement.

**5. Same ownership rules as today:**
- the owner thread token binds the capture;
- a wrong thread touches nothing;
- read-side JSON is bounded and copied from sealed records only;
- no file I/O and no guest state writes.

**6. Read-side:** `scene_capture_ledger_get(token, generation, index, out)` and a bounded JSON row, mirroring
`scene_capture_get` and `scene_capture_json`.

## Effect on T2 r0 (ba059e13)

- T2's `LedgerEntry {x0,y0,x1,y1,textured_index,captured_textured}` maps directly onto the new fields. T2's
  coverage gate would test `ledger_complete` plus the VRAM-barrier rule, instead of `geometry_types_complete`.
- T2 r1 would add the barrier input and a `F_VRAM_BARRIER` frame reason. **This is not done yet**; it needs this
  revision first.

## Test plan (synthetic GP0 streams; CPU only, under a grant)

1. Order: an interleaved stream (sprite, textured polygon, rect, textured polygon, line, fill) yields
   `global_index` 0..5 in order, with `textured_index` 0 and 1 on the two polygons.
2. Bbox per class:
   - polygon, line, all sprite sizes, rect, fill;
   - with a draw offset;
   - with clamping to the drawing area (except fills).
3. Transfers and state: 0x80, 0xA0, 0xC0 and 0xE1-E6 give barrier entries with `vram_rect` or `state_hash` and no
   bbox.
4. Overflow at exactly capacity+1 sets `ledger_overflow`, `ledger_complete = 0`, and records no partial entry.
5. Record overflow (1025 textured polygons) still produces ledger entries with `textured_index = UINT32_MAX` and
   `complete = 0`.
6. Frame-boundary sealing, a malformed command and a wrong-thread call all leave the ledger unchanged.
7. T2 integration (with T2 r1): a VRAM write overlapping a transported polygon's page between two uses gives
   F_VRAM_BARRIER; a non-overlapping write is allowed.

## Not claimed

- Not implemented. No current capture produces a ledger.
- T2 stays diagnostic-only until this revision exists and is qualified.
- No live compositor, RT or acceptance claim.
