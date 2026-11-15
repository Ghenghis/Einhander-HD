# HD proof observer: proposal r3 (claude-einhander). Written 2026-11-14, tool clock 19:57Z

Status: SOURCE ONLY. Not for integration (root msg_eeb80935). Nothing was compiled or run. r2 (doc c151d544…, patches
8aaa2383…/5761a9b3…) is preserved read-only.

r3 is narrow:
- the close-failure fix root found;
- an explicit I/O sub-block a CPU fixture can compile from the exact bytes;
- that fixture's source, not run.

## The r2 defect, confirmed

In r2, `hd_proof_close_log()` counted an `fclose` failure only as a write error. It did not set a stop reason and did
not stop observing. The cap path calls `hd_proof_close_log()` directly. So "marker written, then fclose fails" left
`observing=1, stop_reason=0`, which contradicts the r2 contract.

## r3 changes

- **`hd_proof_stop(reason)`:** the first reason wins, and observing is set to 0.
- **`hd_proof_close_log()`:**
  - takes the FILE and sets `s_hd_proof_file = NULL` **before** `fclose`, so the FILE is closed exactly once whatever
    `fclose` returns;
  - on failure it increments `receipt_close_errors` (new, counted separately) and calls
    `hd_proof_stop(HD_PROOF_CLOSE_FAILED = 4)`;
  - it calls no other closer, so there is no recursion.
- **`hd_proof_fail(reason)`:** a write error, then `hd_proof_stop(reason)`, then the close. When flush and close both
  fail, reason 3 is kept and both counters move.
- **Offset failure:** `hd_proof_stop(2)` before the close, so a failing close keeps reason 2 and only adds a close
  error. `fopen` failure is `hd_proof_stop(1)`.
- **Corrected disabled-state claim.** With the variable unset, the first call does one `getenv` and one write
  (`init_done = 1`). After that there are no per-draw proof-state writes and no proof I/O.
- **Schema `hd-proof-receipt-v5`;** stats add `receipt_close_errors`.
- **`/* HD-PROOF-IO BEGIN (r3) */ … /* HD-PROOF-IO END (r3) */`** encloses the defines, the stop-reason enum, the 13
  I/O statics, and `stop`, `close_log`, `fail`, `write_raw`, `put` and `observer_on`.
  - It needs only `<stdio.h>`, `<stdint.h>`, `getenv` and `s_frame_count`.
  - `HdProofGate` and the gate statics moved just below it, unchanged.

## Pins (sha256)

| Item | sha256 |
|---|---|
| canonical base | 92d080578d2a3d734160deae1d67ae186b08f4e9f7ca2d5ecdd3d5344b37d03c |
| v68 base (frozen, untouched) | 9a878ca4cf74d7c45a43b0308d5820243728a3df3a51a2a01e34d05cdbcfc487 |
| hd-proof-observer.canonical-92d08057.r3.patch | 44f7444e6bf6616fd8e66815d0cb8d78599d1946f6312752976fe6a4a9bfc985 |
| hd-proof-observer.v68-9a878ca4.r3.patch (NEW v69 copy only) | 683e046c327c4e36cafd7f80df4310d5f11cd6087ea257b501a8552232b15ffc |
| canonical + r3 (scratch) | e5fd7924b6388b896388d80558bb8b067f8c9645aabc1b7a5fdfe35f272b6828 |
| v68 + r3 (scratch) | f5a22c055ffa5367eeb2beb85af7da6ef5604f2e0dc25d1dc4cbf996c7cd3dd8 |
| HD-PROOF-IO block (LF lines BEGIN…END + final LF) | e31d6795459a62c73db8334ca77d16e82a357960d3c744d4c71f5e2c4233b02c |
| fixture/test_hd_proof_io.r0.c | listed in the delivery message |
| fixture/build_hd_proof_io_fixture.r0.py | listed in the delivery message |

- Hunk bodies are identical between the two patches (8 hunks on v68, offsets only).
- The identity patch 42690420 dry-run applies on top.
- All files are LF; I counted 0 CR.

## Extracted-code fixture (source only; run only under a CPU-naming grant)

**`build_hd_proof_io_fixture.r0.py`:**
1. Verifies the base and r3 patch pins.
2. Runs `git apply` of the pinned patch onto a copy of the base in its own out dir. The result must hash to
   e5fd7924….
3. Extracts the IO block. Its sha must equal e31d6795…, and its `static` declarations must be **exactly** the 13 names
   the test's `reset()` restores. A future revision that adds state fails closed here.
4. Compiles with `clang++ -x c -std=c11 -Wall -Wextra -Werror` (45 s cap).
5. Runs (10 s cap). The run must report 36 checks passed, `gl_used:false` and `real_file_io:false`.

**`test_hd_proof_io.r0.c`:** it redirects `getenv`, `fopen`, `fseek`, `ftell`, `fwrite`, `fflush` and `fclose` in
the extracted block to fault-injecting shims. There is no real file. Its oracles:
- unset: 1 `getenv`, no I/O, only the init flag set;
- `fopen` failure → reason 1;
- `fseek` failure and `ftell` −1 → reason 2, closed once, nothing written;
- offset failure + `fclose` failure → reason 2 kept, close_errors 1;
- healthy open with a pre-existing size → `start_offset` recorded, exactly one v5 header, idempotent init;
- line cap: MAX-3 and MAX-2 accept; MAX-1 writes the marker, then lines == MAX, closed, observing continues, no I/O
  after;
- byte cap: MAX-M-n-1 and MAX-M-n accept; MAX-M-n+1 writes the marker and bytes ≤ MAX;
- both caps at once → exactly one marker, both caps reached exactly;
- **cap marker + `fclose` failure → reason 4, observing 0, closed once;**
- partial `fwrite` (3 of 8 bytes) → bytes +3, the line not counted, reason 3, closed once, no I/O after;
- `fflush` failure → reason 3;
- `fflush` + `fclose` failure → reason 3 kept, write_errors 1, close_errors 1, closed once;
- dropped lines (n ≥ 2048, 0, −1) → counted, no I/O, observing continues;
- marker `fwrite` failure → reason 3, capped, closed once;
- shim accounting is self-consistent.

**Not covered:** the receipt, dedup, gate, epoch and stats paths. They need the type and stub harness from the
r1/r2 plan, cases 1-10. That remains a later fixture.

## Not claimed

Not compiled or run. Not integrated. No heavy tests during the Tapper hold.
