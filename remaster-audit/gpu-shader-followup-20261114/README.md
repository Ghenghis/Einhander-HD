# GPU shader follow-up — November 14, 2026

These actual results extend the [earlier GPU integration packet](../gpu-integration-20261114/README.md). These GPU tests ran under the earlier authorization; every owned test process below exited or was closed by its bounded watchdog, and its reservation was released. No installed game/driver change or RTX3060 work occurred.

## Actual class-mip shader GPU result: FAIL

Root verified all files in Claude's self-test build `20261114T110630Z`, including executable SHA256 `674df90f266ec67691200a15401320c8d14739980b507e53c3795e008261d642`. It ran below normal on two logical CPUs for **0.69s**, using a hidden64×64 window and an offscreen288×96 framebuffer on **RTX3090Ti / GL3.3 / NVIDIA621.14**. [Full result](class-mip-gpu-r1/root-result.json).

The real extracted shader compiles/links; uniforms/framebuffer pass; GL error is zero. Point mode is unchanged and filtered LOD0 is identical to the old path. Both of those checks pass. The fixture is synthetic; this tests GPU shader behavior, not game geometry/materials or sidecar/uploader integration.

- At4× minification: old level0 visible-stroke pixel count varies0–56 over8 phases; class-aware levels stay28–28.
- At8×: old0–28; class-aware28–28. This is measured improvement in the synthetic fixture.
- At12×: class-aware still varies0–19, so the promised never-vanish check **fails**. The native-level class cap still aliases below one native pixel.
- At2×–12×, class-aware darkest visible luma is122.52, matching authored minimum; the old paths are darker. At1×/LOD0 it remains30.71, the same as the baseline. Therefore the all-scales no-fringe check **fails**. Preserving exact LOD0 while promising to fix its black-cutout RGB fringe was an inconsistent acceptance goal; it is not silently relabeled a pass.

Overall exit1 / `pass:false`, clean process exit and reservation release. The original result is retained. A successful CPU fixture or offline GLSL validation did not predict all these GPU results. Renderer v1 was already superseded for upload/shift defects; this self-test only exercises its shader and synthetic textures, so it does not qualify the rejected uploader.

## Root renderer review before game linking

[Review receipt](renderer-review.json) records unchecked shift counts, unchecked GL uploads, a FAIL result with exit0, and measured synchronous CPU mip generation of95.53ms/343.72ms on the two target2048² pages. The latter are host timings, not controlled gameplay measurements, but they show that first-draw CPU generation is unsuitable for the stutter goal. Root requested precomputed hash-bound level payloads or preparation before gameplay, plus fail-closed upload checks and strict native-key/map/dimension/decoded-level0 admission. No actual game executable containing this renderer has been linked or accepted. Claude owns the revised implementation; earlier versions/failures remain preserved. Real region-O comparisons are required: its all-opaque classes mean the synthetic alpha-stroke win does not establish the same benefit on those signs.

## Native Remix presentation control: unresolved

The [separate native control](sdk-native-r1/result.json), based on the pinned NVIDIA triangle example, uses **no OpenGL context and no custom material**. Startup/mesh/light/camera/draw/Present calls succeed across120frames at640×360, with the owned PID on the3090Ti. The requested runtime screenshot at frame60 was not produced. CUA found the window title, but accessibility was unavailable and its returned screenshot showed underlying Claude content; **no rendered triangle was verified**. Shutdown still stalled and the60s owned-process watchdog closed it. `lifecycle_passed:false`; no inference that OpenGL alone causes the earlier black-output failures.

## Newer SDK compatibility is separate

