# Remix scene, camera and material transport: plan r0 (claude-einhander). Written 2026-11-14, tool clock 19:44:59Z

Request: root msg_b04e80bf, "continue actual missing scene/camera/material transport plan, not just API availability".

Status: SOURCE ONLY. This is a plan: no code, no build, no run. A host hold is active and Tapper preservation has I/O
priority. Every claim below cites the file it was read from. Unverified points are marked **UNVERIFIED**.

## Inputs read (sha256)

| File | sha256 | What it establishes |
|---|---|---|
| v68 `include/pgxp.h` (…/sampling-build-v68-recorder-reserve-r1) | 1f50599f51a53fdc989d1d0bb9c7aea46f0f6cc53b303048367c0f05b18c4c47 | per-vertex view payload `PgxpView` (lines 93-168) |
| v68 `src/scene_capture.h` | b90ebe9da7f11ed0c12ad2ea041564cb45a69a061b4da89b92e05dd9858856c8 | sealed one-frame CPU snapshot `ScenePrimitive`/`SceneVertex` with RT/TR |
| v68 `src/scene_runtime.h` | 6ddedc789b76254f865217c9e4e0eec7bba498cc039397178c7cec4ea5d41544 | runtime glue: command/tick/arm/json; called from debug_server.c 15014/15086 |
| `qualification/game-r2/census-proof.json` (N) | 8eee2ef48935dac8aa565b7a2492e26f66e6d4f73ec957d9151460776a8f6c56 | city census samples, 7 entries 0-30 s |
| SDK `sdk-release-header/remix_c.h` (0.16.1) | e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c | material/mesh/camera/instance/texture API |

## What already exists

**1. The view payload is exact view space, not world space** (`pgxp.h:95-100`).
- `mac = TR*4096 + RT*V` is unshifted int64, so `mac/4096` is the view-space position in model units, with no
  rounding or saturation.
- `v[3]` is the model-space vertex. `h`, `ofx`/`ofy` are the projection.
- `xform_hash` is FNV-1a of RT, TR, H, OFX and OFY. `PGXP_VIEW_NATIVE_DIVERGED` (`:131`) flags vertices whose native
  screen position did not follow the payload.
- The header states that "PS1 folds camera and object into RT/TR". **No world space or camera exists in the data.**

**2. Scene capture** (`scene_capture.h`).
- One sealed frame of at most 1024 primitives (`SCENE_CAPACITY`).
- Each `SceneVertex` carries the `PgxpView`, `rt[9]`, `tr[3]`, `u`/`v`, `rgb`, the native x/y and a miss reason.
- Each primitive carries `tpage`, `clut`, `opcode`, `depth`, `blend_mode`, `raw_texture`, `semi_trans`, indices
  (quad 0,1,2 / 2,1,3), eligibility masks and `mixed_lag`.
- Per-vertex reasons include `SCENE_MIXED_TRANSFORM`, `SCENE_DIVERGED` and `SCENE_STALE`.
- It is diagnostic only: "No SDK calls, file I/O or guest state writes". The owner thread is bound by token.
  `scene_capture_get` copies sealed records and never exposes pointers.

**3. Census at the city** (game-r2, sample at 0 s). These counts are cumulative since reset, so the later samples are
larger.
- Triangles: 850 of 854 all-hit, 2550 of 2562 vertex hits, 0 diverged.
- Quads: 306 of 325 all-hit, 1224 of 1300 vertex hits.
- Every miss is `no_shadow`, one is `no_view`, and there are 0 value mismatches.
- Lag histogram (quads): every hit at lag 1. The GP0 draw in frame N uses the view produced in frame N-1.

**4. SDK 0.16.1** (`remix_c.h`):
- textures: `CreateTextureFromMemory` / `CreateTextureFromFile` (427-431), plus patch updates (`TexturePatchInfo`);
- `CreateMaterial` with `MaterialInfo` (322-338: albedo, normal, emissive, filter and wrap) and Opaque/Translucent EXTs;
- `CreateMesh` with `HardcodedVertex` (441-454: position[3], normal[3], texcoord[2], color, optional texcoordBounds)
  per surface plus material (473-491);
