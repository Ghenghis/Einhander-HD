# Correction r2 to S67-AUDIO-PATH-AUDIT-20261114.md (sha 7c54f66a…)

Prompted by main's msg_3bcf33f0 and msg_6fe6c124. The original report is preserved unchanged; this file corrects it.

1. **Wrong header path.** The original says `R/include/recomp_audio_drc.h`. The canonical header is **`C:/github/Einhander/windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h`** (sha256 `70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29`). The line numbers cited for it are correct for this file. The proposed edit sites in the original (`R/include/...`) also mean `runtime/src/`.
2. **Full sha256 of the canonical sources I verified directly:**
   - `C:/github/Einhander/windows-x64/psxrecomp/runtime/src/main.cpp`: `f4ecc89c69b394ca3c334fdfd54958bf496f5573c03a54c5c79cb96892c67b9c`
   - `C:/github/Einhander/windows-x64/psxrecomp/runtime/src/debug_server.c`: `86ce765bab0ef633f8feaefbf5e9de8eb5068102a66dbfa43b01d7aa777fc883`
   - `C:/github/Einhander/windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h`: `70cb5acd…7a29` (above)

   The other files (`spu.c`, `cdrom.c`, `interrupts.c` and so on) were cited from the subagent's map with 16-hex prefixes. Their claims were not re-verified line by line, and they should be read as subagent-sourced.
3. **Device rate.** "settings.toml requests 48000, so the bridge resamples 44100 → 48000" holds only for the **installed** `build-release/settings.toml` (`68f831cd…`). The rate of a private v68 run comes from the settings in force at that launch, and is **not established** by these files.
4. **Scope.** The audit is valid for its own pins (canonical sources). For v68 specifically: v68's header is identical to canonical; v68's main.cpp comes from the v58 source `5c94d2dd17f52338515ac52df4f8fde04b4eb269ee49ba6bc42b6924bc6523c0`, whose audio lines are identical to canonical; and v68's debug_server.c comes from the v67 source `10e31f8dc50cdf451776f18e4b468f95bb2c97d33f50816d9b9d193557af2eba`, whose `audio_stats` handler is identical. So the findings carry over, except for the device rate (point 3).
5. **New finding.** `rab_get_stats` copies the stats struct without the SDL device lock while `rab_pull` writes it on the audio thread, so torn reads are possible. This affects both `psx_audio_out_stats` callers and the pump's underrun→event bridge.
