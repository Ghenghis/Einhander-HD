// T2 mesh/instance transport r3 (claude-einhander), per spec r1 f673027a and root ADR fa8bf06f.
// r3 (root msg_5e9828cb) on top of r2 (14e87105, preserved): release_underflows is atomic (both threads may
// release); budget_bytes is configuration fixed before the threads start; old_enough never retires at age 0
// (the current frame), whatever retire_frames is.
// r2 (root msg_e8982681) on top of r1 (a00ca23f, preserved): max_entries bounded to the array before any
// find/resolve/pin; retirement uses a modular forward frame age (< 2^31) and never retires on a backward or
// discontinuous frame number; T2Slot reserve/release are overflow/underflow fail-closed with counters.
// r1 applies root reviews msg_ae5bb832 and msg_51d69071 to r0 (ba059e13, preserved):
//   - exact canonical topology and opcode/tpage-derived consistency (no trusting duplicate flags);
//   - native eligibility from v66-r3 scene_capture.cpp 78c4158d :138-156 (every triangle eligible, mapping known,
//     no oversize/clip-out), packet word == view.packed, view.frame + lag == p.frame;
//   - coverage binds info.mode SEALED, malformed 0, info.frame; the ledger carries a provenance header;
//   - resolver initialized by construction, bounded retired-id list at commit, transform_changes (motion
//     UNQUALIFIED), partitioned reuse counts; classification vs final disposition counts.
// MaterialKey is a G2 placeholder (native draw state only), NOT content identity. G4 must bind per-draw
// texture/CLUT content hashes, upload serial, dimensions and an owned RGBA copy of the right draw generation.
// G4 is not implemented; no shader/PBR acceptance.
// SOURCE ONLY: not compiled, not run, not linked into the native renderer (native default untouched).
// Pure CPU, no SDK, GL, threads created, files or globals. C++17.
//
// Four separate pieces with separate tests:
//   t2_build     producer, stateless: sealed ScenePrimitive[] (+ draw-order ledger) -> owned immutable T2Frame
//   T2Resolver   consumer-owned mesh cache: new/reuse ids, retirement, budgets, instance identity
//   T2Slot       single pending slot: CAS(empty->frame) publish, exchange take, global byte budget
//   t2_gate      live presentation gate model: native suppression only for the exact completed frame
//
// Requires, included before this header: <stdint.h>, scene_capture.h (v68 b90ebe9d, includes pgxp.h),
// FLAG_DIV_OVF, gte_divide_extracted.inc (cfa7686a) and remix_t1_reproject.r1.h (4a0a536c).
//
// Field semantics read in v66-r3 scene_capture.cpp: qualified is cleared when any vertex reason != OK (:136);
// mixed_lag (:127); indices are fixed 0,1,2 / 2,1,3 (:115); oversize, clip_out and eligible masks per triangle
// (:151-156); screen_mapping_known = state.native_screen_mapping (:138); ordinal = textured_seen-1 (:110).
#pragma once
#include <atomic>
#include <stdint.h>
#include <string.h>

