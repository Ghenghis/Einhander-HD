# Stage 6 timeout-leg acquisition profile (PROPOSAL)

Task `EIN-S6-TIMEOUT-PROFILE-20261114`, owner `claude-einhander-s67`.

This is a proposal only. codex-einhander owns acquisition-code integration and promotion. Nothing here captures anything, touches RAM or state, or creates end-state evidence.

## Why

Readiness item M6-11 (an AQ-13 run) lets the Stage 6 mission timer expire, which ends the game. Such a run has no boss destruction, no clear, no tally and no next stage. So the canonical `fullgame-prep/acquisition/validate_acquisition.py` fails it on gates X, T, F, A and L by design (M6-13). This profile validates what the timeout leg must prove instead.

**A timeout leg can never count as a Stage 6 clear.**

## Files

| file | purpose |
|---|---|
| `validate_timeout_leg.py` | The validator. It imports the canonical validator read-only and reuses its R/B/C/E/K/H semantics. The canonical tool, schema and gates are not modified. |
| `test_timeout_leg.py` | Synthetic self-test with tiny header-only PNG fixtures, written to a scratch work dir. |

## Gates

| gate | requires |
|---|---|
| M | Schema `ein-stage6-timeout-leg-v1`; `leg == "timeout"`. `counts_as_stage_clear` and `route.acceptance_eligible` both literally false. `clear`, `next_stage_entry` and any boss destruction all null. |
| R | The canonical ordinary-play route, plus Stage 5 lineage, plus `route.timer_untouched == true`. |
| B / C / E / H | Canonical semantics: provenance, private cards, Stage 6 identity from visible evidence plus the Stage 5 tally, file hashes. |
| K | A complete native source for every key drawn from entry to the last end-state frame (canonical check). |
| TX | Timer-expiry frame; the countdown visibly at zero; a 2880x2160 capture. |
| MV | Movie placement after expiry, with an identity basis (for example the CD read log of MOV03.STR), or an explicit none-observed statement. |
| NA | The narration passage index (argument to `0x80048138`) with its basis and captures, or an explicit not-observed statement with the searched frame range. |
| RS | The TEX resident at VRAM 704,256, with its frame and basis, inside the expiry-to-last-end-state window. Basis `draw_rows`: that TEX drawn within ±60 frames, with no other TEX in that window. Basis `marked_vram_snapshot`: a pinned native EINRC01 event whose header, identity, own-session mark row (frame, ms, flags), declared key rect CRC, drawn key and payload checksums all bind (r5). Basis `upload_event`: unsupported. |
| GO | The Game Over still: frame range, a 2880x2160 capture, and either the drawn TEX or a statement that no textured still was drawn. |
| NS | The screen that follows Game Over: frame range and captures. |
| O | Order: entry < expiry ≤ movie ≤ narration ≤ Game Over ≤ next screen. All of it inside one capture-log span. No stage tally after expiry, and no `clear:6` / `tally:stage6` marks. |

The report always contains `counts_as_stage6_clear: false`. It lists canonical X/T/F/A/L as **not evaluated**, never as passed. For the candidate TEX `7AD161DF` (medium confidence) and `DD1C423A` / `0823895F` (low; read only from `stages-v3/ending`) it states whether each was drawn. These are answers, not gates.

## Revisions

- **r1:** preserved unchanged in `r1/`. Files: `validate_timeout_leg.py` `7426a939...`, `test_timeout_leg.py` `1f03179a...`, and `r1/test-results-r1.json` (20/20).
- **r5** (current, NOT yet run). Fixes the claude-einhander-support review (msg_317d33e3; source re-review msg_be013f86 found the fixes match the runtime):
  - F1: `evidence.rect` is required; no rect is assumed. Either `native_page` at 704,256 with depth 0/1/2 and `width_words` = 64<<depth (or an explicitly `narrowed` multiple of 64), 256 rows, wrapping like `hd_page_hash_width`; or `upload` with its own x, y, width_words and height, overlapping the 704,256 page. The CRC is taken over exactly that rect. The claimed TEX must be drawn in the run (`source_draw_query_matched` or `replacement_gl_draw_submitted`) with the same source kind and size, and for a native page the same page and depth.
  - F2: the mark row is taken only from the capture log in the event file's own session directory (research sessions restart event numbering).
  - F4: header ms@24 == row `host_mono_ms`; header flags @48/52/56/60 == row `gpu_dirty`/`pending_cpu_upload_rects`/`pack_dirty`/`cpu_authority_dual`; reserved bytes 88..95 == 0.
  - F3 is unchanged: no mark row means reject (fail closed). Main may choose a runner preflight.
  - Item a (support msg_d0c1c456, verified in `hd_texture_pack.cpp` 883-886 and 1548-1561): an upload or exact-region draw row must recover the declared origin, `(page_x + u_first // (4>>depth) - source_word_x) mod 1024` and `(page_y + v_first - source_y) mod 512`. `source_word_xy` is the first texel's offset inside the upload, not the origin.
  - New controls: 17, listed in `test_timeout_leg.py` under r5. Fixture events now sit next to their own session log.
