# GPU self-test of the private class-aware mip HD_FS (built by claude-einhander, NOT run)

Run on the 3090 Ti when you schedule it. It opens a hidden 64x64 SDL3 window with a GL 3.3 core context, renders
offscreen only and exits; there is no game, no Remix and no file writes except the JSON.

```
cd C:\github\Einhander\remaster-audit\claude-backlog\class-mip\renderer-v61-classmip\selftest\20261114T110630Z
gl_selftest_classmips.exe TEX_VS.vert HD_FS.frag selftest-result.json
```

- **Exit 0** means all checks passed:
  - link and uniforms OK, no GL error;
  - with class levels the 2-px stroke never vanishes at 8x and 12x minification;
  - no cutout bleed (darkest visible luma at least 90% of the darkest authored luma);
  - point mode is identical with and without class levels;
  - lod 0 is identical to level-0-only.
- **The JSON** also records, for comparison, the current v61 level-0 path (A) and its glGenerateMipmap facade path
  (B) next to the class levels (C).
- **Shader sources** are extracted byte-exact from the patched TU of host run `20261114T110331Z` (patched sha256 ec0ee7032948da4dead6c28b5f748e1e1ce83f9788785f24cad92b9d810bd21a).
