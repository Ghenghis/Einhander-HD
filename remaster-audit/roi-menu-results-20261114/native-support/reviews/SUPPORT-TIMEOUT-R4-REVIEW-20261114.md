# Timeout-profile r4: read-only review against the native EINRC01 contract (claude-einhander-support, 2026-11-14 ~16:30Z)

- Reviewer: claude-einhander-support. Native local_8e3e011b-bf64-4dca-a616-f3d138451df8, CLI b8533bfe-ccaa-4158-888f-2f8df67266b9.
- Requested by codex-einhander-crash-check in msg_79fad9980457c3f8.
- Scope: source reading only. No test, fixture, build, game or GPU was run. I am not yet registered in main's roster and have no CPU grant.
- Nothing below is reproduced yet. Every finding is from source, with file:line given.
- This note lives here because it was written before I was registered. My proposed output dir is
  `C:/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/`.

## Inputs (sha256)

**Proposal under review** (`remaster-audit/parallel-stages-20261114/s67/tooling/timeout-profile/`):
- `validate_timeout_leg.py`: b36c7ef6fe25923f757fe0969389ed95c084a9bdc44a4e52a23ee96d88a175c6
- `test_timeout_leg.py`: 06d33f2509ecfe89e71cb423dcfebb03bedcebbec80c8d632bd0438df2ec1cd2
- `test-results-r4.json`: dfef2bd7df797c9598ba03c9087fd4da60b1353a73fa5681013a46c797a63d08 (55/55, all_ok)
- `README.md`: ee778f8bae755f9afcfc118e62a300044b77ccc07e8225233a1d58a4e0b29c5e

**Canonical validator** (imported read-only):
- `remaster-audit/fullgame-prep/acquisition/validate_acquisition.py`: b5952fae2f7687ed057cd93bda8b894412093d4612a21f127b171f303d32d0d1

**Runtime** (`windows-x64/psxrecomp/runtime/src/`):
- `hd_research_event.h`: 22ed3be41c915d0649ea8636f45355344b586ba596989f2693f37454b3184b62
- `hd_research_renderer.h`: 3ffdf13f664a5a69cf84d355d114c7ddf8b263c4412d48299526231824a67b74
- `hd_research_capture.h`: cd935b85ca9b13c4c3d252835d5bc631c70bf61b1aab360a530ddc1f8ac3c3ad
- `hd_native_page.h`: 17d4eb1d5b0b13b272b5fd35132493fc2465c415dc6fae508f72f65a73702458
- `hd_texture_pack.cpp`: 392bb8f227ffa5ec87232e645520f282410e2e03e945da9975daf7b5da1e5387
- `gpu_gl_renderer.c`: 92d080578d2a3d734160deae1d67ae186b08f4e9f7ca2d5ecdd3d5344b37d03c

**Real event** (header and mark row only, read-only):
- `remaster-audit/dev-center-evidence/remaster-4k-preview-20261112-v12/draws-cold-startup/event-0001.bin`

## Verified by reading (consistent)

1. **Header layout matches `hdr_build_event`.**
   - magic "EINRC01\0", version @8, header size @12, frame u64 @16, ms u64 @24.
   - RAM offset and size @32/@36; VRAM offset and size @40/@44.
   - gpu_dirty @48, pending @52, pack_dirty @56, dual @60, renderer @64.
   - FNV RAM @68, FNV VRAM @72, index @76, label length @80, flag @84, label @96.
   - The real event-0001 header reads: frame 186, ms 167912097, gpu_dirty 1, pending 0, pack_dirty 1, dual 0, renderer 1,
     index 1, label "sony-visible", reserved 88..95 zero.
   - Its mark row (capture.jsonl:10) carries the same index, label, frame, host_mono_ms and flags.
2. **Timeout != clear is preserved.**
   - M requires `counts_as_stage_clear` and `route.acceptance_eligible` to be literal false, `clear` and `next_stage_entry`
     to be null, and no boss destruction.
   - The report hard-codes `counts_as_stage6_clear: false` and lists X/T/F/A/L as not evaluated.
   - The canonical validator is only imported (`spec_from_file_location`). Its file and gates are untouched by the proposal.
   - A control still expects the canonical validator to FAIL the timeout leg (X, T).
3. **The VRAM rect indexing and the FNV-1a implementation equal the runtime's.**

## Findings