- **r4:** preserved unchanged in `r4/` (`b36c7ef6`, tests `06d33f25`, results `dfef2bd7` 55/55). Fixes crash-check msg_7cd1e1599f46082f: `marked_vram_snapshot` is bound to the native EINRC01 format, from `windows-x64/psxrecomp/runtime/src/hd_research_event.h` `hdr_build_event`. Checks, in order:
  1. Pin: sha256 equals both the evidence hash and `files_sha256`; size is `HDR_EVENT_BYTES`.
  2. Header: magic `EINRC01\0`, version 1, header size 160, RAM/VRAM offsets and sizes, format flag, and a valid label.
  3. Identity: the header event index (@76) matches the `event-NNNN.bin` file name, and the header frame (u64 @16) equals the claimed residency frame.
  4. Exactly one `mark` row in the capture logs with the same `event_file`, `event_index`, `label`, `frame` and `bytes`.
  5. The VRAM rect (704,256,64,256) CRC32 equals the claimed TEX.
  6. The FNV-1a checksums of the RAM payload (@68) and VRAM payload (@72) match.
  - The stale-mirror flags (`gpu_dirty` / `pending`) produce a warning, not a pass of coherence. Acceptance rests only on the exact CRC match.
  - Results: `test-results-r4.json`, 55/55. The r3 headerless fixture is now an expected rejection.
  - Real-format cross-check (read-only): `dev-center-evidence/remaster-4k-preview-20261112-v12/draws-cold-startup/event-0001.bin` validates with zero problems. Header frame 186, index 1 and label `sony-visible` match its mark row on line 10, and both FNV payload checksums match. A wrong-frame claim (187) on the same file is rejected.
  - r3 is preserved in `r3/` (validator `b247a432...`, test `8ad09020...`, results `81f9adc6...` 46/46).
- **r3.** Fixes crash-check msg_11548f2667c6d055: residency bases are bound to evidence. `upload_event` is reported UNSUPPORTED until the integration owner supplies its schema. `marked_vram_snapshot` needs a pinned receipt:
  - `evidence {path, sha256, mark_frame}`, with the path inside the run;
  - the sha256 equals both the actual file hash and `files_sha256`;
  - EINRC01 size 3,145,888 B;
  - CRC32 of the VRAM (704,256,64,256) rect equals the claimed TEX;
  - a research mark exists at the claimed frame.
  - It fails closed if the assumed snapshot layout is wrong.
  - Results: `test-results-r3.json`, 46/46.
  - r2 is preserved in `r2/` (validator `e83b37db...`, test `6ec2062e...`, results `b5bf8984...` 38/38).
  - A first r3 test attempt crashed in the harness itself (a `:` in a Windows folder name, before any validator verdict). Its traceback-only results file was overwritten; the harness now sanitises folder names.
- **r2.** Fixed the blockers from the main review (msg_3dce6a3c3b2470a2) and the crash-check review (msg_7623c6266e6047e3):
  - `stage.number` must be exactly the integer 6, and it is never overwritten;
  - an observed narration needs a valid in-span `frame_range`;
  - the entry, expiry, narration and residency frames must lie inside a capture span;
  - the residency frame must lie between timer expiry and the last end state, and is bound to draw rows within ±60 frames; another TEX on 704,256 in that window counts as ambiguous;
  - entry must be strictly before expiry;
  - a not-observed narration's `searched_frame_range` must cover expiry through the last end state, inside a capture span;
  - non-object JSON rows produce a K failure in the report instead of an exception.
  - Results: `test-results-r2.json`, 38/38.

## Synthetic self-test result

r5 (validator `c671cc01`, tests `656960b8`): **72/72 PASS** on grant msg_1f578666 (2026-11-14 16:56Z, CPU 15, suite PID 40788, exit 0,
24.71 s, peak 81 MiB; all processes gone afterwards; the wrapper's 0.2 s sampling saw 59 child processes, an undercount: support's job-object accounting of the identical suite counted 73). Results `test-results-r5-run2.json` (`c97274c3`).
- Positives 7/7. Negatives 65/65; all 26 snapshot negatives fail exactly RS with their intended reason (exact-gate rule).
- 6 negatives fail several gates by design (r2 span cases, non-object rows, r2 ambiguous residency with a placeholder key, canonical control).
- The canonical validator still fails the timeout leg on F/L/M/S/T/X.
- Run 1 (67/72; the positive fixtures lacked a native source for the drawn key, so canonical K failed) is preserved as
  `test-results-r5-run1-FAILED-fixture-K.json` (`608dcc3a`).
- Independent replay by claude-einhander-support (grant msg_e8fd3b5c, 17:00Z, CPU 13 job object): **72/72 PASS**, exit 0, 24.1 s, 0 per-case differences from run 2; pins identical before and after; s67 folder byte-identical. Receipt `.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/replay-r5-20261114T170028Z/result.json` (`cdff346b`).
The figures below are r4's.

`python -B -I test_timeout_leg.py <scratch dir>` gives 55/55 cases OK in r4 (46/46 in r3, 38/38 in r2, 20/20 in r1):

- the clean run passes;
- each of 18 single-defect mutations fails exactly its expected gate: M ×2, R ×3, TX ×2, MV, NA ×2, RS, GO, NS, O ×2, H, C, K;
- the canonical validator run on the same timeout leg still fails (F, L, M, S, T, X).

## Not done

- No real AQ-13 run exists. The capture is codex-einhander's, as a separate run from AQ-03.
- The movie-identity and narration-index bases depend on which read-only logs the recorder can provide (the CD read log, a breakpoint log). Main must confirm what is available before promotion.
