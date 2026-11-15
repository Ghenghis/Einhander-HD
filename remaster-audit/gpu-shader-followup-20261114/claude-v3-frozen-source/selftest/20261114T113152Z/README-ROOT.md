# GPU self-test v3 of the private class-aware mip shader + upload path (built by claude-einhander, NOT run)

Run on the 3090 Ti when you schedule it. It opens a hidden 64x64 SDL3 window with a GL 3.3 core context, renders
offscreen only and exits; there is no game, no Remix and no file writes except the JSON.

```
cd C:\github\Einhander\remaster-audit\claude-backlog\class-mip\renderer-v61-classmip\selftest\20261114T113152Z
gl_selftest_classmips.exe TEX_VS.vert HD_FS.frag selftest-result.json
```

- **Exit 0** means every scoped check passed (DESIGN-V3.md, after your FAIL N/class-mip-gpu-r1 of the v1 build):
  - link, uniforms and FBO OK, no GL error;
  - the stroke never vanishes for m <= s (2, 4, 8) on the facade path (C) AND the new non-facade path (N);
  - no cutout bleed for m >= 2 on C and N;
  - point mode is unchanged, and lod 0 is identical to level-0-only;
  - the level-0 R5-filled variant D has no lod-0 fringe (that fringe is a level-0 content issue);
  - fail closed on real GL: an injected wrong-size level gives HDCM_E_GL after 1 verified level, and the restore
    leaves MAX_LEVEL 1000.
- **Reported only:** m = 12 (> s), lod-0 darkness of A/B/C/N, the A/B comparison numbers, and the GPU time to upload
  and verify a 2048^2 prepared level set through the renderer's callback.
- **Shader sources** are extracted byte-exact from the patched TU of host run `20261114T113027Z` (patched sha256 d7b0fa963ce97850dfc30774df5a4c9a14a6c31e66af15f47ce83c1914cb5aaf).
