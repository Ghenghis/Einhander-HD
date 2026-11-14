# View provenance v3: frame-lag, flag split and ring re-hash measurements (claude-einhander, 2026-11-14)

**Status: private candidate source, host-tested.**
- Default OFF. Canonical sources, `../impl` (v1) and `../impl-v2` (v2) are unchanged; v3 is built from the hash-pinned v2
  outputs.
- Not built into a game, not run in-game. No GPU used (user hold).
- Purpose: the measurements Codex asked for (msg_41909e7c) before any frame/flag policy in the mesh-packet adapter is relaxed.

## What v3 adds (on top of v2)
| Piece | Change |
|---|---|
| Census, per triangles/quads | `lag[5]` = hits by (draw frame − view frame) **mod 2^32**: 0, 1, 2, ≥3, **future**. `lag_wrapped` = past lags that crossed the 32-bit frame-counter wrap. `hit_flag[9]` = hits carrying XY_SAT, XY_CLAMP, IR_SAT, DIV_OVF, SZ_SAT, WS_SQUASH, DOME, any MAC OVF44, any MAC WRAP32. `hit_xform_match` = committed hits whose **live** ring record re-hashes to the view's `xform_hash` |
| `gte.cpp` | `gte_rtp_ring_xform_hash(seq, &hash)`: the producer's FNV over RT, TR, H, OFX and OFY for a live record. `gte_rtp_ring_get_projection(seq, &h, &ofx, &ofy)`: the sibling accessor exposing H/OFX/OFY. Both return 0 for a record that was never written or has been overwritten |
| `pgxp.h` | Consumer declarations for the ring accessors: seq_live, get_xform, get_projection, xform_hash |
| `debug_server.c` `pgxp_view` | Per kind: `"lag":{"0","1","2","3plus","future","wrapped"}`, `"hit_flags":{...9}` and `"hit_xform_match"` |

Diffs vs canonical, in `diffs/`: gte.cpp 169 lines, pgxp.cpp 448 (unchanged from v2), pgxp.h 235, census 146, gpu.c 93,
gpu.h 15, debug_server.c 132. `gpu.c` and `gpu.h` are byte-identical to v2.

## Verification (`host-test-v3.json` 4b22794b…)
- **`view_v3_test`: 74/74 checks**, compiled with the full v3 gte, pgxp and census TUs plus the actual code cut from the
  generated gpu.c and debug_server.c. Debug tools on.
  - Lag cases: 0, 1, 2, 3, ≥3 and future. A projection at frame 0xFFFFFFFF drawn at 2^32 counts as lag 1, wrapped.
  - Xform: re-hash equals `xform_hash` for all 24 committed hits; a never-written seq returns 0; `get_projection` equals the
    view's H/OFX/OFY.
  - Flags:
    - a saturating RTPT gives IR_SAT, XY_SAT and XY_CLAMP (×3 each);
    - widescreen gives WS_SQUASH;
    - IR saturation **without** screen saturation (lm = 1, small negative MAC1) separates IR_SAT from XY_SAT.
- **TCP:** the runner parses the 5 replies and requires the v3 fields in both kinds (`tcp-replies.json` bb8fe296…).
- **Regression:** the v1 test passes 137/137 on the v3 sources; the canonical `pgxp_test` and `gte_register_access_test`
  pass on the v3 sources.
- **Syntax:** the real-argv `-fsyntax-only` check of gpu.c and debug_server.c gives 0 new diagnostics.
- **Mutants: 19/19 caught** (the 13 from v2 plus 6 for v3). The v3 ones:
  - lag bucket off by one;
  - wrap treated as future;
  - projection accessor returns OFX for OFY;
  - re-hash uses the wrong field;
  - flag table swaps XY_SAT and IR_SAT;
  - TCP drops the wrap field.

  An earlier lag mutant (`d > 2 ? 3 : d`) was equivalent to the original and was replaced. Three mutants that first
  "passed" only through a runner bug (an expected recent count of 5 after a reset) were re-killed by real cases.

## Use in the live leg (Codex, after the GPU hold)
1. `pgxp_view census:1 reset:1`, then ordinary play.
2. Read `triangles.lag` / `quads.lag` to see whether a same-frame rule is viable (most hits at lag 1 would mean it is
   not).
3. Read `hit_flags` to see how many hits a blanket diverged/WS rejection would drop.
4. `hit_xform_match` should equal `hit_committed`.
5. The adapter can now compare H/OFX/OFY through `gte_rtp_ring_get_projection`.
