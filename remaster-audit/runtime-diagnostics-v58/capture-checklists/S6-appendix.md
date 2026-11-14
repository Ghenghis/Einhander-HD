# S6 appendix: Stage 6 Schwarzgeist (lane-s6, w7-stage6; still being authored)

Written 2026-11-13 by claude-einhander (lane capture-checklists) from `comfy-authoring/w7-stage6/LEDGER.json` (schema `w7-stage6-ledger-v2`, written 2026-11-13T23:48Z, CR-S6-1 to CR-S6-5) and the frozen manifests. Text only: nothing was launched. Lane-s6 is still authoring, so re-read its `LEDGER.json` before the run; this file is a snapshot.

## 1. Purpose

All lane-s6 keys are candidate / predicted-static: nothing is importable until a live Stage 6 capture confirms key and CLUT. The motion verdicts rest on assumed quad sizes and frame order.

| Item | Lane ref | Confirms or unlocks |
|---|---|---|
| S6-1 | CR-S6-1 | The import gate for **101 keys** in 9 current frozen sets (83 in batch 2, 18 in batch 1; the ledger says "83 + 21"), and the semi mode for the review composites. |
| X-704256 + S6-2 | CR-S6-2 (+ CR7-4) | Which texture set (A = 4/0 + 4/6, B = 4/10 + 4/11) is resident in which segment; and whether 704,256 holds the 4/5 explosion page or the 4/12 Hyperion transmission page `9E43A5C3`. **Shared with lane-s7** for 704,256. |
| S6-3 | CR-S6-3 | Part masks and panel-seam placement for the hull material pass (blocked without it; the texture-space grain pilot failed). |
| S6-4 | CR-S6-4 | Real quad sizes, cell order and per-frame CLUT for `D552405C` (smoke/exhaust) and `E653AA46` (electric bolts): the motion SIMULATION currently assumes 40 native px quads, page-order animation and a fixed palette. |
| S6-5 | CR-S6-5 | Runtime-written palettes that no static source predicts (the masters render any CLUT; only the export list is missing). |

### Terms used in every checklist

- **Key** = `TEXCRC-CLUTCRC`: CRC32 of the page words, a dash, CRC32 of the CLUT words (upper-case hex).
- **Draw row** = a `source_draw_query_matched` event in the recorder's `capture.jsonl` (contract `ein-research-v1`). Fields used: `key`, `frame`, `source_kind`, `depth` (0 = 4bpp, 1 = 8bpp), `semi` (-1 = none; 1 = additive), `page_xy`, `clut_xy`, `uv_bounds` [u0,v0,u1,v1], `xy` (screen vertices in 320x240 units; odd-buffer draws carry +240 y). A `replacement_gl_draw_submitted` event shows an installed replacement was drawn (`replacement_size`).
- **Complete source** (acquisition gate-K rule, also used by `validate_predicted.py`): `<KEY>.words.bin`, `.clut.bin`, `.valid.bin` and `.source.json` present; CRC32(words) = key[0:8]; CRC32(clut) = key[9:17]; known_words = total_words; every `valid.bin` byte non-zero. The full key set comes from the stock-first HD dump `<run>/stageN-source/`; the recorder's `native-source-<i>/` folders are capped at 256 sources per window.
- **Marked CPU-VRAM snapshot** = an EINRC01 event file `event-NNNN.bin` (160-byte header + 2 MiB RAM + 1 MiB VRAM = 3,145,888 bytes), written by a research `mark` (phase `point`, or a `before`/`after` pair). It is a CPU mirror flagged `cpu_vram_may_be_stale`; a CLUT read from it counts only on an exact CRC match.
- **Recorder bounds per window** (`windows-x64/tools/research_service.py`): `native_max_sources` ≤ 256, `native_max_records` ≤ 20,000, `native_max_events` ≤ 32 (default 6), `native_max_frames` ≤ 18,000, `duration_seconds` ≤ 300, `native_max_bytes` ≤ 128 MiB (each mark reserves 3,145,888 bytes). Default coverage is `sampled_activation_forward` with `repeat_sample_frames 60`; **full rate** here means `repeat_sample_frames 1`.
- **Phase detectors (read-only):** `read_ram` about once a second of `0x80081380` (current stage), `0x80081382` (current section) and `0x80081384` (boss/event flag; meaning is a candidate). Use them for marks and anchors only; stage identity needs visible evidence.
- **Stills** are 2880x2160 internal captures (`<label>-internal.png`) unless stated.
- **Route** is Codex's authorized route and control method; nothing here says how to get there. Reference-run frame numbers are not portable; use the anchors.
- **A blocked key is an answer, not a capture defect.** If the game draws a predicted key with another CLUT, `gate` blocks that key and the lane re-renders it from its index master with the live CLUT. The capture is sufficient when every key drawn in the window has a complete source.

