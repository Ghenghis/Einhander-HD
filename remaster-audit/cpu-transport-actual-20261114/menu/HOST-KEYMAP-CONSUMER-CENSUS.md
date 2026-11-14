# host_keymap.h consumer census (read-only metadata, 2026-11-14 ~22:35Z)

Method: grep over canonical `windows-x64/psxrecomp/runtime/{src,include}` and `windows-x64/recomp-ui/src`, plus the depfiles and pins of the objects linked into v69. Nothing was compiled or run.

## Translation units that include host_keymap.h
| TU | object linked in v69 (rsp) | object sha256 | header actually used (depfile) | keymap symbols used | uses ACTION_COUNT? | P1 build action |
|---|---|---|---|---|---|---|
| main.cpp | s67/runs/v69-build-2206/obj/main.cpp.obj | 286af211… | `C:/github/Einhander-wt/upload-index-hitch/.../include/host_keymap.h` (c1924f11, old) | many actions, `host_keymap_match_event`, `_label` | no | **rebuilt** from d8abf287, private new header first |
| host_keymap.c | build-ss8c CMakeFiles/.../host_keymap.c.obj | e03f07c5… (also in v68 build.json) | D: tree header (old D: closure NOT available to me; I did not read D:) | defines `s_actions[HOST_KEYMAP_ACTION_COUNT]`, all actions | **yes** (array size, bounds) | **rebuilt** from 8c81f0c6 with the new header ba280651 |
| psx_rewind.c | dev-center-evidence/.../sampling-build-v47-attrib/psx_rewind.c.obj | 7f6093a3… (in v68 build.json) | `C:/github/Einhander/windows-x64/psxrecomp/runtime/include/host_keymap.h` (from its depfile psx_rewind.c.obj.d) | `host_keymap_label(HOST_KEYMAP_REWIND, …)` (src:965) | no | retained |
| psx_savestate_menu.c | build-ss8c CMakeFiles/.../psx_savestate_menu.c.obj | f6edbf5c… (in v68 build.json) | build-ss8c tree (no depfile on disk; ninja deps DB not read) | `host_keymap_label(HOST_KEYMAP_SAVE_STATE_MENU, …)` (src:234) | no | retained |

No other source in runtime/src, runtime/include or recomp-ui/src references `HostKeymapAction`, `HOST_KEYMAP_*` or `HOST_KEYMAP_ACTION_COUNT`.

## Why the retained objects stay valid
- Enum values: P1 appends `HOST_KEYMAP_PLAYER_COLOR_MENU` immediately before `HOST_KEYMAP_ACTION_COUNT`. Every existing enumerator keeps its value: FULLSCREEN 0 … REWIND 5, SAVE_STATE_MENU 6. COUNT changes from 7 to 8.
  - Retained objects pass only REWIND (5) and SAVE_STATE_MENU (6) to `host_keymap_label`, which is defined in the rebuilt host_keymap.c.
  - Neither retained object uses COUNT or `sizeof(s_actions)`.
- Function signatures: unchanged. P1 adds no function, changes no parameter, and changes no struct layout visible outside host_keymap.c.
- Config semantics: `[KeyMap]` is parsed by name in host_keymap.c `action_for_key`. Existing names (Fullscreen, Turbo, VolumeUp, VolumeDown, DisplayPerf, Rewind, SaveStateMenu) are unchanged. `PlayerColorMenu` is new and defaults to F6 when unbound. An existing config file has the same meaning as before.
- Strings: main.cpp:10577 `"Rewind"` and psx_rewind.c:682 are UI/OSD strings, not keymap config names.

## Disclosed limits
- The D: source and include closure of the old host_keymap.c.obj (e03f07c5) is unavailable to me: I may not read D:. The new object compiles from C: canonical-derived sources. P1 changes no header other than host_keymap.h.
- The psx_savestate_menu.c.obj header path is inferred from build-ss8c (no depfile found). Its single keymap use is a value-6 call, which the enum argument above covers.