namespace t2 {

constexpr uint32_t kMaxPrims = 1024;       // == SCENE_CAPACITY
constexpr uint32_t kMaxGroups = 512;
constexpr uint32_t kMaxGroupVerts = 256;   // per group (triangle list, 3 per triangle)
constexpr uint32_t kMaxFrameVerts = 4096;
constexpr uint32_t kMaxTransforms = 256;
constexpr uint32_t kMaxLedger = 4096;

enum PrimReason : uint8_t {
    P_UNSET = 0,             // zeroed storage is never "transported"
    P_TRANSPORTED,
    P_FRAME_NATIVE,          // the whole frame fell back; see T2Frame.frame_reason
    P_NOT_POLYGON, P_NOT_QUALIFIED, P_VERTEX_REASON, P_LAG, P_MIXED_TRANSFORM, P_MAC_RECOMPUTE,
    P_T1, P_MASK_BIT, P_TEXTURE_WINDOW, P_BAD_TOPOLOGY,
    P_INCONSISTENT,          // a flag disagrees with what the opcode/tpage define
    P_NOT_ELIGIBLE,          // a native triangle is not eligible (oversize, clipped out, mapping unknown)
    P_PACKET_MAPPING,        // the GP0 packet word is not the view's SXY word
    P_LAG_BINDING,           // view.frame + lag != primitive frame
};
enum FrameReason : uint8_t {
    F_OK = 0, F_EMPTY, F_TOO_MANY_PRIMS, F_OVERFLOW_GROUPS, F_OVERFLOW_VERTS, F_OVERFLOW_TRANSFORMS,
    F_MULTI_PROJECTION, F_MIXED_FRAME, F_UNORDERED, F_INTERLEAVED, F_INCOMPLETE_COVERAGE,
};
enum SemiClass : uint8_t { S_NONE = 0, S_TEXEL_SPLIT = 1, S_WHOLE_BLEND = 2 };

// Draw-order ledger: EVERY GP0 draw command of the frame in submission order (polygons, sprites, rects,
// lines, fills). The v66/v68 scene capture records ONLY textured polygons (other classes are counters only)
// and ScenePrimitive.ordinal is the textured-polygon index (textured_seen - 1), NOT a global GP0 ordinal.
// No current capture produces this ledger: it needs a separate capture revision. Until then t2_build can
// only run in diagnostic mode and no frame is live-eligible.
struct LedgerEntry { int16_t x0, y0, x1, y1; uint32_t textured_index; uint8_t captured_textured; };
// Provenance of a ledger: the same sealed frame and generation as the capture, completeness over ALL commands
// of the interval, and the full command count (not the textured count).
struct LedgerHeader { uint32_t frame, generation, command_count; uint8_t complete; };

struct TransformKey { int16_t rt[9]; int32_t tr[3]; uint16_t h; int32_t ofx, ofy; };
struct MaterialKey { uint16_t tpage, clut; uint32_t texture_window; uint8_t depth, textured, raw, blend_mode; };
struct Vert { int16_t x, y, z; uint8_t u, v; uint32_t rgb; };   // model-space V, exact
struct Group {
    uint16_t transform;                // index into T2Frame::transforms
    MaterialKey material;
    SemiClass semi;
    uint8_t instances;                 // 2 for S_TEXEL_SPLIT (opaque texels, blend texels), else 1
    uint32_t first_vert, vert_count;   // triangle list: vert_count % 3 == 0
    uint64_t content_hash;             // bucket only; equality is a full key compare in the resolver
};

// Owned, immutable after t2_build. Copied by value; contains no pointers.
struct T2Frame {
    uint32_t frame_id, generation, prim_count;
    FrameReason frame_reason;
    // live_eligible requires complete capture coverage (all GP0 geometry classes recorded) AND a ledger.
    // Dispositions cover ONLY the captured textured polygons; they are not a statement about any other
    // command of the frame. A diagnostic frame (live_eligible == 0) must never suppress native drawing.
    uint8_t live_eligible, diagnostic;
    uint8_t disposition_reason[kMaxPrims];        // PrimReason per input primitive, input order
    uint32_t transported, native;
    uint16_t projection_h; int32_t projection_ofx, projection_ofy;
    uint32_t transform_count, group_count, vert_count;
    TransformKey transforms[kMaxTransforms];
    Group groups[kMaxGroups];
    Vert verts[kMaxFrameVerts];
    // class_counts: the per-primitive classification; final_counts: the final dispositions after any
    // whole-frame fallback. They differ exactly when the frame fell back.
    static constexpr uint32_t kReasons = 24;
    uint32_t class_counts[kReasons], final_counts[kReasons];
};

inline uint64_t fnv(const void *p, size_t n, uint64_t h = 1469598103934665603ull) {
    const uint8_t *b = static_cast<const uint8_t *>(p);
    for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 1099511628211ull; }
    return h;
}

