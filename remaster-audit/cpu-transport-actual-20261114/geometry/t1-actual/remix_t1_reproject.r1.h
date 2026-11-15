// T1 reprojection oracle r1 (claude-einhander). SOURCE ONLY, not compiled or run. Opt-in diagnostic
// r1 (root msg_6fe6105a): the 44-bit accumulator overflow and the 32-bit MAC wrap are RECOMPUTED from the
// raw mac[] with the producer's exact ranges (v61 gte.cpp 1004-1014) BEFORE any int32 narrowing, and are
// never taken from the payload's flags. A recomputed overflow/wrap is REJECTED when the payload agrees and
// is a FLAG MISMATCH when the payload's OVF44/WRAP32 bits are missing or spurious; neither can MATCH.
// r0 (5ddc996e) trusted the claimed flags and is superseded.
// module: no SDK, no GL, no runtime state, no I/O, not linked into the native renderer.
//
// Question answered: does one captured PgxpView (v68 include/pgxp.h 1f50599f) reproduce, bit for bit, the
// native screen position the recompiled GTE produced for that vertex? It models the native RTPS path of
// the v61 gte.cpp that v68 links (139d2e49, lines 871-999) and gte.h push_sxy/saturate_sz (e103d0fa):
//   MAC = mac >> (sf?12:0) as int32;  IR = clamp(MAC, lm?0:-0x8000, 0x7FFF)       (IR saturation)
//   SZ3 = clamp(mac3 >> 12, 0, 0xFFFF)                                            (SZ saturation)
//   n   = gte_divide(H, SZ3)  -- the EXACT runtime UNR divide, extracted, never retyped (DIV overflow)
//   sx16 = OFX + IR1*n, sy16 = OFY + IR2*n; sx = sx16 >> 16 saturated to -0x400..0x3FF (XY saturation)
//   packed = (u16)sy << 16 | (u16)sx;  x16/y16 = sx16/sy16 clamped to +-(4096<<16) (shadow transport clamp)
// Cases it does NOT model are REJECTED with a reason, never compared:
//   widescreen X squash (PGXP_VIEW_WS_SQUASH) and dome expansion (PGXP_VIEW_DOME): depend on runtime
//   configuration not in the payload; 44-bit accumulator overflow and 32-bit MAC wrap: rejected rather
//   than relying on implementation-defined narrowing.
// It also recomputes the payload's own flag bits for the modelled conditions and reports a mismatch.
// It is a GTE-side oracle only. The GP0 vertex (11-bit signed, draw offset, viewport) is checked
// separately (T1b), and no world camera is derived here.
//
// Include order required by the fixture/consumer: <stdint.h>, pgxp.h (v68), then define FLAG_DIV_OVF
// and include "gte_divide_extracted.inc" (from build_t1_fixture.r0.py) before this header.
#pragma once
#include <stdint.h>

enum T1Verdict {
    T1_MATCH = 0,
    T1_REJECT_WIDESCREEN = 1, T1_REJECT_DOME = 2, T1_REJECT_MAC_OVF44 = 3, T1_REJECT_MAC_WRAP32 = 4,
    T1_REJECT_UNCOMMITTED = 5,
    T1_MISMATCH_SZ3 = 10, T1_MISMATCH_FLAGS = 11, T1_MISMATCH_PACKED = 12, T1_MISMATCH_X16 = 13,
};

struct T1Expect {
    int32_t mac1, mac2;
    int16_t ir1, ir2;
    uint16_t sz3;
    int32_t div;
    int64_t sx16, sy16;
    int16_t sx, sy;
    uint32_t packed;
    int32_t x16, y16;
    uint16_t modelled_flags;   // recomputed SF|LM|IR_SAT|SZ_SAT|DIV_OVF|XY_SAT|XY_CLAMP
};

static const uint16_t T1_MODELLED_FLAGS = PGXP_VIEW_SF | PGXP_VIEW_LM | PGXP_VIEW_IR_SAT | PGXP_VIEW_SZ_SAT |
                                          PGXP_VIEW_DIV_OVF | PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP;

static inline int32_t t1_clamp32(int64_t v, int64_t lo, int64_t hi) {
    return (int32_t)(v < lo ? lo : v > hi ? hi : v);
}

