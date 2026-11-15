# Review: root's CPU mesh-packet adapter (claude-einhander, 2026-11-14)

**Reviewed (read only, not modified):** `remaster-audit/runtime-review/cpu-remix-integration-20261114/scene-packet/`
`remix_mesh_packet.h`, `remix_mesh_packet.cpp` and `test_remix_mesh_packet.cpp`.

**What is solid:**
- Every vertex passes a DATAFLOW-only lookup, then a packet-word check, a commit check and a live ring transform.
- The raw MAC is re-validated from the ring's RT/TR and the payload's V.
- The packet and its arrays are non-copyable and non-movable. Failure clears the output. The static size check is pinned.
- The resource hash excludes the combined view transform and the frame. The output keeps the model-space vertices and the
  combined camera·object transform apart, and does not label the latter world space.

Issues follow, ordered by expected impact. Everything is reasoned from source; none of it is measured live.

## 1. Same-frame rule (`v.frame != in.frame` → StaleFrame) will probably reject most real draws
`PgxpView.frame` is `s_frame_count` when the vertex was projected. PS1 titles usually double-buffer the ordering table: the
CPU builds frame N+1's packets (GTE projections included) while the GPU draws frame N's OT, which DrawOTag issues after
VSync. In that pattern every GP0 draw happens one frame-count tick after its projections, and all of them would be
rejected. The fixture only tests equal and minus-one frames, so it cannot reveal this.

**Suggestion:**
- Accept `in.frame − v.frame ∈ {0, 1}` (a configurable lag) and record the lag.
- Identity is already pinned by the address, word and committed-seq checks; the frame test only needs to bound staleness.
- Measure the real lag first. I can add a draw-frame minus view-frame histogram to the `pgxp_view` census (v3) so a live leg
  shows the true distribution.

## 2. Blanket rejection of `PGXP_VIEW_NATIVE_DIVERGED | WS_SQUASH | DOME` throws away valid 3D geometry
These flags mark where the **native screen position** did not follow the payload. The payload itself (raw int64 MAC) is
still the exact view-space point, and the mesh only uses the payload.

| Flag | Meaning for the mesh | Recommendation |
|---|---|---|
| `XY_SAT`, `XY_CLAMP`, `IR_SAT`, `DIV_OVF` | Typical of large near-camera triangles partly off screen (floors, walls, big ships). The 3D point is exact. | Keep; record the flag. Rejecting removes exactly the near geometry Remix needs most. |
| `WS_SQUASH`, `DOME` | Screen-X post-processing only (widescreen). | Keep. Otherwise the Remix path cannot coexist with widescreen. Handle aspect in the camera. |
| `SZ_SAT` or `mac[2] <= 0` | At or behind the camera. | Reject (or clip) as now. |
| `MACn_OVF44` | Real hardware's 44-bit accumulator would differ from our int64. | Reject: the payload may not equal hardware. |
| `MACn_WRAP32` | The guest's own MAC/IR wrapped, so the game's screen result is garbage. | Reject: raster and RT would disagree. |

Split the checks into "3D valid" (gates the mesh) and "native-screen agreement" (a flag for compositing). The fixture
currently asserts that IR_SAT and WS_SQUASH are rejected, so it would need updating.

## 3. Per-frame vertex colour in the mesh resource hash breaks identity stability
`hash_word(hash, in.sdk_vertex_color[i], 4)` puts the vertex colour into the resource hash. On PS1 the vertex colour is
usually per-frame lighting or depth cue (NCCS/NCDS/DPCS, DQA/DQB fog), which changes with distance and camera. The hash
would then change every frame, and Remix replacement anchoring and temporal resources would never see a stable mesh.

**Suggestion:** exclude the colour, and arguably UVs that scroll, from the identity hash. Keep the colour in the vertex
data, or move lighting to the material or instance. Hash V, the material identity and the static UVs only.

## 4. One mesh per triangle is not a viable submission granularity
Each packet is a 3-vertex mesh with its own hash. A Stage 1 frame has thousands of textured triangles, and
CreateMesh/DrawInstance (and later DestroyMesh) per triangle per frame will dominate CPU time. It also scatters the identity
of a model across thousands of tiny resources.

**Suggestion:** batch at the adapter's next layer by (caller RA, committed transform record / combined RT·TR, material
identity) into multi-triangle surfaces with one hash per batch. The per-triangle builder stays the validator.

## 5. Coordinate conventions are not yet stated (winding and normals)
- PS1 view space is x right, y down, z forward (right-handed with y down). Remix and D3D conventions are y up.
- A y flip mirrors the frame, so triangle winding **and** the cross-product normal must flip together.
- If det(RT) < 0 (mirrored models), the winding flips again, and normals then need the inverse transpose.

**Suggestion:**
- Document and test the mapping: PS1 view → Remix camera space, and the instance transform `[RT/4096 | TR]`.
- Orient each flat normal toward the camera using the native NCLIP sign, or submit double-sided until it is proven.
- Projection to FOV: vertical FOV = 2·atan((display_h/2)/H). Pixel aspect depends on the display mode (256/320/368/512/640
  widths).

## 6. The transform check cannot validate RT for components where V is 0
The MAC re-check constrains `RT·V`. For a vertex with V = (0, 0, 0), as in fixture vertex 0, any RT passes. For one zero
component, that RT column is unconstrained. Today the producer's commit (seq, lane, V, xform hash) pins the record, so this
is a defence-in-depth gap, not a live hole.

**Suggestion:**
- Have the transform callback also return H/OFX/OFY. In the runtime, extend `gte_rtp_ring_get_xform`, or add a sibling
  function that returns the ring's H/OFX/OFY (I can do this in v3).
- Recompute the FNV xform hash (`gte_view_xform_hash`: RT, TR, H, OFX, OFY) and compare it with `v.xform_hash`.

## 7. Smaller items
- **Quads:** the caller must split exactly as `gpu.c` does, into (0,1,2) and (2,1,3). Add a fixture that asserts both
  halves share vertices and orientation.
- **Texture windows:** UV resolution must apply the GP0(E2) texture-window mask/offset and the CLUT/tpage of that draw
  before normalising. Note it in `MeshInput`.
- **Semi-transparent and raw-texture draws** (semi mode, STP class) are not represented. Material identity must include
  the semi mode and the class-alpha semantics (class, not opacity), or translucent effects will be submitted opaque.
- **Fixture realism:** the views use `rtp_seq = i + 1`, so each vertex has its own record. Real RTPT lanes share one seq
  with lanes 0/1/2. Add a fixture with the shared seq and lane checks, and one with the vertices of a triangle from two
  commands that share an identical RT/TR (legitimate; accepted).
- `MeshPacket` is non-movable, so it cannot live in a `std::vector` that reallocates. Call that out for the batching layer,
  or provide a stable pool.

## What I can do next (CPU only)
- v3 census additions:
  - a frame-lag histogram (draw frame − view frame) and a per-flag hit split (how many hits carry XY_SAT, IR_SAT, WS, DIV);
  - a ring accessor returning H/OFX/OFY, so the adapter can re-check the xform hash;
  - host tests and mutants.
- Give the live leg exact numbers for issues 1 and 2.
