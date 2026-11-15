# Stage 6-7 strict whole-cell class audit (s67, 2026-11-14)

Owner `claude-einhander-s67`. Tasks `EIN-S6-WHOLE-CELL-20261114` and `EIN-S7-WHOLE-CELL-20261114`. This is data only. It touched no art, frozen folder, pack, runtime or index.

**Headline:**
- **115 of the 127 selected keys** (Stage 6: 89 of 101; Stage 7: 26 of 26) pass the strict whole-cell class check at both 2048 and 1024.
- **12 Stage 6 batch 1 FX keys fail at both sizes** (24 files): the large explosion `10932164` (5 keys), the electric bolts `E653AA46` (3) and the smoke/exhaust `D552405C` (4).
- **Every failing file passes the lane's texel-centre gate** (R1 = 0). This is the gap the brief warned about: a centre-only pass is not a whole-cell pass.
- **Nothing here is a live, look, stage or project acceptance.** Every key is still predicted-static.

## 1. Run

| item | value |
|---|---|
| Run | `remaster-audit/parallel-stages-20261114/s67/runs/20261114T135603Z/` |
| `result.json` sha256 | `e1eeb72d6e2052e2f5bd49feb4d677fc2b6b7008e31ea1574bc95c5bbe79b1ee` |
| Process | PID 28744, started 13:56:03Z, elapsed 42.81 s, exit 0, `complete=true`, not aborted. Granted by codex-einhander (msg_f519603685aca81a); one CPU (affinity [15]), below normal, OMP/BLAS 1, budget 270 s. |
| Tool | `s67/tools/s67_strict_audit.py` sha256 `cb2ebd9eba45a028d0f26f1003989a9f570bce641a9c64792c1a21a76d4c2425`; a copy is in the run folder |
| Validator | frozen `claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b/class_mip.c`, compiled into the run folder (`compile.log`) |
| Inputs | S6 selection map `stage6/selection-map-20261114T133638Z.json` (`3d0961e7...12eb7`); S7 map `stage7/selection-map-20261114T133927Z.json` (`1069a904...66da2`) |
| Dry run | `runs/20261114T134056Z-dry/result.json` (`9d57c65f...8d69`): 282 rows, 0 errors |
| PNG integrity | 254 of 254 selected files match the manifest sha256 |

**Rule.**
- **Native class map:** the CRC-proven page words, read through the CRC-proven CLUT. Word 0x0000 → class 0, STP bit set → 255, otherwise → 127.
  - The 4 Stage 1-shared `10932164` keys take their CLUT from `w2-effects/frozen/large-explosion-10932164-v2/source`.
- **Whole-cell strict pass:** `cm_validate` R1 (centre) = R2 (displaced > s/2) = R3 (uniform neighbourhood) = R4 (island) = non-class alpha = 0.
- **Primary pass:** R1 = 0 and connectivity-only (`cm_flags_ex`, bits 2|4|16) = 0.
- **R5** (cutout-fringe RGB) is diagnostic only.
- Primary and strict gave the same verdict on every file here.

## 2. Results by folder (selected keys)

| stage | folder | keys | files | strict pass | primary pass | R5 fringe px (diag.) |
|---|---|---|---|---|---|---|
| 6 | stage6-camo-craft-CB07BBCB-v1 | 6 | 12 | 12 | 12 | 4,801 |
| 6 | stage6-vram320-0-43C26C42-61A869E5-v1 | 29 | 58 | 58 | 58 | 75,531 |
| 6 | stage6-vram704-0-20961255-fx-v2 | 3 | 6 | 6 | 6 | 36,725 |
| 6 | stage6-vram704-0-20961255-E0849F81-v1 (E0849F81 keys) | 7 | 14 | 14 | 14 | 16,535 |
| 6 | stage6-vram384-0-8F498326-fx-v2 | 7 | 14 | 14 | 14 | 7,311 |
| 6 | stage6-vram384-0-8F498326-F07625EE-v1 (F07625EE keys) | 16 | 32 | 32 | 32 | 15,650 |
| 6 | stage6-vram448-0-03F5CF11-A5969BC9-v1 | 21 | 42 | 42 | 42 | 114,984 |
| 6 | **stage6-large-explosion-10932164-v1** | 5 | 10 | **0** | **0** | 79,582 |
| 6 | **stage6-electric-bolts-E653AA46-v1** | 3 | 6 | **0** | **0** | 50,387 |
| 6 | **stage6-smoke-exhaust-D552405C-v4** | 4 | 8 | **0** | **0** | 275,868 |
| 7 | stage7-fleet-parts-v1 | 22 | 44 | 44 | 44 | 370,042 |
| 7 | stage7-planet-limb-v1 (incl. inferred `C4FDEDD2-EAD968A1`) | 2 | 4 | 4 | 4 | 0 |
| 7 | stage7-space-backdrop-30BB2999-v1 | 2 | 4 | 4 | 4 | 25,345 |
| **total** | | **127** | **254** | **230** | **230** | |

**Retained alternates** (not selected, audited for reference):

