# Private power-profile comparison — November 14, 2026

**Gameplay improved in the second run, but stutter/audio are not accepted as fixed.** The user reported noticeably smoother gameplay and did not notice stuttering in that run. Instrumentation recorded zero new audio starvation, while one 50.8336 ms mini-boss interval remained. This feedback is useful visual evidence, distinct from normal full-stage play and listening acceptance.

The user authorized two short tests and restoration of NVIDIA's power preference for the separate `Einhander_HD_PowerProbe.exe`. Both completed 120-second timer-assisted runs used the same v58 executable bytes, SHA256 `c2c386bd1f0ea59d84f8e95f1a1103cb777904f3eacaacad0c8e4013448145a6`, identical initial private cache manifests, the frozen 1669-PNG pack, scale 2 and existing upload settings. The executable was copied inside each run's own private directory; its basename was identical. The NVIDIA App program entry was added using a separate common full path. Profile matching to the run copies was not verified through NVAPI, so an effective per-process driver policy must not be assumed from the UI alone.

## Actual results

- **Normal, r4b, first:** frames 3061–10247, 7187/7187 valid phase pairs; median 16.6666 ms, p99 18.4699 ms, maximum **230.0131 ms**. Periods over 25/50/100 ms: **22/7/3**. Audio: **+11,808 starved output sample frames**, zero overflow. The nominal 9250–9599 boss bracket contains 350 pairs and has maximum **23.7319 ms**.
- **Prefer maximum performance selected, r5b, second:** frames 3046–10247, 7202/7202 valid pairs; median 16.6665 ms, p99 17.7563 ms, maximum **50.8336 ms**. Periods over 25/50/100 ms: **10/1/0**. Audio: **+0 starved sample frames**, zero overflow. The same nominal 350-pair boss bracket has maximum **50.8336 ms**, worse than r4b's nominal bracket despite the better whole-run result.
- Both proofs have `errors: []`, owned process exit 0 and the debug port closed. Both were unfocused in all **121/121** samples. These are background-focus diagnostic runs, not foreground acceptance. No user card was mounted, and countdown-byte timer assistance was disclosed.
- Normal recorded 785 HD uploads / 4,666,556,416 bytes; the second run recorded 803 / 4,891,213,824 bytes. The largest measured HD-object wrapper was 24.1390 versus 47.3548 ms. Different input timing, observed brackets and uploads prevent a strict identical-workload claim.

Claude independently replayed the pair: Normal had five exact swaps longer than 50 ms; the second run had zero. Of 22 uploads of 4096-square textures per leg, four Normal uploads were followed within eight frames by a swap longer than 50 ms, versus zero in the second leg. This is an upload/wait correlation, not proof of the cause.

## Clock, resource and causal limits

The retained 1 Hz GPU0 monitor spans boot and cleanup. Normal: 191 samples, P0/P3/P5/P8 counts 30/90/70/1, graphics clocks 345/855/2040 MHz (minimum/median/maximum). Second run: 192 samples, counts 21/101/69/1, graphics 330/855/2040 MHz. Both reached 10501 MHz memory clocks; both medians were 5001 MHz. These observations do **not** show clocks pinned high by the preference. Sub-second transitions, uncertain profile matching, run variance and leg order remain possible explanations.

The costly process CPU sampler used in r3 was removed. Only read-only 1 Hz NVML sampling accompanied these runs; no recorder, heavy profiler or GPU art job ran. Claude supplied a fresh manual process-inventory acknowledgment and committed to no shell calls until both legs ended. The user's busy RTX 3060 / ComfyUI 8189 work and active WSL were left running; this was not a completely idle host. No reverse-order pair has run, and no further driver changes are part of these results.

Callback counters precede the physical device; zero new starvation does not establish subjective listening quality. Swap-begin periods are CPU wall intervals, not physical scanout. The earlier [r2/r3 diagnostics](STAGE1-FRAME-PHASE-RESULTS.md) and [seven-stage gates](RUNTIME-CONTINUATION-20261113.md) remain relevant.

## Restoration and retained failures

After both accepted runs, NVIDIA App's selected program heading was verified as `Einhander_HD_PowerProbe.exe`, and Power Management Mode was restored through **Use global – Normal (Default)**. The private program list entry remains with inherited preferences. Global settings, other programs and the user's RTX 3060 project were unchanged. CPU/GPU quiet reservations were released after both owned processes exited.

The first r4 attempt was rejected before gameplay because the executable lived outside that run's private directory. Its identity guard was retained; corrected r4b/r5b used local copies. An attempted launch before preparation completed also stopped at a missing-acknowledgment assertion before launching gameplay. Neither supplies accepted timing.

The [portable telemetry and replay checks](../remaster-audit/runtime-power-pair-v58/README.md) include source-proof hashes, raw selected counters/pages, initial-cache identity, GPU logs, launch receipts, the first rejection and the restoration receipt. No experimental runtime/art was installed. v59's narrower HD-wrapper timestamps have compiled locally but have not been run or installed. The next work prioritizes the user's washed-out green/pink sign report while preserving the remaining pacing/audio defects.

Publication verification also found eight files in the prior r2/r3 results commit whose LF-normalized Git bytes did not match their CRLF-bound manifest hashes. This update restores those original raw bytes without changing numerical content or either earlier manifest. The [byte-integrity receipt](media/gallery/publication-byte-integrity-results.json) records the old and corrected hashes; staged Git blobs are checked directly, in addition to local replay and documentation checks.