- `DrawInstance` with `InstanceInfo` (689-696: category flags, mesh, 3x4 `transform`, `doubleSided`) and
  `InstanceInfoBlendEXT` (550-573: alpha test and blend, texture-stage colour/alpha operations, tFactor,
  `isVertexColorBakedLighting`);
- `SetupCamera` with `CameraInfo` (view/projection 4x4, type WORLD/SKY/VIEW_MODEL) or `CameraInfoParameterizedEXT`
  (position, forward, up, right, fovY, aspect, near, far) (501-528);
- category bits (583-610), including WORLD_UI, SKY, IGNORE, DECAL_*, PARTICLE and ALPHA_BLEND_TO_CUTOUT.

## What is missing

These are the transport gaps, in dependency order.

### G1. Continuous, bounded per-frame scene stream

Capture is one sealed frame of 1024 primitives. Transport needs every frame.

- It needs a double-buffered sealed frame: the emulation thread fills, the Remix-owner thread consumes, with no
  shared mutable state. This is the same discipline as `scene_capture_get`.
- Capacity must come from a measurement (T0), not a guess.
- An overflow must be visible: the frame is marked incomplete and its 3D falls back to native for that frame. It is
  never silently truncated.

### G2. Geometry form and instance identity

Recommendation: **model-space meshes plus per-instance transforms.**

- **Group** the primitives that share one transform (equal `rt`/`tr`, which `xform_hash` gives) and one material key
  into an instance.
- **Mesh vertices are the model-space `v[3]`.** These are constant across frames for rigid objects, so a mesh cache
  keyed by (material key, quantised model-space positions, UVs, colours, topology) can reuse `CreateMesh` handles.
  No create/destroy churn.
- **Instance transform** = `[RT/4096 | TR]` as a 3x4 row-major matrix: the view-space placement. Remix then sees
  stable meshes moving per instance, which keeps motion vectors and temporal reuse coherent.
- **Fallback, per frame**, for primitives whose vertices carry different transforms (`SCENE_MIXED_TRANSFORM`;
  skinned or multi-matrix): a dynamic mesh built from view-space `mac/4096` positions with an identity transform.
  It is counted per frame.
- **Exclude** from 3D transport any vertex flagged `PGXP_VIEW_NATIVE_DIVERGED`, stale, mixed-lag or `no_shadow`; the
  whole primitive stays native. Use the view's own frame (lag 1) consistently.
- **UNVERIFIED:** how often Einhänder uses one transform per object versus per vertex. T0 measures the share of
  mixed-transform primitives.

### G3. Camera

The data is view space, so the first camera is the **identity view camera**: `SetupCamera(WORLD)` every frame,
positioned at the origin.

**Basis:**
- PS1 view axes are +X right, +Y down, +Z forward, so forward = (0,0,1) and up = (0,-1,0).
- `right` must follow Remix's handedness convention. The r7 probe source (751d3231, D1 camera fix) uses
  right = forward × up for its scene; apply the same rule here.
- **UNVERIFIED** until the r7 GPU probe renders a known asymmetric scene. That probe is still unbuilt (PR7-1).

**Projection, from `h` and the display mode:**
- RTP gives SX = OFX/65536 + IR1·H/SZ3, and similarly for Y. The pinhole focal length is therefore H, in screen
  pixels.
- fovY = 2·atan((display_height_px/2)/H). aspect = displayed width / displayed height, with widescreen squash handled
  from `PGXP_VIEW_WS_SQUASH`.
- OFX/OFY, the centre offset, need an off-centre projection. That requires the 4x4 `CameraInfo.projection` with a
  principal-point shift, not the parameterised EXT, unless OFX/OFY equal half the display size. **UNVERIFIED:**
  whether Einhänder keeps them centred; T0 measures it.
- near and far come from the measured SZ range: near just below the smallest qualified SZ, far near 65535.

**World-stable camera (later, G6):** an identity camera means lights and caches live in view space. A world camera
needs the transform of static world geometry. A candidate is the dominant `xform_hash` cluster across consecutive
frames of terrain and facade draws; then camera = that RT/TR and instance world = camera⁻¹ · (RT,TR).

### G4. Materials

**Key:** use the same identity the HD path uses, `(texture_hash, palette_hash)` from `hd_texture_pack_match_source`,
so Remix materials and the HD pack agree.

