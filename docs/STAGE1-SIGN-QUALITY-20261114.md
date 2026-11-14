# Green and pink sign quality — November 14, 2026

Latest continuation: five private class-preserving sign revisions (boards 4, 9, 10, 12 and 26) passed native pack admission and ran through a light 120-second gameplay check. Sparse captures still show uneven quality; the distant green/pink signs and potentially untreated buildings remain open. No full visual acceptance or production installation is claimed. [Actual live results](media/gallery/sign-crisp-v2-live-results.json) and [full 4K/Remix implementation scope](4K-REMIX-IMPLEMENTATION-PLAN.md) supersede the earlier four-board prepared-only snapshot below.

The remaining distinct-sign total is **unknown**. The older register has 37 rows: 29 numbered boards, three posters and five request rows; later W4 work resolves some requests, so these are not five current missing signs. Two numbered entries are an indicator and a backing panel, leaving 30 named sign/poster rows. The 42 artwork entry records include variants and cannot serve as a distinct-sign denominator. Four cube/sign-row texture cells remain known authoring gaps; eleven late-city source/phase records require resolution. These units overlap and must not be summed. [Source-bound census receipt](media/gallery/sign-census-progress-results.json).

**The washed-out signs are unresolved visual defects. They were not accepted as finished HD artwork.** The user's smoother gameplay report does not approve the sign artwork. There is no verified fraction of all signs completed; the existing 42 authored sign entry records are not a complete sign/state denominator.

Claude performed a C-only source/pack audit and built private alternatives without GPU generation. Root inspected the green-sign comparison. The exact native glyph reading is unverified; no new Japanese/Chinese text was invented.

## Identified targets and current assets

- Green three-glyph board 9: exact-region key `0FB1EFC5-F6269484`, native 64 x 48 texels.
- Pink glyph column board 4: `7A652858-600290FE`, native 32 x 64 texels. Its earlier ledger already left blotchy lettering open.
- Red script banner board 10: `67DC56D7-8D0C6ABE`, native 64 x 48 texels; lower lettering remained lumpy.
- Magenta oval board 12: `327E6D9E-89C41FFB`, native 64 x 32 texels.

These four boards share FD81C3C7 atlas layout and palette-phase identities. The installed 964-PNG pack contains older full-page replacements; it has no exact-region overrides for these boards. Its sampled native texel centres remain close to native colors. This is a static source observation, not fresh in-game appearance acceptance.

The larger frozen `frozen-w3-lit-v1` candidate used in the latest gameplay diagnostics contains the W3 exact-region overrides. Their glyph contours are rounded/softened and their shading is pale, which is visible in the comparisons below. Correct alpha-class checks had passed, but those checks did not establish legibility or visual quality. A ledger selection marked USE must not be treated as final visual approval.

Each comparison shows **native source on the left, the current frozen override in the middle, and an unaccepted sharper alternative on the right**. Alpha is displayed using the game's class interpretation, not ordinary image opacity.

![Green board: native, current soft override, private sharper alternative](media/gallery/sign-b09-green-three-glyph-comparison.png)

![Pink glyph column: native, current soft override, private sharper alternative](media/gallery/sign-b04-pink-glyph-column-comparison.png)

## What was created, checked and still needs work

The private `fd-glyph-boards-crisp-v1` alternative applies class-aware EPX/Scale2x four times to each board's source words and CLUT. It uses neighboring source colors/classes and preserves native texel-centre classes. Claude's four-board report records zero new colors/classes and zero native-centre class mismatches. Same output dimensions and keys make private composition possible; they do not establish visual acceptance. Native dither remains busy and can form distracting shapes. This is a sharper source-based alternative, not newly reconstructed HD lettering.

The original W3 files, native inputs and alternatives remain preserved. No alternative was installed, and no new in-game A/B ran during the Remix setup. The next gate is a hash-pinned private composition and a light same-route visual comparison at gameplay size, including the green/pink boards, their palette states, UV edges and motion. Compare improvements per board instead of applying a global sharpening filter or accepting every alternative together. Board 26's yellow-on-magenta glyphs remained outside this initial four-board snapshot.

Local audit: `C:/github/Einhander/remaster-audit/claude-backlog/sign-washout-audit/AUDIT.md`, with `stats.json`, `candidates-report.json`, the source-based builder, comparisons and `frozen/fd-glyph-boards-crisp-v1/manifest.json`. The [published audit receipt](media/gallery/sign-quality-audit-results.json) binds selected local source hashes and the two included comparisons. This does not make the local full artwork pack a portable release.

The [Remix conversion check](RTX-REMIX-SETUP-20261114.md) successfully converted an existing W3 sign to DDS and preserved the original. That conversion did not repair the soft artwork and is not installed in the game. [Overall artwork scope](ARTWORK-STATUS-20261113.md), later stages and normal full-stage acceptance remain incomplete.
