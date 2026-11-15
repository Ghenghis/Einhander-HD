# Menu / HUD state register `20261114T152157Z` (s45, EIN-MENU-HUD-20261114)

Delivered = carried by a frozen candidate folder. That is not installed, not live-accepted and not class-validated.
Live evidence: the closed 600 s Stage 1 census (`docs/media/gallery/stage1-ui-results.json`).

| state | textures | keys | delivered | s45-only candidate | undelivered (region-covered / legacy v13 only) | GL-submitted live | behaviour still open |
|---|---|---|---|---|---|---|---|
| boot splash | 1AEAD6A5, 7F7452F9, 4E783C96 | 3 | 3 | 0 | 0 (0 / 0) | 0 | boot order before pack activation |
| title screen / logo / footer | 282438F3, 1D953D67, 8E1A509D | 50 | 50 | 0 | 0 (0 / 0) | 0 | attract/demo loop and return |
| title menu (GAME START / CONFIGURATION / FILE OPTION / GALLERY) | 323B5FB0 | 1 | 1 | 0 | 0 (0 / 0) | 0 | cursor highlight / STP blend states |
| fighter / armament selection | D0365088, 1AD90FC9, 3DA22883, 41E75A55, 7D2C7E3C, AAE3C8F2, 57FFDED8, EF372CD7, ECFB77E3 | 19 | 19 | 0 | 0 (0 / 0) | 0 | highlighted CLUT states, selector arrows (key unproven) |
| configuration / file option / name entry / rankings | 2C6866AA, 8BE06E98, 8D0FCF8A, 9D8DF52A, AD49126E, C544AC0D, B77B98B9, AEE859DC | 38 | 38 | 0 | 0 (0 / 0) | 0 | every page of Configuration, File Option save/load, name grid, ranking table |
| instructions / demo play | E6B65424 | 3 | 0 | 0 | 3 (0 / 3) | 0 | demo attract text |
| in-play HUD (score, ammo, weapon names, lives, hit gauge, arrows) | BDAE4156, E1F18F98, 786B98BF, 2C781811, 921FC559, D050AD1B, 5C02D3C1, 913A6603, 913FE978, 5F101F62, AAA5C104, E4774D79, 44C16454, 8BA3BB4D, B24C6DA2, B2473AF8 | 142 | 116 | 0 | 26 (11 / 26) | 9 | weapon pickup/swap wordmarks, lives loss |
| pause / CONTINUE? / countdown / QUIT | DD0B6963, BDAE4156 | 8 | 8 | 0 | 0 (0 / 0) | 1 | pause menu, continue countdown, quit-to-title |
| HUD fade overlays (stage-end / boss-kill) | BDAE4156, D050AD1B, 5C02D3C1, 913A6603, 913FE978, 5F101F62, AAA5C104 | 157 | 24 | 133 | 0 (0 / 0) | 0 | 157 historical fade aliases: palette phases |
| game over | 5125FF82 | 1 | 1 | 0 | 0 (0 / 0) | 0 | game over -> title |
| results / evaluation / grades | 8E1A509D, 48F8001A, FCCD2514 | 51 | 51 | 0 | 0 (0 / 0) | 0 | Total / Field / Fight evaluation pages |
| return to title | - | 0 | 0 | 0 | 0 (0 / 0) | 0 | behaviour only: reuses the title textures; not observed live |

Observed live: Total Evaluation, Field Evaluation / Shot Down graph, Exit to native opening movie, Finite Start skip to native story text. Return to title verified: False.

## Typography keys with no frozen delivery and no s45 candidate: high 26, normal 46

- high `44C16454-72FBA1C5` (native source NOT archived): HUD small numeral strip (player-local ammo popup candidate)
- high `8BA3BB4D-00F61447` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-00F61447 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-17761414` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-17761414 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-190A55AD` (native source ready): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-36D62A31` (native source ready): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-87D74FCC` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-87D74FCC uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-91478949` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-91478949 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-C288EEEE` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-C288EEEE uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-D2D9B701` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-D2D9B701 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-D6B2BFF7` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-D6B2BFF7 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-E0AE221F` (native source ready): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-E20902CB` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-E20902CB uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-EE4896FB` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-EE4896FB uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-EF6E99C9` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-EF6E99C9 uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `8BA3BB4D-FEB2DF2F` (native source ready; region-covered by w4-signs-hud/hud-lives-glyphs-832p256-w4-v1:B2473AF8-FEB2DF2F uv [0, 74, 64, 93]): HUD Hit Gauge numeral/multiplier/HIT glyph rectangle [0,64,64,96] on mixed page
- high `B24C6DA2-00F61447` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-17761414` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-87D74FCC` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-91478949` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-C288EEEE` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-D2D9B701` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-D6B2BFF7` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-E20902CB` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-EE4896FB` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-EF6E99C9` (native source ready): HUD arrow gauge strip (graphic, not lettering)
- high `B24C6DA2-FEB2DF2F` (native source ready): HUD arrow gauge strip (graphic, not lettering)

## Undelivered keys per state

- instructions / demo play: `E6B65424-4C1DD349`, `E6B65424-611C5290`, `E6B65424-97713DC6`
- in-play HUD (score, ammo, weapon names, lives, hit gauge, arrows): `44C16454-72FBA1C5`, `8BA3BB4D-00F61447`, `8BA3BB4D-17761414`, `8BA3BB4D-190A55AD`, `8BA3BB4D-36D62A31`, `8BA3BB4D-87D74FCC`, `8BA3BB4D-91478949`, `8BA3BB4D-C288EEEE`, `8BA3BB4D-D2D9B701`, `8BA3BB4D-D6B2BFF7`, `8BA3BB4D-E0AE221F`, `8BA3BB4D-E20902CB`, `8BA3BB4D-EE4896FB`, `8BA3BB4D-EF6E99C9`, `8BA3BB4D-FEB2DF2F`, `B24C6DA2-00F61447`, `B24C6DA2-17761414`, `B24C6DA2-87D74FCC`, `B24C6DA2-91478949`, `B24C6DA2-C288EEEE`, `B24C6DA2-D2D9B701`, `B24C6DA2-D6B2BFF7`, `B24C6DA2-E20902CB`, `B24C6DA2-EE4896FB`, `B24C6DA2-EF6E99C9`, `B24C6DA2-FEB2DF2F`
