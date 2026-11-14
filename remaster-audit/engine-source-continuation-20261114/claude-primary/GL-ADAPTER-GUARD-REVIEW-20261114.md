# Review: root's gl_adapter_identity_guard.py (claude-einhander). Tool clock 2026-11-14 19:47Z

Source read only; nothing was executed.

| File | sha256 |
|---|---|
| remaster-audit/gl_adapter_identity_guard.py (112 lines) | d9b5c22d0c538e3dfc0af39b63fba258ea0cf15976f562f0a868e6dd85ec0b8a |
| remaster-audit/test_gl_adapter_identity_guard.py (80 lines, 14 tests) | 1db8136e131cc277752c06b5d52413c108266654a8ae22d6661a3b78c3387f52 |

**Verdict:** consistent with the identity patch (canonical 42690420 / v68 2f603398), with no blocking defect. I found five
points to consider before wiring it in.

## Matches the patch's output

- **The line regex fully matches what the patch emits.** The patch replaces `"` and `\` with `?`, so a field can never
  break the `[^"\r\n]*` groups.
- **NULL or empty driver strings are rejected.** The patch emits `?` for them, and the guard refuses `field == '?'`.
  Good: an unknown adapter cannot qualify.
- **The `truncated=1` refusal matches the patch's flag.**
- **Model comparison works on real strings.** `_model()` compares the whole prefix before `/`, case-folded with
  whitespace collapsed:
  - `NVIDIA GeForce RTX 3090 Ti/PCIe/SSE2` equals `NVIDIA GeForce RTX 3090 Ti`;
  - `3090` (no Ti) and `... 3090 Ti Laptop GPU` are refused.
- **Both ready-line variants pass.** `READY` matches both the `(dual-raster, ...` and `(internal scale ...` lines
  (`gpu_gl_renderer.c:4935/4939`) by `startswith`.
- **The real fallback line is caught.** `FALLBACK` with `in` catches the actual line
  `psxrecomp: GL pipeline init failed — falling back to software renderer` (`:5003`, which contains an em dash).
- **Context or MakeCurrent failure is rejected.** On those paths (`:4952/4953`) no identity line and no ready line are
  emitted, so the log is refused.

## Points to consider

1. **Whole-log bound.** `MAX_STARTUP_BYTES` (1 MiB) is applied to the whole `stdout` string. If a caller passes the
   full `stdout.log` of a long or verbose run, the gate fails closed. That is safe, but it may refuse good runs.
   Suggestion: the caller passes a bounded prefix, from the start through the first ready or fallback line, and
   records its byte length.
2. **Order is not checked.** The identity line should come before the ready line, since the capture runs before
   `load_modern_gl`. Ordering is not enforced. It is cheap to require `index(identity) < index(ready)`.
3. **Present responses are not tied to the owned process.** PID and creation are checked for the process, but
   `present_before`/`present_after` come from the debug port. If another runtime instance owned that port, the ring
   would not belong to the owned PID. Suggestion, if the caller does not already enforce it: verify that the
   debug-port listener PID equals the owned PID at both queries, or bind it to a response field that carries the PID.
   I did not check whether `launch_ui_candidate` already does this.
4. **Decoding.** The fallback line contains UTF-8 (the em dash). The caller should decode `stdout.log` as UTF-8 with
   `errors='strict'`. A different codec or `errors='replace'` changes the text the guard sees; it still matches
   because of `in`, but it is cleaner to state the decoding.
5. **Test additions (optional):**
   - the dual-raster ready variant;
   - the exact real fallback text;
   - identity after ready (if point 2 is adopted);
   - a renderer with an extra suffix such as `Laptop GPU` (refused);
   - a case-only difference in the expected model (accepted).

## Not claimed

The guard was not executed, and its tests were not run (they are pure stdlib, per root they run in under 1 s). This
review does not qualify any adapter or game run.