inline TransformKey transform_of(const SceneVertex &v) {
    TransformKey k; memset(&k, 0, sizeof k);             // padding zeroed: memcmp is a full-field compare
    memcpy(k.rt, v.rt, sizeof k.rt); memcpy(k.tr, v.tr, sizeof k.tr);
    k.h = v.view.h; k.ofx = v.view.ofx; k.ofy = v.view.ofy;
    return k;
}

// MAC_a = TR[a]*4096 + RT[a][0]*V0 + RT[a][1]*V1 + RT[a][2]*V2, exactly as the producer computes it.
inline bool mac_recompute_equal(const SceneVertex &v) {
    for (int a = 0; a < 3; a++) {
        const int64_t m = (int64_t)v.tr[a] * 4096 + (int64_t)v.rt[a * 3 + 0] * v.view.v[0] +
                          (int64_t)v.rt[a * 3 + 1] * v.view.v[1] + (int64_t)v.rt[a * 3 + 2] * v.view.v[2];
        if (m != v.view.mac[a]) return false;
    }
    return true;
}

inline bool is_polygon(uint8_t op) { return (op & 0xE0) == 0x20; }

// Per-primitive gate. Returns P_TRANSPORTED or the first native reason.
inline PrimReason classify(const ScenePrimitive &p) {
    if (!is_polygon(p.opcode)) return P_NOT_POLYGON;
    if (!p.qualified || p.mixed_lag) return P_NOT_QUALIFIED;
    if (p.state.check_mask || p.state.set_mask) return P_MASK_BIT;
    const bool textured = (p.opcode & 0x04) != 0;
    if (textured && p.state.texture_window) return P_TEXTURE_WINDOW;
    // Topology is defined by the opcode, never trusted from the stored flags.
    const uint8_t nverts = (p.opcode & 0x08) ? 4 : 3, tris = (uint8_t)(nverts - 2);
    if (p.nverts != nverts || p.triangle_count != tris) return P_BAD_TOPOLOGY;
    static const uint8_t kCanonical[6] = {0, 1, 2, 2, 1, 3};
    if (memcmp(p.indices, kCanonical, (size_t)tris * 3) != 0) return P_BAD_TOPOLOGY;
    // Duplicate flags must agree with the opcode and tpage that define them (capture :112-114).
    if (p.semi_trans != ((p.opcode >> 1) & 1) || p.raw_texture != (p.opcode & 1)) return P_INCONSISTENT;
    if (textured && (p.depth != ((p.tpage >> 7) & 3) || p.blend_mode != ((p.tpage >> 5) & 3))) return P_INCONSISTENT;
    // Native eligibility (capture :138-156): every native triangle eligible, mapping known, none oversize or
    // clipped out. A triangle the native GPU discards or never shows must not become transported geometry.
    const uint8_t all = (uint8_t)((1u << tris) - 1u);
    if (!p.screen_mapping_known || p.oversize_mask || p.clip_out_mask || (p.eligible_triangle_mask & all) != all)
        return P_NOT_ELIGIBLE;
    const TransformKey k0 = transform_of(p.vertex[0]);
    for (int i = 0; i < p.nverts; i++) {
        const SceneVertex &v = p.vertex[i];
        if (v.reason != SCENE_VERTEX_OK) return P_VERTEX_REASON;
        if (v.lag > 1 || v.lag != p.vertex[0].lag) return P_LAG;
        if ((uint32_t)(v.view.frame + v.lag) != p.frame) return P_LAG_BINDING;   // declared lag, actually checked
        if (v.packet_word != v.view.packed) return P_PACKET_MAPPING;           // T1b: GP0 word is the SXY word
        const TransformKey k = transform_of(v);
        if (memcmp(&k, &k0, sizeof k) != 0) return P_MIXED_TRANSFORM;
        if (!mac_recompute_equal(v)) return P_MAC_RECOMPUTE;
        T1Expect e;
        if (t1_reproject(v.view, true, &e) != T1_MATCH) return P_T1;
    }
    return P_TRANSPORTED;
}

