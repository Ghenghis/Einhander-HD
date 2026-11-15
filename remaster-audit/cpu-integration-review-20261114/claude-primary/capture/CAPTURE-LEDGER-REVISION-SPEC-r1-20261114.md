# Scene capture: full GP0 command ledger, revision spec r1 (claude-einhander). Tool clock 2026-11-14 20:52Z

Status: SOURCE-ONLY SPECIFICATION, no code. r0 (0e7cf0f0…) is preserved read-only and superseded. r1 applies root's
full read msg_969285059 and my own erratum.

The current capture is v66-r3 `src/scene_capture.cpp` 78c4158d. It is retained unchanged.

## Erratum to r0

r0 said `qualified = 1` for every recorded primitive. **That is wrong.**
- :114 sets it to 1;
- :136 clears it whenever any vertex reason is not VERTEX_OK.

So `qualified` means that every vertex has view provenance. It does not mean native eligibility, which is carried by
the per-triangle masks at :151-156.

## Corrected rules

**1. VRAM mutation policy for the first pilot: simplest and safe.**
- **Any VRAM mutation in the sealed frame** sends the **whole frame native**, whether before, between or after the
  draws. "Mutation" means a fill (0x02), a VRAM→VRAM copy (0x80) or a CPU→VRAM write (0xA0). It applies when the
  destination rect intersects:
  - any transported polygon's texture page area (depth-dependent width);
  - any transported polygon's CLUT row span;
  - or the displayed framebuffer area.
- There is no before/after-use assumption. r0's "only between first and last use" rule was insufficient, because
  material pixels sampled at frame end are changed even by a write after the last draw of a single-draw material.
- A later revision may replace this with a per-draw owned material version, meaning pixels copied at draw time
  (the G4 contract). Not now.

**2. Transfer bounds come from the native GPU decoder, never from a naive xy+size.**
- Copies record **both** the source and destination rects.
- Fill, copy and write rects follow the hardware rules:
  - wrap and split at 1024×512 (a rect crossing the right or bottom edge becomes up to four pieces);
  - fills use 16-pixel aligned x and width;
  - zero-size encodings decode as the native unpack defines them.
- The capture revision must reuse the existing GPU command decoder's exact unpacking. Duplicate arithmetic is not
  allowed. Piece lists are bounded, at up to 4 rects per transfer.

**3. Bbox arithmetic is exact.**
- int32 intermediates;
- vertex x/y use the exact 11-bit sign extension (as the capture already does at :120-121);
- the draw offset is added in int32;
- the native oversize semantics (dx > 1023 or dy > 511 discards the triangle) are recorded per triangle, as now;
- ledger rects are **half-open** [x0,x1)×[y0,y1). Inclusive native extents convert once, at the boundary, to avoid
  off-by-one overlap errors;
- the drawing-area clamp applies to draws, but not to fills (hardware);
- **polylines** (0x48-0x5F, terminated by 0x5xxx5xxx or the word limit) are bounded by their actual decoded vertices.
  An unterminated or over-long polyline is malformed, which means unknown coverage and therefore whole frame
  native.

**4. Unknown means native.**
- Any malformed command, unsupported or unknown opcode, ledger overflow or state the capture cannot represent sets
  `ledger_complete = 0`.
- T2 then keeps the whole frame native. There are no partial frames.

**5. The ledger header carries full provenance:**
- frame, generation, owner token, sealed;
- complete, and the global command count over the sealed interval (all classes, not the textured count);
- malformed and overflow counters;
- a final draw-state hash.

T2 r1 (a00ca23f) already requires frame, generation, complete and command_count equal to the entry count. The token
and sealed fields would be added in T2 r2.

**6. Limits of what this proves.** A complete ledger proves **ordering and coverage of commands** only. It proves
**neither material content identity** (G4: per-draw native words, CLUT/version serial, dimensions and an owned pixel
copy) **nor that a 2D/3D composition is valid**.

T2 stays diagnostic-only until the ledger revision and the G4 material versioning are both implemented and
qualified.

## Ledger entry (unchanged from r0, with r1 types)

| Field | Content |
|---|---|
| `global_index` | u32 |
| `op` | GP0 opcode |
| `class` | command class |
| `textured_index` | u32 |
| `bbox` | half-open, int32 |
| `vram_dst[≤4]`, `vram_src[≤4]` | decoded pieces |
| `state_hash` | draw state in force |
| `flags` | as in r0 |

## Test plan r1 (synthetic GP0 streams; CPU only, under a grant)

1. Order and class for an interleaved stream, as in r0.
2. Bbox:
   - 11-bit sign edges (±1024 encodings);
   - offset overflow into int32;
   - half-open conversion;
   - drawing-area clamp for draws;
   - no clamp for fills;
   - oversize triangles flagged.
3. Transfers:
   - a copy records both src and dst;
   - a rect crossing x = 1024 splits into 2 pieces, a corner crossing into 4;
   - fill alignment to 16;
   - zero-size encodings match the existing decoder for every opcode.
4. Polylines: a terminated polyline gives the exact bbox; an unterminated or over-long one is malformed, so
   `ledger_complete = 0`.
5. Policy: a VRAM write after the last draw that overlaps a transported page gives whole-frame native, and so does
   one before the first draw. A write that overlaps nothing transported and not the framebuffer is allowed.
6. Overflow, unknown opcode and wrong thread all give `ledger_complete = 0` and leave the ledger unchanged
   (wrong thread).
7. The header binding: frame, generation, token, sealed and command count, cross-checked against T2 r1's
   LedgerHeader.

## Not claimed

Not implemented; no build, import or test. The capture is unchanged. No live, material or composition acceptance.
