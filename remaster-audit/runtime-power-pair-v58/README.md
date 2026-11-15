# Scoped private NVIDIA power comparison — November 14, 2026

The second 120-second run had zero new audio starvation and a smaller whole-run maximum, but a 50.8336 ms nominal mini-boss period remains. One ordered pair does not establish a driver-setting fix. See the [interpretation and limitations](../../docs/STAGE1-POWER-PROFILE-RESULTS.md).

Run `python remaster-audit/runtime-power-pair-v58/verify_results.py` from the repository. This replays all three existing analyzers for each leg and independently checks raw phase validity, period tails, nominal boss window, audio deltas, focus, HD upload totals, 1 Hz GPU samples and owned-process cleanup. It launches no game and uses no GPU workload. The [manifest](manifest.json) binds exact file bytes; [verification](verification.json) records the executed replay result.

The two observation extracts retain named counters and complete selected phase/upload pages, with original-proof hashes. They omit RAM, BIOS/disc media, executables, cards, audio and screenshots. `initial-cache-manifest.json` lists paths and hashes, not cached binaries. Both launch receipts bind the identical initial cache list and executable hash. The 1 Hz GPU logs cover boot and cleanup as well as measurement; they are not per-process or sub-frame clock proof.

The restoration receipt records the observed NVIDIA App state after both runs. It is not a driver API readback or proof that the profile matched each differently located executable. The private program entry remains, inheriting Global – Normal. Global and other-program settings were untouched.

The initial rejected attempt is retained as an error/cleanup extract. Its executable-location guard was preserved; it supplied no accepted gameplay timing. The original r2/r3 numerical evidence and manifests remain unchanged. Eight files from that earlier publication are restored to their manifest-bound CRLF bytes in this update; the previous commit had stored normalized LF bytes. See the [byte audit](../../docs/media/gallery/publication-byte-integrity-results.json).
