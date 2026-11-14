# Stage 1 frame phases — November 13, 2026

**The larger private artwork still fails pacing and audio. No new runtime or artwork was installed.** These two completed, 120-second, timer-assisted diagnostics replace the earlier prepared-only status. Both used the exact v58 executable `c2c386bd1f0ea59d84f8e95f1a1103cb777904f3eacaacad0c8e4013448145a6`, the frozen 1669-color-PNG candidate, scale 2, PBO uploads, a 5120 MiB GPU texture budget and rewind 50/15 with FMV interval 4. No video, continuous display readback or source capture ran during measurement.

The [replay package](../remaster-audit/runtime-results-v58/README.md) includes actual phase rows, upload events, sampled counters, analyzers and source-proof hashes. The original [v58 source/check package](../remaster-audit/runtime-diagnostics-v58/README.md) remains frozen. Neither diagnostic establishes foreground acceptance, physical scanout, full-stage completion or actual listening acceptance.

## Completed observations

- **r2, Claude:** frames 3044–10218; 7175/7175 valid neighboring phase pairs. Swap-begin period median 16.6665 ms, p99 22.0838 ms, maximum 204.7892 ms; 49 periods over 25 ms, 13 over 50 ms and 6 over 100 ms. Audio counters increased by **16,112 starved output sample frames**, with zero overflow drops. All 121 focus samples were unfocused.
- **r3, Codex after recovery copying stopped:** frames 3046–10243; 7198/7198 valid neighboring pairs. Median 16.6664 ms, p99 19.4746 ms, maximum 198.9995 ms; 38 periods over 25 ms, 12 over 50 ms and 5 over 100 ms. Audio increased by **3,214 starved sample frames**, with zero overflow drops. Focus was active in 21/121 samples, making this a mixed-focus diagnostic.
- Both proofs have `errors: []`, owned process exit 0 and the debug port confirmed closed. The quit command itself returned `emu busy or frozen`; the later process exit and closed port establish cleanup, not a successful quit-command reply. User cards were not mounted, and the command audit permits only the disclosed countdown-byte assistance; no state load or stage jump occurred.

r3 held Claude's GPU authoring, with ComfyUI 8188 stopped and a fresh manual process-inventory acknowledgment. The user's busy RTX 3060 / ComfyUI 8189 project was left running. LM Studio remained open with an idle model; it was not unloaded. GPU0 total memory over the retained monitor interval was **1446–5911 MiB of 24564 MiB**. This does not support a GPU0 near-capacity explanation for r3, but it is not per-process residency proof.

The added CPU sampler cost a median **17.23 ms** per one-second sample, maximum **96.773 ms**, across 197 observations including boot and cleanup. Its overhead is material and disclosed. Claude also reported one shell invocation at 06:38:58 UTC during measurement, running three short Node acknowledgment/message commands plus their shell host, despite the requested quiet window. r3 therefore does not have complete Claude CPU isolation. r2 had no matching resource log. Focus, host activity, input timing, private cache lineage and observer load differ; the lower r3 starvation total is **not a causal improvement estimate** from stopping ComfyUI. No runtime fix was applied between them.

## Where time was spent

In r2, all six periods exceeding 100 ms were dominated by the exact previous-frame `SDL_GL_SwapWindow` call. Seven of 22 uploads of 4096×4096 RGBA8 textures (64 MiB each) were followed within eight frames by a swap longer than 50 ms; six landed exactly four frames later. In r3, five of 22 such uploads were followed by a swap over 50 ms; four landed at +4. The largest r3 swap took 180.5305 ms, inside the 198.9995 ms period ending at frame 5352.

This locates a wait and a repeated upload correlation. CPU wall timestamps do not distinguish GPU work, driver allocation/copying, operating-system scheduling or compositor behavior. A new texture uses a fresh GL object; changing that object to immutable storage alone has no demonstrated fix mechanism. Total ledgered base upload bytes remained below the 5 GiB retention budget in both runs; budget eviction must not be asserted without evidence.

The r3 mini-boss interval ending at **frame 9275** took **191.7257 ms**, including **191.4223 ms outside vblank**. The preceding upload event at guest frame 9274 identifies `29358D65-BEEDE6FC`, 1024×32 RGBA8, just 128 KiB:

- Entire `hd_tex_object`: **175.224 ms**.
- Its exact `glTexImage2D`: **0.0213 ms**.
- The sampled HD draw timer increased about 193.3 ms in that second; decode-queue acquisition increased only about 0.031 ms and the readback timer did not increase.

The wrapper includes batch flushing, slot lookup/release/reservation, object creation/binding and texture parameters. The existing measurements do not identify which remaining operation blocked. `outside_vblank` includes renderer work and guest execution; it must not be described as pure guest CPU time.

## Audio interpretation and next gate

The r2 one-second join places 12,521 of 16,112 starved samples in one interval with only 35 guest frames. That is consistent with a transient host slowdown, but the recordings do not prove an external process caused it. In r3, starvation remained despite low total GPU0 memory. Callback counters and retained callback PCM precede the physical audio device; neither is listening acceptance.

Frame registers are sampled before audio counters, and a register sample can occur inside an open vblank cycle. A one-second frame-bracket join may assign the corresponding phase period to the next interval. In particular, r3's 878 starved samples at t≈104 s and the long period ending at 9275 should not be treated as evidence that audio starvation occurred independently of a long frame merely because their naive one-second bins differ.

The next small diagnostic splits the remaining `hd_tex_object` wrapper with opt-in CPU timestamps, preserving GL calls, render order, native qualification, alpha and cache policy. It is diagnostic work, not a fix. A behavior change needs a measured mechanism and another bounded reproduction with no worse total frame tails or audio. Normal foreground play, actual listening, full-stage progression and the [seven-stage E2E gates](RUNTIME-CONTINUATION-20261113.md) remain open.