| alternate | files | strict pass | note |
|---|---|---|---|
| `stage6-smoke-exhaust-D552405C-v1` | 8 | 0 | Identical counts to v4. The v4 class plane is v1's, so v4 inherits the failure. |
| `stage6-vram704-0-20961255-E0849F81-v1` (20961255 keys) | 6 | 6 | |
| `stage6-vram384-0-8F498326-F07625EE-v1` (8F498326 keys) | 14 | 14 | |

**Stage 7 forced centres.** `30BB2999-418C69D6` records 75 / 124 forced texel centres, but it passes strict: the pins do not create R2/R4 violations.

## 3. The failing keys (every one has R1 = 0)

| key | 2048: R2 / R3 / R4 / connectivity px (bad cells) | 1024: R2 / R3 / R4 / connectivity px (bad cells) |
|---|---|---|
| 10932164-8E3D08E7 (Stage 6 render) | 73 / 29 / 95 / 108 (28) | 15 / 6 / 28 / 28 (18) |
| 10932164-0386F43A (Stage 1 file) | 629 / 311 / 627 / 714 (125) | 124 / 57 / 131 / 148 (77) |
| 10932164-66175427 (Stage 1 file) | 629 / 311 / 627 / 714 (125) | 124 / 57 / 131 / 148 (77) |
| 10932164-5F4DE3D3 (Stage 1 file) | 354 / 257 / 329 / 354 (47) | 63 / 45 / 58 / 63 (29) |
| 10932164-AF93AEF2 (Stage 1 file) | 250 / 248 / 251 / 251 (38) | 47 / 47 / 47 / 47 (25) |
| E653AA46 (all 3 CLUTs, same class field) | 7,768 / 5,840 / 6,402 / 7,778 (757) | 1,448 / 1,078 / 1,197 / 1,453 (544) |
| D552405C-92AC1558 / -98C90B96 / -5E251958 | 4,950 / 3,300 / 1,558 / 4,950 (322) | 921 / 622 / 333 / 925 (287) |
| D552405C-C12DB7DC | 29,338 / 13,952 / 11,363 / 29,338 (1,376) | 5,766 / 2,754 / 2,309 / 5,774 (1,324) |

`result.json` lists the worst native cells (u, v, px) for every failing file. Examples:

- D552405C at row v=209: u 156-176;
- E653AA46 at row v=237: u 220-226;
- 10932164 at (61,78), (78,59), (157,203), (182,101-102).

**Cause.** These are the three soft-silhouette FX families: the explosion's "soft silhouette, classes exact at the texel centres", and the bolt and smoke class fields. Their alpha deviates from the native cell class farther than s/2 from any native cell of that class (R2), and as islands (R4). The 2x2-px centre gate cannot see that.

**Stage 1 impact (for claude-einhander and codex-einhander).** The four `10932164-0386F43A / -5F4DE3D3 / -66175427 / -AF93AEF2` files are byte-identical to the Stage 1 frozen `w2-effects/frozen/large-explosion-10932164-v2` deliverable. So the Stage 1 large-explosion files fail the same strict whole-cell check, unless the Stage 1 owner's own audit says otherwise. s67 did not audit the Stage 1 folder itself.

## 4. Proposed repairs (not done; each needs its own CPU grant)

1. **FX class-ownership repair r1** (12 keys, 24 files). Run the frozen proto-v2b `cm_repair` on copies of the failing files, into `s67/repairs/`:
   - R1/R2/R4 violators take their native cell's class;
   - the authored RGB of pixels that stay visible is never changed (`visible_rgb_changed` must be 0);
   - R5 fill applies to cutout RGB only.
   - Then re-run the strict audit on the outputs, and build review sheets so the silhouette can be judged against v1. That judgement matters: the lane rejected a blocky native silhouette for the Stage 7 explosion.
   - Frozen v1/v4 and the Stage 1 files stay untouched.
   - Estimated cost: under 30 s on one CPU.
2. **A5969BC9 de-dither r1** (14 keys, 28 files). Tool `s67/tools/s6_dedither_A5969BC9.py`; mask `s67/repairs/A5969BC9-dedither-mask-20261114T135126Z.json`, D = 18,691 texels.
   - Synthetic unit test: interior pair means exact (5,854 / 0), stripe contrast 49.5 → 3.9, luminance 187.05 → 186.95, alpha and everything outside D byte-identical to v1.
   - Estimated cost: about 60 s on one CPU.
3. **30BB2999 star-burst analytic rebuild** (Stage 7). Native fit: the four bursts are Euclidean digital discs centred at (16 / 48 / 80 / 112, 231), with ≤ 8 radial-order violations out of 344-507 ring texels. This supports iso-circle class boundaries without pins.
   - Fit tool: `s67/tools/s7_burst_fit.py`. The full fit JSON and the builder come next.

## 5. Limits

- PS1 class only. No RGB or look acceptance, no motion check, no live draw. All keys are predicted-static.
- Stage 6 set A/B residency, GP0 part masks, real quad sizes and runtime CLUTs are not captured. The Stage 7 drawn CLUTs and the `C4FDEDD2-EAD968A1` pairing are unconfirmed. See `requests/S67-CAPTURE-REQUESTS-20261114.md`.
- The validator measures the class plane against the native map of each delivered CLUT. A runtime CLUT with a different zero/STP layout gives a different native map; those keys must be re-rendered and re-audited after capture.
