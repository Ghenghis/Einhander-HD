# Completed v58 runtime diagnostics

Actual [results and limitations](../../docs/STAGE1-FRAME-PHASE-RESULTS.md). Both runs still fail pacing/audio. This package adds completed r2/r3 data without modifying the frozen v58 source/check package.

`manifest.json` binds the two original local proof SHA256 values, selected public telemetry and analysis inputs. The observation files retain exact phase pages, HD upload events, passive presentation events, sampled audio/HD counters and cleanup/selftest receipts. Register records are reduced to the frame number. No RAM contents, game code, BIOS, disc images, cards or texture pixels are included. Large callback recordings stay local.

The analyzers follow the frozen `analysis-contract.json`: the interval ending at frame F includes the swap at F−1, both rows must be closed/ordinary with neighboring sequence/frame IDs, and each component must be ordered and sum to the whole interval. Open/ambiguous rows are excluded. CPU wall time locates waits; it does not establish GPU or external-process causality.

Replay from this directory with an existing Python 3 installation:

```text
python test_analyze_frame_phases.py
python analyze_frame_phases.py r3-observations.json --top 15 --out replay-analysis.json
python correlate_swap_uploads.py r3-observations.json --out replay-uploads.json
python correlate_audio_stalls.py r3-observations.json --out replay-audio.json
```

Use the corresponding r2 filename to replay r2. The upload report's `proof` field is the supplied input pathname and can differ across hosts; numeric results are independent of that pathname. The audio join uses one-second frame brackets, which can straddle an open cycle; see the result document before inferring that a starved interval had no corresponding pause. Scripts request below-normal priority on Windows when available. They do not launch a game, contact D:, install dependencies, use the GPU or alter settings.

`gpu0-memory.csv` and `host-cpu-observations.jsonl` cover r3 boot through cleanup. `r3-launch.json` and `prepare-r3.json` retain actual arguments, outcome, environment differences and cache/focus scope. Resource sampling itself cost CPU time and is not baseline overhead-free acceptance. Focus was mixed in r3 and absent in r2. Source-proof cleanup shows quit replies failed while actual process exit/port closure succeeded.

`verification.json` records the independent row/counter checks and exported-file hashes. Frozen source gates and earlier rejected attempts remain in [runtime-diagnostics-v58](../runtime-diagnostics-v58/README.md).