inline MaterialKey material_of(const ScenePrimitive &p) {
    MaterialKey m; memset(&m, 0, sizeof m);
    m.textured = (p.opcode & 0x04) != 0;
    if (m.textured) { m.tpage = p.tpage; m.clut = p.clut; m.texture_window = p.state.texture_window; m.depth = p.depth; }
    m.raw = m.textured ? p.raw_texture : 0;           // raw bypasses colour modulation only
    m.blend_mode = p.semi_trans ? p.blend_mode : 0;
    return m;
}

inline SemiClass semi_of(const ScenePrimitive &p) {
    if (!p.semi_trans) return S_NONE;
    return (p.opcode & 0x04) ? S_TEXEL_SPLIT : S_WHOLE_BLEND;   // raw or modulated textured: per-texel STP
}

inline bool overlap(const LedgerEntry &a, const LedgerEntry &b) {
    return a.x0 <= b.x1 && b.x0 <= a.x1 && a.y0 <= b.y1 && b.y0 <= a.y1;
}

inline void frame_native(T2Frame *f, FrameReason r) {
    f->frame_reason = r;
    f->transported = 0; f->native = f->prim_count;
    f->transform_count = f->group_count = f->vert_count = 0;
    for (uint32_t i = 0; i < f->prim_count; i++)
        if (f->disposition_reason[i] == P_TRANSPORTED || f->disposition_reason[i] == P_UNSET)
            f->disposition_reason[i] = P_FRAME_NATIVE;
}

