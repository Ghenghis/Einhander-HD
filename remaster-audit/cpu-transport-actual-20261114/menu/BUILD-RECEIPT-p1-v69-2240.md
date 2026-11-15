# P1 private build receipt: v69 + F6 Player color (owner claude-einhander-ui)

**Status: incremental private CPU build PASS; root independent readback PASS (msg_4d59f4d7, 22:41:16Z).**
Not launched, installed, or run on the GPU. Live input acceptance is NOT established.

## Authority
- Grant: crash-check `msg_a878829bdeac1bc5`, consumed once. Main's relay `msg_e7641dfa` identifies it as the same single coordinator grant `msg_9d61317891ef8881`.
- Condition: main's source-clear for builder 5f713865, `msg_6f2ccac1b5eee40c` (22:37:36Z), confirmed by the relay. crash-check later cited `msg_4905a73b7d9eb851`, which did not reach this inbox.
- Single attempt. The alternative `P1-r3-build-1` command was never run.

## Executed identities
| item | sha256 |
|---|---|
| wrapper `receipts/P1-build-2240-runner/executed-watchdog.py` (fa5) | fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36 |
| builder `proposals/p1-player-color/build/build_p1_v69_r3.py` (read-only) | 5f713865c62ed3cb899df775206c588a121172f64ff28dd9444da7b20267bda7 |
| retained-input table `retained-inputs.v69.tsv` (read-only) | d9eb77e020cc36a45b5c533869a938b2a82839826fbe2634a408579b503de757 |
| P1 main (v69 8022b148 + P1 hunks) | d8abf287ee313e15b8dbe01837b1a217ef13f57d290e51d2d47947671c82e144 |
| P1 host_keymap.c | 8c81f0c65100ba1aa10ac8f84f25027ff4298a56a05013fb874e1fe09345ac96 |
| P1 host_keymap.h | ba28065153423cc39640832ef169143794a14f9babe69adc3616923da8dcbf0f |
| v69 manifest (argv and closure source) | e6ab30e9c9c03697b3c4dcd64a253d232cd0de1d1fbc9bc73d5c7880748de8b4 |

## Run (fa5 Job envelope)
- Precheck 22:38:54.91Z: CPU 52.6%, free 56.59 GiB.
- Job: CPU15 (mask 0x8000), BelowNormal, 1 GiB hard cap.
- Wrapper pid 24228 (ctime 1794695933.75), child pid 43492 (ctime 1794695934.91).
- 22:38:54.92Z to 22:39:03.71Z, 8.768 s.
- rc, child and wrapper all 0. Peak job memory 275,922,944 B.
- 7 descendants seen, 0 left. Job empty, tree absent.
- Children:
  - compile:main: pid 34128, 6.205 s, rc 0. One warning, the inherited pgxp.h -Wcomment.
  - compile:keymap: pid 36892, 0.291 s, rc 0.
  - link: pid 23212, 0.376 s, rc 0.

## Results
- Verdict PASS, 12/12 required steps.
- 155 inputs re-hashed, 0 mismatched.
- deps:main: 1142/1142, with every shared header hash-equal to v69's recorded closure. Only main.cpp and host_keymap.h were substituted. Audio header c84258e1 retained.
- deps:keymap: 118 C:-only entries, new header only.
- rsp `Einhander_Recompiled.p1.rsp` 604a7e9f…4393: exactly 2 objects replaced, 153 retained (including debug dc75afc2).

| output | sha256 |
|---|---|
| `builds/p1-v69-2240/obj/main.cpp.obj` | 24072e54c25c809a7076f284bc4abd51f2ddb88ceba30ed0f5664351b59e85a4 |
| `builds/p1-v69-2240/obj/host_keymap.c.obj` | 96a9fb4011d9a3d383c0a3599a6b4103a75aba99f4f4d4105ae6ea737ba1a4e9 |
| `builds/p1-v69-2240/Einhander_Recompiled.exe` (21,473,280 B) | 37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc |
| `builds/p1-v69-2240/manifest.json` | e34ca075064dfa594652a8361fa0842c75569b7c2375b853e4ff05eda39882fa |
| `receipts/P1-build-2240-envelope.json` | 890e84e08534a5ae6b1af384f9a4d597f46bf7d361916b66626ff7a61663b4f8 |

The original v69 exe f1ccb34d is unchanged (checked by the builder and again by root).

## Provenance limits (disclosed)
- The historical D: source and include closure of the replaced old keymap object e03f07c5 is UNKNOWN; D: was never read. The new keymap object is built from C: only.
- The psx_savestate_menu object's header path is inferred; there is no depfile on disk. See HOST-KEYMAP-CONSUMER-CENSUS.md.
- Only source review and the build are proven. The F6 menu's runtime behaviour, held-input bleed (the guard is bounded at about 90-700 ms) and visual appearance all need a separate granted live check (README "Suggested checks once granted").
- This is a host tint selector, not proof of realistic skins or materials, and not final menu acceptance.
