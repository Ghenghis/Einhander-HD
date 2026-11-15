# Stage 2 / Stage 3 gates (claude-einhander-s23)

Written 20261114T135401Z from actual s23 outputs and pinned lane evidence. Nothing here is live, look or stage acceptance. All keys stay
predicted-static until S2.md / S3.md captures confirm them (`validate_predicted.py confirm` + `gate`).

## Evidence produced by s23
| Output | sha256 | What it shows |
|---|---|---|
| runs/selection-20261114T133254Z/selection-map.json | f29ff130d3f2d087e95a90cfebe7892415cf480af3cc3718723f4594b7256250 | 39 + 39 selected keys, folder pins, byte hashes, centre-only lane checks, CLUT kinds, PAL competition |
| runs/selection-20261114T133254Z/strict-join.json | 697cd133725c5161efe087433f92b97af90ad23d6a2b35b99ef4fb6957083324 | join to claude-einhander's proto-v2b DLL audit e28553ba |
| runs/j1-20261114T134041Z/summary.json | af4c65b1b4265e68c4cefd779e9264c2a6ccb90c1189a5e648042b2e9318698e | 156/156 strict pass, independent numpy == DLL on all counters |
| runs/j1-20261114T134041Z/fringe-summary.json | 0fe2cb32ebde88ce5e5c50ddb8b1c6ec000ccc00402b4af403852c568913f173 | sampled dark cutout fringe (S2 44 files, S3 32 files) |
| runs/phase-coverage-20261114T134554Z/phase-coverage.json | 2dc3c14d97fe49d9c0fd16ec829308d51746b29d86e7b235bc6d26433b92bff2 | cycling-phase coverage of the prep-v2 keys |

## Stage 2 (39 keys)
| Gate | State | Evidence / next |
|---|---|---|
| Whole-cell class (R1-R4) | PASS 78/78 files | J1; DLL e28553ba |
| Cutout RGB fringe (R5) | OPEN: 44/78 files, all dark-biased; worst 6AE78470-BE14F28C, 0F01F0FA-F11578EE | J4 bleed-fill copies (script ready, needs CPU grant) |
| Palette phases (prep-v2, 8 keys) | BLOCKED: 4/39 and 4/29 phases have words; 17.0% / 12.1% of sampled cycling draws | S2-2 capture (60 unknown phase words + AQ-05 hold); then export all phases from prep-v1 masters |
| Phase silhouettes on shared pages | NOT RUN | J3 (script ready) |
| Thin edge-on train draws | OPEN (SIMULATION): 0F01F0FA-8FD3DE52 0.93x stock shimmer, F11578EE 0.92x, BE954EE4 0.85x (flipbook train-ground-r1 2ced9b9b) | needs class-aware mips (runtime, class-mip M1-M5); not fixable in art |
| Ground crawl 6AE78470 (sky-ground-v3) | OPEN (SIMULATION 0.69-0.78x stock; material layer +17% vs v2) | S2-5 live fly-past; fallback rebuild with S2_HP_BLUR_PX=3.0 / k_lp 0.08 |
| Live key/CLUT/UV confirmation | MISSING | S2.md S2-1, S2-3 |
| Cross-lane | 4 drawn static-CLUT 3DD37B6B actor keys (3C1DB4B6, 86558368, B949240B, FAC936BC) unexported in any lane | owner w4-enemies (post_drache_actors), S2-4 sources |

## Stage 3 (39 keys)
| Gate | State | Evidence / next |
|---|---|---|
| Whole-cell class (R1-R4) | PASS 78/78 files | J1; DLL e28553ba |
| Cutout RGB fringe (R5) | OPEN: 32/78 files; worst B53A4C57 2-entry speck keys | J4 |
| E49BC3F1 / AA5DBEF2 dither + granite camouflage (14 keys) | BLOCKED from shipping (ledger) | J2 proposal (variants a/b, script ready, needs CPU grant); CAUTION-plate stipple largely outside the detector (letters bound it), stays v1 until the S3-4 in-game size is known |
| Draw evidence | NONE (0 records for all 39 keys) | S3.md S3-1 |
| Palette identity | OPEN: every key has 2-5 PAL candidates at its CLUT position | S3.md S3-2 |
| Wall motion (walls-v1 vs material-v1) | SIMULATION only | S3.md S3-3 |
