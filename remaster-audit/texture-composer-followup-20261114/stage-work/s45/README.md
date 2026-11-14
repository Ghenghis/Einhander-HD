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

7. **J-B, the S5 strict audit** `strict-audit/20261114T140010Z-s5`, 24 files:
   - 22/24 pass at s/2. `BFC445B0-A132B3B3` fails R2 inside the FX flame box: 386 px / 61 cells at 2048, 89 / 47 at 1024.
   - R1 = R3 = R4 = R5 = 0.
   - Correction: the "primary" columns of the J-A and J-B runs used the s/2 flags, so both folders carry a
     `CORRECTION.txt`.
   - **J-AB2 (corrected)**, runs `strict-audit/20261114T141041Z-s5` (PID 19004) and `20261114T141046Z-s4` (PID 32752):
     - primary (R1 + connectivity-only at bound 1e9) passes for S4 26/26 and S5 24/24;
     - the s/2 diagnostic (bound 0.5) passes for S4 26/26 and S5 22/24. The two S5 failures are the BFC445B0 R2 cases.
     - R5 = 0 everywhere, but no cutout texels exist under the review CLUTs.
8. **Backlog** `BACKLOG-S45.md`, with sources `backlog/` and `page-reuse/`:
   - Beyond the 23 selected keys, the 4bpp content pages left to author are 23 for S4 (750 keys) and 11 for S5 (246).
   - Runtime-composed or raw pages that need capture: 7 for S4 and 22 for S5.
   - 8bpp / 15bpp fallbacks: 17 for S4 and 19 for S5, mostly 1-2 static keys each.
   - Common-member textures are mostly also predicted for Stage 1.
   - `011FFCA6` is an all-zero cleared page shared by S4 and S5, so it needs no art.
9. **Page reuse** `page-reuse/20261114T140003Z/reuse.json`: the best word overlap is S4 2/22 `9B8107D2` vs the authored
   `E8769E55`, at 72% of texels.
10. **w7m2, R-D, R-E and R-F:**
    - `w7m2` adds the class-aware FX blend (`fx_region` docstring/code mismatch found).
    - R-D is a `cm_repair` copy tool for BFC445B0; R-E is Duerer v3 with class-aware FX.
    - R-B now uses class-aware FX.
    - R-F is a DRAFT job for the unauthored member 3/17 pages 768/832/896.

11. **J-D, the S4 transparency probes** `probe-audit/20261114T141200Z-s4` (PID 32752, 73 s):
    - The run is partial: 12 of 13 probes. The skipped probe is effects v3 `AFCCB3B5-70EEEA84` (time budget).
    - The 24 files are audit-only renders, from the frozen masters, of each page's most-cutout candidate CLUT.
    - R1 = R2 = R3 = R4 = 0, with the s/2 flags and connectivity-only both 0: strict and primary pass 24/24.
    - R5 fringe is > 0 on all 24 (median 2.9% of cutout px). Cutout px are raw black, so the pack composer needs an R5
      fill (class-mip renderer proposal, step 1).

12. **J-E, the S5 transparency probes** `probe-audit/20261114T141451Z-s5` (PID 33016, 63 s), complete with 12 probes and
    24 files:
    - primary passes 20/24 and s/2 passes 16/24. Every failure is inside a lane-s5 FX-contract box.
    - Primary FAIL: `1A2ACF78-0DA351E7`, the smoke page, under its 134-pair transparent candidate CLUT. At 2048:
      conn 83 / R4 8 / R3 75 / R2 8098.
    - Primary FAIL: `3D108041-BE3400E6`, shock rings and debris. At 2048: conn 220 / R4 1 / R3 219 / R2 9846.
    - s/2-only fails: `BFC445B0-066C0B81` and `1168CC84-A345AE9E`.
    - The fix is `w7m2` `fx_region(class_aware=True)` in R-A and R-E, re-audited on these exact probe keys.
    - R5 fill is the composer's job (root decision, msg_80aa44e1). s45 ships no filled copies.

