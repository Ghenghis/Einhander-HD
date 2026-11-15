# P1 r2: enemy channel in the F6 colour menu (private source proposal; NOT built, NOT run)

The smallest concrete UI patch from SKIN-SELECTOR-BINDING-MAP-20261115.md §5. It surfaces the already-valid ENEMY material
profiles in game through the existing live API.

## Base and output
- Base: P1 r1 proposed main `proposals/p1-player-color/proposed/main.cpp` sha256 994af594…98fa, copied verbatim to
  `base/main.p1r1-994af594.cpp`. That is the source-cleared r1, built privately as exe 37c137e8.
- Output: `main.cpp` (CRLF and BOM preserved; see the hash in the report), plus `diff-main-vs-p1r1.patch`.
- This changes only the P1 colour-menu block of main.cpp. It does not touch host_keymap (the F6 action already exists),
  host_osd, the renderer, hd_skin_material.h, S67's hd_skin_targets.h, or the launcher.
- A v69 build would need the same 3-way merge as before (onto 8022b148) and a new build revision. Neither is done here.

## Behaviour change
- Two rows: "Player color" and "Enemy color"; only the active row is shown on the OSD line (at most 62 chars).
- Keyboard: Up/Down switch rows (fresh presses only). Left/Right change the active row (hold-to-scroll only for an arrow
  pressed inside the menu, as in r1).
- Pad: D-pad up/down switch rows (edge-triggered; seeded at open). D-pad left/right or the stick step the row (held-at-open
  directions are still ignored until neutral).
- Enter / pad A applies BOTH rows in one atomic `gl_renderer_skin_material_configure(pid, ps, eid, es, NULL, NULL, -1)`.
  - Each strength is the value read at open.
  - An unchanged row is passed its current id.
  - Both unchanged closes as "Colors unchanged".
  - A rejection changes nothing and keeps the menu open with "not available".
- The result toast reads "Player <name> / Enemy <name>".
- Unchanged from r1: guest freeze, close-stops-dispatch, repeat rules, pad A/B seeding, the modal guards, SDL_QUIT, the
  60 s toast refresh, the availability gate and the input guard on exit.

## Not covered
- Persistence (the browser lab's tools/material-selection.json is still the only save).
- Per-target / role selection (S67 r2: 7 of 8 roles UNRESOLVED).
- Detail maps (next launch only).
- Any realistic-skin claim: these are colour-tint profiles on 4 player hull keys and 6 Stage-1 enemy strip keys.

## Checks done
- A diff read and an independent read-only reviewer pass (see the report).
- Not compiled; build and live behaviour UNKNOWN. A live check would extend the existing plan's L2 with an enemy-row case:
  skin_material get shows enemy.profile changed, enemy strength kept, player unchanged.

## Review
- Independent read-only reviewer pass: no defects at confidence 80 or above. It checked compile and call sites, channel/strength
  order, held-input seeding, no dispatch after close, and line lengths (menu at most 60, note 57, result at most 61 with
  the 0% hint).
- Low-severity note 1 is fixed: the result toast again explains a 0%-strength channel (" (0% str)").
- Notes 2 and 3 are left as-is and documented:
  - a fresh D-pad diagonal switches the row and then steps it in one poll (allowed by the rules);
  - the line-length comment counts only the longer "Player" prefix.
