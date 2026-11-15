# s45: Einhander Stages 4-5 worker outputs (`claude-einhander-s45`)

Native Claude Code session "Einhander Stages 4-5":
- desktop session `local_23875684-e1a4-4e97-971e-d9abd3f77f52`;
- CLI session `3cf72e9f-f6a6-4f00-9cf2-66f68dea820d`;
- worktree `C:/github/Einhander/.claude/worktrees/einhander-stages-4-5-f992fe`.

Tasks EIN-S4-WHOLE-CELL-20261114 and EIN-S5-WHOLE-CELL-20261114 were claimed at 13:30Z and picked from the durable queue
at 13:35Z. The recovery checkpoint is `.hermes3d_orchestrator/continuity/claude-einhander-s45.json`.

Rules this folder follows:
- **CPU only.** The 3090 Ti is user-reserved, and every heavy job runs only on an individual grant from `codex-einhander`.
- **Read-only inputs.** Frozen lanes, static exports, runtime source and failed evidence are never edited.
- **Not acceptance.** Nothing here is installed, integrated or accepted. Every key is predicted-static.

## Results so far (newest last)

1. **Source map** `source-map/20261114T133831Z/source-map.json`: 0 issues.
   - S4 has 11/11 unique selected keys (effects v2/v3 are alternatives) and S5 has 12/12. Both equal the checklist gate
     lists.
   - Renderable-later: 233 / 245. Palette-hold: 23 / 44, plus the all-zero `190A55AD` keys.
   - Words and CLUT CRCs are proven, and the manifests match lane-readiness.
2. **Panorama 05E1881C** `PANORAMA-05E1881C-OWNERSHIP.md`: NOT BUILT.
   - The words are byte-identical in both stages. The doc proposes a single owner (s45) and one master, and gives the
     exact capture request.
   - The S5 "ramp" CLUTs are 16-word slices of the 8bpp CLUT rows 509-511.
3. **Duerer 8bpp** `DUERER-8BPP-PLAN.md`.
   - Runtime key rule: CRC32 of 128 columns x 256 rows, read from `hd_native_page.h`.
   - The exact static depth-1 keys decompose into the Duerer 4bpp half-pages.
   - The doc separates assumptions from proofs, refines the S5-5 capture requirements, and gives the authoring plan.
4. **J-A, the S4 strict whole-cell audit** `strict-audit/20261114T135014Z-s4/result.json`:
   - 26/26 files pass strict and primary checks, R5 = 0, and every PNG sha256 equals the manifest.
   - Limit: all review CLUTs are opaque. 8/11 keys are single-class, and no key has a cutout texel.
5. **CLUT class coverage** `clut-coverage/20261114T135254Z/coverage.json`:
   - 186 static candidate keys on the 23 selected pages create cutout texels; every review CLUT has none.
   - 5 pages have a more-paired candidate CLUT than their review CLUT.
   - Run `20261114T135223Z` is superseded (bugs); it is kept as failed evidence.
6. **Repair proposals** `REPAIR-PROPOSALS.md`: three isolated repair jobs (R-A, R-B, R-C) and the merged tool copy
   `tools/w7m`. The byte-identity checks V1/V2 must pass before any repair build.

## Pending on CPU grants, in order

J-B (S5 strict audit), J-D / J-E (transparency probes S4 / S5), J-C (8bpp static ranking), V1 / V2 (w7m equivalence),
R-A / R-B / R-C (repair builds).

## Blocked on the live capture (Codex)

- the S4 / S5 stock-first runs: key / CLUT confirmation for 23 selected keys, 478 renderable-later keys and 25 panorama
  keys;
- the 05E1881C pan, CLUT dump and stills;
- the S5-5 8bpp Duerer draws;
- S4-4 sprite sizes and the S5-4 disk phases;
- the look decisions (user).

## Files (sha256)

