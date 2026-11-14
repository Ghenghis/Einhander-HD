# P1 live-check packet for exe 37c137e8 (source-only plan; NOT executed)

Needs its own grant: GPU/OpenGL HD game launch, private, no install. The pinned subject is
`builds/p1-v69-2240/Einhander_Recompiled.exe` (37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc),
launched the same private way root runs v69 (same HD pack root, same skin key configuration, same save state).

## Facts that shape the method (from source, base f4ecc89c / v69 8022b148 + P1)
1. **F6 is a host SDL key.** The debug server injects guest pad input only, so it cannot press F6. Host keys need OS-level
   keyboard input to the focused game window (Windows SendInput or a scoped desktop tool), one key event at a time with
   real down/up pairs.
2. **The debug server does not answer while the menu is open.** `debug_server_poll()` runs in `sdl_vblank_present_body`,
   and the colour menu's pause loop does not call it. So `skin_material` reads and `present_shot` requests are made
   only before opening and after closing. Requests sent while open are answered after close, which also proves the guest
   was frozen.
3. **Readback:** `{"cmd":"skin_material","id":N}` on TCP port 4370 (DEFAULT_DEBUG_PORT) returns
   `player.profile`, `player.strength_percent`, the `enemy.*` fields, `generation` and `frame`.
4. **Visual evidence of the open menu** needs an OS window capture. present_shot can't be staged while open. A
   present_shot taken after close shows the applied tint.

## Controls (each one is a separate press; record the key timestamps)
| # | action | expected (all from skin_material before/after + window capture) |
|---|---|---|
| L0 | baseline get | `ready:true`, `opengl_ready:true`, `hd_ready:true`; record player profile P0, strength S0, enemy E0/ES0, generation G0 |
| L1 | F6 | window capture shows `Player color: < *<P0 label> >  Enter apply  Esc`; game frame frozen |
| L2 | Right, Right, Enter (quick, one batch) | after close: player = the profile at index(P0)+2, strength S0, enemy E0/ES0, generation G0+1 (**exactly one apply**); toast `Player color: <name>`; no 60 s menu toast afterwards |
| L3 | F6, Esc, Right | generation unchanged; no menu visible after Esc; Right has no effect |
| L4 | F6, Enter (current selection) | "Player color unchanged"; generation unchanged |
| L5 | hold F6 for at least 1.5 s | opens once and does not flicker or close (repeats ignored); release, then F6 closes |
| L6 | hold Right (steering) before and through F6 | the selection does not scroll; Esc closes; generation unchanged |
| L7 | hold a fire/move key for more than 700 ms across close | record any guest bleed after close (known bounded guard of about 90-700 ms); a finding, not a pass/fail claim |
| L8 | F6 then F7, then F8 | F7 and F8 do nothing while open; after Esc, F7 opens save states normally |
| L9 | F7 open, then F6 | F6 is refused while F7 is open |
| L10 | (optional, if granted) same exe on Vulkan/software | F6 shows the "Player color needs the OpenGL renderer" toast; nothing opens |
| L11 | close the window while the menu is open | clean exit via the SDL_QUIT path (crash trace origin `sdl_window_close`) |

Pass for P1 functional acceptance: L0-L6 and L8-L9 as expected, and L11 exits cleanly. L7 is reported, not gated.

## Evidence to record
- Every skin_material response verbatim, with timestamps.
- The OS window captures for L1 and L2, plus a present_shot after L2.
- Key event log (time, key, down/up).
- Process pid, ctime, exit and peak, inside the granted envelope.

## Not covered (by design)
- Persistence across launches.
- Enemy channel selection.
- Detail layers (`detail_changes: next_launch_only`).
- Whether the tints look good, which is a separate art/look review on the final composed game background.
- Any claim of realistic skins or materials.