## 2. Prerequisites

- **Route:** a continuous run into Stage 6 (AQ-03). Do the thrusters run normally (it leads to MOV04 and Stage 7, so this run can continue into the S7 checklist). The timeout / second-ending leg (AQ-13) is a separate later run.
- **Pack:** stock textures for every Stage 6 key. HD dumping stock-first to `<run>/stage6-source/`, Stage 6 entry (`0x80081380` reads 6) to clear.
- **Recorder:** whole stage, windows rotated per segment, paired `seg:6:<id>` marks at each `0x80081382` change; full rate for `D552405C` and `E653AA46` during S6-4.

## 3. Anchors and VRAM layout

No run has reached Stage 6. Two texture sets write the same VRAM; the TEX half of each drawn key tells which version is resident:

| VRAM page (64x256 words) | set A | set B |
|---|---|---|
| 320,0 | `43C26C42` (4/6) | `61A869E5` (4/10) |
| 384,0 | `8F498326` (4/6) | `F07625EE` (4/10) |
| 448,0 | `03F5CF11` (4/6) | `A5969BC9` (4/10) |
| 704,0 | `20961255` (4/0) | `E0849F81` (4/10) |
| 704,256 | `10932164` (4/5, large explosion) | or `9E43A5C3` (4/12, Hyperion transmission page) |
| 320,256 / 384,256 / 448,256 | `D552405C` / `E653AA46` / `CB07BBCB` (4/6, single writer) | |

The readiness review reads set A content (platform, boosters, briefing, digits) as the timed thruster mission and set B content (disks, saucer, small craft) as the Schwarzgeist part. Visual candidates only.

## 4. Capture list

### S6-1 (CR-S6-1). Draw rows for the twelve TEX

- **Trigger:** Stage 6 entry to clear.
- **Record:** draw rows for TEX `10932164`, `E653AA46`, `CB07BBCB`, `D552405C`, `43C26C42`, `61A869E5`, `20961255`, `E0849F81`, `8F498326`, `F07625EE`, `03F5CF11`, `A5969BC9`: `key`, `frame`, `uv_bounds`, `xy`, `clut_xy` and the tpage semi bits (`semi`). Plus the stock-first dump.
- **Keys** (`keys/S6-gate-keys.txt`, 101 keys), with predicted CLUT xy (from `stages-v4/stage6`; the four Stage 1 explosion keys are not in the Stage 6 key list):