| file | sha256 |
|---|---|
| `clut-coverage/20261114T135223Z/coverage.json` | `549f1888aa2e1362612f172f961f0784ecfb645ab3dcc6c9646acc392d2d9efe` |
| `clut-coverage/20261114T135223Z/SUPERSEDED.txt` | `ba35829d211828ef129f768c3fff8121551f919229c88b57e141b1f8f7a8cb5b` |
| `clut-coverage/20261114T135254Z/coverage.json` | `26f22df2dbd9ae1ee2796e5586597f67fde24393c495f0cdcfea02bd3b073be0` |
| `DUERER-8BPP-PLAN.md` | `d948312f66477b37e800b37e35630fb4fffd110da50ae54bf6634b010a7418cf` |
| `PANORAMA-05E1881C-OWNERSHIP.md` | `a69606534a800666d77f2d89110e1c5c5083af05dafaf48721c7584554d5d210` |
| `REPAIR-PROPOSALS.md` | `e45ed3af3c4aa4cfbaba4824d1a334972e3e905980ef5fbe711a8fbb722d790e` |
| `repairs/jobs/s4-enemies-2-13-v3-s45.json` | `46870338379edfda68f9d4b804a74529ea9748d11da9480c83de0c67382597c0` |
| `repairs/jobs/s5-effects-3-6-v2-s45.json` | `9f264634d6ef7e020b5860c2bcf09450778f14453e7e3047fbd4e87f2285d60b` |
| `repairs/jobs/s5-world-3-1-v3-s45.json` | `366ea67d4a11edb1496edac6b4f4180e8675f23df7b23cd5f51b3e84c2a39ae5` |
| `source-map/20261114T133831Z/source-map.json` | `14bf34419adf0c3129b52fc5dd06a4c9aec4add68dcf96fc8ec022ab2645d0cd` |
| `strict-audit/20261114T135014Z-s4/result.json` | `15682e54baa071823b3856283c28f5f478df2426308ab4259675c5076f7df8d8` |
| `strict-audit/J-A-stage4.log` | `789c8f9c39b92951fb61dd43ec7d405e69c69d0ce6b37c62bc014d39155f0324` |
| `tools/make_w7m.py` | `ff4e86b29321e54f80ba46d15301424664d001dc3cd92ab3e7c513ba1a349f91` |
| `tools/s45_8bpp_rank.py` | `aae576beccf27a110256dd0ab44f07c8ae191ba1f293c55e3b7b91df0d2f1b33` |
| `tools/s45_clut_coverage.py` | `66b486188061cee69b9816aae3223011f5909fe101902bcd99709f83f7a1875b` |
| `tools/s45_probe_audit.py` | `98ac13f558a02b3479bb06a60535c6ad56b15f8900a153e09d4fffc25e839d65` |
| `tools/s45_source_map.py` | `965d2b6737f07c45ed60e4f51095b97a37fa4396d5a3bfd6a6c8527bd91be48a` |
| `tools/s45_strict_audit.py` | `a6ea99c58108467f7c0a63a8938f7b31672dde5ad0a095384e5bc180191eeab9` |
| `tools/s45_w7m_verify.py` | `33f3cf1c45c43e2fc2e30e16b5760d65884a33c11fdca2fa9e9b2783dac3d89c` |
| `tools/w7m/build_w7.py` | `d3e09d2e66aaa3f85604d32c8d7492b4247e5f63bbb0c21e4d8a78c0a304f0dc` |
| `tools/w7m/freeze_w7.py` | `7036a638eb8eada34eea83d6876a947781759d0327406ad27a789ab2997d576e` |
| `tools/w7m/glyph_check.py` | `8fe258410fbe8a77aa64750b5ffb4c24570591f09beeb52a785ab24bf25d221a` |
| `tools/w7m/lowprio.py` | `b0fc5d59b8ae7030312ea5173680ed057c4f4ea42b64189accbfcb6a07f30d9d` |
| `tools/w7m/make_w7m.py` | `ff4e86b29321e54f80ba46d15301424664d001dc3cd92ab3e7c513ba1a349f91` |
| `tools/w7m/MERGE-RECORD.json` | `940acd85bb230baa93f2784d87330cc421500371060f42716caf96aa919baa94` |
| `tools/w7m/twinkle_sim.py` | `159f38f15626bf9b61dc23ec39613ce51f8ae211f9369d43871366bf2d1f58d3` |
| `tools/w7m/verify_frozen.py` | `b10b9f4b32061de3b29d65309208ee83c76e0f7176911ff8ebf2210d6bd006b3` |
| `tools/w7m/w7lib.py` | `80de86c886bfe770b3168b3202e2c595748970913f37381d94e5dcb01ed3f8ad` |

Run folders also hold provenance copies of the tool, class_mip.c/.h and the compiled DLL; `tools/w7m-r0-unused/` is the superseded, never-used first merge.
