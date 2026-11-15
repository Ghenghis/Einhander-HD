# R1>0 look-review queue (claude-einhander-ui, source-only, from census fff7a1c8)

These 51 units have wrong native centre texels (R1>0) in the authored candidate. They were NOT repaired.
J-R2 showed snap-native restores native panels but leaves stair-stepped glyph edges, and needs look review before any proposal.

| texture | folder | units | files | dirs | R1 range | conn range | prior evidence |
|---|---|---|---|---|---|---|---|
| 8E1A509D | w2-hud/results-footer-8E1A509D-v5 | 12 | 12 | pack, runtime-1024, runtime-2048 | 352-10058 | 5842-220452 | results footer; no look review yet |
| 8E1A509D | t9-title-menus/results-footer-8E1A509D-v4 | 9 | 9 | pack, runtime-1024, runtime-2048 | 352-7280 | 5842-120302 | results footer; no look review yet |
| BDAE4156 | t9-title-menus/hud-prompts-BDAE4156-v4 | 9 | 12 | pack, runtime-1024, runtime-2048 | 4790-6105 | 74861-1339104 | prompt font; w5 prompt-sheet provisionally preferred (R1=0 files) |
| 1AD90FC9 | w2-hud/selection-labels-1AD90FC9-v4 | 6 | 9 | pack, runtime-1024, runtime-2048 | 9459-11864 | 38010-1123087 | J-R2/J-C1/J-S1: neither w4 nor w5 accepted; cause unproven |
| BDAE4156 | w2-hud/hud-prompts-BDAE4156-v5 | 6 | 9 | pack, runtime-1024, runtime-2048 | 71-87 | 107-4021 | prompt font; w5 prompt-sheet provisionally preferred (R1=0 files) |
| D0365088 | t9-title-menus/selection-headers-D0365088-v3 | 6 | 6 | pack, runtime-1024, runtime-2048 | 947-7381 | 18626-193780 | selection headers; no look review yet |
| 323B5FB0 | t9-title-menus/title-menu-323B5FB0-v5 | 3 | 3 | pack, runtime-1024, runtime-2048 | 2386-2427 | 3511-22184 | title menu; no look review yet |

Total: 51 units / 60 files.

Proposed order (pending root): smallest R1 first per texture, one representative sheet each (J-C1-style, fixed ROI, no auto window), then root look decision per texture before any repair tool.
