// T2 r6: owned present lifecycle for the frame-bound scanout handoff (claude-einhander), per root msg_31e3312e.
// SOURCE ONLY: not compiled, not run, not linked into the native renderer; no live gate, no native suppression.
// r6 is root's "new r5 source": remix_t2.r5.h (f429cc3b) is preserved unchanged and is NOT included. r6 is a
// self-contained layer over r4; remix_t2.r3.h (8baba81c) and remix_t2.r4.h (eebb2c8f, including arm_epoch() and
// its F7 test) are unchanged. Include them (and their prerequisites) before this header.
//
// Root decisions applied (msg_31e3312e):
//   1. Capture begin. The r6 capture path calls capture_begin() INSTEAD of r4 arm_epoch(). It returns the CURRENT
//      lifecycle epoch without a bump, and only while the owner is healthy (live owner_errors == 0 and the glue's
//      own health flag). An ordinary new capture therefore never invalidates an owned pending or displayed present
//      frame. arm_epoch() keeps its r4 meaning: calling it bumps the epoch and kills every r6 record.
//   2. Still invalidating: cancel, reset, savestate, foreign calls, an invalid capture and external VRAM writes
//      (r4 epoch bump; on the owner thread through invalidate_all(); a foreign thread can only call
//      L.invalidate(), which the owner turns into retirement at its next boundary()), and EVERY unexpected GP1
//      scanout change (observe_scanout() bumps the epoch itself).
//   3. Owned present records. PresentState (emulation owner) holds at most one PENDING candidate (sealed, bound,
//      waiting for its flip) and one DISPLAYED frame (flipped, being scanned out). A later capture can never
//      overwrite the pending candidate (T2B_PENDING_BUSY). Only the expected flip moves pending -> displayed, and
//      it retires the previous displayed frame. The gate requires the exact serial, frame, generation, epoch,
//      boundary and target, plus a completion stamped with that serial and that scanout generation and state.
//   4. Bounded rules. A pending candidate retires (abandoned) after kMaxPendingBoundaries declared boundaries
//      without its flip; a displayed frame retires (stale) after kMaxDisplayedBoundaries boundaries without the
//      next expected flip. A late flip of a retired candidate is an unexpected change.
//   5. Writes. Every native GP0 draw / fill / copy / upload and every external direct write with a KNOWN footprint
//      (VRAM halfword rect, non-wrapping, inside 1024x512) retires each record whose target rect it overlaps. An
//      unknown, wrapping or out-of-range footprint retires everything. Reference mode retires everything and
//      refuses new candidates. Both fall back native.
//   6. No relaxed gates: r4 provenance, epoch, owner_errors and VRAM policy, and the display-hazard hook, stay
//      required. G4 owned material snapshot, compositor and synchronization remain unqualified.
// Glue duties (glue r3, not written):
//   - observe_scanout() for every GP1 03/05-08 write, with the full raw state (glue r2 gpu_scene_scanout_state);
//   - boundary() at every declared seal, BEFORE that interval's build and bind; the SealedScanout boundary and
//     boundary_generation are read from owner_snapshot() right after it;
//   - note_write() on every VRAM write path with its footprint: a draw, its drawing area (or a tighter clipped
//     box); a fill, its own rect (fills ignore the drawing area); a copy, its destination; an upload, its rect.
//     The display rect of 24-bit or interlaced modes must be computed in VRAM halfwords;
//   - set_reference_mode(true) whenever the ledger or the renderer cannot account for writes;
//   - transport of T2FrameR6 to the consumer (slot) and the consumer's stamping of CompletionR6 from a
//     PresentState snapshot taken at composition.
// Residual (as r4): the gate check is the linearization point; a later change applies from the next check on.
// Not claimed: composition validity, interop image content, G4 material identity, any live suppression.
#include <atomic>
#include <stdint.h>
#include <string.h>
#include <type_traits>

