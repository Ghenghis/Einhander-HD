// CPU-only fixture for the T1 reprojection oracle r1 (claude-einhander). No GL, SDK, game or files except
// the result JSON. pgxp.h (v68, 1f50599f) and gte_divide_extracted.inc (exact runtime UNR divide,
// cfa7686a) are copied in by build_t1_fixture.r1.py after pin checks. Expected values below are
// hand-derived from the native rules quoted in remix_t1_reproject.r1.h, not produced by the oracle.
// r1 adds forged-overflow, missing/spurious OVF44/WRAP32 flag and exact boundary controls.
// Usage: test-t1.exe RESULT.json   exit 0 only when every check passed.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pgxp.h"
#define FLAG_DIV_OVF (1u << 17)            // gte.h e103d0fa: FLAG_DIV_OVF = 1u << 17
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"

static int checks, failures;
static char failed[4096];
static void check(bool ok, const char *name) {
    ++checks;
    if (!ok) { ++failures; if (strlen(failed) + strlen(name) + 2 < sizeof failed) { strcat(failed, name); strcat(failed, ","); } }
}

// A payload exactly as the producer would have written it for the given native results.
static PgxpView view(int64_t m1, int64_t m2, int64_t m3, uint16_t h, int32_t ofx, int32_t ofy, uint16_t flags,
                     uint16_t sz3, uint32_t packed, int32_t x16, int32_t y16) {
    PgxpView v; memset(&v, 0, sizeof v);
    v.mac[0] = m1; v.mac[1] = m2; v.mac[2] = m3; v.h = h; v.ofx = ofx; v.ofy = ofy;
    v.flags = flags; v.sz3 = sz3; v.packed = packed; v.x16 = x16; v.y16 = y16;
    return v;
}
static uint32_t pack(int sx, int sy) { return ((uint32_t)(uint16_t)sy << 16) | (uint32_t)(uint16_t)sx; }

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    const int32_t OFX = 160 << 16, OFY = 120 << 16;
    const uint16_t SF = PGXP_VIEW_SF, LM = PGXP_VIEW_LM;
    uint32_t fl = 0;

    // Divide: hand-derived from the extracted algorithm (table[0]=255, recip(0x8000)=131072).
    check(gte_divide(0x8000, 0x8000, fl) == 0x10000 && fl == 0, "div_unity_is_0x10000");
    fl = 0; check(gte_divide(0x8000, 0x4000, fl) == 0x1FFFF && (fl & FLAG_DIV_OVF), "div_overflow_at_2sz_eq_h");
    fl = 0; check(gte_divide(0x8000, 0, fl) == 0x1FFFF && (fl & FLAG_DIV_OVF), "div_overflow_sz0");
    fl = 0; check(gte_divide(0x8000, 0x4001, fl) < 0x1FFFF && fl == 0, "div_no_overflow_just_above");

    T1Expect e;
    // A plain: IR1=100, IR2=-50, SZ3=0x8000=H -> n=0x10000 -> sx=260, sy=70.
    PgxpView a = view(100LL << 12, -50LL * 4096, 0x8000LL << 12, 0x8000, OFX, OFY, SF, 0x8000,
                      pack(260, 70), 260 << 16, 70 << 16);
    check(t1_reproject(a, false, &e) == T1_MATCH && e.sx == 260 && e.sy == 70 && e.div == 0x10000, "a_plain_match");

    // B IR saturation: MAC1=40000 -> IR1=0x7FFF; sx=32927 saturates to 0x3FF; x16 clamps to 4096<<16 - 1.
    PgxpView b = view(40000LL << 12, -50LL * 4096, 0x8000LL << 12, 0x8000, OFX, OFY,
                      SF | PGXP_VIEW_IR_SAT | PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP, 0x8000,
                      pack(0x3FF, 70), (4096 << 16) - 1, 70 << 16);
    check(t1_reproject(b, false, &e) == T1_MATCH && e.ir1 == 0x7FFF, "b_ir_and_xy_saturation_match");

    // C lm=1 negative MAC1 -> IR1=0 (IR_SAT) -> sx=160.
    PgxpView c = view(-100LL * 4096, -50LL * 4096, 0x8000LL << 12, 0x8000, OFX, OFY, SF | LM | PGXP_VIEW_IR_SAT,
                      0x8000, pack(160, 120), 160 << 16, 120 << 16);
    check(t1_reproject(c, false, &e) == T1_MATCH && e.ir1 == 0 && e.ir2 == 0, "c_lm_clamps_negative_to_zero");

    // D divide overflow: SZ3=0x4000, H=0x8000 -> n=0x1FFFF; IR1=1 -> sx16=10616831 -> sx=161; sy=120.
    PgxpView d = view(1LL << 12, 0, 0x4000LL << 12, 0x8000, OFX, OFY, SF | PGXP_VIEW_DIV_OVF, 0x4000,
                      pack(161, 120), 10616831, 120 << 16);
    check(t1_reproject(d, false, &e) == T1_MATCH && e.div == 0x1FFFF, "d_div_overflow_match");

    // E SZ saturation: mac3>>12=-5 -> SZ3=0 -> n=0x1FFFF; sx16=23592860 -> 359; sy16=1310770 -> 20.
    PgxpView ez = view(100LL << 12, -50LL * 4096, -5LL * 4096, 0x8000, OFX, OFY,
                       SF | PGXP_VIEW_SZ_SAT | PGXP_VIEW_DIV_OVF, 0, pack(359, 20), 23592860, 1310770);
    check(t1_reproject(ez, false, &e) == T1_MATCH && e.sz3 == 0, "e_sz_saturation_match");

    // F sf=0: unshifted MAC1=100 -> IR1=100; SZ3 still mac3>>12 -> same screen result as A.
    PgxpView f0 = view(100, -50, 0x8000LL << 12, 0x8000, OFX, OFY, 0, 0x8000, pack(260, 70), 260 << 16, 70 << 16);
    check(t1_reproject(f0, false, &e) == T1_MATCH && e.ir1 == 100, "f_sf0_match");

    // Rejections: never compared.
    PgxpView g = a; g.flags |= PGXP_VIEW_WS_SQUASH; check(t1_reproject(g, false, &e) == T1_REJECT_WIDESCREEN, "g_reject_widescreen");
    g = a; g.flags |= PGXP_VIEW_DOME; check(t1_reproject(g, false, &e) == T1_REJECT_DOME, "h_reject_dome");
    // r1: OVF44/WRAP32 claims are no longer trusted; a spurious claim on clean accumulators is a mismatch.
    g = a; g.flags |= PGXP_VIEW_MAC2_OVF44; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "i_spurious_ovf44_claim");
    g = a; g.flags |= PGXP_VIEW_MAC3_WRAP32; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "j_spurious_wrap32_claim");

    // Root's forgery: mac1 = 2^44 + 100*4096 with SF only and A's outputs. mac1 >> 12 = 2^32 + 100 would
    // narrow to 100 and reproduce A exactly; r1 recomputes OVF44 (axis 1) and WRAP32 (axis 1) first.
    const int64_t T43 = (int64_t)1 << 43, T44 = (int64_t)1 << 44;
    g = a; g.mac[0] = T44 + 100LL * 4096; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "t_forged_overflow_missing_flags");
    g.flags |= PGXP_VIEW_MAC1_OVF44; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "u_forged_overflow_missing_wrap_flag");
    g.flags |= PGXP_VIEW_MAC1_WRAP32; check(t1_reproject(g, false, &e) == T1_REJECT_MAC_OVF44, "v_true_overflow_rejected");

    // Exact 44-bit boundary, sf=1. mac1 = 2^43-1: no OVF44; >>12 = 2^31-1 = INT32_MAX: no wrap;
    // IR1 = 0x7FFF -> same screen result as B (sx saturated, x16 clamped).
    PgxpView hi = view(T43 - 1, -50LL * 4096, 0x8000LL << 12, 0x8000, OFX, OFY,
                       SF | PGXP_VIEW_IR_SAT | PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP, 0x8000,
                       pack(0x3FF, 70), (4096 << 16) - 1, 70 << 16);
    check(t1_reproject(hi, false, &e) == T1_MATCH && e.mac1 == INT32_MAX, "w_boundary_2pow43_minus1_matches");
    // mac1 = 2^43: OVF44, and 2^43 >> 12 = 2^31 > INT32_MAX also wraps; both bits are required.
    g = hi; g.mac[0] = T43; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "x_boundary_2pow43_missing_flags");
    g.flags |= PGXP_VIEW_MAC1_OVF44; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "x2_boundary_2pow43_missing_wrap");
    g.flags |= PGXP_VIEW_MAC1_WRAP32; check(t1_reproject(g, false, &e) == T1_REJECT_MAC_OVF44, "y_boundary_2pow43_rejected");
    // Negative boundary: mac1 = -2^43 is in range (>= -2^43); >>12 = -2^31 = INT32_MIN, no wrap; IR1 clamps
    // to -0x8000 -> sx = 160 - 32768 saturates to -0x400; x16 clamps to -(4096<<16).
    PgxpView lo = view(-T43, -50LL * 4096, 0x8000LL << 12, 0x8000, OFX, OFY,
                       SF | PGXP_VIEW_IR_SAT | PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP, 0x8000,
                       pack(-0x400, 70), -(4096 << 16), 70 << 16);
    check(t1_reproject(lo, false, &e) == T1_MATCH && e.mac1 == INT32_MIN && e.ir1 == -0x8000, "z_boundary_minus_2pow43_matches");
    g = lo; g.mac[0] = -T43 - 1; g.flags |= PGXP_VIEW_MAC1_OVF44 | PGXP_VIEW_MAC1_WRAP32;
    check(t1_reproject(g, false, &e) == T1_REJECT_MAC_OVF44, "aa_below_minus_2pow43_rejected");
    // 32-bit wrap without 44-bit overflow, sf=0: mac1 = 2^31 -> wrap; 2^31-1 -> in range, IR clamps.
    PgxpView w0 = view(((int64_t)1 << 31) - 1, -50, 0x8000LL << 12, 0x8000, OFX, OFY,
                       PGXP_VIEW_IR_SAT | PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP, 0x8000,
                       pack(0x3FF, 70), (4096 << 16) - 1, 70 << 16);
    check(t1_reproject(w0, false, &e) == T1_MATCH, "bb_sf0_int32max_matches");
    g = w0; g.mac[0] = (int64_t)1 << 31; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "cc_sf0_wrap_missing_flag");
    g.flags |= PGXP_VIEW_MAC1_WRAP32; check(t1_reproject(g, false, &e) == T1_REJECT_MAC_WRAP32, "dd_sf0_wrap_rejected");
    // Axis 3 (depth) overflow is recomputed too.
    g = a; g.mac[2] = T43; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "ee_axis3_overflow_missing_flag");
    check(t1_reproject(a, true, &e) == T1_REJECT_UNCOMMITTED, "k_reject_uncommitted_when_required");
    g = a; g.flags |= PGXP_VIEW_RTP_COMMITTED; check(t1_reproject(g, true, &e) == T1_MATCH, "l_committed_matches");

    // Detected mismatches (a corrupted payload must not pass).
    g = a; g.flags |= PGXP_VIEW_IR_SAT; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "m_flag_claim_mismatch");
    g = b; g.flags &= (uint16_t)~PGXP_VIEW_XY_CLAMP; check(t1_reproject(g, false, &e) == T1_MISMATCH_FLAGS, "n_missing_flag_mismatch");
    g = a; g.packed += 1; check(t1_reproject(g, false, &e) == T1_MISMATCH_PACKED, "o_packed_mismatch");
    g = a; g.x16 += 1; check(t1_reproject(g, false, &e) == T1_MISMATCH_X16, "p_x16_mismatch");
    g = a; g.y16 -= 1; check(t1_reproject(g, false, &e) == T1_MISMATCH_X16, "q_y16_mismatch");
    g = a; g.sz3 = 0x7FFF; check(t1_reproject(g, false, &e) == T1_MISMATCH_SZ3, "r_sz3_mismatch");
    g = a; g.h = 0x9000; check(t1_reproject(g, false, &e) != T1_MATCH, "s_wrong_projection_detected");

    FILE *r = fopen(argv[1], "wb");
    if (!r) return 4;
    fprintf(r, "{\"fixture\":\"t1-reproject\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"failed\":\"%s\","
               "\"passed\":%s,\"gl_used\":false,\"sdk_used\":false}\n",
            checks, failures, failed, failures ? "false" : "true");
    fclose(r);
    return failures ? 1 : 0;
}