// require_committed: also reject views whose GTE ring record was not committed (PGXP_VIEW_RTP_COMMITTED).
static inline int t1_reproject(const PgxpView &v, bool require_committed, T1Expect *e) {
    const uint16_t f = v.flags;
    // Not recomputable from the payload (runtime configuration): trusted claims, always rejected.
    if (f & PGXP_VIEW_WS_SQUASH) return T1_REJECT_WIDESCREEN;
    if (f & PGXP_VIEW_DOME) return T1_REJECT_DOME;

    const int shift = (f & PGXP_VIEW_SF) ? 12 : 0;
    // Recompute overflow and wrap from the raw int64 accumulators first (producer 1004-1014):
    //   OVF44 axis a: mac >= 2^43 || mac < -2^43;  WRAP32 axis a: (mac >> shift) outside int32.
    const int64_t m44 = (int64_t)1 << 43;
    uint16_t ovf = 0, wrap = 0;
    for (int a = 0; a < 3; a++) {
        if (v.mac[a] >= m44 || v.mac[a] < -m44) ovf |= (uint16_t)(PGXP_VIEW_MAC1_OVF44 << a);
        const int64_t r = v.mac[a] >> shift;
        if (r > (int64_t)INT32_MAX || r < (int64_t)INT32_MIN) wrap |= (uint16_t)(PGXP_VIEW_MAC1_WRAP32 << a);
    }
    const uint16_t ovf_mask = PGXP_VIEW_MAC1_OVF44 | PGXP_VIEW_MAC2_OVF44 | PGXP_VIEW_MAC3_OVF44;
    const uint16_t wrap_mask = PGXP_VIEW_MAC1_WRAP32 | PGXP_VIEW_MAC2_WRAP32 | PGXP_VIEW_MAC3_WRAP32;
    if ((f & ovf_mask) != ovf || (f & wrap_mask) != wrap) return T1_MISMATCH_FLAGS;   // missing or spurious
    if (ovf) return T1_REJECT_MAC_OVF44;
    if (wrap) return T1_REJECT_MAC_WRAP32;
    if (require_committed && !(f & PGXP_VIEW_RTP_COMMITTED)) return T1_REJECT_UNCOMMITTED;
    // From here every mac >> shift and mac3 >> 12 fits int32, so the narrowing below is exact.

    const bool lm = (f & PGXP_VIEW_LM) != 0;
    const int64_t lo = lm ? 0 : -0x8000;
    T1Expect x{};
    x.mac1 = (int32_t)(v.mac[0] >> shift);          // in range: WRAP32 was rejected above
    x.mac2 = (int32_t)(v.mac[1] >> shift);
    x.ir1 = (int16_t)t1_clamp32(x.mac1, lo, 0x7FFF);
    x.ir2 = (int16_t)t1_clamp32(x.mac2, lo, 0x7FFF);
    const int64_t z12 = v.mac[2] >> 12;
    x.sz3 = (uint16_t)t1_clamp32(z12, 0, 0xFFFF);
    uint32_t gte_flag = 0;
    x.div = gte_divide(v.h, x.sz3, gte_flag);       // extracted runtime code
    x.sx16 = (int64_t)v.ofx + (int64_t)x.ir1 * x.div;
    x.sy16 = (int64_t)v.ofy + (int64_t)x.ir2 * x.div;
    const int64_t sx = x.sx16 >> 16, sy = x.sy16 >> 16;
    x.sx = (int16_t)t1_clamp32(sx, -0x400, 0x3FF);
    x.sy = (int16_t)t1_clamp32(sy, -0x400, 0x3FF);
    x.packed = ((uint32_t)(uint16_t)x.sy << 16) | (uint32_t)(uint16_t)x.sx;
    const int64_t lim = (int64_t)4096 << 16;
    x.x16 = t1_clamp32(x.sx16, -lim, lim - 1);
    x.y16 = t1_clamp32(x.sy16, -lim, lim - 1);
    uint16_t m = 0;
    if (shift) m |= PGXP_VIEW_SF;
    if (lm) m |= PGXP_VIEW_LM;
    if (x.mac1 < lo || x.mac1 > 0x7FFF || x.mac2 < lo || x.mac2 > 0x7FFF) m |= PGXP_VIEW_IR_SAT;
    if (z12 < 0 || z12 > 0xFFFF) m |= PGXP_VIEW_SZ_SAT;
    if ((uint32_t)x.sz3 * 2 <= (uint32_t)v.h) m |= PGXP_VIEW_DIV_OVF;
    if (sx < -0x400 || sx > 0x3FF || sy < -0x400 || sy > 0x3FF) m |= PGXP_VIEW_XY_SAT;
    if ((int64_t)x.x16 != x.sx16 || (int64_t)x.y16 != x.sy16) m |= PGXP_VIEW_XY_CLAMP;
    x.modelled_flags = m;
    if (e) *e = x;

    if (v.sz3 != x.sz3) return T1_MISMATCH_SZ3;
    if ((f & T1_MODELLED_FLAGS) != m) return T1_MISMATCH_FLAGS;
    if (v.packed != x.packed) return T1_MISMATCH_PACKED;
    if (v.x16 != x.x16 || v.y16 != x.y16) return T1_MISMATCH_X16;
    return T1_MATCH;
}
