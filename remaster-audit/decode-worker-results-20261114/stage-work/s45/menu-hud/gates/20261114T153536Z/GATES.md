# Menu / HUD gates join `20261114T153536Z` (s45)

Gates and capture requests are w4-menus' own (`comfy-authoring/w4-menus/LEDGER.md`, `CAPTURE-REQUESTS.md`).
This only joins them with the s45 register and orders the J-L class-policy audit. Delivered = frozen candidate.

| ledger state | gates | capture requests | keys | with frozen candidate | class policy |
|---|---|---|---|---|---|
| S1. Boot splashes (Sony, SQUARESOFT, WAIT) | G-S1 | CR-01 | 5 | 5 | pending J-L |
| S2. Title, boot path (logo design E) | G-S2 | CR-01 | 5 | 3 | pending J-L |
| S3. Title after attract/demo return | G-S3 | CR-02 | 2 | 1 | pending J-L |
| S4. Title after quit (pause -> QUIT -> YES) | G-S4 | CR-07 | 0 | 0 | pending J-L |
| S5. Title after Game Over | G-S2, G-S5 | CR-01, CR-09 | 0 | 0 | pending J-L |
| S6. Title menu items (GAME START / PILOT / FILE OPTION / CONFIGURATION / GALLERY) | G-S6 | CR-03 | 2 | 2 | pending J-L |
| S7. File option, data load/save, discard, Score/NO DATA, Score Ranking pages, name entry (CREATE DATA FILE) | G-S7 | CR-04 | 3 | 3 | pending J-L |
| S8. Configuration (root, Difficulty, Controller, Screen Adjust, Audio) | G-S8 | CR-05 | 0 | 0 | pending J-L |
| S9. Fighter selection | G-S9 | CR-06 | 5 | 5 | pending J-L |
| S10. ARM (armament) selection | G-S10 | CR-06 | 3 | 3 | pending J-L |
| S11. Pause | G-S11 | CR-07 | 2 | 2 | pending J-L |
| S12. Continue | G-S12 | CR-08 | 4 | 4 | pending J-L |
| S13. Game Over | G-S13 | CR-08 | 1 | 1 | pending J-L |
| S14. Total Evaluation / Field Graph / Fight Graph / Exit | G-S14 | CR-09 | 6 | 5 | pending J-L |
| S15. Save prompt after results; high-score name entry | G-S15 | CR-09 | 0 | 0 | pending J-L |
| S16. Stage banners, warnings, stage clear | G-S16 | CR-10 | 0 | 0 | pending J-L |
| S17. Gallery / stage select | - | - | 0 | 0 | pending J-L |

## J-L audit order (frozen folders by number of dependent gates)

- `w4-menus/menu-class-exact-v1`: G-S1, G-S2, G-S6, G-S7, G-S9, G-S10, G-S11, G-S12, G-S13, G-S14
- `t9-title-menus/hud-prompts-BDAE4156-v4`: G-S1, G-S9, G-S11, G-S12, G-S14
- `w2-hud/hud-prompts-BDAE4156-v5`: G-S1, G-S9, G-S11, G-S12, G-S14
- `t9-title-menus/results-footer-8E1A509D-v4`: G-S2, G-S6, G-S7, G-S14
- `w2-hud/results-footer-8E1A509D-v5`: G-S2, G-S6, G-S7, G-S14
- `t9-title-menus/title-menu-323B5FB0-v1`: G-S2, G-S6, G-S7
- `t9-title-menus/title-menu-323B5FB0-v5`: G-S2, G-S6, G-S7
- `w5-cleanup/prompt-sheet-BDAE4156-DD0B6963-w5-v1`: G-S1, G-S11, G-S12
- `t9-title-menus/selection-headers-D0365088-v3`: G-S9, G-S10
- `t9-title-menus/selection-labels-1AD90FC9-v3`: G-S9, G-S10
- `w2-hud/selection-labels-1AD90FC9-v4`: G-S9, G-S10
- `w3-hud/hud-label-font-BDAE4156-v1`: G-S9, G-S14
- `w4-menus/story-font-AEE859DC-v1`: G-S3, G-S7
- `w5-cleanup/spec-text-1AD90FC9-w5-v2`: G-S9, G-S10
- `w5-cleanup/weapon-names-1AD90FC9-w5-v1`: G-S9, G-S10
- `w6-hud-fades/w3-hud-classfix-v1`: G-S9, G-S14
- `t9-title-menus/arm-strip-AAE3C8F2-v1`: G-S10
- `t9-title-menus/prompts-DD0B6963-v2`: G-S1
- `w2-hud/gameover-5125FF82-v1`: G-S13
- `w2-hud/hud-prompts-BDAE4156-robincluts-v1`: G-S12
- `w2-hud/results-8E1A509D-drawn-cluts-v1`: G-S14
- `w3-hud/results-footer-8E1A509D-v6`: G-S14
- `w3-hud/results-grades-8E1A509D-v1`: G-S14
- `w3-hud/results-score-header-48F8001A-v1`: G-S14
- `w4-menus/continue-icons-BDAE4156-v1`: G-S12
- `w6-native-gaps/fighter-select-absent-keys-v1`: G-S9