// Producer. Stateless: reads only its arguments.
//   info:       the SceneCaptureInfo of the same sealed capture (required).
//   ledger:     every GP0 draw command of the frame in order (required for live eligibility; none exists yet).
//   diagnostic: true builds a captured-textured-subset frame WITHOUT coverage/ledger proof, for the captured-frame
//               diagnostic (T3) only; such a frame has live_eligible = 0 and never authorizes native suppression.
inline void t2_build_impl(const ScenePrimitive *prims, uint32_t count, const SceneCaptureInfo *info,
                          const LedgerHeader *lh, const LedgerEntry *ledger, uint32_t ledger_count,
                          bool diagnostic, T2Frame *f) {
    memset(f, 0, sizeof *f);
    f->diagnostic = diagnostic ? 1 : 0;
    f->prim_count = count > kMaxPrims ? kMaxPrims : count;
    if (count == 0) { f->frame_reason = F_EMPTY; return; }
    if (count > kMaxPrims) { f->prim_count = kMaxPrims; frame_native(f, F_TOO_MANY_PRIMS); return; }
    f->frame_id = prims[0].frame; f->generation = prims[0].generation;
    for (uint32_t i = 0; i < count; i++) {
        f->disposition_reason[i] = classify(prims[i]);
        f->class_counts[f->disposition_reason[i]]++;
        if (prims[i].frame != f->frame_id || prims[i].generation != f->generation) { frame_native(f, F_MIXED_FRAME); return; }
    }
    const bool coverage = info && info->mode == SCENE_SEALED && info->complete && info->malformed == 0 &&
                          info->geometry_types_complete && info->overflow == 0 && info->count == count &&
                          info->generation == f->generation && info->frame == f->frame_id;
    if (!coverage && !diagnostic) { frame_native(f, F_INCOMPLETE_COVERAGE); return; }
    if (!diagnostic) {
        // The ledger must prove the same sealed frame/generation and complete coverage of ALL its commands.
        if (!lh || !ledger || ledger_count > kMaxLedger || !lh->complete || lh->frame != f->frame_id ||
            lh->generation != f->generation || lh->command_count != ledger_count) { frame_native(f, F_UNORDERED); return; }
        // Order: map captured textured polygons (by textured index) to ledger positions; any mismatch -> unordered.
        uint32_t pos[kMaxPrims];
        { uint32_t c = 0;
          for (uint32_t j = 0; j < ledger_count; j++) {
              if (!ledger[j].captured_textured) continue;
              if (c >= count || ledger[j].textured_index != prims[c].ordinal) { frame_native(f, F_UNORDERED); return; }
              pos[c++] = j;
          }
          if (c != count) { frame_native(f, F_UNORDERED); return; } }
        // Interleave: a NON-transported draw that precedes a later transported polygon and overlaps it on
        // screen -> the whole frame stays native (pilot rule).
        { bool transported_at[kMaxLedger]; memset(transported_at, 0, sizeof transported_at);
          for (uint32_t i = 0; i < count; i++) if (f->disposition_reason[i] == P_TRANSPORTED) transported_at[pos[i]] = true;
          for (uint32_t j = 0; j < ledger_count; j++) {
              if (transported_at[j]) continue;
              for (uint32_t k = j + 1; k < ledger_count; k++)
                  if (transported_at[k] && overlap(ledger[j], ledger[k])) { frame_native(f, F_INTERLEAVED); return; }
          } }
    }
    // Groups: contiguous runs of equal (transform, material, semi class) in submission order.
    bool have_projection = false;
    for (uint32_t i = 0; i < count; i++) {
        if (f->disposition_reason[i] != P_TRANSPORTED) continue;
        const ScenePrimitive &p = prims[i];
        const TransformKey tk = transform_of(p.vertex[0]);
        if (!have_projection) { f->projection_h = tk.h; f->projection_ofx = tk.ofx; f->projection_ofy = tk.ofy; have_projection = true; }
        else if (tk.h != f->projection_h || tk.ofx != f->projection_ofx || tk.ofy != f->projection_ofy) { frame_native(f, F_MULTI_PROJECTION); return; }
        uint32_t t = 0;
        for (; t < f->transform_count; t++) if (memcmp(&f->transforms[t], &tk, sizeof tk) == 0) break;  // full equality
        if (t == f->transform_count) {
            if (f->transform_count >= kMaxTransforms) { frame_native(f, F_OVERFLOW_TRANSFORMS); return; }
            f->transforms[f->transform_count++] = tk;
        }
        const MaterialKey mk = material_of(p);
        const SemiClass sc = semi_of(p);
        Group *g = f->group_count ? &f->groups[f->group_count - 1] : nullptr;
        const bool contiguous = g && g->transform == t && g->semi == sc && memcmp(&g->material, &mk, sizeof mk) == 0 &&
                                i > 0 && f->disposition_reason[i - 1] == P_TRANSPORTED;
        const uint32_t add = (uint32_t)p.triangle_count * 3;
        if (!contiguous || g->vert_count + add > kMaxGroupVerts) {
            if (f->group_count >= kMaxGroups) { frame_native(f, F_OVERFLOW_GROUPS); return; }
            g = &f->groups[f->group_count++];
            memset(g, 0, sizeof *g);
            g->transform = (uint16_t)t; g->material = mk; g->semi = sc; g->instances = sc == S_TEXEL_SPLIT ? 2 : 1;
            g->first_vert = f->vert_count;
        }
        if (f->vert_count + add > kMaxFrameVerts) { frame_native(f, F_OVERFLOW_VERTS); return; }
        for (int k = 0; k < p.triangle_count * 3; k++) {
            const SceneVertex &v = p.vertex[p.indices[k]];
            Vert &o = f->verts[f->vert_count++];
            memset(&o, 0, sizeof o);
            o.x = v.view.v[0]; o.y = v.view.v[1]; o.z = v.view.v[2]; o.u = v.u; o.v = v.v; o.rgb = v.rgb;
        }
        g->vert_count += add;
        f->transported++;
    }
    f->native = count - f->transported;
    for (uint32_t gi = 0; gi < f->group_count; gi++) {
        Group &g = f->groups[gi];
        uint64_t h = fnv(&g.material, sizeof g.material);
        h = fnv(&g.semi, sizeof g.semi, h);
        g.content_hash = fnv(&f->verts[g.first_vert], sizeof(Vert) * g.vert_count, h);
    }
    f->frame_reason = F_OK;
    f->live_eligible = diagnostic ? 0 : 1;   // only reachable non-diagnostic with coverage + ledger proven
}

