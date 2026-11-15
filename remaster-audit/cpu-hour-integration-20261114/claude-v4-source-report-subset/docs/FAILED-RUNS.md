# renderer-v61-classmip: failed runs, kept as produced (claude-einhander)

| Run | Outcome | Cause | Kept where | Fix |
|---|---|---|---|---|
| run_host.py run 1 (no folder) | crash before any step | `below_normal()` used unannotated ctypes: `GetCurrentProcess()`'s pseudo-handle was truncated, `GetProcessAffinityMask` returned an empty mask, and the code hit a negative shift. No run folder was created and nothing ran. | `host-console-1.log` | psutil priority + one-CPU affinity, asserted |
| `runs/20261114T110114Z` | **FAIL**: 16/17 mutants caught | Mutant "R5 fill neighbour order" survived. It is an **equivalent mutant**: multi-source BFS fill is invariant to the per-pixel neighbour order. `evidence/bfs_equiv.py`: 0 of 3,000 random images differ under any of the 24 neighbour orders, while 2,519 differ under reversed seed order. Every other step passed. | `runs/20261114T110114Z/` (result 0d1b0593…), `host-console-2.log` | The mutant was replaced by "R5 fill seeds in reverse scan order" (a real behaviour change: ties resolve to a different source) |

| `frozen/renderer-v61-classmip-v1` (from passing run `runs/20261114T110331Z`) | **SUPERSEDED** after root review msg_6dc79298 | Two defects my tests missed: (1) `hdcm_build_level` shifted by L before bounding it (L >= 32 is undefined behaviour); (2) uploads were counted without verification, so a partial chain could be admitted. Separately, the runner exited 0 on a FAIL verdict (msg_2918e6db). | kept unchanged; `frozen/SUPERSEDED.md` | v2: bound first; fail-closed `hdcm_build_upload_chain` with reason GL and restore; exit code follows the verdict; 3 new mutants |

| `frozen/renderer-v61-classmip-v2` (from passing run `runs/20261114T110919Z`) | **REJECTED performance design** | Builds levels synchronously on the draw thread (56–63 ms per 2048² page here; 95/344 ms in run 3). Root msg_28928d65. | kept unchanged; `frozen/REJECTED-PERFORMANCE.md` | v3: prepared levels in HDCMSC02 sidecars, preload at init, no builder in the runtime |
| `runs/20261114T112632Z` (v3 run 5) | **FAIL**: 26/27 mutants (exit 1) | The mutant "parse accepts non-class native values" deleted the `if` that was the body of a `for` loop, so the next declaration became the loop body and the mutant did not compile. A broken mutant, not a code defect; every other check passed. | `runs/20261114T112632Z/`, `host-console-5.log` | The mutant now replaces the check with an empty statement |

Before the first run, the generated sources were edited twice; nothing had run at either point:
- the centre-pixel authority (`DESIGN.md`) was replaced by native sidecars;
- a sampling guard was dropped because it contradicted the "rejection keeps the original path" requirement.