Official NVIDIA Minecraft integration commit `4b228424b5794b91a994198c3e48b3a00c25e87e` publishes an SDK0.16.1 header with Submit, interop-image controls and in-memory textures; its manifest pins a separate `minecraft-rtx2-a00da12a-win64-release` runtime. The [reference pins](sdk-minecraft-reference/reference.json) retain exact provenance. A [CPU-only compatibility probe](sdk-version-result.json) against the installed1.6.1 renderer returns **error8 (incompatible version)** with null newer functions. The older0.6.11 API table initialization succeeded in prior evidence. These headers/runtimes cannot be mixed, and no newer runtime has been installed or new feature enabled by this inspection. The [official integration source](https://github.com/NVIDIAGameWorks/rtx-remix-minecraft/blob/4b228424b5794b91a994198c3e48b3a00c25e87e/rtxremix-java/native/remixbridge.cpp) is useful reference for a future separately qualified backend.

Next acceptance requires measured correct SDK image/lifecycle; revised class-sidecar/upload source checks; actual GPU sampling with honest scale-specific limits; bounded in-game comparisons including distant signs and frame/audio effects. No ray-traced gameplay, DLSS integration, final artwork coverage or complete-remaster claim is made.

## Separate RGB-only shader experiment: narrow GPU goals pass

Root then implemented a separate, default-zero-uniform shader variant that filters RGB using only non-cutout taps and renormalizes their weights, following the existing native-edge shader's principle. For LOD between0 and1 it blends visible-weighted level0/1 RGB. Categorical class selection, discard and STP decisions are kept separate. This changes filtered edge color deliberately; it is not a claim of level0 identity. No source images are rewritten and no CPU fill/build is added to a game draw.

[First result](rgb-edge-run-r1/root-result.json) and [expanded fractional-LOD result](rgb-edge-run-r2/root-result.json) retain both the original suite and explicitly declared narrower RGB goals. The first/second GPU runs took0.715s/0.682s on the3090Ti. The expanded run tests scales0.5,1,1.125,1.25,1.5,1.75,2,4,8,12 over8phases.

- Darkest visible fixture luma is122.52 at every tested scale, including LOD0, versus the baseline's30.71 at LOD0. This removes the measured synthetic dark fringe.
- Cutout support and output alpha/STP compare exactly against the uniform-off class path at all tested scales/phases. Point-path images remain identical.
- An all-opaque varying-color/mixed-STP LOD0 control differs at most1RGB code value, with output alpha unchanged.
- The original suite still reports `pass:false`, executable exit1: the12× stroke aliases, and filtered LOD0 intentionally differs. Both are retained. The wrapper's `rgb_edge_goal_passed:true` / `passed:true` refer only to the narrower predeclared RGB goals; **they are not overall renderer/game acceptance**.

Fragment SHA256 `f3a279bef48337fdf032034e6c914c37c4622745b22899fdb43251d88ba786a8`; [exact fragment](rgb-edge-gpu-r2/HD_FS.frag), [test source](rgb-edge-gpu-r2/gl_selftest_classmips.c). It is sent to Claude for independent review and possible separate opt-in integration into the revised private renderer. UV seam/real-asset behavior, shader cost, full game linking and in-game visual/frame/audio acceptance are pending. No fix for beyond-native minification is claimed.

Reproduction scope: recipes retain their exact original C: workspace/toolchain paths and fresh-output guards. Executables and runtime/asset dependencies stay local; regenerate in a new scratch directory with verified roots/inputs. These are source/evidence packets, not an installable game build or portable CI package.

## Latest guarded RGB variant and private v62 build

The [guarded RGB-only shader run](rgb-edge-run-r3/root-result.json) preserves the original hardware result whenever all contributing level0 taps are opaque. It retains the measured fringe improvement and now matches the all-opaque varying-color/mixed-STP control **exactly** at all10 tested scales. Additional mixed0/127/255 fixtures preserve support and output alpha across semi subpasses0/1/2. GPU duration0.743s; shader SHA256 `3746b128778fa968e3655c78071bcf8a9225dbcadbbe94502391713cb5c7aa2a`. The original full suite remains false for its previously documented goals.

Root also qualified an independent **ordinary level0-only RGB branch**, for filtered HD draws with facade sampling off. It requires no class sidecar, offline mip payload or CPU generation. The [actual GPU result](rgb-edge-run-r4/root-result.json) passes the narrow RGB/support/STP/point/opaque controls across the10scales/8phases, in0.82s; original full suite still false. It fixes color bleed, **not thin-stroke sampling aliasing**: stroke counts continue to vary at4×/8×/12× in this level0-only mode. Default-zero uniform gates the change; native-edge override and categorical class selection remain unchanged.

[Private v62 build](private-v62/build.json) rebuilds the renderer and debug-server translation units, retaining the pinned parent guest/core/platform objects and143 private headers. Compile/link passed below normal on one logical CPU; executable SHA256 `ecf6b8824b4b98e3083666d7c5024428fa3932da73d8e4efae0e347931f5b9a7`. It is **not a clean full-source rebuild**. `PSXRECOMP_HD_RGB_EDGES=1` opts in; default is off. A read-only `hd_rgb_edges` debug verb reports enabled state and filtered HD draw assignments, not corrected-fragment counts. Exact sources, header snapshots, recipes and logs are included; binary stays local.

The [preprocessed shader check](private-v62/shader-qualification.json) matches the2453 GLSL tokens of the GPU-tested ordinary RGB branch after removing unrelated class-mip paths. This verifies that the private executable contains the intended shader; it is not game acceptance. The [12-second HD-on visual candidate](private-v62/prepared-candidate.json) was prepared with an empty own cache, autocompile off, rewind off, scale2, no recording/timers, CPU affinity10–13. **It was not launched.** No new in-game screenshot or performance/audio acceptance exists for v62.

## Current GPU handoff

At11:30UTC the user asked to use the3090Ti for another project. Root verified no owned GPU/game executable was running and no test reservation/lock remained, then wrote the [user-owned reservation](user-gpu-hold-1130.json) without automatic expiry. Further Einhander/Claude game, GL, Remix Startup, GPU authoring/upscaling or AudioSR work stays on hold until explicit return. CPU-only source/review/documentation may continue below normal. The3060 project remains untouched. This current hold supersedes the earlier available-GPU checkpoint; it does not alter the historical test receipts.

## Subsequent CPU-only Claude v3 delivery

While the user held the GPU, Claude delivered the revised offline-prepared mip implementation. Root verified **all212 frozen file hashes** against READY `90cb506ddae3952509baabd2f1f6a7218f0c17ab2589029b98c1e139d9efa625` and SHA256SUMS `a43774a12dc6c9f195976515a31b754f7e67302507f7b1cd1a7470a605a70995`, then independently recompiled/replayed the CPU fixture and exact renderer-glue recording stubs: **6,182 checks +28 opt-in checks +2 opt-out checks pass**. [Root receipt](v3-cpu-verification-r2/result.json). No GL context, game or GPU selftest ran. The user reservation bytes remain unchanged. Root's initial missing-header replay setup failed before tests; its source/log/note are retained in a separate directory.

The [source/report subset](claude-v3-frozen-source/PUBLICATION-SUBSET.json) explicitly lists included files and omitted local binary/raw-RGBA/prepared-image payloads; original author manifests are retained. Their212-file verification is local, not a claim that every payload is published. Author reports27/27 mutation controls caught; root did not replay mutant compilation. Author compile-only patched/control TUs and offline GLSL checks pass; this is not a full game link or GPU acceptance of v3.

Changes address the rejected draw-thread builder: HDCMSC02 sidecars contain prepared categorical/RGB levels with per-level dimensions/length/hash, native map, key/scale/decoded-level0 binding and self-hash. A fixed8-entry/96MiB cache preloads before gameplay. Root's CPU stub replay reads/verifies8 sidecars/25,774,976bytes in40.297ms at init; first draw admission plus stub uploads takes1.029ms for the1024×512 fixture. Those are host measurements, **not real GPU upload or game timings**. There is no builder, allocation or file load on the renderer draw path. Each uploaded level is dimension-checked with fail-closed restore; shift bounds and runner exit code were corrected.

Numeric real-data analysis confirms the initial fully opaque region-O pages get no useful class-mip benefit. The8-key whitelist now targets verified drawn textures with cutout structure, independent of the old facade/world gate; default remains off. The distant O artwork/clarity problem is therefore **not declared fixed**. Root has authorized Claude's next CPU-only v4 to combine the reviewed RGB filter safely with these class levels: preserve class-level minification on non-facade draws, skip opaque keys using an identity-bound flag, retain native-edge/point/STP behavior and report anisotropic edge differences. That v4 is ongoing, not accepted or GPU-tested.
