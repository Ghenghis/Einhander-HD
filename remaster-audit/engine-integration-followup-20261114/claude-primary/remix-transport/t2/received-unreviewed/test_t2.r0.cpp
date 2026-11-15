// CPU-only fixture for T2 r0 (claude-einhander). SOURCE ONLY, not compiled or run. No GL, SDK, game or files
// except the result JSON. Inputs (copied by a future driver after pin checks): scene_capture.h (v68 b90ebe9d),
// pgxp.h (v68 1f50599f), gte_divide_extracted.inc (cfa7686a), remix_t1_reproject.r1.h (4a0a536c), remix_t2.r0.h.
// Vertices are built from an identity RT so MAC, SZ3 and screen values are known by hand; native fields
// (packed, x16, y16, sz3, flags) are filled by the T1 oracle, which has its own independent hand-derived tests.
// Usage: test-t2.exe RESULT.json      exit 0 only when every check passed.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r0.h"
using namespace t2;

static int checks, failures;
static char failed[8192];
static void check(bool ok, const char *name) {
    ++checks;
    if (!ok) { ++failures; if (strlen(failed) + strlen(name) + 2 < sizeof failed) { strcat(failed, name); strcat(failed, ","); } }
}

static const int16_t RT_ID[9] = {4096, 0, 0, 0, 4096, 0, 0, 0, 4096};
static const uint16_t H = 500;
static const int32_t OFX = 160 << 16, OFY = 120 << 16;

static SceneVertex vert(const int16_t rt[9], const int32_t tr[3], int16_t x, int16_t y, int16_t z, uint8_t u, uint8_t v,
                        uint16_t h = H) {
    SceneVertex s; memset(&s, 0, sizeof s);
    memcpy(s.rt, rt, sizeof s.rt); memcpy(s.tr, tr, sizeof s.tr);
    s.view.v[0] = x; s.view.v[1] = y; s.view.v[2] = z; s.view.h = h; s.view.ofx = OFX; s.view.ofy = OFY;
    for (int a = 0; a < 3; a++)
        s.view.mac[a] = (int64_t)tr[a] * 4096 + (int64_t)rt[a * 3] * x + (int64_t)rt[a * 3 + 1] * y + (int64_t)rt[a * 3 + 2] * z;
    s.view.flags = PGXP_VIEW_SF;
    T1Expect e; memset(&e, 0, sizeof e);
    t1_reproject(s.view, false, &e);
    s.view.sz3 = e.sz3; s.view.packed = e.packed; s.view.x16 = e.x16; s.view.y16 = e.y16;
    s.view.flags = (uint16_t)(e.modelled_flags | PGXP_VIEW_RTP_COMMITTED);
    s.reason = SCENE_VERTEX_OK; s.lag = 1; s.u = u; s.v = v; s.rgb = 0x808080;
    return s;
}

static const int32_t TR0[3] = {0, 0, 1000};
static ScenePrimitive prim(uint8_t opcode, uint32_t ordinal, const int32_t tr[3] = TR0, int16_t dx = 0,
                           uint16_t h = H, uint32_t generation = 1) {
    ScenePrimitive p; memset(&p, 0, sizeof p);
    p.opcode = opcode; p.qualified = 1; p.frame = 10; p.generation = generation; p.ordinal = ordinal;
    p.tpage = 0x10; p.clut = 0x20; p.depth = 0;
    p.semi_trans = (opcode & 0x02) ? 1 : 0; p.raw_texture = (opcode & 0x01) ? 1 : 0;
    const bool quad = (opcode & 0x08) != 0;
    p.nverts = quad ? 4 : 3; p.triangle_count = quad ? 2 : 1;
    const uint8_t idx[6] = {0, 1, 2, 2, 1, 3}; memcpy(p.indices, idx, sizeof idx);
    p.vertex[0] = vert(RT_ID, tr, (int16_t)(dx + 0), 0, 0, 0, 0, h);
    p.vertex[1] = vert(RT_ID, tr, (int16_t)(dx + 10), 0, 0, 16, 0, h);
    p.vertex[2] = vert(RT_ID, tr, (int16_t)(dx + 0), 10, 0, 0, 16, h);
    p.vertex[3] = vert(RT_ID, tr, (int16_t)(dx + 10), 10, 0, 16, 16, h);
    return p;
}

