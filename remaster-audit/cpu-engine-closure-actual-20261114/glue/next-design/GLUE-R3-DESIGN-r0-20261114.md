# Glue r3 design r0: wiring T2 r6 and ledger r1 into the runtime (claude-einhander), written 2026-11-14 ~23:58Z

**Status: DESIGN NOTE ONLY.** No code was written, compiled or run. Root's T2 r6 clearance (msg_ebd898c5) explicitly
does not admit glue r3, and this note does not change that. It records the concrete wiring so root can direct,
amend or reject it before any source is authored. Every input named here is frozen:

| Input | sha256 (prefix) |
|---|---|
| glue r2 | de9dfd77 / 3bbc6821 / 730b5b4f / a88b6911 / c6a59759 |
| T2 r6 header | 419dea94 |
| T2 r4 | eebb2c8f |
| ledger r0 | 220d1a5e / 9614a6a8 |
| ledger r1 | f080658b / f39a4363 |

## 1. Footprints in EVERY ledger mode (the main gap)

`PresentState::note_write` must see every VRAM write from the seal of frame N until frame N is retired. That window
includes the ARMED and IDLE phases, where ledger r0 does not record. In ARMED it keeps only `last_opens_body`; see
r0 `scene_ledger_command` :394-404.

**Proposal: ledger r2, additive.** A stateless function:

```
int scene_ledger_footprint(const uint32_t *words, int count, const SceneLedgerState *state,
                           LedgerRect dst[SCENE_LEDGER_MAX_PIECES], uint8_t *dst_count, uint8_t *known);
```

- **Reuses r0 unchanged:** the same `class_of`, the `nat::` decoders (fill, copy, CPU->VRAM, rect sizes,
  `parse_vertex`), `split_wrap` and `clamp_draw`.
- **No hdr writes.** r0's `draw_footprint` writes hdr counters, so the pure function duplicates only the footprint
  arithmetic rather than refactoring r0. That keeps every r0 byte.
- **Divergence guard (fixture):** for a corpus covering every command class, the pure footprint must equal the
  `dst` that `scene_ledger_get` returns for the same command recorded in RECORDING mode.
- **What counts as known.** `known = 0` for:
  - polyline headers (their bodies stream outside the hook);
  - `native_screen_mapping == 0`;
  - malformed commands, or a word count other than the native one;
  - unsupported commands (`LC_OTHER`).

  No-write classes (STATE, NOP, VRAM->CPU read) report `known = 1` with zero pieces.
- **Rect format.** The pieces are half-open and already wrap-split inside 1024x512. The glue converts each to the r6
  `{x, y, w, h}` and calls `note_write` once per piece, or `note_write(any, false)` when `known == 0`.

## 2. Hook placement (scene_runtime, emulation owner)

| Event | Glue r2 today | Glue r3 proposal |
|---|---|---|
| every collected GP0 command and polyline header (`scene_runtime_ledger_command`) | ledger record only | ledger record, plus `scene_ledger_footprint` then `P.note_write` per piece. This runs in any ledger mode while `enabled`, before dispatch. |
| GP1 03/05-08 (`scene_runtime_scanout_changed`) | conservative: any raw change runs `invalidate` | `P.observe_scanout(state, L)`. It bumps the epoch itself on every change except the expected flip. |
| arm (`scene_runtime_arm`) | `armed_epoch = scene_t2_arm_epoch()` (bump) | First, if `P` has never observed a state, `P.observe_scanout(gpu_scene_scanout_state())`; that bumps the epoch. Then `capture_begin(L, healthy, &armed_epoch)`, with healthy = enabled && ledger armed && runtime owner_errors == 0. No bump. |
| seal (capture and ledger reach SEALED) | none (the build is the caller's job) | `P.boundary(L)`. Then the producer: the r6 build with `SealedScanout` from `P.owner_snapshot()` and the ledger r1 hazard adapter, then `P.bind`, then publish. |
| incomplete seal (overflow, malformed, frame gap, unknown footprint) | frame stays native through r3 coverage | **also** `P.invalidate_all(L, T2R_INVALIDATED)` ("invalid capture" invalidates; root msg_31e3312e) |
| cancel, owner reset, owner savestate | `scene_t2_invalidate` | `P.invalidate_all(L, ...)` |
| foreign reset / savestate / external write | `scene_t2_invalidate` (epoch) | unchanged. The owner retires records with `T2R_EPOCH` at the next boundary. |
| `!enabled`, `!ledger_enabled`, PGXP payload unavailable | frame native | `P.set_reference_mode(true)`, so nothing binds. Cleared only when all three recover. |

Two producer inputs need definitions:
- **The drawing-area constancy** that the r6 build requires (`SealedScanout.draw_area_constant` and the draw rect)
  comes from the ledger state stream. The proposal is a recorded first state plus a flag that clears on any
  draw-area change between arm and seal. This is one more field in ledger r2's header, which is additive.
- **The target rect** is the displayed VRAM area computed by the same gpu.c path that fills
  `SceneLedgerState.display_x/y/w/h`, moved to the target start. That keeps it consistent with the ledger's display
  areas, which the hazard check compares. 24-bit and interlaced widths and heights come from that same path in
  halfwords; nothing is recomputed from raw GP1 words.

## 3. Ledger r1 hazard adapter (bridge)

`DisplayHazardHook.fn(ctx, frame, generation, ordinals, count, rect)` runs in this order:
1. `scene_runtime_ledger_header` must be sealed and complete, and must name the same frame and generation;
2. then `scene_ledger_display_hazard(owner, generation, ordinals, count, rect, &v)`;
3. return `v.verdict`.

Any failure returns `LP_NATIVE_INCOMPLETE`. The existing r4 policy hook (glue r2 `ledger_policy`) is unchanged and
still required.

## 4. Consumer side (not designed here; needs root direction)

- A single pending slot for `T2FrameR6`, with r4 `T2SlotR4` semantics sized by `sizeof(T2FrameR6)`. It belongs in a
  T2 r7 header or the glue; it is not in r6.
- `CompletionR6` stamping from one `PresentState::read` snapshot taken at composition.
- The compositor and G4 material identity are unchanged. Both are unqualified.

## 5. Fixture plan (when authored, before any grant)

1. **Ledger r2:** pure-footprint equality with recorded entries for every class; unknown cases; no hdr side
   effects; draw-area constancy flag. Plus the r0 99 and r1 32 regressions.
2. **Glue r3 harness** (gpu.c faked as in glue fixture r0), covering:
   - the arm sequence (first observation, then `capture_begin`, no bump);
   - expected flip versus each unexpected GP1 change;
   - a fill, an upload or a draw-area overlap into the displayed or pending target retiring that record;
   - a polyline header retiring all records;
   - an incomplete seal invalidating;
   - reference mode;
   - a foreign reset leading to boundary retirement;
   - the hazard adapter refusing a stale header.
3. **Build closure r2:** closure r1 plus the new TUs, with the same native/strict split and the same hermetic and
   v69-closure checks.

## Open decisions for root

1. Whether ledger r2's pure footprint may duplicate the r0 footprint arithmetic, guarded by the equality fixture, or
   must refactor r0's `draw_footprint`. A refactor is not byte-additive.
2. The reference-mode triggers in the table above.
3. Whether an incomplete seal must invalidate the pending and displayed records of earlier frames. That is root's
   msg_31e3312e reading, and it is conservative: one bad interval drops presentation to native for one frame.
4. Where the `T2FrameR6` slot type lives.

Not claimed: any code, compile, run, live behaviour or Stage 1 progress.