**Albedo source:**
- the HD replacement RGBA already decoded by the renderer's decode cache, through `CreateTextureFromMemory`;
- otherwise native page pixels decoded through the CLUT;
- patch updates (`UpdateTextureFromMemory` batches) for VRAM-animated textures. Cache handles by key and LRU-bound
  them like the HD texture cache.

**PS1 render state, mapped onto `InstanceInfoBlendEXT`:**

| PS1 state | BlendEXT / instance setting |
|---|---|
| texel 0x0000, STP=0 (transparent black) | alpha test (cutout) |
| semi-transparency mode 0 (B/2+F/2) | blend |
| mode 1 (B+F) | additive |
| mode 2 (B−F) | reverse-subtract op |
| mode 3 (B+F/4) | additive with a 0.25 factor via tFactor |
| raw texture | no modulation |
| vertex colour × texture × 2 | modulate-2x texture op |

**UNVERIFIED:** the BlendEXT fields read as D3D9 texture-stage and blend enum values, but the exact numbers must be
taken from the SDK documentation or comments before any code.

### G5. Non-3D content and composition

Sprites and rects (`textured_sprites`, `untextured_rects`, `lines`, `vram_fills` counters in `SceneCaptureInfo`),
2D HUD, unqualified primitives and anything excluded in G2 stay on the existing native GL path.

The frame is composed as:
1. Remix renders the 3D into the interop image (the probe's design).
2. Host GL draws that image.
3. The native 2D overlay is drawn on top in painter order.

Risk: PS1 has no depth buffer, so 2D layers drawn **behind** 3D (parallax backdrops) need an underlay pass or the SKY
camera. This must be classified per stage. **UNVERIFIED** for the Einhänder city; T0 counts 2D draws issued before
the first 3D draw of a frame.

### G6. Threads and frame flow

- **Emulation thread:** seal frame N's 3D stream. Release it to a bounded single-slot handoff, dropping a frame if the
  consumer is busy (counted).
- **Remix-owner thread**, which owns `Startup` and `Present` as in the probe:
  1. look up or create textures, materials and meshes;
  2. `DrawInstance` for each;
  3. `SetupCamera`;
  4. `Present` through the interop semaphores;
  5. the host composite step.
- Never call `glGetString` or GL from the debug server. Never call Remix from the emulation thread.

## Test ladder (each step needs its own grant; the CPU steps first)

- **T0 (game run, GPU-held; when granted).** Read-only metrics over 30 s in the city through the existing v68 scene
  capture and census RPCs:
  - primitives per frame and per qualified frame;
  - the mixed-transform share;
  - xform clusters per frame;
  - the lag distribution;
  - the SZ range;
  - whether OFX/OFY are centred;
  - 2D-before-3D counts.
  No Remix.
- **T1 (CPU only, on existing captured data).** Reprojection identity:
  - for every non-diverged qualified vertex, compute OFX/65536 + H·(mac1/mac3) for X (and the same for Y), and
    compare with the native `x16`/`y16`;
  - expect agreement within the UNR divide error (sub-pixel);
  - this proves the G3 projection math with no GPU.
  - Input is a sealed scene JSON already produced by v64/v66 scene-capture builds, if one exists under N. Not yet
    located: I ran no broad search.
- **T2 (CPU only).** Mesh and instance builder unit tests on synthetic and captured primitives: grouping by transform,
  model-space cache hits across two frames, mixed-transform fallback, exclusion flags, quad index order.
- **T3 (GPU, grant).** Extend the r7 probe to draw one captured frame's instances with the identity camera. Compare the
  silhouette mask against the native frame at the same resolution.
- **T4 (GPU, grant).** Materials and BlendEXT on the captured frame; per-mode checks for the 4 semi-transparency modes
  and cutout.
- **T5.** A live bounded run with the G1 stream and the G5 composition. Acceptance is visual review, not this plan.

## Not claimed

No part of this plan has been implemented or tested.

- The census numbers are a single city sample from one prior run (game-r2). They are not per-stage coverage.
- Camera handedness, the BlendEXT enum values, OFX/OFY centring, the transform-per-object share and the 2D-underlay
  need are UNVERIFIED as marked.
