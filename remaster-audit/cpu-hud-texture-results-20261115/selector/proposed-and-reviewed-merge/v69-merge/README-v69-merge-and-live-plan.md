# P1 r2 on v69: exact merge, build recipe and live-check plan (SOURCE ONLY; nothing built or run)

## Merge (done, text-only)
| role | file (this folder) | sha256 |
|---|---|---|
| ours = current 37c main (v69 8022b148 + P1 r1) | ours.v69-plus-p1-d8abf287.cpp | d8abf287ee313e15… |
| base = P1 r1 proposed main | base.p1r1-994af594.cpp | 994af594cec87124… |
| theirs = P1 r2 enemy-row main | theirs.p1r2-91a2bcab.cpp | 91a2bcab3ec889b7… |
| **result** | **main.v69-plus-p1r2.cpp** | **fe85c7e4caf7be4f76ce3a8528ba08868e9468113940ea44e716aa68a2ae6dd3** |
| diff result vs ours | diff-v69-plus-p1-to-p1r2.patch | 3f5709e1… |

- Command: `git merge-file -p ours base theirs`. Result: rc 0, 0 conflict markers.
- The +/- lines of (result vs ours) are byte-identical to those of (theirs vs base): 143 lines each, checked with `cmp`.
- The v69 audio and other changes are untouched.
- UTF-8 BOM and CRLF are preserved, as in ours.
- The inputs are copies; their sources are unchanged and the 37c / v69 parents are preserved.

## Build recipe (NOT RUN; needs a fresh coordinator CPU grant)
- Builder: `proposals/p1-player-color/build/build_p1r2_v69_r4.py`, sha256 a8a8f8628de324d640dcdd9e9ae11a18a413f2b66ccc68e894ca32dcbbe50a2f.
  - It is a copy of r3 (5f713865, frozen) with exactly 2 changes: the docstring, and the `p1_main` pin, which now points to the file above (fe85c7e4).
  - The keymap .c/.h pins (8c81f0c6 / ba280651), the v69 manifest, the rsp, retained-inputs and the closure checks are all unchanged.
  - Path resolution was checked with pathlib (exists = True). AST parse OK. No review has been run yet on r4.
- Run the same way as the 2240 build, inside a fresh copy of the fa5 envelope:
  `run_rc2_envelope_r1.py --out <new receipts dir> --cpu <granted N> --timeout <granted> --max-job-mib <granted> --no-window --max-cpu 60 --min-free-gib 16 -- <python> build_p1r2_v69_r4.py --grant-id <id> --out <new absolute dir under builds/>`.
- Expected outputs: a new exe and a manifest in a NEW directory. Never install it, and never touch 37c37e8 / builds/p1-v69-2240.

## Live-check plan additions (all NOT RUN; coordinator-owned game run; no SendInput by me)
These extend LIVE-CHECK-PLAN-p1-v69-2240 (d0bb13e5). In each case, read `skin_material get` before and after.
- **E1 enemy row only:** F6, Down, Right x N, Enter.
  - enemy.profile changed; enemy.strength equals the value read at open.
  - The whole player block, the scopes and the accents are unchanged.
  - Toast: "Player <same> / Enemy <new>".
- **E2 both rows:** change the player and the enemy, then Enter. Both change in ONE configure (a single debug-log line or event, if one is logged). Both strengths are kept.
- **E3 nothing changed:** F6, then Enter. Toast "Colors unchanged"; no configure call; state is identical.
- **E4 rejection is atomic:** force a rejected configure (only if the coordinator has a supported way to do it; otherwise HOLD, NOT RUN).
  - Expected: player AND enemy state both unchanged, the menu stays open, and "not available" is shown.
- **E5 source keys:** the enemy tint applies only to the 6 Stage-1 strip keys (palette 527B28B9), and the player tint only to the 4 hull keys. This is visual or by draw-key evidence. If no draw-key probe exists: HOLD, NOT RUN.
- **E6 0% strength:** if a channel's strength is 0 at open, the toast shows " (0% str)" and the strength is NOT silently changed.
- Unsupported holds stay NOT RUN. A passing E1-E6 would still be only an incremental colour selector, not completed skins or menus.

## Follow-up noted (root)
A future UI should let the user set the intensity in game without the browser, as a user-visible control. It must never
silently overwrite the user's strength. Not part of r2.
