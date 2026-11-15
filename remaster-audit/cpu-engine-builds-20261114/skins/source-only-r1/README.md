# Per-target skin binding r1 `ein-skin-targets-v0r1-proposal` (source/JSON only)

This revision answers main's msg_bea1f8ba27a5df9b.

**r0 is unchanged.** It lives in `../skin-targets/`: header `666daa59…`, diff `172ba64a…`, catalog `7157be87…`, controls `c7b356e8…`.

**Status:** nothing was compiled, imported, decoded or run, and no canonical file was edited.

**What this is not:**
- authored PBR or realistic 4K skin art, which does not exist yet;
- a named-craft skin;
- live-accepted.

## Corrections vs r0
1. **Three selection modes:**
   - **UNSET**: the variable is absent or empty. The legacy path runs unchanged.
   - **INVALID**: the variable is set but rejected. **Fail closed**: every draw is stock and the legacy channels are suppressed. r0 fell back to the legacy tint here, which was wrong.
   - **VALID**: the selection was accepted.
   - `target=stock` is now a **valid** entry that disables that target. Duplicates are tracked in a separate `seen[]`, because a NULL profile means stock. A strength on `stock` is invalid.
   - `hd_skin_target_decide` is the single decision function (UNSET → legacy pointer, INVALID → NULL, VALID → target or NULL). The renderer and the controls both call it.
2. **Gate qualification is explicit.** The HD-image gate is **UNQUALIFIED**. It checks only that a replacement is sampled and that its size matches. It does **not** prove native alpha preservation or that the image is the frozen, admitted file. No trusted pack-entry admission identity bound at load exists. The header comment and the catalog `gates` section now say this.
3. **Vetted rectangle lists replace the min/max envelope.** Each hull key carries its exact Stage 2 boxes: 5, 9, 6 and 7 rectangles. Each list's length equals `uv_distinct`, and its counts sum to the key's draw count.
   - A draw must lie inside **one** rectangle.
   - Negative controls cover a **hole between rectangles** (v=44 of `724E77DA`, which is inside the envelope) and an envelope corner that no rectangle covers.
   - This is observation provenance, not exclusive actor ownership.
   - The target is relabelled `player.hull.shared_candidate`, a "generic shared player-hull candidate (not a named craft; not live-accepted)".
4. **The catalog check now covers every target, whatever its status:**
   - a valid status;
   - a unique, non-empty id;
   - `key_count` between 0 and 16;
   - keys present whenever `key_count` > 0 (r0 would have dereferenced NULL here);
   - `rect_count` between 1 and 32, with rectangles present and ordered;
   - no duplicate keys;
   - no rectangle of one target overlapping another target's rectangle on the same page and CLUT.
5. **The proof receipt now makes the same decision as the draw.** It calls the shared `s67_skin_decide` before deduplicating. The dedup key now includes reason, target, applied and generation, so an early stock or refusal receipt cannot hide a later one that applied. The receipt adds `target_mode`, `target_reason` and `material_generation`.
   - This is still first-of-kind evidence, capped at 4,096 entries. **It is not a complete per-draw record.**
6. **Still OPEN:** re-committing a target selection after a live material change (the generation bump at about `gpu_gl_renderer.c:3557`) is not implemented. A later live change therefore leaves target mode stock until restart.
   - No canonical renderer merge is proposed.

## Files (full sha256 in the s67 message and checkpoint)
- `hd_skin_targets.h`: the header. Existing headers, profiles, allowlists and GLSL are unchanged.
- `test_hd_skin_targets.c`: pure controls, not compiled or run. They cover:
  - all three modes, including caller fallback where INVALID suppresses legacy tint on hull and legacy-enemy keys;
  - 12 rejected selections;
  - `stock` as a valid entry;
  - each gate refusing on its own, including the hole and corner cases;
  - every vetted rectangle of every hull key;
  - reason names;
  - the batch helper;
  - synthetic catalogs for cross-target fallback, ambiguity, shared rectangles versus disjoint ones, and catalog-check codes 1–9;
  - the canonical profile count and allowlist being unchanged.
- `gpu_gl_renderer.c.diff` / `.proposed`: against canonical `92d08057`. It adds the include, the state, `s67_skin_decide` after `hd_skin_for_draw`, the env parse that logs INVALID as fail-closed, batch exclusion for keys in a VALID catalog, the draw site, and the proof receipt.
- `skin-target-catalog.json`: modes, gate qualification, the exact rectangles with counts, the HD file pins (each marked UNQUALIFIED) and the unresolved targets.

Generator: s67 scratchpad `make_skin_targets_r1.py`. It pins every input, requires each replacement to match exactly once, reads only PNG IHDR headers, and refuses to overwrite.