namespace t2 {
namespace r6 {

constexpr uint32_t kScanoutWords = 8;   // glue r2 SCENE_SCANOUT_WORDS: x, y, hx1, hx2, vy1, vy2, mode, disabled
struct ScanoutState { uint32_t w[kScanoutWords]; };
inline bool same(const ScanoutState &a, const ScanoutState &b) { return memcmp(a.w, b.w, sizeof a.w) == 0; }
inline bool same_except_start(const ScanoutState &a, const ScanoutState &b) {
    return memcmp(a.w + 2, b.w + 2, sizeof(uint32_t) * (kScanoutWords - 2)) == 0;
}

constexpr int32_t kVramWidth = 1024, kVramHeight = 512;   // halfwords
constexpr uint32_t kMaxPendingBoundaries = 1;
constexpr uint32_t kMaxDisplayedBoundaries = 2;

// x, y, w, h: non-empty, non-wrapping, inside VRAM.
inline bool rect_valid(const int32_t r[4]) {
    return r[2] > 0 && r[3] > 0 && r[0] >= 0 && r[1] >= 0 && r[0] <= kVramWidth - r[2] && r[1] <= kVramHeight - r[3];
}
// Both rects must be rect_valid.
inline bool rect_overlap(const int32_t a[4], const int32_t b[4]) {
    return a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
}

// Emulation owner at the start of a capture interval, instead of r4 arm_epoch(): the current lifecycle epoch.
inline bool capture_begin(const r4::T2Liveness &L, bool owner_healthy, uint64_t *epoch) {
    *epoch = 0;
    if (!owner_healthy || L.owner_errors_now() != 0) return false;
    const uint64_t e = L.epoch_now();
    if (L.owner_errors_now() != 0) return false;   // note_foreign() raises owner_errors before the epoch
    *epoch = e;
    return true;
}

// Producer (emulation owner) at the seal of the interval: the declared boundary and the explicit target.
struct SealedScanout {
    ScanoutState boundary;                 // raw scanout state at the declared frame boundary
    uint64_t boundary_generation;          // PresentState scanout generation at that boundary
    ScanoutState target;                   // the ONE acceptable next scanout state
    int32_t target_rect[4];                // native displayed VRAM rect at the target: x, y, w, h (halfwords)
    uint8_t draw_area_constant;            // glue: the native drawing area did not change over the sealed interval
    uint16_t draw_left, draw_top, draw_right, draw_bottom;   // that drawing area (native, inclusive)
};
// Zero is never a success value (fail closed on zeroed storage).
enum ScanReason : uint8_t {
    T2S_UNSET = 0, T2S_OK, T2S_NOT_LIVE, T2S_DRAW_AREA_VARIED, T2S_TARGET_NOT_BUFFER, T2S_TARGET_STATE,
    T2S_SINGLE_BUFFER, T2S_TARGET_DISABLED, T2S_RECT, T2S_PRIM_AREA, T2S_HAZARD, T2S_HAZARD_MISSING,
};
enum BindReason : uint8_t {
    T2B_UNBOUND = 0, T2B_OK, T2B_NOT_CANDIDATE, T2B_REFERENCE, T2B_PENDING_BUSY, T2B_NOT_LIVE, T2B_SCANOUT_MOVED,
    T2B_TARGET_DISPLAYED,
};
// Producer-thread hook: VRAM display hazard of the target's displayed rect against the transported pages/CLUTs of
// the exact ordinal set (ledger r1 scene_ledger_display_hazard, not implemented yet). kPolicyTransportOk when clear.
struct DisplayHazardHook {
    uint32_t (*fn)(void *ctx, uint32_t frame, uint32_t generation, const uint32_t *ordinals, uint32_t count,
                   const int32_t rect[4]);
    void *ctx;
};
struct PresentBinding {
    ScanoutState boundary;
    uint64_t boundary_generation;
    ScanoutState target;
    int32_t target_rect[4];
    uint64_t serial;                       // PresentState serial after a successful bind(); 0 = not bound
    uint8_t scan_ok;                       // 1 only after every build() check
};
struct T2FrameR6 {
    r4::T2FrameR4 r4;
    PresentBinding present;
    ScanReason scan_reason;
    BindReason bind_reason;
    uint32_t hazard_verdict;               // audit
};

// Producer, owner thread. r4::build first (unchanged), then the scanout checks. Pure: binds nothing yet.
inline void build(const ScenePrimitive *prims, uint32_t count, const SceneCaptureInfo *info, const r4::SealedBinding &b,
                  const LedgerHeader *lh, const LedgerEntry *ledger, uint32_t ledger_count,
                  const r4::PolicyHook *policy, const r4::T2Liveness &L, const SealedScanout &ss,
                  const DisplayHazardHook *hazard, T2FrameR6 *out) {
    memset(out, 0, sizeof *out);
    r4::build(prims, count, info, b, lh, ledger, ledger_count, false, policy, L, &out->r4);
    out->hazard_verdict = r4::kPolicyNotEvaluated;
    const T2Frame &f = out->r4.frame;
    ScanReason r = T2S_OK;
    if (out->r4.prov_reason != r4::PR_OK || !out->r4.prov.bound || !out->r4.prov.policy_ok || !f.live_eligible ||
        f.frame_reason != F_OK)
        r = T2S_NOT_LIVE;
    else if (!ss.draw_area_constant) r = T2S_DRAW_AREA_VARIED;
    else if (ss.target.w[0] != (uint32_t)ss.draw_left || ss.target.w[1] != (uint32_t)ss.draw_top) r = T2S_TARGET_NOT_BUFFER;
    else if (!same_except_start(ss.target, ss.boundary)) r = T2S_TARGET_STATE;
    else if (ss.target.w[0] == ss.boundary.w[0] && ss.target.w[1] == ss.boundary.w[1]) r = T2S_SINGLE_BUFFER;
    else if (ss.target.w[7] != 0) r = T2S_TARGET_DISABLED;
    else if (!rect_valid(ss.target_rect) || ss.target_rect[0] != (int32_t)ss.target.w[0] ||
             ss.target_rect[1] != (int32_t)ss.target.w[1])
        r = T2S_RECT;
    uint32_t ords[kMaxPrims];
    uint32_t n = 0;
    if (r == T2S_OK) {
        for (uint32_t i = 0; i < f.prim_count && r == T2S_OK; i++) {
            if (f.disposition_reason[i] != P_TRANSPORTED) continue;
            const SceneDrawState &st = prims[i].state;
            if (st.draw_left != ss.draw_left || st.draw_top != ss.draw_top || st.draw_right != ss.draw_right ||
                st.draw_bottom != ss.draw_bottom)
                r = T2S_PRIM_AREA;
            ords[n++] = prims[i].ordinal;
        }
    }
    if (r == T2S_OK) {
        if (!hazard || !hazard->fn) r = T2S_HAZARD_MISSING;
        else {
            out->hazard_verdict = hazard->fn(hazard->ctx, out->r4.prov.frame, out->r4.prov.generation, ords, n,
                                             ss.target_rect);
            if (out->hazard_verdict != r4::kPolicyTransportOk) r = T2S_HAZARD;
        }
    }
    out->scan_reason = r;
    if (r != T2S_OK) return;   // the r4 frame stays as built; without scan_ok it can never be bound or gated
    out->present.boundary = ss.boundary;
    out->present.boundary_generation = ss.boundary_generation;
    out->present.target = ss.target;
    memcpy(out->present.target_rect, ss.target_rect, sizeof ss.target_rect);
    out->present.scan_ok = 1;
}

enum PresentKind : uint32_t { T2P_EMPTY = 0, T2P_PENDING, T2P_DISPLAYED };
enum RetireReason : uint32_t {
    T2R_NONE = 0, T2R_SUPERSEDED, T2R_ABANDONED, T2R_STALE, T2R_UNEXPECTED_SCANOUT, T2R_WRITE, T2R_UNKNOWN_WRITE,
    T2R_REFERENCE, T2R_EPOCH, T2R_INVALIDATED,
};
enum ChangeKind : uint8_t { T2C_NO_CHANGE = 0, T2C_FLIP_EXPECTED, T2C_UNEXPECTED };
struct PresentRecord {
    uint64_t serial, epoch, boundary_generation, flip_generation;   // flip_generation: 0 while pending
    uint32_t kind, frame, generation, boundaries;                   // boundaries waited (pending) or shown (displayed)
    ScanoutState target;
    int32_t target_rect[4];
};
struct PresentSnapshot {
    uint64_t scanout_generation;           // 0 until the first observation
    uint64_t retired_serial;               // audit: serial of the last retired record
    ScanoutState scanout;
    PresentRecord pending, displayed;
    uint32_t reference_mode, last_retire_reason;
};
static_assert(sizeof(PresentRecord) == 96 && sizeof(PresentSnapshot) == 248, "no padding: published word by word");
static_assert(std::is_trivially_copyable<PresentSnapshot>::value, "published by memcpy");

// Single writer (emulation owner); any number of readers through a seqlock over atomic words (Boehm's pattern).
class PresentState {
public:
    static constexpr uint32_t kWords = sizeof(PresentSnapshot) / sizeof(uint32_t);
    PresentState() { memset(&cur_, 0, sizeof cur_); }

