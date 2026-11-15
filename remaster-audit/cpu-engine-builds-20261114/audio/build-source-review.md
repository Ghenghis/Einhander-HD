# Private v69 audio-integration build proposal (source only; nothing compiled or linked)

This proposal answers main's msg_576f15ace091bc0a.

**What v69 is:** the verified v68 recorder-reserve executable (`5c1436ff…`), relinked with **exactly two** objects rebuilt to carry the combined audio telemetry r1 changes, which already passed both host fixtures (Dr2 and Dr5).

**What v69 is not:** it is not installed, launched or released, it opens no SDL device, and there is no listening test. It makes no audible-fix or performance claim.

## Source map (all pins full sha256; preimages checked)
| object in v68 link | v68 source (preimage) | v69 source | header |
|---|---|---|---|
| `sampling-build-v58-frame-phases/main.cpp.obj` `911b117a…` | v58 `main.cpp` `5c94d2dd…`; v58 build.json `7f4640f6…` records its compile command (`arguments`, clang++, cwd `C:\github\Einhander`) | `audio-telemetry-combined-r1/main.cpp.proposed` `8022b148…` | combined `recomp_audio_drc.h.proposed` `c84258e1…` (replaces canonical `70cb5acd…`) |
| `sampling-build-v67-decode-identity-r3/debug_server.c.obj` `1947bca3…` | v67 `src/debug_server.c` `10e31f8d…`; v67 build.json `85deaaf3…` (`args`, clang, `-MD`) | `audio-telemetry-combined-r1/debug_server.c.proposed` `b50aef2a…` | does not include the header (checked) |
| the other 153 inputs: v68 `gpu_gl_renderer.c.obj` `b38a4a33…`, `psx_sdl_audio.cpp.obj` `ee778e96…`, `libSDL3.a` `5316825f…`, etc. | v68 build.json `21944d69…` `link_inputs` | **unchanged**, each re-hashed at link time | — |

- **Change lineage** (each step generated from pinned bytes by exact single-match edits): v58 `5c94d2dd` → gap proposal `2b5ec718` → combined r0 `57f915a4` → combined r1 `8022b148`. The debug chain is v67 `10e31f8d` → `2d54ae68` → `b080…` → `b50aef2a`. The header chain is `70cb5acd` → `7de21fb8` → `0022c3bc` → `c84258e1`.
- **Focused diffs to review** (already published in `audio-telemetry-combined-r1/` and `audio-telemetry-combined/`): `main.cpp.vs-v68-original.diff` `0272c42a…`, `debug_server.c.vs-v68-original.diff` `247f644c…` and `recomp_audio_drc.h.vs-v68-original.diff` `1b078ceb…` (all against the original v68 sources); plus the r1-over-r0 deltas `*.vs-r0.diff`.
- **Link:** cwd `C:\github\Einhander\windows-x64\build-ss8c`; `clang++.exe -O3 -static -Wl,--stack,67108864 @rsp -o exe`. The v68 rsp `c2b737c6…` (192 lines) contains each replaced object path exactly once. The rest is unchanged: the CMake-relative `.a` files, `libSDL3.a`, `libz.a` and the `-l` system libraries.
- **SDL closure** is real, not a stub. The headers come from `-isystem …/latest/deps/include` and are captured by the depfiles. The import/object side is the retained `psx_sdl_audio.cpp.obj` plus `libSDL3.a`, both hash-checked.

## Read-only preflight (done now; no compiler)
- All 12 source, object and build-record pins match, and all 5 toolchain files match: `clang.exe` = `clang++.exe` `a8b7a614…`, `clang-22.exe` `870a1393…`, `libclang-cpp.dll` `df189bb4…` and `libLLVM-22.dll` `1e2aed17…`.
- **All 155 v68 link inputs match their recorded sha256 today.**
- **v67 debug depfile:** 403 dependencies, all present. 286 of them resolve under the toolchain's `C:\Users\Admin\AppData\Local\retcomm\toolchains\cmake-clang-v1\.staging-host\{lib,inc}` system headers. The audio header is not included.
- **v58 `main.cpp` was compiled without `-MD`, and its includes point at another worktree:** `C:\github\Einhander-wt\upload-index-hitch\windows-x64\psxrecomp\runtime\{include,src}`. That tree still exists, its HEAD is f453222 and its working tree is clean, and its `recomp_audio_drc.h` is `70cb5acd…`. Its full include closure is **unrecorded**, so the build reproduces it before trusting it (phase R below).

## Driver `build_v69_audio.py`: two separately granted phases, fail closed
**Phase `repro`:** recompiles the unmodified v58 `main.cpp` and v67 `debug_server.c` **in place**, so the original paths are kept.
- It uses their exact recorded arguments. Only `-o` and `-MF` point to the new output directory; main gets an added `-MD -MF`, which does not change the object.
- **Both objects must be byte-identical** to the v68-linked `911b117a…` and `1947bca3…`.
- Every depfile dependency is hashed.
- `main` must include exactly one `recomp_audio_drc.h`, and it must be `70cb5acd`. `debug` must include none.
- The original sources are re-hashed afterwards.

**Phase `build`:** requires a PASS repro manifest, given by path and sha256.
- It makes read-once hashed copies of the three changed files.
- It compiles the copies with the same arguments. `main` gets one leading `-I<copied header dir>`.
- **Each depfile closure must equal the repro closure, with identical hashes, except for the source file and `recomp_audio_drc.h`.** This catches any include-order shift caused by moving the source file.
- It links using the v68 rsp with only the two object paths replaced, after re-hashing the 153 retained inputs against v68's records.
- It records the v69 executable's sha256 and size. Never installed or launched.

**Receipts:** per child, it records step, argv, cwd, pid, best-effort creation time, rc, timeout, elapsed time, stdout and stderr. The manifest is written in try/finally. `--out` must not exist.

**Exact commands** (each inside the qualified envelope, with a fresh grant per phase):
```
python -I -B C:/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/watchdog/run_rc2_envelope_r1.py --out C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/runs/v69-repro-<ID>-envelope.json --cpu 15 --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- python -I -B C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/proposals/v69-audio-integration/build_v69_audio.py --grant-id <GRANT_R> --phase repro --out C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/runs/v69-repro-<ID>
python -I -B …/run_rc2_envelope_r1.py --out …/s67/runs/v69-build-<ID>-envelope.json --cpu 15 --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- python -I -B …/v69-audio-integration/build_v69_audio.py --grant-id <GRANT_B> --phase build --repro-manifest …/s67/runs/v69-repro-<ID>/manifest.json --repro-manifest-sha256 <SHA_OF_THAT_MANIFEST> --out …/s67/runs/v69-build-<ID>
```

**Budget:** inner envelope 105 s per phase.
- repro: main 75 s, debug 20 s.
- build: main 65 s, debug 20 s, link 15 s.
- Historical times: v67 `debug_server.c` took 2.5 s and the v68 link 0.44 s. **No `main.cpp` compile time is recorded anywhere.**
- If the 120 s / 1024 MiB envelope proves too small for an `-O3` compile of `main.cpp`, the phase fails closed and I will ask for a larger, honest limit rather than splitting silently.
- Peak memory for the `main.cpp` `-O3` compile is unknown.

## What a later PASS would and would not show
- **Would show:** v69 builds and links from exactly the reviewed sources against the reproduced v68 closure.
- **Would not show:** that v69 runs, opens audio, sounds correct or performs. Those need separate granted live, device and listening steps.
- **Still open from the source reviews:**
  - `s_drc_ready` lifecycle;
  - real SDL3 lock behaviour;
  - trace-order acceptance;
  - generation re-commit.
