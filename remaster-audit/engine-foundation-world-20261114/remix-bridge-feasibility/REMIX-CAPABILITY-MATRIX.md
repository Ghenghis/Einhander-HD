# RTX Remix capability matrix and engine tracks (claude-einhander, 2026-11-14)

**Correction to `REMIX-CAPTURE-ASSESSMENT.md` (sha256 414e81f6…, which keeps its bytes as received):**
- That report treated a Direct3D9 rewrite of the renderer as the only route into Remix. **That is wrong.**
- Codex confirmed upstream `dxvk-remix` `public/include/remix/remix_c.h` (API 0.6.11). It lets a native 64-bit application
  submit meshes, materials, a camera and lights directly through the Remix runtime, with no D3D9 translation layer.
- The installed runtime is `C:/Program Files/NVIDIA Corporation/RTX Remix/deps/remix_runtime/runtime/.trex/d3d9.dll`.
  Codex is qualifying its exported ABI CPU-only; until then, no function-level claim below is verified against that binary.
- What remains true from the earlier report:
  - Today's OpenGL stream carries no 3D scene: GP0 screen-space vertices at z = 0.
  - Remix needs real geometry, a camera, stable identities and materials, whichever submission API is used.
  - A wrapper that intercepts our GL calls preserves none of that.

Nothing here is ray-traced today. No item is claimed working until a gameplay capture or a live run shows it.

## What each Remix-dependent capability needs from the engine
| Capability | Hard dependencies | Status of each dependency | Realistic outcome |
|---|---|---|---|
| **A. Submit 3D geometry per frame** (SDK mesh plus instance) | 3D position for every GTE-projected vertex, joined to the GP0 primitive that draws it; triangle assembly; UV, CLUT and texture identity | Per-vertex provenance: **private v1 implemented and host-tested** (`remix-provenance/impl`). The primitive join reuses the existing per-word DATAFLOW lookup. Texture keys exist in the HD pack system. | Feasible. View-space geometry submitted with an identity camera is valid input. |
| **B. Material and texture replacement** (PBR albedo, normal, roughness, emissive) | A plus a stable texture identity (TEX-CLUT key → material handle) plus authored PBR maps | Keys are stable (1,669 in the current pack). PBR maps are mostly unauthored; emissive masks exist only for facades. | Feasible on top of A. This is where the 4K art pays off. |
| **C. Path-traced lighting** (shadows, reflections, GI) | A plus normals (flat from winding, or authored), emissive and light sources (neon signs, windows, sky), and **temporal stability** | Normals: derivable. Lights: unauthored. Temporal stability needs persistent instance identity and frame-to-frame transforms (see E). | Single frames are possible after A and B. In motion, expect heavy noise and ghosting until E exists. |
| **D. Mesh replacement** (authored high-poly ships and buildings) | A plus **object-space** geometry with a stable hash per model | PS1 folds camera and object into RT/TR. v1 gives view space only. The ring keeps RT/TR per projection (`gte_rtp_ring_get_xform`) but not yet a model identity. | Blocked on E. View-space vertices change every frame, so their hashes never repeat. |
| **E. Camera/object separation** (stable model identity; camera vs object transform) | Per-draw model identity (caller RA plus vertex-buffer address plus RT/TR history) and a camera estimate | Not started. Research: cluster RT/TR by caller and frame; the camera is the transform shared across static scenery. | The hardest engine track, game-specific (Einhänder). It gates C-in-motion, D and motion vectors. |
| **F. 2D layers** (HUD, menus, sprites drawn as screen-space GP0 without the GTE) | Composite over the Remix output, or submit as screen-space UI | The SDK presents to its own swapchain on our HWND, so a GL overlay on that same window is not given. The UI path through the SDK must be qualified. **Unknown.** | Required for a playable build. Must be qualified before any Remix gameplay build. |
| **G. GTE-projected billboards** (bullets, explosions, smoke: RTPS points plus 2D quads) | A for the anchor point, plus a size and orientation policy | Point provenance is in v1; quad expansion is game-specific. | Feasible as camera-facing quads. Classify separately from meshes. |
| **H. DLSS SR / DLAA / Ray Reconstruction** | Inside Remix: provided by the runtime once A–E feed it. Outside Remix (OpenGL path, via Streamline): color, depth, **dense motion vectors**, camera, jitter | Depth: v1 gives view z. Motion vectors need E. Jitter needs renderer work. | 3090 Ti: SR, DLAA and RR are supported once integrated. **Frame Generation needs RTX 40/50; Multi-Frame Gen and DLSS 5 need RTX 50.** Gate each by hardware detection; never offer them on the 3090 Ti. |

## Implementation tracks, in dependency order
1. **Provenance (A1). Done privately:** `remix-provenance/impl`.
   - Exact int64 MAC1..3, V, H/OFX/OFY and saturation flags.
   - RTPT lane, and the ring identity committed after execute.
   - DATAFLOW-only consumer, default off.
   - Host-tested on the full translation units, with mutation controls.
   - Next: a debug-server coverage query, then a live coverage leg run by Codex (fraction of textured triangles whose three
     vertices all carry a view).
2. **Primitive assembly (A2):** in `gpu.c`, behind the same opt-in, look up each textured polygon's vertex words → a triangle
   with view XYZ, UV, CLUT, texture key, semi mode and draw order. Ring-buffered and queried over TCP (no files).
3. **Remix backend (A3):** a `GpuRenderBackend` implementation (vtable seam `gpu_render.h` 123–175) that drives `remix_c.h`.
   - Startup on our HWND; per frame, SetupCamera(identity, H-derived FOV) → CreateMesh/DrawInstance per batch → Present.
   - Materials come from pack keys (DDS albedo first).
   - Opt-in, with the OpenGL backend unchanged.
   - The first gate is a real gameplay capture opened in the Remix toolkit. A sample or dummy scene does not count.
4. **2D/UI qualification (F):** decide between UI submitted through the SDK and an overlay path. This blocks the playable gate.
5. **Camera/object separation (E):** research, then implementation. It unlocks stable lighting, mesh replacement and motion
   vectors.
6. **PBR and lights (B, C):** albedo, normal, roughness and emissive for the drawn world keys, prioritized from
   `claude-backlog/sign-census/WORLD-SIGN-CENSUS.md`; neon and window emitters; a sky light.
7. **Upscaling (H)** through Remix or through Streamline, with hardware gating.
8. **Launcher and in-game options:** expose only implemented capabilities, with hardware detection and persistence.

## What must not be claimed
- "Ray-traced Einhänder" before a gameplay capture renders through the Remix backend.
- Mesh replacement before E.
- Frame Generation on the RTX 3090 Ti.
- That a view-space capture is a reconstructed world. It is the foundation result, not a scene.