static SceneCaptureInfo info(uint32_t count, uint32_t generation = 1, uint32_t complete_types = 1) {
    SceneCaptureInfo i; memset(&i, 0, sizeof i);
    i.complete = 1; i.geometry_types_complete = complete_types; i.overflow = 0; i.count = count; i.generation = generation;
    return i;
}
static LedgerEntry led(uint32_t textured_index, int16_t x0, int16_t y0, int16_t x1, int16_t y1, bool captured = true) {
    LedgerEntry e; memset(&e, 0, sizeof e);
    e.x0 = x0; e.y0 = y0; e.x1 = x1; e.y1 = y1; e.textured_index = textured_index; e.captured_textured = captured ? 1 : 0;
    return e;
}

static ScenePrimitive P[1100];
static LedgerEntry L[1200];
static T2Frame F, F2;
static T2Resolver RES;
static ResolveResult RR, RR2;

// Live build of P[0..n) with a ledger that lists exactly the n captured polygons (no other commands).
static void build_live(uint32_t n, T2Frame *f) {
    for (uint32_t i = 0; i < n; i++) L[i] = led(P[i].ordinal, 0, 0, 1, 1);
    const SceneCaptureInfo in = info(n);
    t2_build(P, n, &in, L, n, false, f);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;

    // B1 one rigid textured triangle -> one group, payload is the model-space vertices.
    P[0] = prim(0x24, 0);
    build_live(1, &F);
    check(F.frame_reason == F_OK && F.live_eligible == 1 && F.transported == 1 && F.native == 0, "b1_transported");
    check(F.group_count == 1 && F.vert_count == 3 && F.groups[0].instances == 1 && F.groups[0].semi == S_NONE, "b1_one_group");
    check(F.verts[1].x == 10 && F.verts[1].y == 0 && F.verts[2].y == 10 && F.verts[1].u == 16, "b1_model_space_payload");
    check(F.disposition_reason[0] == P_TRANSPORTED, "b1_disposition");

    // B2 same model, two transforms (both live in one frame, non-contiguous groups) -> 2 transforms, same content hash.
    { const int32_t tr2[3] = {50, 0, 1000};
      P[0] = prim(0x24, 0); P[1] = prim(0x24, 1, tr2);
      build_live(2, &F);
      check(F.frame_reason == F_OK && F.transform_count == 2 && F.group_count == 2, "b2_two_transforms");
      check(F.groups[0].content_hash == F.groups[1].content_hash && F.groups[0].transform != F.groups[1].transform, "b2_same_mesh_key"); }

    // B3 transform identity is full equality: identical RT/TR share one transform; one differing RT entry does not.
    { P[0] = prim(0x24, 0); P[1] = prim(0x24, 1);
      build_live(2, &F);
      check(F.transform_count == 1 && F.group_count == 1 && F.vert_count == 6, "b3_equal_transform_shared_contiguous_group");
      int16_t rt2[9]; memcpy(rt2, RT_ID, sizeof rt2); rt2[1] = 1;     // tiny off-diagonal difference
      P[1] = prim(0x24, 1);
      for (int k = 0; k < 4; k++) P[1].vertex[k] = vert(rt2, TR0, P[1].vertex[k].view.v[0], P[1].vertex[k].view.v[1], 0, 0, 0);
      build_live(2, &F);
      check(F.frame_reason == F_OK && F.transform_count == 2, "b3_one_rt_entry_differs"); }

    // B4 mixed transform inside one primitive.
    { const int32_t tr2[3] = {0, 0, 1001};
      P[0] = prim(0x2C, 0); P[0].vertex[3] = vert(RT_ID, tr2, 10, 10, 0, 16, 16);
      build_live(1, &F);
      check(F.disposition_reason[0] == P_MIXED_TRANSFORM && F.transported == 0 && F.native == 1, "b4_mixed_transform_native"); }

    // B5 stale/colliding transform record: every vertex carries the SAME (stale) RT, so the transform check
    // passes, but each view MAC was produced with the old RT. Vertex 0 has x=y=z=0 (MAC unaffected); vertex 1
    // (x=10) differs by 10 -> MAC recompute catches it although the screen check alone would pass.
    { P[0] = prim(0x24, 0);
      for (int k = 0; k < 4; k++) P[0].vertex[k].rt[0] = 4095;
      build_live(1, &F);
      check(F.disposition_reason[0] == P_MAC_RECOMPUTE, "b5_stale_rt_mac_recompute"); }

    // B6 T1 non-match on one vertex (corrupted native packed word) -> whole primitive native.
    { P[0] = prim(0x2C, 0); P[0].vertex[2].view.packed += 1;
      build_live(1, &F);
      check(F.disposition_reason[0] == P_T1 && F.transported == 0, "b6_t1_mismatch_native");
      P[0] = prim(0x24, 0); P[0].vertex[0].view.flags &= (uint16_t)~PGXP_VIEW_RTP_COMMITTED;
      build_live(1, &F);
      check(F.disposition_reason[0] == P_T1, "b6_uncommitted_view_native"); }

    // B7 per-texel STP: modulated and raw textured semi -> 2 instances; untextured semi -> whole blend; raw only modulation.
    { P[0] = prim(0x26, 0); P[1] = prim(0x27, 1); P[2] = prim(0x22, 2); P[3] = prim(0x24, 3);
      build_live(4, &F);
      check(F.frame_reason == F_OK && F.transported == 4 && F.group_count == 4, "b7_four_groups");
      check(F.groups[0].semi == S_TEXEL_SPLIT && F.groups[0].instances == 2 && F.groups[0].material.raw == 0, "b7_modulated_semi_split");
      check(F.groups[1].semi == S_TEXEL_SPLIT && F.groups[1].instances == 2 && F.groups[1].material.raw == 1, "b7_raw_semi_split");
      check(F.groups[2].semi == S_WHOLE_BLEND && F.groups[2].instances == 1 && F.groups[2].material.textured == 0, "b7_untextured_semi_whole");
      check(F.groups[3].semi == S_NONE && F.groups[3].instances == 1, "b7_opaque_textured_none"); }

    // B8 mask set, mask check and texture window stay native.
    { P[0] = prim(0x24, 0); P[0].state.set_mask = 1;
      P[1] = prim(0x24, 1); P[1].state.check_mask = 1;
      P[2] = prim(0x24, 2); P[2].state.texture_window = 0x1234;
      build_live(3, &F);
      check(F.disposition_reason[0] == P_MASK_BIT && F.disposition_reason[1] == P_MASK_BIT &&
            F.disposition_reason[2] == P_TEXTURE_WINDOW && F.transported == 0 && F.native == 3, "b8_mask_and_window_native"); }

    // B9 capacities, each exactly one past the limit -> whole frame native.
    { for (uint32_t i = 0; i < kMaxTransforms; i++) { const int32_t tr[3] = {(int32_t)i, 0, 1000}; P[i] = prim(0x24, i, tr); }
      build_live(kMaxTransforms, &F);
      check(F.frame_reason == F_OK && F.transform_count == kMaxTransforms, "b9_transforms_at_limit_ok");
      const int32_t trx[3] = {(int32_t)kMaxTransforms, 0, 1000}; P[kMaxTransforms] = prim(0x24, kMaxTransforms, trx);
      build_live(kMaxTransforms + 1, &F);
      check(F.frame_reason == F_OVERFLOW_TRANSFORMS && F.transported == 0 && F.native == kMaxTransforms + 1 &&
            F.group_count == 0 && F.disposition_reason[0] == P_FRAME_NATIVE, "b9_transforms_overflow_whole_native");
      for (uint32_t i = 0; i < kMaxGroups + 1; i++) { P[i] = prim(0x24, i); P[i].tpage = (uint16_t)(i & 1); }  // alternate material
      build_live(kMaxGroups, &F);
      check(F.frame_reason == F_OK && F.group_count == kMaxGroups, "b9_groups_at_limit_ok");
      build_live(kMaxGroups + 1, &F);
      check(F.frame_reason == F_OVERFLOW_GROUPS && F.transported == 0, "b9_groups_overflow_whole_native");
      for (uint32_t i = 0; i < 683; i++) P[i] = prim(0x2C, i);       // quads: 6 vertices each; 682*6 = 4092 fits
      build_live(682, &F);
      check(F.frame_reason == F_OK && F.vert_count == 4092, "b9_verts_at_limit_ok");
      build_live(683, &F);
      check(F.frame_reason == F_OVERFLOW_VERTS && F.transported == 0, "b9_verts_overflow_whole_native");
      const SceneCaptureInfo in = info(kMaxPrims + 1);
      t2_build(P, kMaxPrims + 1, &in, L, 0, false, &F);
      check(F.frame_reason == F_TOO_MANY_PRIMS && F.transported == 0, "b9_too_many_prims"); }

    // B10 interleave: native draw before an overlapping later transported polygon -> whole frame native;
    // non-overlapping before, or overlapping after, is allowed.
    { P[0] = prim(0x24, 0);
      const SceneCaptureInfo in = info(1);
      L[0] = led(0xFFFFFFFFu, 0, 0, 50, 50, false); L[1] = led(0, 10, 10, 20, 20);
      t2_build(P, 1, &in, L, 2, false, &F);
      check(F.frame_reason == F_INTERLEAVED && F.transported == 0, "b10_overlap_before_native");
      L[0] = led(0xFFFFFFFFu, 100, 100, 120, 120, false);
      t2_build(P, 1, &in, L, 2, false, &F);
      check(F.frame_reason == F_OK && F.transported == 1, "b10_disjoint_before_ok");
      L[0] = led(0, 10, 10, 20, 20); L[1] = led(0xFFFFFFFFu, 0, 0, 50, 50, false);
      t2_build(P, 1, &in, L, 2, false, &F);
      check(F.frame_reason == F_OK && F.transported == 1, "b10_overlap_after_ok"); }

    // B11 one disposition per input and the counts add up.
    { P[0] = prim(0x24, 0); P[1] = prim(0x24, 1); P[1].state.set_mask = 1; P[2] = prim(0x2C, 2);
      build_live(3, &F);
      bool all_set = true; for (int i = 0; i < 3; i++) all_set = all_set && F.disposition_reason[i] != P_UNSET;
      check(all_set && F.transported + F.native == 3 && F.transported == 2, "b11_dispositions_complete"); }

    // B12 more than one projection in a frame -> whole frame native.
    { P[0] = prim(0x24, 0); P[1] = prim(0x24, 1, TR0, 0, (uint16_t)(H + 1));
      build_live(2, &F);
      check(F.frame_reason == F_MULTI_PROJECTION && F.transported == 0, "b12_multi_projection"); }

    // B13 coverage and order: incomplete coverage live -> native; diagnostic -> built but never live-eligible;
    // missing ledger / wrong textured index -> unordered.
    { P[0] = prim(0x24, 0);
      const SceneCaptureInfo partial = info(1, 1, 0);
      L[0] = led(0, 0, 0, 1, 1);
      t2_build(P, 1, &partial, L, 1, false, &F);
      check(F.frame_reason == F_INCOMPLETE_COVERAGE && F.live_eligible == 0 && F.transported == 0, "b13_incomplete_coverage_native");
      t2_build(P, 1, &partial, nullptr, 0, true, &F);
      check(F.frame_reason == F_OK && F.diagnostic == 1 && F.live_eligible == 0 && F.transported == 1, "b13_diagnostic_subset_not_live");
      const SceneCaptureInfo full = info(1);
      t2_build(P, 1, &full, nullptr, 0, false, &F);
      check(F.frame_reason == F_UNORDERED, "b13_no_ledger_unordered");
      L[0] = led(7, 0, 0, 1, 1);
      t2_build(P, 1, &full, L, 1, false, &F);
      check(F.frame_reason == F_UNORDERED, "b13_wrong_textured_index_unordered"); }

    // B14 primitives from different generations -> whole frame native.
    { P[0] = prim(0x24, 0); P[1] = prim(0x24, 1, TR0, 0, H, 2);
      build_live(2, &F);
      check(F.frame_reason == F_MIXED_FRAME && F.transported == 0, "b14_mixed_generation"); }

    // ---------------- resolver ----------------
    { const int32_t tr2[3] = {50, 0, 1000};
      P[0] = prim(0x24, 0); P[1] = prim(0x2C, 1, tr2);          // two distinct meshes
      build_live(2, &F);
      check(RES.resolve(F, &RR) && RR.created == 2 && RR.reused == 0 && RR.groups[0].mesh_id == 1 && RR.groups[1].mesh_id == 2, "r1_first_frame_new_ids");
      F2 = F; F2.frame_id = F.frame_id + 1;
      check(RES.resolve(F2, &RR2) && RR2.created == 0 && RR2.reused == 2 && RR2.groups[0].mesh_id == 1 &&
            RR2.groups[1].mesh_id == 2 && RR2.reassigned == 0, "r2_identical_frame_reuses_ids"); }
    { RES.max_entries = 2; RES.retire_frames = 5;                   // cache holds ids 1,2 last used at frame 11
      const int32_t tr3[3] = {0, 50, 1000};
      P[0] = prim(0x26, 0, tr3);                                    // a new mesh (semi class differs)
      build_live(1, &F); F.frame_id = 12;
      check(!RES.resolve(F, &RR) && RES.entries[0].id == 1 && RES.entries[1].id == 2 && RES.next_id == 3, "r4_full_cache_fails_unchanged");
      RES.pin(RR2, +1);                                             // frame 11 still in flight: both pinned
      F.frame_id = 30;
      check(!RES.resolve(F, &RR), "r3_pinned_meshes_not_retired");
      RES.pin(RR2, -1);
      check(RES.resolve(F, &RR) && RR.created == 1 && RR.retired == 1 && RR.groups[0].mesh_id == 3, "r3_retire_unused_new_id_never_reused"); }
    { T2Resolver *r = new T2Resolver();                             // fresh resolver for reassignment
      P[0] = prim(0x24, 0);
      build_live(1, &F); F.frame_id = 1;
      r->resolve(F, &RR);
      const int32_t tr2[3] = {7, 0, 1000};
      P[0] = prim(0x24, 0, tr2);
      build_live(1, &F); F.frame_id = 2;
      check(r->resolve(F, &RR2) && RR2.reused == 1 && RR2.groups[0].mesh_id == RR.groups[0].mesh_id && RR2.reassigned == 1,
            "r5_same_mesh_new_transform_reassigned");
      delete r; }

    // ---------------- hand-off ----------------
    { T2Slot s; s.budget_bytes = 2 * sizeof(T2Frame);
      T2Frame *a = &F, *b = &F2;
      check(s.reserve() && s.reserve() && !s.reserve() && s.refused_budget == 1, "h3_global_budget_refuses_third");
      check(s.publish(a) && s.pending.load() == a, "h1_cas_publish_into_empty");
      check(!s.publish(b) && s.pending.load() == a && s.dropped_busy == 1, "h2_busy_drop_keeps_pending");
      check(s.take() == a && s.pending.load() == nullptr, "h1_take_empties");
      s.release(); check(s.reserve(), "h3_release_then_reserve"); }

    // ---------------- presentation gate ----------------
    { P[0] = prim(0x24, 0); build_live(1, &F);
      const Completion ok{F.frame_id, F.generation, true, 0xABCDull};
      check(t2_gate_allow_suppress(F, 0xABCDull, &ok), "g1_exact_completion_allows");
      const Completion other_frame{F.frame_id + 1, F.generation, true, 0xABCDull};
      const Completion other_gen{F.frame_id, F.generation + 1, true, 0xABCDull};
      const Completion not_done{F.frame_id, F.generation, false, 0xABCDull};
      const Completion bad_order{F.frame_id, F.generation, true, 0x1234ull};
      check(!t2_gate_allow_suppress(F, 0xABCDull, &other_frame) && !t2_gate_allow_suppress(F, 0xABCDull, &other_gen) &&
            !t2_gate_allow_suppress(F, 0xABCDull, &not_done) && !t2_gate_allow_suppress(F, 0xABCDull, &bad_order) &&
            !t2_gate_allow_suppress(F, 0xABCDull, nullptr), "g2_any_mismatch_or_late_is_native");
      const SceneCaptureInfo partial = info(1, 1, 0);
      t2_build(P, 1, &partial, nullptr, 0, true, &F2);
      const Completion d{F2.frame_id, F2.generation, true, 0xABCDull};
      check(!t2_gate_allow_suppress(F2, 0xABCDull, &d), "g2_diagnostic_frame_never_suppresses"); }

    FILE *out = fopen(argv[1], "wb");
    if (!out) return 4;
    fprintf(out, "{\"fixture\":\"t2\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"failed\":\"%s\",\"passed\":%s,"
                 "\"gl_used\":false,\"sdk_used\":false}\n", checks, failures, failed, failures ? "false" : "true");
    fclose(out);
    return failures ? 1 : 0;
}