// Public entry: build, then derive final disposition counts from the final dispositions (after any
// whole-frame fallback), separately from the classification counts.
inline void t2_build(const ScenePrimitive *prims, uint32_t count, const SceneCaptureInfo *info,
                     const LedgerHeader *lh, const LedgerEntry *ledger, uint32_t ledger_count,
                     bool diagnostic, T2Frame *f) {
    t2_build_impl(prims, count, info, lh, ledger, ledger_count, diagnostic, f);
    memset(f->final_counts, 0, sizeof f->final_counts);
    for (uint32_t i = 0; i < f->prim_count; i++) f->final_counts[f->disposition_reason[i]]++;
}

// ---------------- consumer-owned resolver (Remix thread) ----------------
constexpr uint32_t kCacheEntries = 512;
struct MeshEntry {
    bool used; uint64_t id, hash; uint32_t last_frame, refs;   // refs: pending + in-flight frames using it
    MaterialKey material; SemiClass semi; uint32_t vert_count; Vert verts[kMaxGroupVerts];
};
struct Resolution { uint64_t mesh_id; bool created; uint32_t run_ordinal; uint16_t transform; };
struct ResolveResult {
    bool ok;
    uint32_t created;                 // groups that created a new mesh
    uint32_t reused;                  // groups mapped to a mesh that existed BEFORE this frame
    uint32_t duplicate_new;           // groups mapped to a mesh created earlier in THIS frame
    uint32_t transform_changes;       // (mesh id, run ordinal) seen last frame with a different transform.
                                      // This includes ordinary motion; it is NOT an identity-reassignment
                                      // measure and qualifies no motion vectors.
    uint32_t retired_count;           // meshes evicted at commit; the consumer must DestroyMesh exactly these
    uint64_t retired_ids[kCacheEntries];
    Resolution groups[kMaxGroups]; uint32_t group_count;
};

struct T2Resolver {
    // Initialized by construction (value-initialized arrays): a default-initialized or `new T2Resolver`
    // object never reads indeterminate used/refs/ids.
    MeshEntry entries[kCacheEntries] = {};
    uint64_t next_id = 1;
    uint32_t retire_frames = 60, max_entries = kCacheEntries;
    struct Prev { uint64_t id; uint32_t ordinal; TransformKey xf; } prev[kMaxGroups] = {};
    uint32_t prev_count = 0;