| set | keys (CLUT xy) |
|---|---|
| `stage6-large-explosion-10932164-v1` (704,256) | `10932164-8E3D08E7` (160,511); Stage 1 files reused byte for byte: `-0386F43A`, `-5F4DE3D3`, `-66175427`, `-AF93AEF2` |
| `stage6-electric-bolts-E653AA46-v1` (384,256) | `E653AA46-47823F21` (160,510), `-8E3D08E7` (160,511), `-4CAF3E0F` (224,511) |
| `stage6-camo-craft-CB07BBCB-v1` (448,256) | `CB07BBCB-8513C505` (128,494), `-6CFD44D8` (96,511), `-0344ADB9` (64,511), `-6F28D777` (16,510), `-0717A4D3` (16,510), `-A12BB890` (144,511) |
| `stage6-smoke-exhaust-D552405C-v4` (preferred; v1 is the fallback) (320,256) | `D552405C-92AC1558` (96,494), `-98C90B96` (128,510), `-5E251958` (112,494), `-C12DB7DC` (272,504) |
| `stage6-vram320-0-43C26C42-61A869E5-v1` (320,0) | set A `43C26C42-521B0B1A` (32,495), `-2B66A97F` (128,511), `-6EDE7B7C` (240,495), `-25C360FE` (160,495), `-870A1255` (48,494), `-FFF1C1BF` (16,511), `-3C7F8A8F` (48,495), `-60579FEB` (0,510), `-1E4043BA` (240,511), `-4CAF3E0F` (224,511); set B `61A869E5-11674191` (16,496), `-FF01A5DB` (96,497), `-9F20800F` (0,497), `-334D9EFF` (64,496), `-3E21CF50` (80,496), `-05C38755` (32,490), `-5FA94A42` (112,491), `-09E96477` (16,511), `-F2E4A647` (160,497), `-47823F21` (160,510), `-2E90A992` (112,496), `-1689DF90` (144,496), `-8D920799` (0,510), `-3F02B716` (160,491), `-B97689E3` (48,496), `-B675A0C2` (96,491), `-BD161002` (128,496), `-AB139F82` (0,508), `-DE388F4C` (16,508) |
| `stage6-vram384-0-8F498326-F07625EE-v1` (384,0; `8F498326` keys superseded by `-fx-v2`) | set A `8F498326-870A1255` (48,494), `-847D772B` (32,494), `-899D7E1D` (0,494), `-0344ADB9` (64,511), `-31689705` (80,511), `-0F04A907` (48,511), `-4CAF3E0F` (224,511); set B `F07625EE-AA609B3E` (48,490), `-0DD8FE23` (64,511), `-0902919B` (144,490), `-E2432AE9` (80,511), `-46EBDEF1` (80,490), `-55345BAD` (64,490), `-995DA972` (32,491), `-C157881A` (128,490), `-4FB18FAB` (160,490), `-34CF1D58` (16,490), `-19BC58B9` (16,491), `-47CC0499` (128,491), `-328481EB` (64,497), `-AB139F82` (0,508), `-A3ED112B` (48,511), `-DB8D9451` (240,496) |
| `stage6-vram448-0-03F5CF11-A5969BC9-v1` (448,0) | set A `03F5CF11-870A1255` (48,494), `-AA87046E` (80,493), `-111CA9A9` (48,510), `-61869F1D` (64,493), `-3C7F8A8F` (48,495), `-810A0B32` (32,510), `-0B9F0CD2` (240,493); set B `A5969BC9-FD5E0863` (64,510), `-28E85C14` (48,510), `-B675A0C2` (176,490), `-CD90D27E` (112,490), `-F3BEA083` (32,510), `-7DFC973F` (144,497), `-B3A5B734` (208,490), `-AD6DB7AA` (32,511), `-4FB18FAB` (160,490), `-165DD2B8` (224,490), `-3A9A151E` (192,490), `-995DA972` (32,491), `-98C90B96` (128,510), `-AB139F82` (0,508) |
| `stage6-vram704-0-20961255-E0849F81-v1` (704,0; `20961255` keys superseded by `-fx-v2`) | set A `20961255-810A0B32` (32,510), `-EE2BAE09` (144,493), `-A83C5B65` (208,511); set B `E0849F81-F3BEA083` (32,510), `-7DFC973F` (144,497), `-5379DE11` (16,497), `-AA609B3E` (48,490), `-0902919B` (144,490), `-47823F21` (160,510), `-98C90B96` (128,510) |

- **Pass criterion:** a complete source for every key drawn; draw rows that carry `semi` for every drawn key; each segment's rows show which set's TEX are drawn.

### X-704256 + S6-2 (CR-S6-2, shared with CR7-4). Texture-set residency per segment