    // ---- emulation owner only ----
    const PresentSnapshot &owner_snapshot() const { return cur_; }

    // Every GP1 scanout write. A same-value rewrite is no change. Only the pending candidate's exact target, as the
    // first change after its boundary, is the expected flip; anything else retires every record and bumps the epoch.
    ChangeKind observe_scanout(const ScanoutState &s, r4::T2Liveness &L) {
        if (initialized_ && same(s, cur_.scanout)) return T2C_NO_CHANGE;
        const bool first = !initialized_;
        initialized_ = true;
        const uint64_t before = cur_.scanout_generation;
        cur_.scanout = s;
        cur_.scanout_generation = before + 1;
        PresentRecord &p = cur_.pending;
        ChangeKind k = T2C_UNEXPECTED;
        if (!first && !cur_.reference_mode && p.kind == T2P_PENDING && p.boundary_generation == before &&
            same(s, p.target) && p.epoch == L.epoch_now() && L.owner_errors_now() == 0) {
            retire(&cur_.displayed, T2R_SUPERSEDED);
            cur_.displayed = p;
            cur_.displayed.kind = T2P_DISPLAYED;
            cur_.displayed.flip_generation = before + 1;
            cur_.displayed.boundaries = 0;
            memset(&p, 0, sizeof p);
            k = T2C_FLIP_EXPECTED;
        } else {
            retire_all(T2R_UNEXPECTED_SCANOUT);
        }
        publish();
        if (k == T2C_UNEXPECTED) L.invalidate();
        return k;
    }