    static bool same(const MeshEntry &e, const T2Frame &f, const Group &g) {
        return e.hash == g.content_hash && e.semi == g.semi && e.vert_count == g.vert_count &&
               memcmp(&e.material, &g.material, sizeof g.material) == 0 &&
               memcmp(e.verts, &f.verts[g.first_vert], sizeof(Vert) * g.vert_count) == 0;   // full compare
    }
    // max_entries is public configuration; any value above the array is rejected before indexing.
    bool capacity_valid() const { return max_entries >= 1 && max_entries <= kCacheEntries; }
    int find(const T2Frame &f, const Group &g) const {
        if (!capacity_valid()) return -1;
        for (uint32_t i = 0; i < max_entries; i++) if (entries[i].used && same(entries[i], f, g)) return (int)i;
        return -1;
    }
    // Forward frame age with uint32 wraparound: valid only when the current frame is the same or later by
    // less than 2^31 frames; a backward or discontinuous frame number is never old enough to retire.
    static bool old_enough(uint32_t now, uint32_t last, uint32_t retire) {
        const uint32_t age = now - last;                 // modular
        return age > 0 && age < 0x80000000u && age >= retire;   // never the current frame, even with retire 0
    }
    // Two-phase: plan without mutation; on any failure the cache is unchanged and the frame goes native.
    bool resolve(const T2Frame &f, ResolveResult *r) {
        memset(r, 0, sizeof *r);
        if (!capacity_valid()) return false;
        if (f.frame_reason != F_OK) return false;
        int slot_of[kMaxGroups]; bool is_new[kMaxGroups];
        uint32_t free_slots[kCacheEntries], nfree = 0;
        bool reserved[kCacheEntries]; memset(reserved, 0, sizeof reserved);
        for (uint32_t gi = 0; gi < f.group_count; gi++) {
            const int s = find(f, f.groups[gi]);
            slot_of[gi] = s; is_new[gi] = s < 0;
            if (s >= 0) reserved[s] = true;                       // used by this frame: never retired now
        }
        for (uint32_t i = 0; i < max_entries; i++) {
            const MeshEntry &e = entries[i];
            const bool retirable = e.used && !reserved[i] && e.refs == 0 && old_enough(f.frame_id, e.last_frame, retire_frames);
            if (!e.used || retirable) free_slots[nfree++] = i;
        }
        uint32_t need = 0;
        for (uint32_t gi = 0; gi < f.group_count; gi++) {
            if (!is_new[gi]) continue;
            int dup = -1;                                         // identical new mesh earlier in this frame
            for (uint32_t gj = 0; gj < gi; gj++)
                if (is_new[gj] && f.groups[gj].content_hash == f.groups[gi].content_hash &&
                    f.groups[gj].vert_count == f.groups[gi].vert_count && f.groups[gj].semi == f.groups[gi].semi &&
                    memcmp(&f.groups[gj].material, &f.groups[gi].material, sizeof(MaterialKey)) == 0 &&
                    memcmp(&f.verts[f.groups[gj].first_vert], &f.verts[f.groups[gi].first_vert], sizeof(Vert) * f.groups[gi].vert_count) == 0) { dup = (int)gj; break; }
            if (dup >= 0) { slot_of[gi] = -2 - dup; continue; }   // resolved after its first occurrence
            if (need >= nfree) return false;                       // cache full: nothing mutated
            slot_of[gi] = (int)free_slots[need++];
        }
        // Commit.
        for (uint32_t k = 0; k < need; k++) {           // evictions: report the exact ids for DestroyMesh
            MeshEntry &e = entries[free_slots[k]];
            if (e.used) r->retired_ids[r->retired_count++] = e.id;
        }
        uint32_t ordinal_of[kMaxGroups];
        for (uint32_t gi = 0; gi < f.group_count; gi++) {
            const Group &g = f.groups[gi];
            int s = slot_of[gi];
            bool created = false;
            if (s <= -2) s = slot_of[-2 - s];
            else if (is_new[gi]) {
                MeshEntry &e = entries[s];
                memset(&e, 0, sizeof e);
                e.used = true; e.id = next_id++; e.hash = g.content_hash; e.material = g.material; e.semi = g.semi;
                e.vert_count = g.vert_count; memcpy(e.verts, &f.verts[g.first_vert], sizeof(Vert) * g.vert_count);
                created = true; r->created++;
            }
            if (slot_of[gi] <= -2) r->duplicate_new++;
            else if (!created) r->reused++;
            MeshEntry &e = entries[s];
            e.last_frame = f.frame_id;
            uint32_t ord = 0;
            for (uint32_t gj = 0; gj < gi; gj++) if (r->groups[gj].mesh_id == e.id) ord++;
            ordinal_of[gi] = ord;
            r->groups[gi] = Resolution{e.id, created, ord, g.transform};
        }
        // Instance identity across frames: (mesh id, run ordinal). A different transform than last frame for
        // the same identity is counted as a transform change (ordinary motion included; motion UNQUALIFIED).
        for (uint32_t gi = 0; gi < f.group_count; gi++)
            for (uint32_t pi = 0; pi < prev_count; pi++)
                if (prev[pi].id == r->groups[gi].mesh_id && prev[pi].ordinal == ordinal_of[gi] &&
                    memcmp(&prev[pi].xf, &f.transforms[f.groups[gi].transform], sizeof(TransformKey)) != 0) r->transform_changes++;
        prev_count = f.group_count;
        for (uint32_t gi = 0; gi < f.group_count; gi++)
            prev[gi] = Prev{r->groups[gi].mesh_id, ordinal_of[gi], f.transforms[f.groups[gi].transform]};
        r->group_count = f.group_count;
        r->ok = true;
        return true;
    }
    // A resolved frame is pending/in flight until the consumer finishes with it: its meshes are pinned and
    // never retirable meanwhile (ADR: retire only resources no pending or in-flight frame uses).
    void pin(const ResolveResult &r, int delta) {
        if (!capacity_valid()) return;
        for (uint32_t gi = 0; gi < r.group_count; gi++)
            for (uint32_t i = 0; i < max_entries; i++)
                if (entries[i].used && entries[i].id == r.groups[gi].mesh_id) {
                    if (delta > 0) entries[i].refs++;
                    else if (entries[i].refs) entries[i].refs--;
                    break;
                }
    }
};