- **Trigger:** the whole Stage 6 run, with segment marks; continue into Stage 7 for the 704,256 part (S7 checklist, X-704256).
- **Record:** VRAM upload events (rect + CRC + frame) for VRAM pages **320,0 / 384,0 / 448,0 / 704,0** (64x256 words each) and **704,256**. The existing upload history command `a0_history` (used by `remaster-audit/capture_stage1.py`, fields frame, x, y, w, h) logs upload rects and frames; where it gives no CRC, a marked snapshot after the upload, or the TEX half of the next draw row on that page, supplies it.
- **Pass criterion:** for each segment and each of the five pages, the resident TEX CRC (set A, set B, or for 704,256 `10932164` / `9E43A5C3` / other) with the frame of the upload that put it there.

### S6-3 (CR-S6-3). GP0 textured-polygon dump

- **Trigger:** while `CB07BBCB`, `43C26C42`, `61A869E5`, `8F498326`, `F07625EE`, `03F5CF11`, `A5969BC9`, `20961255` and `E0849F81` are drawn (each set A and set B page at least once).
- **Record:** textured-polygon records with vertex `xy`, `uv`, tpage and `clut` for those draws. The existing dense path is the per-frame GP0 ring dump (`gpu_frame_dump`, as in `remaster-audit/record_gp0_burst.py`), pulled before the frames leave the ring.
- **Pass criterion:** for each of the nine TEX, complete (untruncated) GP0 frames containing its polygons. The lane gave no window length; the Stage 1 Drache request used 60 consecutive frames, which is a reasonable unit per page.

### S6-4 (CR-S6-4). Real quad sizes and animation of `D552405C` and `E653AA46`

- **Trigger:** every segment where the smoke/exhaust (`D552405C`, 320,256) or electric bolts (`E653AA46`, 384,256) are drawn.
- **Record:** full-rate draw rows: the on-screen quad size per draw (`xy` extents), the cell sequence over consecutive frames (`uv_bounds`), and the CLUT per frame (`clut_xy` plus the key's CLUT CRC).
- **Pass criterion:** for each TEX, at least one run of consecutive frames with every draw logged, giving quad sizes, cell order and the CLUT of each frame.

### S6-5 (CR-S6-5). CLUT rows 490-511 at segment starts

- **Trigger:** each segment start in Stage 6.
- **Record:** a marked CPU-VRAM snapshot at each segment start; the lane reads **CLUT rows 490-511, x 0-511**.
- **Pass criterion:** one snapshot per segment start. Any CLUT a drawn key uses that matches no static source is recorded with its `clut_xy` (per the Stage 6 readiness review, the code overlays 4/2, 4/4 and 4/7 upload another 20 palettes at runtime as 16x1 CLUT records).

## 5. After the capture (lane-s6 runs these)

Run from `C:/github/Einhander/remaster-audit/fullgame-prep/static-extraction`. Batch 2 and the fx-v2 sets were built from `stages-v4/stage6`, batch 1 from `stages/stage6`; run `confirm` against both if their reports differ:

```
python -I validate_predicted.py confirm --stage-dir stages-v4/stage6 --live <run>/stage6-source --live <run>/native-source-0 [--live ...] --draws <run>/native-source-0/capture.jsonl [--draws ...] --out <report-confirm.json>
python -I validate_predicted.py gate --stage-dir stages-v4/stage6 --live <run>/stage6-source --live <run>/native-source-0 [...] --keys C:/github/Einhander/remaster-audit/claude-backlog/capture-checklists/keys/S6-gate-keys.txt --out <report-gate.json>
```

- Re-export newly confirmed CLUTs from the existing CLUT-free masters; record set A/B residency per segment.
- Hull material detail once S6-3 lands (do not retry texture-space grain).
- Re-run the motion SIMULATION with the real quad sizes and cell order (S6-4).
- `tools/s6_verify.py` on all frozen folders before any hand-off to Codex.

## 6. Open questions

- **Key count:** the frozen manifests list 101 distinct keys (83 + 18); the ledger text says "83 + 21". Lane-s6 should confirm the batch 1 count before the gate run.
- **Upload CRCs (S6-2):** whether `a0_history` keeps the whole stage (or only a recent ring) and whether it carries a CRC was not checked; the snapshot or draw-row fallback above answers residency either way.
- Lane-s6 is still authoring; re-read `LEDGER.json` before the run for new candidates or requests.