    // Every declared boundary (seal), before that interval's build and bind: epoch check, then the bounded rules.
    void boundary(const r4::T2Liveness &L) {
        const uint64_t e = L.epoch_now();
        const bool unhealthy = L.owner_errors_now() != 0;
        if (cur_.pending.kind != T2P_EMPTY && (unhealthy || cur_.pending.epoch != e)) retire(&cur_.pending, T2R_EPOCH);
        if (cur_.displayed.kind != T2P_EMPTY && (unhealthy || cur_.displayed.epoch != e))
            retire(&cur_.displayed, T2R_EPOCH);
        if (cur_.pending.kind == T2P_PENDING && ++cur_.pending.boundaries > kMaxPendingBoundaries)
            retire(&cur_.pending, T2R_ABANDONED);
        if (cur_.displayed.kind == T2P_DISPLAYED && ++cur_.displayed.boundaries > kMaxDisplayedBoundaries)
            retire(&cur_.displayed, T2R_STALE);
        publish();
    }

    // Bind a built frame as THE pending candidate. Never replaces an existing pending candidate.
    BindReason bind(const r4::T2Liveness &L, T2FrameR6 *f) {
        BindReason r = T2B_OK;
        if (!f->present.scan_ok || f->scan_reason != T2S_OK) r = T2B_NOT_CANDIDATE;
        else if (cur_.reference_mode) r = T2B_REFERENCE;
        else if (cur_.pending.kind != T2P_EMPTY) r = T2B_PENDING_BUSY;
        else if (r4::liveness(L, f->r4) != r4::PR_OK) r = T2B_NOT_LIVE;
        else if (!initialized_ || cur_.scanout_generation != f->present.boundary_generation ||
                 !same(cur_.scanout, f->present.boundary))
            r = T2B_SCANOUT_MOVED;
        else if (cur_.displayed.kind == T2P_DISPLAYED && rect_overlap(cur_.displayed.target_rect, f->present.target_rect))
            r = T2B_TARGET_DISPLAYED;
        f->bind_reason = r;
        if (r != T2B_OK) {
            f->present.serial = 0;
            return r;
        }
        PresentRecord &p = cur_.pending;
        p.serial = ++next_serial_;
        p.epoch = f->r4.prov.epoch;
        p.boundary_generation = f->present.boundary_generation;
        p.flip_generation = 0;
        p.kind = T2P_PENDING;
        p.frame = f->r4.prov.frame;
        p.generation = f->r4.prov.generation;
        p.boundaries = 0;
        p.target = f->present.target;
        memcpy(p.target_rect, f->present.target_rect, sizeof p.target_rect);
        f->present.serial = p.serial;
        publish();
        return T2B_OK;
    }

