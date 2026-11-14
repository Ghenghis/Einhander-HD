# Additional exact-key source and draw admission

This isolated proposal closes the specific S7 inferred-planet admission gap
reported by `claude-einhander-s67`. The original `validate_predicted.py` and all
frozen artwork are preserved. The existing gate validates matching live source
bytes but does not require a draw. The regression test reproduces this with an
unlisted palette on a known texture: the old gate passes with an empty draw log.

`source_draw_admission.py` additionally requires a complete CRC-proven native
page and CLUT, exact counts and nonempty complete validity, source metadata key,
depth and CLUT slot, and an actual native-page draw for the exact key, page,
palette slot and depth inside an explicitly supplied stage frame window. It
checks the real recorder's `uv_bounds`, primitive coordinates, native page
dimensions and semi-transparency mode. `uv_vertices` is not required.
It records SHA256 of the exact bytes read, streams logs and caps row witnesses
at100 while retaining the total matching count. Malformed logs fail admission.

For `C4FDEDD2-EAD968A1`, the required page is832,0, CLUT0,504 and depth0.
The static words file is
`C:/github/Einhander/remaster-audit/fullgame-prep/static-extraction/stages-v4/stage7/textures/C4FDEDD2.words.bin`.
The integration owner must supply an independently qualified S7 run, exact
live source base, draw logs and entry/clear frame window. Example argument shape:

```text
python -B source_draw_admission.py --static-words <static words file> --source-base <live dump/C4FDEDD2-EAD968A1> --key C4FDEDD2-EAD968A1 --page 832 0 --clut 0 504 --depth 0 --frames <S7 entry frame> <S7 clear frame> --draws <same run/capture.jsonl> --out <new report.json>
```

Do not substitute Stage1 draw rows for a later-stage occurrence. This guard
does not establish the supplied run's identity or route; use acquisition
validation and independent run evidence for that. It does not establish every
palette phase, full UV coverage, artwork fidelity, audio or stage completion.
No real key has been admitted by this packet. GPU/live capture remains held.

Verification:13 focused tests pass, including a verbatim real recorder row
rekeyed to synthetic source bytes, the old-gate
counterexample, exact positive4bpp/8bpp sources, CLI failure/report output,
wrong key/page/slot/depth/frame/source-kind/ROI negatives, corrupted or incomplete
sources and malformed draw logs. The actual old tool emits ResourceWarning
for its unclosed file handles in the counterexample; it remains unmodified.

Run from this directory with `python -B test_source_draw_admission.py`.
The tests create tiny scoped temporary fixtures, no PNGs or real game jobs.
Main coordinator `codex-einhander` owns independent review and publication.

Only complete native4/8bpp pages are supported; ROI derivatives and16bpp are
excluded. A matched source query does not prove submission or screen visibility.
Any malformed line conservatively blocks this guard: an unparseable truncated
line has no trustworthy frame attribution. Preserve failed/truncated captures
and supply a new complete recording for admission.
