# frozen v1 and v2: REJECTED performance design (kept unchanged as evidence)

Root decided this in msg_28928d65 (2026-11-14T11:08Z), and I agree.

Both `renderer-v61-classmip-v1` and `renderer-v61-classmip-v2` build class levels **synchronously on the draw thread** in
`hd_class_mips_build_slot` (first non-resident draw of an admitted key). Measured host build cost for all levels of
one 2048² page, on one pinned below-normal logical CPU:

| Host run | Region-O green | Region-O pink | 95A3 397FBE8A | K page | RISE (1024×512) |
|---|---:|---:|---:|---:|---:|
| `runs/20261114T110114Z` (FAIL run, kept) | 67.2 ms | 66.0 ms | 65.1 ms | 72.5 ms | 12.3 ms |
| `runs/20261114T110331Z` (v1) | 95.5 ms | 343.7 ms | 98.4 ms | 102.2 ms | 15.6 ms |
| `runs/20261114T110919Z` (v2) | 59.4 ms | 62.8 ms | 56.4 ms | 58.8 ms | 10.7 ms |

- Any of these is a frame hitch of more than 50 ms on first use, exactly the kind of stutter the project is fixing.
- v1 also has the defects listed in `SUPERSEDED.md`.
- v2 fixed those defects, but keeps the synchronous builder.

Replacement (v3):
- levels 1..log2(s) are built **offline** into hash-bound sidecars;
- they are loaded and verified into a bounded preload cache at renderer init, before gameplay;
- the draw thread only validates level-0 identity and uploads the prepared levels with verification.

The GPU self-test result for the v1 shader path is root's `N/class-mip-gpu-r1`: **FAIL**.
- The m12 stroke can vanish; this is beyond native scale (12 > s = 8).
- The lod-0 fringe is unchanged by design; it is the level-0 R5 content defect.

My analysis of both is in msg_e0abd316.
