// T2 r4: ownership / provenance / VRAM-policy layer over T2 r3 (claude-einhander), per root msg_a04dd76a and
// msg_54b45d88. SOURCE ONLY: not compiled, not run, not linked into the native renderer (native default untouched).
// remix_t2.r3.h (8baba81c) is preserved byte-for-byte; include it (and its prerequisites) before this header.
// The ledger r0 T2 adapter (scene_ledger_t2.r0.h) stays diagnostic-only: it never consults the ledger policy.
//
// Gaps closed:
//   1. r3 checks coverage once, inside t2_build. A foreign-thread GP0 command, a reset/savestate invalidation or an
//      external VRAM write AFTER the seal (or after build, export, take or completion) left a frame able to
//      authorize native suppression. r3 never read owner_errors.
//   2. Command coverage alone admitted frames whose transported pages/CLUTs were mutated, fed back into, displayed
//      or read back (the ledger policy can be native while the export is complete).
// Rules:
//   - owner_errors == 0 and an unchanged, immutable epoch binding at EVERY boundary: build/acceptance (read
//     before the r3 build and again AFTER the policy walk), export (publish), consumer take, resolve, and the
//     suppression gate (whose completion must carry the same epoch). Each boundary re-reads the live atomics.
//   - Acceptance requires the VRAM policy verdict LP_TRANSPORT_OK, evaluated by a producer-thread hook on the
//     EXACT final transported ordinal set (input order, after r3 classification and all r3 whole-frame rules) with
//     the binding's exact frame and generation. Publish and gate require that accepted policy.
// T2Liveness: one per process, owned by the runtime glue; the consumer touches only these atomics (never the
// owner-only capture/ledger headers):
//   - epoch: monotonic 64-bit, never reset or decreased (no API for either). arm_epoch() assigns the epoch of a new
//     generation; invalidate() (cancel, gpu_reset_state, savestate parse, external VRAM write) and note_foreign()
//     bump it, so every frame bound to an older epoch is dead for good. 2^64 bumps are assumed unreachable.
//   - owner_errors: process-lifetime count of GP0/frame calls from a foreign thread. Any nonzero value disables
//     transport for the rest of the process (root: owner_errors == 0).
//   Glue duty (not in this header; root msg_fb74eece): note_foreign() on EVERY runtime entry that can mutate or
//   observe the GP0/frame stream from a foreign thread (enabled, command, ledger_command, tick, arm, cancel,
//   invalidate), not only enabled/tick; invalidate() at cancel, gpu_reset_state and savestate parse REGARDLESS of
//   the calling thread (a foreign reset/savestate must still kill exported frames), at every external VRAM write,
//   and at every GP1 display-area / range / mode change (gp1_display_area_start, h/v range, display mode), since
//   neither the capture nor the ledger sees GP1 and a change after the last GP0 would otherwise go unnoticed.
// SealedBinding: filled by the producer (owner thread) at build time from the sealed capture info, the sealed
// ledger header (scene_ledger_header) and the arm epoch; a frame then carries an immutable T2Provenance.
// Barriers are NOT relaxed: r3 coverage/ledger/order/interleave rules run unchanged; any r4 failure forces the whole
// frame native (r3 frame_native, live_eligible 0). Diagnostic frames are refused here (they stay on r3).
// Material (G4) and composition validity remain unproven; no live gate is enabled by this header.
// Residual: the gate check is the linearization point; an invalidation after it applies from the next frame on.
#include <atomic>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace t2 {
namespace r4 {

enum ProvReason : uint8_t {
    PR_OK = 0,
    PR_OWNER_ERRORS,          // capture info or live owner_errors != 0
    PR_EPOCH,                 // live epoch != bound epoch (invalidated, re-armed or foreign since arm)
    PR_CHANGED_DURING_BUILD,  // epoch or owner_errors changed between the pre-build and post-policy reads
    PR_CAPTURE,               // capture not sealed/complete
    PR_LEDGER,                // ledger not sealed/complete
    PR_BINDING,               // frame / generation / command count / transported count disagree
    PR_DIAGNOSTIC,            // diagnostic builds stay on r3; never exported or gated here
    PR_POLICY,                // VRAM policy verdict != LP_TRANSPORT_OK
    PR_POLICY_MISSING,        // live frame but no policy hook
    PR_UNBOUND,               // frame carries no provenance (failed build)
    PR_NOT_LIVE_ELIGIBLE,     // r3 frame is native or not live-eligible: nothing to export
    PR_BUSY,                  // slot occupied (r3 semantics: never overwrite)
};

constexpr uint32_t kPolicyTransportOk = 0;   // == LP_TRANSPORT_OK (scene_ledger.r0.h)
constexpr uint32_t kPolicyNotEvaluated = 0xFFFFFFFFu;
// Producer-thread hook; the glue implements it with scene_ledger_policy(owner token, generation, ordinals, count)
// after checking that the sealed ledger header still names this frame and generation.
struct PolicyHook {
    uint32_t (*fn)(void *ctx, uint32_t frame, uint32_t generation, const uint32_t *ordinals, uint32_t count);
    void *ctx;
};

class T2Liveness {
public:
    // Emulation owner at arm, after the capture and ledger arms succeeded: the epoch of the new generation.
    uint64_t arm_epoch() { return epoch_.fetch_add(1, std::memory_order_acq_rel) + 1; }
    // Any thread: cancel, gpu_reset_state / savestate invalidate, external VRAM write.
    void invalidate() { epoch_.fetch_add(1, std::memory_order_acq_rel); }
    // Any thread: a GP0 or frame-path call from a foreign thread (beside the runtime's own owner_errors).
    void note_foreign() {
        owner_errors_.fetch_add(1, std::memory_order_acq_rel);
        epoch_.fetch_add(1, std::memory_order_acq_rel);
    }
    uint64_t epoch_now() const { return epoch_.load(std::memory_order_acquire); }
    uint64_t owner_errors_now() const { return owner_errors_.load(std::memory_order_acquire); }
private:
    std::atomic<uint64_t> epoch_{1};
    std::atomic<uint64_t> owner_errors_{0};
};

struct SealedBinding {
    uint32_t frame, generation, command_count;
    uint64_t epoch;                                   // arm_epoch() of this generation
    uint8_t capture_sealed, capture_complete, ledger_sealed, ledger_complete;
};
struct T2Provenance {
    uint32_t frame, generation, command_count;
    uint64_t epoch;
    uint32_t policy_verdict, policy_count;            // audit: verdict and size of the evaluated transported set
    uint64_t policy_set_hash;                         // r3 fnv of the evaluated ordinal list
    uint8_t bound;                                    // 1 only after a fully checked r4 build
    uint8_t policy_ok;                                // 1 only when that build's live frame passed the policy
};
struct T2FrameR4 {
    T2Frame frame;                                    // the r3 frame, built by r3's t2_build unchanged
    T2Provenance prov;
    ProvReason prov_reason;
};

// Boundary check, re-evaluated at every call.
inline ProvReason liveness(const T2Liveness &L, const T2FrameR4 &fr) {
    if (!fr.prov.bound) return PR_UNBOUND;
    if (L.owner_errors_now() != 0) return PR_OWNER_ERRORS;
    if (L.epoch_now() != fr.prov.epoch) return PR_EPOCH;
    return PR_OK;
}

inline void force_native(T2FrameR4 *fr, ProvReason r) {
    frame_native(&fr->frame, F_INCOMPLETE_COVERAGE);  // r3 helper: whole frame native
    fr->frame.live_eligible = 0;
    memset(fr->frame.final_counts, 0, sizeof fr->frame.final_counts);   // as r3 t2_build derives them
    for (uint32_t i = 0; i < fr->frame.prim_count; i++) fr->frame.final_counts[fr->frame.disposition_reason[i]]++;
    memset(&fr->prov, 0, sizeof fr->prov);
    fr->prov_reason = r;
}

// Boundary 1: acceptance. r3 builds first (stateless, unchanged); r4 then checks provenance, evaluates the VRAM
// policy on the final transported set of a live frame, re-reads the epoch, and binds or forces native.
inline void build(const ScenePrimitive *prims, uint32_t count, const SceneCaptureInfo *info, const SealedBinding &b,
                  const LedgerHeader *lh, const LedgerEntry *ledger, uint32_t ledger_count, bool diagnostic,
                  const PolicyHook *policy, const T2Liveness &L, T2FrameR4 *fr) {
    memset(fr, 0, sizeof *fr);
    const uint64_t e0 = L.epoch_now(), o0 = L.owner_errors_now();
    t2_build(prims, count, info, lh, ledger, ledger_count, false, &fr->frame);
    ProvReason r = PR_OK;
    if (diagnostic) r = PR_DIAGNOSTIC;
    else if (!info || info->owner_errors != 0 || o0 != 0) r = PR_OWNER_ERRORS;
    else if (!b.capture_sealed || !b.capture_complete || info->mode != SCENE_SEALED || !info->complete) r = PR_CAPTURE;
    else if (!b.ledger_sealed || !b.ledger_complete || !lh || !lh->complete) r = PR_LEDGER;
    else if (b.frame != info->frame || b.generation != info->generation || b.frame != lh->frame ||
             b.generation != lh->generation || b.command_count != lh->command_count || b.command_count != ledger_count ||
             (fr->frame.prim_count && (fr->frame.frame_id != b.frame || fr->frame.generation != b.generation)))
        r = PR_BINDING;
    else if (e0 != b.epoch) r = PR_EPOCH;
    const bool live = fr->frame.frame_reason == F_OK && fr->frame.live_eligible;
    uint32_t verdict = kPolicyNotEvaluated, n = 0;
    uint64_t set_hash = 0;
    if (r == PR_OK && live) {
        uint32_t ords[kMaxPrims];
        for (uint32_t i = 0; i < fr->frame.prim_count; i++)
            if (fr->frame.disposition_reason[i] == P_TRANSPORTED) ords[n++] = prims[i].ordinal;
        set_hash = fnv(ords, sizeof(uint32_t) * n);
        if (n != fr->frame.transported) r = PR_BINDING;
        else if (!policy || !policy->fn) r = PR_POLICY_MISSING;
        else {
            verdict = policy->fn(policy->ctx, b.frame, b.generation, ords, n);
            if (verdict != kPolicyTransportOk) r = PR_POLICY;
        }
    }
    // Read again AFTER the policy walk: an event during export, r3 build or the walk itself is caught here.
    if (r == PR_OK && (L.epoch_now() != e0 || L.owner_errors_now() != 0)) r = PR_CHANGED_DURING_BUILD;
    if (r != PR_OK) {
        force_native(fr, r);
        fr->prov.policy_verdict = verdict;            // audit only; bound and policy_ok stay 0
        fr->prov.policy_count = n;
        fr->prov.policy_set_hash = set_hash;
        return;
    }
    fr->prov = T2Provenance{b.frame, b.generation, b.command_count, b.epoch, verdict, n, set_hash, 1,
                            static_cast<uint8_t>(live ? 1 : 0)};
    fr->prov_reason = PR_OK;
}

// Single pending slot for r4 frames: r3 T2Slot semantics (CAS into empty, exchange take, fail-closed budget),
// sized by sizeof(T2FrameR4). Same thread contract: one producer, one consumer; budget fixed before start.
struct T2SlotR4 {
    std::atomic<T2FrameR4 *> pending{nullptr};
    std::atomic<uint64_t> bytes_in_use{0};
    std::atomic<uint64_t> release_underflows{0};
    uint64_t budget_bytes = 4 * sizeof(T2FrameR4);
    uint64_t dropped_busy = 0, refused_budget = 0, refused_stale = 0;   // producer-only writers
    bool reserve() {
        const uint64_t need = sizeof(T2FrameR4);
        uint64_t cur = bytes_in_use.load();
        do {
            if (budget_bytes < need || cur > budget_bytes - need) { refused_budget++; return false; }
        } while (!bytes_in_use.compare_exchange_weak(cur, cur + need));
        return true;
    }
    bool release() {
        const uint64_t need = sizeof(T2FrameR4);
        uint64_t cur = bytes_in_use.load();
        do { if (cur < need) { release_underflows.fetch_add(1); return false; } }
        while (!bytes_in_use.compare_exchange_weak(cur, cur - need));
        return true;
    }
};

// Boundary 2: export. Only a bound, live, policy-accepted, live-eligible F_OK frame is published; on any other
// result the producer still owns `fr` and must release only that unpublished frame.
inline ProvReason publish(T2SlotR4 &s, T2FrameR4 *fr, const T2Liveness &L) {
    const ProvReason r = liveness(L, *fr);
    if (r != PR_OK) { s.refused_stale++; return r; }
    if (!fr->frame.live_eligible || fr->frame.frame_reason != F_OK) return PR_NOT_LIVE_ELIGIBLE;
    if (!fr->prov.policy_ok) return PR_POLICY;
    T2FrameR4 *expected = nullptr;
    if (s.pending.compare_exchange_strong(expected, fr)) return PR_OK;
    s.dropped_busy++;
    return PR_BUSY;
}
// Boundary 3: consumer take. A non-null frame with *reason != PR_OK is stale: the consumer must release it
// without resolving or presenting it.
inline T2FrameR4 *take(T2SlotR4 &s, const T2Liveness &L, ProvReason *reason) {
    T2FrameR4 *fr = s.pending.exchange(nullptr);
    *reason = fr ? liveness(L, *fr) : PR_OK;
    return fr;
}
// Boundary 4: resolve. A stale or policy-unaccepted frame never mutates the consumer cache.
inline bool resolve(T2Resolver &res, const T2FrameR4 &fr, const T2Liveness &L, ResolveResult *out) {
    if (liveness(L, fr) != PR_OK || !fr.prov.policy_ok) { memset(out, 0, sizeof *out); return false; }
    return res.resolve(fr.frame, out);
}
// The consumer stamps the epoch of the exact frame whose interop image it completed.
struct CompletionR4 { Completion c; uint64_t epoch; };
// Boundary 5: suppression. Live provenance now, accepted policy, completion bound to the same frame/generation/
// epoch, then r3's gate (live_eligible, F_OK, image complete, exact frame/generation, overlay order) unchanged.
inline bool gate_allow_suppress(const T2FrameR4 &fr, uint64_t expected_overlay_hash, const CompletionR4 *c,
                                const T2Liveness &L) {
    return c && liveness(L, fr) == PR_OK && fr.prov.policy_ok && c->epoch == fr.prov.epoch &&
           c->c.frame_id == fr.prov.frame && c->c.generation == fr.prov.generation &&
           t2_gate_allow_suppress(fr.frame, expected_overlay_hash, &c->c);
}

}  // namespace r4
}  // namespace t2