// ---------------- single pending slot + global budget ----------------
// Threads: exactly ONE producer (emulation owner thread: reserve, publish, release of an unpublished frame)
// and ONE consumer (Remix owner thread: take, release after the frame is finished). pending and
// bytes_in_use and release_underflows are atomics (release may run on either thread). budget_bytes is
// configuration: set once before either thread starts and never written afterwards. dropped_busy and
// refused_budget are plain counters written ONLY by the producer (publish, reserve) and read by others only
// after the producer thread is joined.
struct T2Slot {
    std::atomic<T2Frame *> pending{nullptr};
    std::atomic<uint64_t> bytes_in_use{0};      // building + pending + in-flight
    std::atomic<uint64_t> release_underflows{0};
    uint64_t budget_bytes = 4 * sizeof(T2Frame);   // immutable once the threads start
    uint64_t dropped_busy = 0, refused_budget = 0; // producer-only writers

    bool reserve() {                            // before building; failure -> do not build (native frame)
        const uint64_t need = sizeof(T2Frame);
        uint64_t cur = bytes_in_use.load();
        do {
            // Overflow-safe: compare against budget - need instead of computing cur + need.
            if (budget_bytes < need || cur > budget_bytes - need) { refused_budget++; return false; }
        } while (!bytes_in_use.compare_exchange_weak(cur, cur + need));
        return true;
    }
    // Fail-closed: a release without a matching reservation never wraps the counter.
    bool release() {
        const uint64_t need = sizeof(T2Frame);
        uint64_t cur = bytes_in_use.load();
        do { if (cur < need) { release_underflows.fetch_add(1); return false; } }
        while (!bytes_in_use.compare_exchange_weak(cur, cur - need));
        return true;
    }
    // Conditional publish into an EMPTY slot; never overwrites. On false the caller still owns `f`
    // and must release only that unpublished frame.
    bool publish(T2Frame *f) {
        T2Frame *expected = nullptr;
        if (pending.compare_exchange_strong(expected, f)) return true;
        dropped_busy++;
        return false;
    }
    T2Frame *take() { return pending.exchange(nullptr); }
};

// ---------------- live presentation gate model ----------------
struct Completion { uint32_t frame_id, generation; bool image_complete; uint64_t overlay_order_hash; };
// Native suppression of frame F is allowed only when the consumer completed the interop image for exactly
// F and its generation, and the native overlay order it composited matches the order F expects.
// A diagnostic or coverage-incomplete frame (live_eligible == 0) never allows suppression.
inline bool t2_gate_allow_suppress(const T2Frame &f, uint64_t expected_overlay_hash, const Completion *c) {
    return f.live_eligible && f.frame_reason == F_OK && c && c->image_complete &&
           c->frame_id == f.frame_id && c->generation == f.generation &&
           c->overlay_order_hash == expected_overlay_hash;
}

}  // namespace t2