13. **Keyed capture and admission checklist** `checklist/20261114T143022Z/CHECKLIST-S45.json` and `.md`:
    - Per key it gives the page, depth, CLUT xy, PAL, phase, s45 audit and probe status, competing CLUTs and missing
      evidence.
    - Stage 4: 11 gate keys, 12 panorama keys, 34 phase holds, 25 unauthored pages.
    - Stage 5: 12 gate keys, 15 panorama keys, 52 phase holds, 19 unauthored pages, and 15 Duerer 8bpp items (12
      candidate keys and 3 sub-images).
    - Run `20261114T142955Z` is superseded because it labelled CLUT row 509 as runtime-written.

14. **J-F, the option-2 class snap** `repairs/J-F-20261114T143602Z.json` (runner PID 32968 on CPU 13, 8.0 s, all exit
    codes 0):
    - It repaired copies of the 4 failing J-E probe keys; all 8 files then pass both policies.
    - Visible RGB is unchanged (proof field and independent diff).
    - A launch earlier at 14:33:52Z stalled on Git Bash quoting and ran nothing. Its empty `repairs/J-F.log` is kept.

## Pending on CPU grants, in order

J-D2 (the skipped S4 probe: `--stage 4 --sets s4-effects-2-13-v3 --pages AFCCB3B5`), J-C (8bpp static ranking), V1 / V2 (w7m
equivalence) and V3 (w7m2 with class_aware off), R-D (cm_repair copy), R-A / R-B / R-C / R-E repair builds, R-F (after
S5-5).

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
| `backlog/20261114T135849Z/backlog.json` | `f23bca51ee0cd710550e80172cab1bd49c7329a2a6189b7c50b6e1508bed2d31` |
| `BACKLOG-S45.md` | `0b01d37d7777e619e5c0bae48e9ff4ef69aecf8c621939bea597cca9f757e552` |
| `checklist/20261114T142955Z/CHECKLIST-S45.json` | `a42255c1cc096c8452957f47da4a24d1e01d2e7b308816cfb0c33e95c57cbe9f` |
| `checklist/20261114T142955Z/CHECKLIST-S45.md` | `e73ed91b07dce77c3b72efbd32ff0d83ca8e126a3736b7d77832a18ba1159bc3` |
| `checklist/20261114T142955Z/SUPERSEDED.txt` | `acd97783e89504f208e8b2cb166cb62d1f394bbbfbfd7f9d71cb2bbdcdd5d704` |
| `checklist/20261114T143022Z/CHECKLIST-S45.json` | `88b24b695c5e88e5c037b27116e2ede211f8e42a49bd049feaba671dc7e5829e` |
| `checklist/20261114T143022Z/CHECKLIST-S45.md` | `336a02da7dd672813f40039907b90803975488638abc353241e125943529a041` |
| `clut-coverage/20261114T135223Z/coverage.json` | `549f1888aa2e1362612f172f961f0784ecfb645ab3dcc6c9646acc392d2d9efe` |
| `clut-coverage/20261114T135223Z/SUPERSEDED.txt` | `ba35829d211828ef129f768c3fff8121551f919229c88b57e141b1f8f7a8cb5b` |
| `clut-coverage/20261114T135254Z/coverage.json` | `26f22df2dbd9ae1ee2796e5586597f67fde24393c495f0cdcfea02bd3b073be0` |
| `DUERER-8BPP-PLAN.md` | `d948312f66477b37e800b37e35630fb4fffd110da50ae54bf6634b010a7418cf` |
| `page-reuse/20261114T140003Z/reuse.json` | `9c2e3d3144bf98c615207a0df92aa50dd5643d253ccbd07ff691c10505ced40f` |
| `PANORAMA-05E1881C-OWNERSHIP.md` | `a69606534a800666d77f2d89110e1c5c5083af05dafaf48721c7584554d5d210` |
| `probe-audit/20261114T141200Z-s4/pid.txt` | `7a3c66289c021d1c3f91984e0db52a0ccf5a5f0a92971509cd8746bb58f38956` |
| `probe-audit/20261114T141200Z-s4/result.json` | `d7ecb2a97318ff3c38c61755a94672b8dad79d2480e381ecd0e2394e765626d8` |
| `probe-audit/20261114T141451Z-s5/pid.txt` | `43545c11d3204218fe0015f1342ad7d73422f01b1ec8082f7177b06a0b06a2bb` |
| `probe-audit/20261114T141451Z-s5/result.json` | `9e138d586edd945f9c340ba990717b72e2ab485f2e81d187fa4defbaf95bbf37` |
| `probe-audit/J-D-stage4.log` | `74c493ee31dd18aa4a62482fc22ae8d548492e706d8951dbca63b15aa899d44b` |
| `probe-audit/J-D.start` | `ab3d0479f815f37cbf399b91123e778b203aa4bb0de9579186f92a5bb55db5f9` |
| `probe-audit/J-E-stage5.log` | `27f98bbaedf189dfd5a96804ec4af9f24587633ff963db69642f07582391ed19` |
| `probe-audit/J-E.start` | `b24167ff5a3c2c78c1967b73a88ffd551463ac7d4f023b888edc0141e8e9cbe1` |
| `REPAIR-PROPOSALS.md` | `6b51133edc87def102182b633f8e8a519ea81bddb8c0a1ed66bf4fce9aa0fc2a` |
| `repairs/20261114T143555Z-cmrepair-1A2ACF78-0DA351E7/pid.txt` | `199247f5fcc05095a4ba6fdc41c7413086f127a59ad742c7e2bca2a83d6e0713` |
| `repairs/20261114T143555Z-cmrepair-1A2ACF78-0DA351E7/result.json` | `b8195b19c22f29af273f439995392fa308357d9c22879e8c0302c71dfc0a1634` |
| `repairs/20261114T143557Z-cmrepair-3D108041-BE3400E6/pid.txt` | `be88164736e72c02a4a8e9ed740950dbb675ed8d6f6f463830d95a226605bc77` |
| `repairs/20261114T143557Z-cmrepair-3D108041-BE3400E6/result.json` | `2741974e8b504f7d244a76c6f3827e08a5df5616bca29d1036111e2ce9f1f8da` |
| `repairs/20261114T143559Z-cmrepair-BFC445B0-066C0B81/pid.txt` | `c36e8929b43c867d5fdd02f7b786979408cbdd84c6ac06b1f63f702959cc5f45` |
| `repairs/20261114T143559Z-cmrepair-BFC445B0-066C0B81/result.json` | `7d1e15516429717b0e3d96683117edf708c37d7f6dc158d000e8958c4517a1f1` |
| `repairs/20261114T143601Z-cmrepair-1168CC84-A345AE9E/pid.txt` | `efb9567b9d471a2bc96841a362fb52eacf15e756407129aa8c01d3c44f0e088a` |
| `repairs/20261114T143601Z-cmrepair-1168CC84-A345AE9E/result.json` | `8aad5fb8d2741d892a66af8c7e07b44ddb7116c82f02011a45a6ff4a9ac21fcd` |
| `repairs/J-F-20261114T143602Z.json` | `5e5f8e06d47ff37c7522ce971e6372e6791fe720b82278691c364220e15e51bb` |
| `repairs/J-F.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `repairs/J-F2.log` | `b4ac6134581918a6897c03800621d9d426a57d7ae299f9d1348d4913438da764` |
| `repairs/J-F2.log.err` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `repairs/jobs/s4-enemies-2-13-v3-s45.json` | `46870338379edfda68f9d4b804a74529ea9748d11da9480c83de0c67382597c0` |
| `repairs/jobs/s5-duerer-armour-v3-s45.json` | `e5575614c02bfe36d87e6b776bfa37e3f64837795d8ef1358d3b98048a3ea414` |
| `repairs/jobs/s5-effects-3-6-v2-s45.json` | `02b5635dfc087943a53b3c81dac0d2ea49061699e5fb86da8fa177512f8069c2` |
| `repairs/jobs/s5-member3-17-ext-v1-s45.json` | `6e6fecbc8806ad25756943cfe1f80e0498bd835cfa1bce4b28af668f59bb8b6a` |
| `repairs/jobs/s5-world-3-1-v3-s45.json` | `168082ccf68e5b6f876749970aaca2f75c6464d6507dfc191251df33367c1fd2` |
| `source-map/20261114T133831Z/source-map.json` | `14bf34419adf0c3129b52fc5dd06a4c9aec4add68dcf96fc8ec022ab2645d0cd` |
| `strict-audit/20261114T135014Z-s4/CORRECTION.txt` | `b54b01bb814879fd6e58bb91da1727fcdd9d15dc1b42d5d31eedaf552a9b2d48` |
| `strict-audit/20261114T135014Z-s4/result.json` | `15682e54baa071823b3856283c28f5f478df2426308ab4259675c5076f7df8d8` |
| `strict-audit/20261114T140010Z-s5/CORRECTION.txt` | `b54b01bb814879fd6e58bb91da1727fcdd9d15dc1b42d5d31eedaf552a9b2d48` |
| `strict-audit/20261114T140010Z-s5/pid.txt` | `02c575d1c4fb9f7322dae246f740412de471075b3da6b0e5cacec4011c9f89dd` |
| `strict-audit/20261114T140010Z-s5/result.json` | `404db16071154b2381b5432a573f41ffe8ccc0aa0f2f1abd8665ef8815bc8c88` |
| `strict-audit/20261114T141041Z-s5/pid.txt` | `b7f9aaa95fdc157c962a76190193fe190e1f199366488ac0a51dba70a43e1db4` |
| `strict-audit/20261114T141041Z-s5/result.json` | `2bf3db571e4b8a2d7af76223e7016ec78a178e2cd203711df556488cf4615b4d` |
| `strict-audit/20261114T141046Z-s4/pid.txt` | `703f92b4b5facf1e7efc7d1fa60fdede59ad65f85279f95028cac996c7cbe094` |
| `strict-audit/20261114T141046Z-s4/result.json` | `2705453ddf8bb8ef988255b85924671f2efef239563585a69f13fdc195d9c0ec` |
| `strict-audit/J-A-stage4.log` | `789c8f9c39b92951fb61dd43ec7d405e69c69d0ce6b37c62bc014d39155f0324` |
| `strict-audit/J-AB2.log` | `4dbeaabe4b0911c5b1dd804c06d8ac3ceb2255d17857786d6931a0a834e166be` |
| `strict-audit/J-B-stage5.log` | `8178684aea9e6208f98d82c8bdb63e80a3418c076035744527f1e7dbb1f6a225` |
| `tools/make_w7m.py` | `ff4e86b29321e54f80ba46d15301424664d001dc3cd92ab3e7c513ba1a349f91` |
| `tools/make_w7m2.py` | `7a940a56efcf796671e5442e512f6c4bc7958b9171de968979f096c4a11f1b44` |
| `tools/README-head.md` | `84c5f289ba8295de3f725f2b0c0f7e3881ea1e80f38e4f785332e4fb0c8dc5d2` |
| `tools/s45_8bpp_rank.py` | `aae576beccf27a110256dd0ab44f07c8ae191ba1f293c55e3b7b91df0d2f1b33` |
| `tools/s45_backlog.py` | `7929947c6044e832d2061c24bbf6180bf81c535c7b1cd34edb9d8a7374015200` |
| `tools/s45_backlog_doc.py` | `8cdf80bc525a345efe4156525de705fe1725ae324834299fb13087b744f472e7` |
| `tools/s45_checklist.py` | `935e3068845017efe0186191db8f2a1453e9da8bf5c468d2aa256340d78447f8` |
| `tools/s45_clut_coverage.py` | `66b486188061cee69b9816aae3223011f5909fe101902bcd99709f83f7a1875b` |
| `tools/s45_cm_repair.py` | `6a54dda22ab5c7e5c2f337381124b7d49ac18be58bb640748fbc4cbdbcf7e2a9` |
| `tools/s45_jf_run.py` | `07a52a8806c83387cae2606169353652a4d812e9d4463f6040d052bb9d3645ee` |
| `tools/s45_page_reuse.py` | `e0ea0635b9413941d60f1c8745f49f4d362823d57a015946af11ff52d979e735` |
| `tools/s45_probe_audit.py` | `d8827f7b4c377ea69bce659771060cd0a37d576f7251e70c552826d1347c679d` |
| `tools/s45_readme.py` | `5e18f2df5007c9eb7877d99e02c679dcd4938f9e18844d5b6ae9a4dbc52e6ed4` |
| `tools/s45_source_map.py` | `965d2b6737f07c45ed60e4f51095b97a37fa4396d5a3bfd6a6c8527bd91be48a` |
| `tools/s45_strict_audit.py` | `f920acb7fcb2a100cdd338b6d6055ff712cf1ac5b15e590c444c19630369970a` |
| `tools/s45_w7m_verify.py` | `33bfd9bd79a50e1262885ccd054870756b099fa013eb684b3341e1f220a4e462` |
| `tools/w7m/build_w7.py` | `d3e09d2e66aaa3f85604d32c8d7492b4247e5f63bbb0c21e4d8a78c0a304f0dc` |
| `tools/w7m/freeze_w7.py` | `7036a638eb8eada34eea83d6876a947781759d0327406ad27a789ab2997d576e` |
| `tools/w7m/glyph_check.py` | `8fe258410fbe8a77aa64750b5ffb4c24570591f09beeb52a785ab24bf25d221a` |
| `tools/w7m/lowprio.py` | `b0fc5d59b8ae7030312ea5173680ed057c4f4ea42b64189accbfcb6a07f30d9d` |
| `tools/w7m/make_w7m.py` | `ff4e86b29321e54f80ba46d15301424664d001dc3cd92ab3e7c513ba1a349f91` |
| `tools/w7m/MERGE-RECORD.json` | `940acd85bb230baa93f2784d87330cc421500371060f42716caf96aa919baa94` |
| `tools/w7m/twinkle_sim.py` | `159f38f15626bf9b61dc23ec39613ce51f8ae211f9369d43871366bf2d1f58d3` |
| `tools/w7m/verify_frozen.py` | `b10b9f4b32061de3b29d65309208ee83c76e0f7176911ff8ebf2210d6bd006b3` |
| `tools/w7m/w7lib.py` | `80de86c886bfe770b3168b3202e2c595748970913f37381d94e5dcb01ed3f8ad` |
| `tools/w7m2/build_w7.py` | `d3e09d2e66aaa3f85604d32c8d7492b4247e5f63bbb0c21e4d8a78c0a304f0dc` |
| `tools/w7m2/freeze_w7.py` | `7036a638eb8eada34eea83d6876a947781759d0327406ad27a789ab2997d576e` |
| `tools/w7m2/glyph_check.py` | `8fe258410fbe8a77aa64750b5ffb4c24570591f09beeb52a785ab24bf25d221a` |
| `tools/w7m2/lowprio.py` | `b0fc5d59b8ae7030312ea5173680ed057c4f4ea42b64189accbfcb6a07f30d9d` |
| `tools/w7m2/make_w7m.py` | `ff4e86b29321e54f80ba46d15301424664d001dc3cd92ab3e7c513ba1a349f91` |
| `tools/w7m2/make_w7m2.py` | `7a940a56efcf796671e5442e512f6c4bc7958b9171de968979f096c4a11f1b44` |
| `tools/w7m2/MERGE-RECORD.json` | `940acd85bb230baa93f2784d87330cc421500371060f42716caf96aa919baa94` |
| `tools/w7m2/MERGE-RECORD2.json` | `56c043f82d58ee4fda4c9b530b0b1ea070ea47945975f9f65eb0c38024a3b1cc` |
| `tools/w7m2/twinkle_sim.py` | `159f38f15626bf9b61dc23ec39613ce51f8ae211f9369d43871366bf2d1f58d3` |
| `tools/w7m2/verify_frozen.py` | `b10b9f4b32061de3b29d65309208ee83c76e0f7176911ff8ebf2210d6bd006b3` |
| `tools/w7m2/w7lib.py` | `5b3bfd706990dc0bb2822b912121e5ebe27596bd53f4b19fa721204105e8c2fe` |

Run folders also hold provenance copies of the tool, class_mip.c/.h and the compiled DLL; `tools/w7m-r0-unused/` is the superseded, never-used first merge.