    // Every VRAM write path (native GP0 draw / fill / copy / upload, external direct write) with its footprint.
    void note_write(const int32_t rect[4], bool footprint_known) {
        bool changed = false;
        if (!footprint_known || !rect_valid(rect)) {
            changed = retire_all(T2R_UNKNOWN_WRITE);
        } else {
            if (cur_.pending.kind != T2P_EMPTY && rect_overlap(rect, cur_.pending.target_rect))
                changed = retire(&cur_.pending, T2R_WRITE) || changed;
            if (cur_.displayed.kind != T2P_EMPTY && rect_overlap(rect, cur_.displayed.target_rect))
                changed = retire(&cur_.displayed, T2R_WRITE) || changed;
        }
        if (changed) publish();
    }

    // Reference / unaccounted mode: retire everything and refuse new candidates while on.
    void set_reference_mode(bool on) {
        cur_.reference_mode = on ? 1u : 0u;
        if (on) retire_all(T2R_REFERENCE);
        publish();
    }

    // Owner-thread cancel, reset, savestate, invalid capture, external write: retire everything, bump the epoch.
    void invalidate_all(r4::T2Liveness &L, RetireReason why) {
        retire_all(why);
        publish();
        L.invalidate();
    }

    // ---- any thread: a consistent snapshot, or false if none was seen within the retry bound ----
    bool read(PresentSnapshot *out) const {
        for (int attempt = 0; attempt < 64; attempt++) {
            const uint64_t q0 = seq_.load(std::memory_order_acquire);
            if (q0 & 1u) continue;
            uint32_t w[kWords];
            for (uint32_t i = 0; i < kWords; i++) w[i] = pub_[i].load(std::memory_order_relaxed);
            std::atomic_thread_fence(std::memory_order_acquire);
            if (seq_.load(std::memory_order_relaxed) == q0) { memcpy(out, w, sizeof w); return true; }
        }
        return false;
    }

private:
    bool retire(PresentRecord *r, RetireReason why) {
        if (r->kind == T2P_EMPTY) return false;
        cur_.retired_serial = r->serial;
        cur_.last_retire_reason = why;
        memset(r, 0, sizeof *r);
        return true;
    }
    bool retire_all(RetireReason why) {
        const bool a = retire(&cur_.pending, why);
        const bool b = retire(&cur_.displayed, why);
        return a || b;
    }
    void publish() {
        uint32_t w[kWords];
        memcpy(w, &cur_, sizeof w);
        const uint64_t q = seq_.load(std::memory_order_relaxed);
        seq_.store(q + 1, std::memory_order_relaxed);              // odd: write in progress
        std::atomic_thread_fence(std::memory_order_release);
        for (uint32_t i = 0; i < kWords; i++) pub_[i].store(w[i], std::memory_order_relaxed);
        seq_.store(q + 2, std::memory_order_release);              // even: stable
    }

    PresentSnapshot cur_;                  // owner only
    bool initialized_ = false;             // owner only: the first observation is always a change
    uint64_t next_serial_ = 0;             // owner only
    std::atomic<uint64_t> seq_{0};
    std::atomic<uint32_t> pub_[kWords] = {};
};

// The consumer stamps the serial and the scanout generation and state its interop image was composited for.
struct CompletionR6 { r4::CompletionR4 c; uint64_t serial; uint64_t scanout_generation; ScanoutState scanout; };

// Consumer: suppression of exactly the displayed record's frame.
inline bool gate_allow_suppress(const T2FrameR6 &f, uint64_t expected_overlay_hash, const CompletionR6 *c,
                                const r4::T2Liveness &L, const PresentState &P) {
    if (!c || !f.present.scan_ok || f.present.serial == 0 || f.bind_reason != T2B_OK) return false;
    if (!r4::gate_allow_suppress(f.r4, expected_overlay_hash, &c->c, L)) return false;
    PresentSnapshot s;
    if (!P.read(&s)) return false;
    const PresentRecord &d = s.displayed;
    return !s.reference_mode && d.kind == T2P_DISPLAYED && d.serial == f.present.serial &&
           d.frame == f.r4.prov.frame && d.generation == f.r4.prov.generation && d.epoch == f.r4.prov.epoch &&
           d.boundary_generation == f.present.boundary_generation && d.flip_generation == d.boundary_generation + 1 &&
           same(d.target, f.present.target) && s.scanout_generation == d.flip_generation && same(s.scanout, d.target) &&
           c->serial == d.serial && c->scanout_generation == d.flip_generation && same(c->scanout, d.target);
}

}  // namespace r6
}  // namespace t2
