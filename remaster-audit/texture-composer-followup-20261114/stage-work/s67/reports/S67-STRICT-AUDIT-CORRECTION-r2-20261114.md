# Correction r2 to the s67 strict whole-cell audit (2026-11-14, about 14:10Z)

This corrects `reports/S67-STRICT-WHOLE-CELL-AUDIT-20261114.md` (sha256 `6eb24918...4081`) and run `runs/20261114T135603Z/result.json` (sha256 `e1eeb72d...b1ee`). Both stay byte-for-byte unchanged. The defect was found by codex-einhander-crash-check (msg_5ff32dc973ac9df9) and confirmed by s67.

## Defect

- `s67_strict_audit.py` (sha `cb2ebd9e...`) called `cm_flags_ex(..., bound_frac=0.5, metric=0, ...)`. It then labelled bits 2|4|16 as `conn_viol_px` / "connectivity" and used them for `primary_pass`.
- Bound 0.5 is the strict s/2 R2 rule. That makes those fields an s/2 diagnostic, not root's connectivity-only policy (`bound_frac = 1e9`).
- The `cm_validate` strict counters (R1-R4, non-class, R5), the PNG hashes and the strict verdicts (230 of 254 selected files) were never affected.

## Policy verdict, settled from the frozen validator source without a rerun

Facts from `proto-v2b/class_mip.c`, `classify()`:

- **bit 16 (R1)** compares the centre pixel with the native class. It does not use the bound.
- **bit 4 (R4)** is a breadth-first search over same-class pixels, starting from non-deviant pixels. It does not use the bound.
- **bit 2** is set when `best > s * bound_frac`. `best` is the distance to the nearest of the 8 neighbouring native cells of the pixel's class, and it stays 1e30 when no neighbouring cell has that class.
  - So bit 2 at 1e9 flags only deviant pixels with no neighbouring native cell of their class.
  - Every such pixel is also flagged at 0.5.
  - Therefore bit 2 at 1e9 is a subset of bit 2 at 0.5.

So the connectivity-only set (1e9, bits 2|4|16) is a subset of the s/2 set (0.5, bits 2|4|16), and the R4 pixels are a subset of both. This gives:

- **The 230 strict-pass selected files also pass root's primary policy.** Their s/2 set is empty (cm_validate R1 = R2 = R4 = 0 at the same 0.5 bound), so their connectivity-only set is empty too.
- **The 24 failing selected files also fail root's primary policy.** Every one has cm_validate R4 > 0: the minimum is 28 px (`10932164-8E3D08E7` at 1024), and R4 pixels are inside the connectivity-only set.
- **Retained alternates:** D552405C-v1, 8 files, all fail (R4 > 0). The 20961255 v1 and 8F498326 v1 alternates (20 files) all pass, by the same argument.

**Still provisional:** the exact connectivity-only pixel and cell counts of the 24 failing files. The report's 714 / 354 / 251 / 7,778 / 4,950 / 29,338 figures are s/2 numbers. Under root policy each failing file has at least as many pixels as its R4 count, and at most as many as its s/2 count.

## Tool fix (no heavy run)

| tool | sha256 | what changed |
|---|---|---|
| `tools/s67_strict_audit.py` (r2) | `cb05452e48aee2ef4233668608394ffbf8b761d1c9d6deb3c336d63729827f9f` | Measures both bounds explicitly: `s2_viol_px` / `s2_bad_cells` / `s2_worst_cells_uv_px` at 0.5, and `conn_viol_px` / `conn_bad_cells` / `conn_worst_cells_uv_px` at 1e9. `primary_pass` now uses 1e9 only. The result carries `bounds` and `tool_revision`. |
| `tools/s6_fx_classrepair.py` | `5b021079363d38a5bfe0e0e054e60f5d3b14f63f722aca87888829d3757fb52b` | Reports `flags_before` and `flags_after` at both bounds, plus `became_visible_px`, `became_cutout_px` and `stp_toggled_px`. |

Synthetic check (scratch, using the run's DLL): an overhang of 12 px past s/2, plus one detached island.

| bound | bit 2 | bit 4 | bit 16 | union |
|---|---|---|---|---|
| 0.5 | 265 | 9 | 4 | 265 |
| 1e9 | 137 | 9 | 4 | 141 |

The 1e9 bit-2 pixels are the overhang pixels whose neighbouring cells hold no native cell of their class. This is as expected.

## Exact remeasure cost (for the next slot, if wanted)

| option | scope | cost |
|---|---|---|
| A | The 24 failing selected files only, with r2 | about 6-8 s; one CPU, below normal, < 250 MiB, no compile (reuses the run DLL, or about 4 s with a compile) |
| B | All 282 files, with r2 | about 50-55 s (42.8 s before, plus one more flags pass per file); budget 120 s |

The FX repair r1 (≤ 30 s) already reports both bounds before and after, so option A can be folded into it.