### F1 (should fix): the snapshot TEX check hard-codes a 64x256 rect, but the runtime TEX key is not always that rect
- Validator lines 160-164: CRC32 of VRAM (704,256), 64 words x 256 rows.
- How the runtime defines TEX:
  - A native-page key is `hd_page_hash_width(..., depth, page_w)`, the CRC32 over page_w x 256 (hd_native_page.h:68-96).
    - page_w = 64<<depth, or the admission-narrowed width `hd_page_admission_width` (gpu_gl_renderer.c ~3800-3851).
  - An upload key is the CRC32 over the upload's OWN width x height at its own origin (hd_texture_pack.cpp:1340-1385).
- So the check equals the runtime key only for a depth-0 (4bpp) native page, or for a 64x256 upload exactly at 704,256.
- For an 8bpp or 16bpp page, or an upload-derived key, the outcome depends on the claimed TEX:
  - **Real key claimed:** legitimate evidence is rejected (fails closed).
  - **Rect CRC claimed:** RS passes with a TEX that is not a pack key.
- The RS snapshot path never requires the TEX to appear as a key anywhere in the run.
- The requests file says candidate 7AD161DF is `runtime-composed-needs-capture` because a 4/21 raw (16bpp) upload overlaps
  704,256. That is exactly the composed case.
- Proposed r5:
  - require `depth`/`width_words`, or derive them from a draw row on 704,256 (`native_words`, `depth`);
  - compute the CRC over width x 256;
  - require the TEX to exist as a draw-row or source-quad TEX half in the run, or label the output "rect CRC, not a pack key";
  - keep upload-derived keys unsupported until their rect is pinned.
- Test gap: every r4 snapshot fixture is 64-wide/4bpp.

### F2 (should fix): the mark row is matched by basename across ALL capture logs, but event numbering restarts in every research session
- Validator line 148 matches on `r['event_file'] == basename`.
- The runtime restarts numbering for each session:
  - hdrc_start memsets the state and needs a new directory with an exclusive capture.jsonl (hd_research_capture.h:160-174);
  - the event index is `events+1` (hd_research_renderer.h:68);
  - the blob and its mark row are written to that session's own directory (hd_research_capture.h:210-223,
    hd_research_renderer.h:70-78).
- One session is capped at 18000 frames / 300 s (hd_research_capture.h:45-49,177-186; default limits 3600 frames / 60 s, :43).
  So a continuous Stage 6 leg needs several sessions, and `event-0001.bin` recurs.
- Two sessions that each mark once give "found 2" and RS fails for a legitimate run.
- In principle the snapshot can also bind to another session's row.
- Proposed r5:
  - only consider mark rows from the capture log in the same directory as the event file;
  - keep "exactly one" within that log.
- Test gap: no two-session fixture.

### F3 (note): the native writer can omit the mark row while still writing the event
- hd_research_renderer.h:74-77: the row is written only if `records < max_records` and there is evidence room.
- The runtime comment says the binary stays complete and the command response carries the association.
- hdrc_json returns 0 at the record cap without failing the session (hd_research_capture.h:197).
- The validator then fails closed. That is safe, but a run that reaches the cap (default 5000 records) during the end
  sequence cannot bind a real snapshot.
- Options:
  - the runner checks record room before marking;
  - or the validator accepts a pinned command-response receipt as the alternative binding. Main to decide.

### F4 (cheap hardening)
- Also bind these fields:
  - header ms @24 == mark row `host_mono_ms`;
  - header gpu_dirty / pending / pack_dirty / dual == the row fields;
  - reserved 88..95 == 0.
- All of them hold on the real event-0001.

### F5 (policy, root decision; not a defect)
- Both real native events carry gpu_dirty 1 and dual 0.
- The mark row hard-codes `cpu_vram_may_be_stale: true` and `gpu_readback: false`.
- So every real snapshot gets the stale warning, and RS rests on the exact CPU-mirror CRC alone. That proves the mirror
  held the TEX at the safe point, not GPU VRAM coherence.

## Not done
- No reproduction. Under a CPU grant the proposed controls are:
  - a positive 8bpp page at 704,256 (128x256);
  - an upload-derived key;
  - two sessions, each with event-0001 plus a mark row;
  - a dropped mark row;
  - mark ms or flag mismatches.
- Each would be shown against r4 (before) and the r5 proposal (after).
- Scope with s67, which owns the tool, is not agreed yet. Nothing has been edited.
