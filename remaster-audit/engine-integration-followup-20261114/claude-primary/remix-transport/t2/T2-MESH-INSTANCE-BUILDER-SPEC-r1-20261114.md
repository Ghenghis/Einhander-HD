# T2 mesh/instance builder: spec r1 (claude-einhander). Written 2026-11-14, tool clock 20:17Z

Status: SOURCE ONLY, specification, no code. r0 (f17bb355…) is preserved read-only and superseded.

r1 applies root's review msg_6fe6105a and root's ownership decision msg_3d2b027f
(docs/REMIX-TRANSPORT-OWNERSHIP-DECISION-20261114.md). This spec follows that ADR; where the two differ, the ADR
governs. Everything else in r0 sections 2, 5 and 7 stands unless changed here.

## Changes from r0

**1. Ownership is split explicitly** (r0 §1 and §3 were inconsistent: a stateless builder cannot know
consumer-owned mesh ids).

- **Producer** (`t2_build`, emulation owner thread, stateless):
  - emits an immutable, owned `T2Frame` with no persistent ids;
  - each primitive group carries its **full mesh content key and full geometry payload** (model-space positions,
    UVs, colours, indices), copied by value, plus its transform, material key and semi class;
  - it never emits `reuse(id)`.
- **Consumer resolver** (`t2_resolve`, Remix-owner thread, pure CPU, deterministic):
  - owns the mesh cache, mesh ids (monotonic 64-bit, never reused), retirement (`retire_frames`), the mesh-count
    and mesh-byte budgets, and instance identity across frames, which is `(mesh id, run ordinal)` with
    reassignments counted;
  - it turns a `T2Frame` into a `T2Resolved`: per group, `new mesh` or `reuse id`, plus the instance list;
  - **new/reuse/retire/instance-identity assertions test this resolver**, never the builder.
- **No mutable state is shared across threads.**

**2. Hand-off, per the ADR.**
- There is exactly **one pending slot**. The producer publishes with **CAS(empty → frame)** and never overwrites.
  - If the CAS fails (busy), the producer releases **only its own unpublished frame** and counts
    `frames_dropped_busy`.
- The consumer takes with an exchange (pending → empty).
- A **global byte budget** covers building + pending + in-flight frames together. Exceeding it means the frame is
  not built: whole-frame native.

**3. MAC recompute before any model-space transport.** The T1 screen check cannot catch a stale or colliding RT/TR
record. So for every vertex, T2 recomputes all three raw accumulators:
  - `MAC_a = TR[a]·4096 + Σ_j RT[a][j]·V[j]`, in int64, from `SceneVertex.rt[9]`, `tr[3]` and `view.v[3]`;
  - requires `MAC_a == view.mac[a]` exactly, before using V as a model-space position;
  - any mismatch means the primitive stays native, with reason `T2_PRIM_MAC_RECOMPUTE`.
- The transport gate is now:
  - one full transform key across the primitive;
  - every vertex VERTEX_OK, with uniform lag ≤ 1 and no divergence;
  - **MAC recompute equal** for every vertex;
  - **T1 r1 = MATCH** with commit required. T1 r1 recomputes OVF44/WRAP32 from the raw MACs and never trusts the
    claimed flags.

**4. Per-texel STP, corrected** (r0 §4 and fixture case 7 were wrong). `raw_texture` bypasses only the **colour
modulation** (texel × vertex colour × 2). It does **not** bypass STP.
- **Every textured semi primitive, raw or modulated, is split into the two texel classes**: OPAQUE_TEXELS (STP = 0,
  alpha-tested) and BLEND_TEXELS (STP = 1, the primitive's blend mode). This is the same split the native
  `hd_draw_passes` makes with `u_semipass` 1/2.
- `raw_texture` only selects no-modulation in the material/instance state.
- **Only untextured semi primitives blend whole** (flat or gouraud polygons; one instance).
- Non-semi textured primitives: transparent-black cutout only.
- Mask bit set/check or a non-zero texture window: native, unchanged from r0.

**5. Presentation transaction before native suppression (the live gate, per the ADR).**
- A CPU `T2_TRANSPORTED` disposition is **not** permission to skip a native draw.
- The native renderer may suppress the transported primitives of frame F **only after** the consumer reports that
  the **exact frame F and source generation** completed its Remix interop image, and that the native overlay order
  for F matches.
- Any drop, failure or late consumer means **the whole frame F is drawn native**. There is never an implicit
  combination of an older Remix image with a newer HUD or overlay.
- This gate sits outside T2's CPU code. T2 only provides the frame id, the generation and the disposition array it
  must be checked against.

**6. Known capture.**
- **None exists.** Root confirmed that game-r2 holds only 5 JSON files (candidate, launch-candidate, launch-ready,
  pacing-boot, census) with no sealed scene vertices, and no saved `scene_capture` path is documented.
- The known-capture case is removed from the fixture plan until a real sealed capture is produced under a future
  grant. No known-capture result is claimed.

**7. Camera.** Unchanged: view_identity only, diagnostic. The first GPU step is the T3 captured-frame diagnostic. It
makes no world-stable RT, light or DLSS/motion claim, and stays blocked until r7 CPU qualification and a fresh grant.

## Fixture plan r1 (CPU only, run only under a grant)

**Builder tests** (stateless; no persistent ids are asserted):

| # | Case |
|---|---|
| B1 | one rigid quad gives one group with the full payload and key |
| B2 | the same model with two transforms gives two groups with an identical mesh key |
| B3 | an injected hash collision with unequal RT gives two transforms (full-equality proof) |
| B4 | a mixed transform goes native (MIXED_TRANSFORM) |
| B5 | a MAC recompute mismatch on one vertex (stale or colliding record) makes the whole primitive native (MAC_RECOMPUTE) |
| B6 | a T1 r1 non-MATCH on one vertex, including a forged overflow with missing flags, makes the primitive native |
| B7 | textured semi, **raw and modulated**, gives two instances (OPAQUE/BLEND texel classes); **untextured** semi gives one blended instance; the raw flag changes only the modulation state |
| B8 | mask set, mask check and texture window go native |
| B9 | each capacity limit, hit by exactly one more, gives whole-frame native |
| B10 | interleaved overlapping native-before-3D gives whole-frame native; non-overlapping is allowed; native-after-3D is allowed |
| B11 | one disposition per input, and the counts add up |
| B12 | multi-projection gives whole-frame native |

**Resolver tests** (a CPU resolver over synthetic frames):

| # | Case |
|---|---|
| R1 | the first frame gives new meshes and ids 1..n |
| R2 | an identical next frame gives reuse with the same ids and the same instance ids |
| R3 | retirement after `retire_frames`; the id is never reused; an in-use mesh is never evicted |
| R4 | the mesh budget is full with nothing retirable: resolution fails, the whole frame goes native, and the cache is unchanged |
| R5 | a run-ordinal change is counted as `instances_reassigned` |

**Hand-off tests:**

| # | Case |
|---|---|
| H1 | CAS on an empty slot publishes |
| H2 | a busy slot drops and releases only the producer's frame; the pending frame is untouched |
| H3 | exceeding the global budget means no frame is built |

**Gate tests** (a CPU model of the live gate):

| # | Case |
|---|---|
| G1 | completion for the exact frame and generation allows suppression |
| G2 | completion for another frame or generation, a late completion or a failure gives whole-frame native, with no stale image |

## Not claimed

Not implemented, built or run. No RT rendering, camera, lights or motion qualification. No known capture.
