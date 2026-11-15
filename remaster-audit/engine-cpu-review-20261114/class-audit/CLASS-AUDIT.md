# Native-word/CLUT class audit of world-integrated-crisp-v3 (claude-einhander, 2026-11-14)

CPU only, below normal, one process, one image decoded at a time. No GPU; the user's 3090 Ti hold stays in place. Every
input was opened read-only and no frozen file was changed. Nothing was repainted.

**Target:** `dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v3`.
**Checker:** `audit_native_classes.py` (sha256 e2f2d049…20f3). **Results:**
`class-audit-world-integrated-crisp-v3.json` (3c213436…aa85), with per-key status, source, sha256 pins, pair counts and
examples.

## Method
- **Reference = native words + CLUT, proven by CRC:**
  - recomputed CRC32(words) equals the first half of the key, and CRC32(CLUT) the second (00000000 for 15bpp);
  - every word is known (valid.bin all 1, or known_words == total_words);
  - sizes are consistent with the shape.
- **Exact regions** use the pack's own bound dumps, the loader's proof.
- **Page/strip keys** take the first passing dump from: REMASTER_STAGING stock, root's derived Uhu source, frozen-set
  `source/` folders, then retained capture folders. **Stock PNG alpha is never used as the reference.**
- **Native class:** CLUT word (or the 15bpp word) 0x0000 → 0; bit 15 → 255; else 127.
- **Compared:** the pack PNG alpha at pixel floor((i+0.5)·scale) for every native texel, with an integer scale equal on
  both axes.

## Results (1,699 files)
| | Files | Texels |
|---|---:|---:|
| PASS | 1,182 | |
| MISMATCH | **299** (all `unchanged immutable parent`; **0 of the 53 newly authored patches**) | 142,550 of 48,162,560 checked |
| NOT CHECKED: no CRC-proven native dump | 218 (0 of them drawn in the four Stage 1 flypasts) | |

Mismatch pairs (native → png):

| Pair | Texels |
|---|---:|
| 0 → 127 | 17,098 |
| 0 → 255 | 5,183 |
| 127 → 0 | 31,216 |
| 255 → 0 | 24,693 |
| 127 → 255 | 16,318 |
| 255 → 127 | 48,042 |

- **235 keys carry transparency errors** (0 ↔ opaque, wrong in every draw mode). The other 64 have only STP errors
  (127 ↔ 255), which matter for semi-transparent draws and the mask bit.
- Keys drawn in the four Stage 1 flypasts: 183 mismatching, 160 of them with transparency errors.
- Size of the mismatch per key: under 0.5 % of texels for 159 keys, 0.5–5 % for 81, 5 % or more for 59. The worst are menu
  and results typography pages, e.g. `8E1A509D-5726596A` at 29.6 % and `1AD90FC9-*` at 14–18 %.

## Every mismatch already has a prepared class-exact fix that world-v3 does not carry
| Fix source | Keys | Independently re-checked here |
|---|---:|---|
| `w6-livepack-classfix/frozen/livepack-classfix-v2` (70 exact regions + 15 pages, incl. all 15 mismatching 95A3BCF8 palettes) | 85 | **85/85 pass at 0** with this checker |
| `claude-backlog/w4-import-plan/import-plan-v3.json` (+ v4 addendum) rows | 214 | not re-run here; the plans record 0-mismatch class checks |

The import-plan rows by delivery:

| Delivery | Keys |
|---|---:|
| uhu-87C52FC0-v2 | 67 |
| uhu-46D3938E-v2 | 42 |
| rise-82831823-classfix-v1 | 33 |
| fighter-2294438F-v2 | 32 |
| menu-class-exact-v1 | 18 |
| results-strips-class-exact-v1 | 11 |
| W5 ranking-font / prompt-sheet / spec-text | 10 |
| continue-icons | 1 |

0 keys are left without a fix. The overlap lists are `v2-overlap.json` (17eca4d6…) and `import-plan-overlap.json` (f388053a…).

The W6 ledger records the same situation on the older live pack (386 mismatching keys). Its "excluded: already replaced
by import plan v3" rows were never composed into the world-integrated packs.

## Not checked (218)
Largest groups by texture prefix:

| Prefix | Keys |
|---|---:|
| 17B61263 | 26 |
| D050AD1B | 21 |
| 5C02D3C1 | 20 |
| 913A6603 | 19 |
| B77B98B9 | 7 |
| 2C6866AA, 9D8DF52A, C544AC0D | 6 each |

By treatment: authored 122, neural 52, nearest 36, UI 8. None was drawn in the Stage 1 flypasts.
`w6-livepack-classfix/CAPTURE-REQUESTS.md` already lists 30 open capture requests, including the 25 `17B61263` CLUTs.

## Consequence for the 95A3 region-K panel
My `95A3BCF8-K-panel-v1/page2048` also stamps the native class at every centre. It is consistent with the
livepack-classfix-v2 file for that key: both are 0 at centres, and the RGB outside region K is the live page's. Compose it
in place of the v2 file for `95A3BCF8-723E222C` and the class fix is preserved.

## Suggested composition, private, for root (not done here)
1. Base world-integrated-crisp-v3.
2. Add livepack-classfix-v2 for its 85 keys.
3. Add the import-plan v3/v4 rows for the 214 keys, at the live size where the row offers it.
4. Add the K panel.
5. Re-run this checker on the result. Expected: 0 mismatches on the 1,481 checkable keys. Then verify_native.exe admission.
