/* test_pgxp_view.cpp — host tests for the PRIVATE opt-in GTE view provenance
 * (remix-provenance v1, claude-einhander). Links the FULL modified gte.cpp and
 * pgxp.cpp translation units (debug tools ON, so gte_execute writes the GTE
 * projection ring and commits view records exactly as in a dev build). Drives
 * real RTPS/RTPT through gte_execute and the real psx_pgxp_* hooks.
 * Test harness output only (stderr/stdout of this host executable). */

#include "cpu_state.h"
#include "pgxp.h"
#include "pgxp_hooks.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" void gte_set_display_aspect(int num, int den);
extern "C" int  gte_replay_side_effects_begin(void);
extern "C" void gte_replay_side_effects_end(void);
extern "C" uint64_t gte_rtp_ring_total(void);
extern "C" int gte_rtp_ring_seq_live(uint64_t seq);
extern "C" int gte_rtp_ring_get_xform(uint64_t seq, int16_t rt[9], int32_t tr[3],
                                      uint32_t *frame, uint32_t *caller_ra);

/* gte.cpp runtime dependencies outside the GTE (same set as the canonical
 * gte_register_access_test harness). */
extern "C" int gpu_ws_present_native_43(void) { return 0; }
extern "C" int gpu_ws_precise_nclip_enabled(void) { return 0; }
extern "C" void gpu_pgxp_rederive_enable(void) {}
extern "C" uint32_t memory_get_ram_bytes(void) { return 2u * 1024u * 1024u; }
extern "C" void psx_ws_note_gte_project(int) {}
extern "C" uint32_t psx_read_word(uint32_t) { return 0; }
extern "C" { uint64_t s_frame_count = 0; }
extern "C" uint32_t psx_gte_cmd_latency(uint32_t cmd) { return 7u + (cmd & 0x3Fu); }
extern "C" void psx_gte_set(CPUState *cpu, uint32_t latency) { cpu->gte_ts_done += latency; }
/* nd_intro_ot.c debug-tool queries (only reached by an env-gated CTR path that
 * these tests never enable): no batch/hint captured. */
extern "C" uint32_t psx_nd_wood_batch_ot(void) { return 0; }
extern "C" uint32_t psx_nd_sibling_ot_hint(void) { return 0; }

static int g_fail = 0, g_checks = 0;
#define CHECK(c)                                                                    \
    do {                                                                            \
        ++g_checks;                                                                 \
        if (!(c)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
                    ++g_fail; }                                                     \
    } while (0)

/* ---- encodings ----------------------------------------------------------- */
static uint32_t enc_i(uint32_t op, uint32_t rs, uint32_t rt, uint16_t imm) {
    return (op << 26) | (rs << 21) | (rt << 16) | imm;
}
static uint32_t enc_r(uint32_t rs, uint32_t rt, uint32_t rd, uint32_t funct) {
    return (rs << 21) | (rt << 16) | (rd << 11) | funct;
}
static uint32_t enc_cop2(uint32_t sub, uint32_t rt, uint32_t rd) {
    return (0x12u << 26) | (sub << 21) | (rt << 16) | (rd << 11);
}
#define LW(rt)        enc_i(0x23, 1, rt, 0)
#define SW(rt)        enc_i(0x2B, 1, rt, 0)
#define SH(rt)        enc_i(0x29, 1, rt, 0)
#define SWC2(rt)      enc_i(0x3A, 1, rt, 0)
#define MFC2(rt, rd)  enc_cop2(0x00, rt, rd)
#define MTC2(rt, rd)  enc_cop2(0x04, rt, rd)
#define ADDU(rs, rt, rd) enc_r(rs, rt, rd, 0x21)
#define ADDIU(rs, rt, imm) enc_i(0x09, rs, rt, (uint16_t)(imm))

static const uint32_t RTPS_SF = 0x00180001u;     /* sf=1, lm=0 */
static const uint32_t RTPT_SF = 0x00280030u;
static const uint32_t LM_BIT  = 1u << 10;

/* ---- GTE setup ----------------------------------------------------------- */
struct Xf { int16_t rt[9]; int32_t tr[3]; uint16_t h; int32_t ofx, ofy; };
static uint32_t pk(int16_t lo, int16_t hi) {
    return (uint32_t)(uint16_t)lo | ((uint32_t)(uint16_t)hi << 16);
}
static void load_xf(CPUState &c, const Xf &x) {
    c.gte_ctrl[0] = pk(x.rt[0], x.rt[1]);
    c.gte_ctrl[1] = pk(x.rt[2], x.rt[3]);
    c.gte_ctrl[2] = pk(x.rt[4], x.rt[5]);
    c.gte_ctrl[3] = pk(x.rt[6], x.rt[7]);
    c.gte_ctrl[4] = (uint32_t)(int32_t)x.rt[8];
    c.gte_ctrl[5] = (uint32_t)x.tr[0];
    c.gte_ctrl[6] = (uint32_t)x.tr[1];
    c.gte_ctrl[7] = (uint32_t)x.tr[2];
    c.gte_ctrl[24] = (uint32_t)x.ofx;
    c.gte_ctrl[25] = (uint32_t)x.ofy;
    c.gte_ctrl[26] = x.h;
}
static void set_v(CPUState &c, int lane, int16_t x, int16_t y, int16_t z) {
    c.gte_data[lane * 2] = pk(x, y);
    c.gte_data[lane * 2 + 1] = (uint32_t)(int32_t)z;
}
static int64_t exp_mac(const Xf &x, int row, const int16_t v[3]) {
    return (int64_t)x.tr[row] * 4096 + (int64_t)x.rt[row * 3 + 0] * v[0] +
           (int64_t)x.rt[row * 3 + 1] * v[1] + (int64_t)x.rt[row * 3 + 2] * v[2];
}

/* A 30-degree yaw with an offset: a non-trivial, unsaturated projection. */
static const Xf XF = {{3547, 0, 2048, 0, 4096, 0, -2048, 0, 3547}, {17, -33, 1500}, 300,
                      160 << 16, 120 << 16};

static uint32_t A(uint32_t i) { return 0x80100000u + i * 4u; }   /* packet slots */

/* SWC2 a GTE data reg to RAM through the real hook; returns the guest word. */
static uint32_t swc2(const CPUState &c, int reg, uint32_t addr) {
    psx_pgxp_cop2(nullptr, SWC2(reg), c.gte_data[reg], addr);
    return c.gte_data[reg];
}

static PgxpViewStats vstats() { PgxpViewStats s; pgxp_get_view_stats(&s); return s; }

/* ========================================================================== */
static void t8_default_off_and_identity() {
    /* T8: view payload never enabled: no allocation, no payload, and guest
     * state + existing PGXP results byte-identical to a view-on run. */
    CHECK(pgxp_view_payload() == 0);
    CHECK(pgxp_test_view_alloc_bytes() == 0);
    pgxp_set_enabled(1);
    CPUState off{}, on{};
    load_xf(off, XF);
    set_v(off, 0, -300, 120, 250);
    set_v(off, 1, 40, -60, 900);
    set_v(off, 2, 500, 10, -400);
    on = off;
    gte_execute(&off, RTPT_SF);
    uint32_t w = swc2(off, 14, A(0));
    int32_t x16a = 0, y16a = 0; uint16_t sza = 0;
    int ra = pgxp_get_precise_vertex(A(0), w, (int16_t)(w & 0xFFFF), (int16_t)(w >> 16), &x16a, &y16a, &sza);
    PgxpView v;
    CHECK(pgxp_get_precise_vertex_view(A(0), w, &v) == PGXP_SRC_NATIVE);
    CHECK(pgxp_test_view_alloc_bytes() == 0);
    /* The always-on GTE projection ring is pre-existing and allocates regardless
     * of this feature; T8 does not claim a zero-allocation runtime. */
    CHECK(gte_rtp_ring_total() >= 1);

    /* T8b: allocation failure fails closed. */
    pgxp_test_view_fail_next_alloc(1);
    pgxp_set_view_payload(1);
    CHECK(pgxp_view_payload() == 0);
    CHECK(vstats().alloc_fail == 1);
    CHECK(pgxp_test_view_alloc_bytes() == 0);

    pgxp_set_view_payload(1);
    CHECK(pgxp_view_payload() == 1);
    PgxpViewStats s = vstats();
    std::printf("view storage: record %llu B x 65536 + RAM tags 2 MiB = %llu B allocated\n",
                (unsigned long long)s.record_bytes, (unsigned long long)s.alloc_bytes);
    CHECK(s.alloc_bytes == (uint64_t)(0x200000u >> 2) * 4u + 65536ull * s.record_bytes);

    gte_execute(&on, RTPT_SF);
    CHECK(std::memcmp(on.gte_data, off.gte_data, sizeof(on.gte_data)) == 0);
    CHECK(std::memcmp(on.gte_ctrl, off.gte_ctrl, sizeof(on.gte_ctrl)) == 0);
    uint32_t w2 = swc2(on, 14, A(1));
    CHECK(w2 == w);
    int32_t x16b = 0, y16b = 0; uint16_t szb = 0;
    int rb = pgxp_get_precise_vertex(A(1), w2, (int16_t)(w2 & 0xFFFF), (int16_t)(w2 >> 16), &x16b, &y16b, &szb);
    CHECK(ra == rb && x16a == x16b && y16a == y16b && sza == szb);
    CHECK(pgxp_get_precise_vertex_view(A(1), w2, &v) == PGXP_SRC_DATAFLOW);
}

static void t1_math() {
    /* T1: payload == independently computed TR*4096 + RT*V for every lane, and
     * the unsaturated case re-projects to the shadow within UNR tolerance. */
    CPUState c{};
    load_xf(c, XF);
    const int16_t vs[3][3] = {{-300, 120, 250}, {40, -60, 900}, {500, 10, -400}};
    for (int l = 0; l < 3; l++) set_v(c, l, vs[l][0], vs[l][1], vs[l][2]);
    gte_execute(&c, RTPT_SF);
    const uint64_t seq = gte_rtp_ring_total() - 1;
    for (int r = 12; r <= 14; r++) {
        const int lane = r - 12;
        uint32_t w = swc2(c, r, A(10 + r));
        PgxpView v;
        CHECK(pgxp_get_precise_vertex_view(A(10 + r), w, &v) == PGXP_SRC_DATAFLOW);
        for (int i = 0; i < 3; i++) CHECK(v.mac[i] == exp_mac(XF, i, vs[lane]));
        CHECK(v.v[0] == vs[lane][0] && v.v[1] == vs[lane][1] && v.v[2] == vs[lane][2]);
        CHECK(v.lane == lane && v.cmd == 0x30);
        CHECK(v.rtp_seq == seq);
        CHECK((v.flags & PGXP_VIEW_RTP_COMMITTED) != 0);
        CHECK((v.flags & PGXP_VIEW_SF) != 0 && (v.flags & PGXP_VIEW_LM) == 0);
        CHECK((v.flags & (PGXP_VIEW_IR_SAT | PGXP_VIEW_SZ_SAT | PGXP_VIEW_DIV_OVF |
                          PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP | PGXP_VIEW_WS_SQUASH)) == 0);
        CHECK(v.h == XF.h && v.ofx == XF.ofx && v.ofy == XF.ofy && v.packed == w);
        /* (a) faithful re-projection: native X/Y use the TRUNCATED integer
         * IR1/IR2 = mac>>12 (sf=1) and the UNR reciprocal; with exact division
         * the only residual is the UNR error (a few 1/65536 units of H/SZ3). */
        const double sz3 = (double)v.sz3;
        const double xf = XF.ofx / 65536.0 + (double)(v.mac[0] >> 12) * XF.h / sz3;
        const double yf = XF.ofy / 65536.0 + (double)(v.mac[1] >> 12) * XF.h / sz3;
        CHECK(std::fabs(xf - v.x16 / 65536.0) < 0.05);
        CHECK(std::fabs(yf - v.y16 / 65536.0) < 0.05);
        /* (b) ideal pinhole from the exact payload: differs from native by up to
         * one truncated view unit (H/SZ3 px) — the precision the payload adds. */
        const double xi = XF.ofx / 65536.0 + (double)v.mac[0] * XF.h / (double)v.mac[2];
        const double yi = XF.ofy / 65536.0 + (double)v.mac[1] * XF.h / (double)v.mac[2];
        const double tol = XF.h / sz3 + 0.05;
        CHECK(std::fabs(xi - v.x16 / 65536.0) < tol);
        CHECK(std::fabs(yi - v.y16 / 65536.0) < tol);
        int32_t x16, y16; uint16_t sz;
        CHECK(pgxp_get_precise_vertex(A(10 + r), w, (int16_t)(w & 0xFFFF), (int16_t)(w >> 16),
                                      &x16, &y16, &sz) == PGXP_SRC_DATAFLOW);
        CHECK(x16 == v.x16 && y16 == v.y16 && sz == v.sz3);
    }
}

static void t1b_saturation() {
    /* Saturated / overflow projections: the payload stays the exact unsaturated
     * MAC and the flags say the native screen position did not follow it. */
    PgxpView v;
    {   /* IR1 > 0x7FFF -> IR_SAT; screen far off -> XY_SAT and transport clamp */
        Xf x = XF; x.rt[0] = 4096; x.rt[1] = 0; x.rt[2] = 0; x.tr[0] = 40000; x.tr[2] = 1000; x.h = 200;
        CPUState c{}; load_xf(c, x); set_v(c, 0, 0, 0, 0);
        gte_execute(&c, RTPS_SF);
        uint32_t w = swc2(c, 14, A(30));
        CHECK(pgxp_get_precise_vertex_view(A(30), w, &v) == PGXP_SRC_DATAFLOW);
        const int16_t z[3] = {0, 0, 0};
        CHECK(v.mac[0] == exp_mac(x, 0, z) && v.mac[0] == 40000ll * 4096);
        CHECK((v.flags & PGXP_VIEW_IR_SAT) && (v.flags & PGXP_VIEW_XY_SAT) && (v.flags & PGXP_VIEW_XY_CLAMP));
        CHECK(!(v.flags & PGXP_VIEW_SZ_SAT) && !(v.flags & PGXP_VIEW_DIV_OVF));
    }
    {   /* behind the camera: mac3>>12 < 0 -> SZ3 = 0 -> SZ_SAT + DIV_OVF */
        Xf x = XF; x.tr[2] = -500;
        CPUState c{}; load_xf(c, x); set_v(c, 0, 0, 0, 0);
        gte_execute(&c, RTPS_SF);
        uint32_t w = swc2(c, 14, A(31));
        CHECK(pgxp_get_precise_vertex_view(A(31), w, &v) == PGXP_SRC_DATAFLOW);
        CHECK(v.mac[2] == -500ll * 4096);
        CHECK((v.flags & PGXP_VIEW_SZ_SAT) && (v.flags & PGXP_VIEW_DIV_OVF));
    }
    {   /* near plane: 2*SZ3 <= H -> DIV_OVF only */
        Xf x = XF; x.tr[2] = 50; x.h = 200;
        CPUState c{}; load_xf(c, x); set_v(c, 0, 0, 0, 0);
        gte_execute(&c, RTPS_SF);
        uint32_t w = swc2(c, 14, A(32));
        CHECK(pgxp_get_precise_vertex_view(A(32), w, &v) == PGXP_SRC_DATAFLOW);
        CHECK((v.flags & PGXP_VIEW_DIV_OVF) && !(v.flags & PGXP_VIEW_SZ_SAT));
    }
    {   /* lm=1 with a negative MAC1 -> IR clamps at 0 -> IR_SAT; LM recorded */
        Xf x = XF; x.rt[0] = 4096; x.rt[1] = 0; x.rt[2] = 0; x.tr[0] = -20;
        CPUState c{}; load_xf(c, x); set_v(c, 0, 0, 0, 0);
        gte_execute(&c, RTPS_SF | LM_BIT);
        uint32_t w = swc2(c, 14, A(33));
        CHECK(pgxp_get_precise_vertex_view(A(33), w, &v) == PGXP_SRC_DATAFLOW);
        CHECK((v.flags & PGXP_VIEW_LM) && (v.flags & PGXP_VIEW_IR_SAT));
        CHECK(v.mac[0] == -20ll * 4096);
    }
}

static void t2_fifo() {
    /* T2: RTPT then RTPS shifts payloads exactly like the SXY FIFO; reg 15
     * mirrors reg 14. */
    CPUState c{};
    load_xf(c, XF);
    const int16_t vs[3][3] = {{11, 22, 33}, {-44, 55, 66}, {77, -88, 99}};
    for (int l = 0; l < 3; l++) set_v(c, l, vs[l][0], vs[l][1], vs[l][2]);
    gte_execute(&c, RTPT_SF);
    const uint64_t s1 = gte_rtp_ring_total() - 1;
    set_v(c, 0, 123, -45, 67);
    gte_execute(&c, RTPS_SF);
    const uint64_t s2 = gte_rtp_ring_total() - 1;
    PgxpView a, b, d, e;
    uint32_t w12 = swc2(c, 12, A(40)), w13 = swc2(c, 13, A(41)), w14 = swc2(c, 14, A(42)), w15 = swc2(c, 15, A(43));
    CHECK(pgxp_get_precise_vertex_view(A(40), w12, &a) == PGXP_SRC_DATAFLOW);
    CHECK(pgxp_get_precise_vertex_view(A(41), w13, &b) == PGXP_SRC_DATAFLOW);
    CHECK(pgxp_get_precise_vertex_view(A(42), w14, &d) == PGXP_SRC_DATAFLOW);
    CHECK(pgxp_get_precise_vertex_view(A(43), w15, &e) == PGXP_SRC_DATAFLOW);
    CHECK(a.lane == 1 && a.cmd == 0x30 && a.rtp_seq == s1 && a.mac[0] == exp_mac(XF, 0, vs[1]));
    CHECK(b.lane == 2 && b.cmd == 0x30 && b.rtp_seq == s1 && b.mac[1] == exp_mac(XF, 1, vs[2]));
    const int16_t n[3] = {123, -45, 67};
    CHECK(d.lane == 0 && d.cmd == 0x01 && d.rtp_seq == s2 && d.mac[2] == exp_mac(XF, 2, n));
    CHECK(e.tag == d.tag && w15 == w14);
}

static void t3_overwrite() {
    /* T3: MTC2 overwrites and the (unmodelled) SXYP push never leave a view on
     * a word it no longer describes. */
    CPUState c{};
    load_xf(c, XF);
    for (int l = 0; l < 3; l++) set_v(c, l, (int16_t)(10 * l + 5), (int16_t)(7 - l), (int16_t)(200 + l));
    gte_execute(&c, RTPT_SF);
    PgxpView v;
    /* MTC2 $zero -> SXY1: shadow reset, no view */
    psx_pgxp_cop2(nullptr, MTC2(0, 13), 0u, 0);
    c.gte_data[13] = 0;
    uint32_t w = swc2(c, 13, A(50));
    CHECK(pgxp_get_precise_vertex_view(A(50), w, &v) == PGXP_SRC_NATIVE);
    /* direct write path: reg 14 killed */
    const uint32_t old14 = c.gte_data[14];
    pgxp_gte_reg_written(14, 0x00100010u);
    c.gte_data[14] = 0x00100010u;
    w = swc2(c, 14, A(51));
    CHECK(pgxp_get_precise_vertex_view(A(51), w, &v) == PGXP_SRC_NATIVE);
    /* SXYP push by MTC2 15: guest regs shift, shadows do not -> validation drops */
    gte_execute(&c, RTPT_SF);
    const uint32_t g13 = c.gte_data[13];
    psx_pgxp_cop2(nullptr, MTC2(0, 15), 0x00200020u, 0);
    c.gte_data[12] = c.gte_data[13]; c.gte_data[13] = c.gte_data[14];
    c.gte_data[14] = c.gte_data[15] = 0x00200020u;
    w = swc2(c, 12, A(52));                       /* guest word = old SXY1 */
    CHECK(w == g13);
    CHECK(pgxp_get_precise_vertex_view(A(52), w, &v) == PGXP_SRC_NATIVE);
    (void)old14;
}

static void t4_provenance() {
    /* T4: identity copies keep the view; stale overwrites, half writes and
     * non-identity arithmetic drop it. */
    CPUState c{};
    load_xf(c, XF);
    set_v(c, 0, -77, 31, 140);
    gte_execute(&c, RTPS_SF);
    PgxpView v0, v;
    const uint32_t w = swc2(c, 14, A(60));
    CHECK(pgxp_get_precise_vertex_view(A(60), w, &v0) == PGXP_SRC_DATAFLOW);
    /* LW -> MOVE (addu rd, rs, $zero) -> SW */
    psx_pgxp_load(nullptr, LW(8), A(60), w);
    psx_pgxp_alu(nullptr, ADDU(8, 0, 9), w, w, 0);
    psx_pgxp_store(nullptr, SW(9), A(61), w);
    CHECK(pgxp_get_precise_vertex_view(A(61), w, &v) == PGXP_SRC_DATAFLOW);
    CHECK(v.tag == v0.tag && v.mac[0] == v0.mac[0] && v.mac[2] == v0.mac[2]);
    /* MFC2 -> MTC2 -> SWC2 */
    psx_pgxp_cop2(nullptr, MFC2(10, 14), w, 0);
    psx_pgxp_cop2(nullptr, MTC2(10, 13), w, 0);
    c.gte_data[13] = w;
    const uint32_t w13 = swc2(c, 13, A(62));
    CHECK(pgxp_get_precise_vertex_view(A(62), w13, &v) == PGXP_SRC_DATAFLOW && v.tag == v0.tag);
    /* wrong word at the slot -> value mismatch */
    CHECK(pgxp_get_precise_vertex_view(A(60), w ^ 1u, &v) == PGXP_SRC_NATIVE);
    /* foreign untracked store over the slot -> gone for both words */
    psx_pgxp_store(nullptr, SW(0), A(60), 0x12345678u);
    CHECK(pgxp_get_precise_vertex_view(A(60), 0x12345678u, &v) == PGXP_SRC_NATIVE);
    CHECK(pgxp_get_precise_vertex_view(A(60), w, &v) == PGXP_SRC_NATIVE);
    /* half write of the same low half: precision may survive, the view must not
     * (transport rule checked directly, not only through the consumer) */
    CHECK(pgxp_test_view_flag(A(61)) == 1);
    psx_pgxp_store(nullptr, SH(8), A(61), w);
    CHECK(pgxp_test_view_flag(A(61)) == 0);
    CHECK(pgxp_get_precise_vertex_view(A(61), w, &v) == PGXP_SRC_NATIVE);
    /* non-identity arithmetic (cpu mode): x+1 keeps sub-pixel precision, not the view */
    pgxp_set_cpu_mode(1);
    psx_pgxp_alu(nullptr, ADDIU(8, 11, 1), w + 1u, w, 1);
    psx_pgxp_store(nullptr, SW(11), A(63), w + 1u);
    int32_t x16, y16; uint16_t sz;
    CHECK(pgxp_get_precise_vertex(A(63), w + 1u, (int16_t)((w + 1u) & 0xFFFF), (int16_t)((w + 1u) >> 16),
                                  &x16, &y16, &sz) == PGXP_SRC_DATAFLOW);
    CHECK(pgxp_get_precise_vertex_view(A(63), w + 1u, &v) == PGXP_SRC_NATIVE);
    CHECK(pgxp_test_view_flag(A(63)) == 0);
    pgxp_set_cpu_mode(0);
    /* immediate GP0 words (unknown address) never carry a view */
    CHECK(pgxp_get_precise_vertex_view(0xFFFFFFFFu, w, &v) == PGXP_SRC_NATIVE);
}

static void t5_ring() {
    /* T5: commit pins the ring identity; validation rejects mismatches; ring
     * overwrite and record reuse are detected, never returned stale. */
    CPUState c{};
    load_xf(c, XF);
    set_v(c, 0, 9, 8, 7);
    gte_execute(&c, RTPS_SF);
    const uint64_t seq = gte_rtp_ring_total() - 1;
    const uint32_t w = swc2(c, 14, A(70));
    PgxpView v;
    CHECK(pgxp_get_precise_vertex_view(A(70), w, &v) == PGXP_SRC_DATAFLOW);
    CHECK((v.flags & PGXP_VIEW_RTP_COMMITTED) && v.rtp_seq == seq && gte_rtp_ring_seq_live(seq) == 1);
    int16_t rt[9]; int32_t tr[3]; uint32_t fr = 0, ra = 0;
    CHECK(gte_rtp_ring_get_xform(seq, rt, tr, &fr, &ra) == 1);
    CHECK(std::memcmp(rt, XF.rt, sizeof(rt)) == 0 && tr[0] == XF.tr[0] && tr[2] == XF.tr[2]);
    CHECK(gte_rtp_ring_seq_live(gte_rtp_ring_total()) == 0);

    /* direct commit validation */
    PgxpViewInput in{};
    in.mac[2] = 4096 * 100; in.v[0] = 1; in.v[1] = 2; in.v[2] = 3; in.lane = 0; in.cmd = 0x01;
    in.rtp_seq = 777; in.xform_hash = 0xABCD1234u;
    const int16_t vv[3][3] = {{1, 2, 3}, {0, 0, 0}, {0, 0, 0}};
    const int16_t vbad[3][3] = {{1, 2, 4}, {0, 0, 0}, {0, 0, 0}};
    const uint64_t mm0 = vstats().commit_mismatch;
    pgxp_gte_push_sxy_view(1 << 16, 1 << 16, 100, 0x00010001u, &in);
    CHECK(pgxp_view_commit_rtp(778, 0x01, vv, 0xABCD1234u) == 0);          /* wrong seq  */
    pgxp_gte_push_sxy_view(1 << 16, 1 << 16, 100, 0x00010001u, &in);
    CHECK(pgxp_view_commit_rtp(777, 0x01, vv, 0xABCD1235u) == 0);          /* wrong xform */
    pgxp_gte_push_sxy_view(1 << 16, 1 << 16, 100, 0x00010001u, &in);
    CHECK(pgxp_view_commit_rtp(777, 0x01, vbad, 0xABCD1234u) == 0);        /* wrong V    */
    pgxp_gte_push_sxy_view(1 << 16, 1 << 16, 100, 0x00010001u, &in);
    CHECK(pgxp_view_commit_rtp(777, 0x30, vv, 0xABCD1234u) == 0);          /* lane count */
    pgxp_gte_push_sxy_view(1 << 16, 1 << 16, 100, 0x00010001u, &in);
    CHECK(pgxp_view_commit_rtp(777, 0x01, vv, 0xABCD1234u) == 1);          /* exact      */
    CHECK(vstats().commit_mismatch == mm0 + 4);

    /* > 64K projections: the view record of A(70) is reused -> evicted, not stale */
    const uint64_t ev0 = vstats().evicted;
    for (int i = 0; i < 65536 + 8; i++) { set_v(c, 0, (int16_t)(i & 1023), 3, 5); gte_execute(&c, RTPS_SF); }
    CHECK(pgxp_get_precise_vertex_view(A(70), w, &v) == PGXP_SRC_NATIVE);
    CHECK(vstats().evicted == ev0 + 1);
    /* > 256K ring records: the old ring identity is no longer live */
    for (int i = 0; i < (1 << 18); i++) gte_execute(&c, RTPS_SF);
    CHECK(gte_rtp_ring_seq_live(seq) == 0);
    int16_t rt2[9]; int32_t tr2[3];
    CHECK(gte_rtp_ring_get_xform(seq, rt2, tr2, nullptr, nullptr) == 0);
}

static void t6_widescreen() {
    /* T6: X-squash changes the screen position only; the payload is identical
     * and WS_SQUASH is recorded. */
    CPUState c{};
    load_xf(c, XF);
    set_v(c, 0, 250, -20, 300);
    gte_execute(&c, RTPS_SF);
    PgxpView n, s;
    uint32_t wn = swc2(c, 14, A(80));
    CHECK(pgxp_get_precise_vertex_view(A(80), wn, &n) == PGXP_SRC_DATAFLOW);
    gte_set_display_aspect(16, 9);
    gte_execute(&c, RTPS_SF);
    uint32_t ws = swc2(c, 14, A(81));
    gte_set_display_aspect(4, 3);
    CHECK(pgxp_get_precise_vertex_view(A(81), ws, &s) == PGXP_SRC_DATAFLOW);
    CHECK((s.flags & PGXP_VIEW_WS_SQUASH) && !(n.flags & PGXP_VIEW_WS_SQUASH));
    CHECK(s.mac[0] == n.mac[0] && s.mac[1] == n.mac[1] && s.mac[2] == n.mac[2]);
    CHECK(s.x16 != n.x16 && s.y16 == n.y16);
}

static void t7_suppression() {
    /* T7: speculative bracket and replay sandbox write no payload and commit
     * nothing; invalidation, mode toggles and tag wrap drop every view. */
    CPUState c{};
    load_xf(c, XF);
    set_v(c, 0, 1, 2, 3);
    gte_execute(&c, RTPS_SF);
    PgxpView v;
    const uint32_t w = swc2(c, 14, A(90));
    CHECK(pgxp_get_precise_vertex_view(A(90), w, &v) == PGXP_SRC_DATAFLOW);
    PgxpViewStats s0 = vstats();
    pgxp_suppress_begin();
    set_v(c, 0, 4, 5, 6);
    gte_execute(&c, RTPS_SF);
    pgxp_suppress_end();
    PgxpViewStats s1 = vstats();
    CHECK(s1.produced == s0.produced && s1.commit_ok == s0.commit_ok);
    CHECK(gte_replay_side_effects_begin() == 1);
    gte_execute(&c, RTPS_SF);
    gte_replay_side_effects_end();
    PgxpViewStats s2 = vstats();
    CHECK(s2.produced == s1.produced && s2.commit_ok == s1.commit_ok);
    CHECK(pgxp_get_precise_vertex_view(A(90), w, &v) == PGXP_SRC_DATAFLOW);  /* untouched */
    pgxp_invalidate_all();
    CHECK(pgxp_get_precise_vertex_view(A(90), w, &v) == PGXP_SRC_NATIVE);
    /* toggle: off drops, on does not revive */
    set_v(c, 0, 7, 8, 9);
    gte_execute(&c, RTPS_SF);
    const uint32_t w2 = swc2(c, 14, A(91));
    CHECK(pgxp_get_precise_vertex_view(A(91), w2, &v) == PGXP_SRC_DATAFLOW);
    pgxp_set_view_payload(0);
    CHECK(pgxp_get_precise_vertex_view(A(91), w2, &v) == PGXP_SRC_NATIVE);
    pgxp_set_view_payload(1);
    CHECK(pgxp_get_precise_vertex_view(A(91), w2, &v) == PGXP_SRC_NATIVE);
    /* 2^32 tag wrap */
    pgxp_test_view_set_seq(0xFFFFFFFFu);
    gte_execute(&c, RTPS_SF);
    const uint32_t w3 = swc2(c, 14, A(92));
    CHECK(pgxp_get_precise_vertex_view(A(92), w3, &v) == PGXP_SRC_DATAFLOW && v.tag == 0xFFFFFFFFu);
    const uint64_t wraps0 = vstats().seq_wraps;
    set_v(c, 0, 10, 11, 12);
    gte_execute(&c, RTPS_SF);
    CHECK(vstats().seq_wraps == wraps0 + 1);
    CHECK(pgxp_get_precise_vertex_view(A(92), w3, &v) == PGXP_SRC_NATIVE);
    const uint32_t w4 = swc2(c, 14, A(93));
    CHECK(pgxp_get_precise_vertex_view(A(93), w4, &v) == PGXP_SRC_DATAFLOW && v.tag == 1u);
}

int main() {
    t8_default_off_and_identity();
    /* The 0.5 px seam clamp (G1.10) is orthogonal to provenance; disable it so
     * precise-position comparisons see every DATAFLOW hit. */
    pgxp_set_tolerance(-1.0f);
    t1_math();
    t1b_saturation();
    t2_fifo();
    t3_overwrite();
    t4_provenance();
    t6_widescreen();
    t7_suppression();
    t5_ring();
    PgxpViewStats s = vstats();
    std::printf("checks %d failures %d | produced %llu commit_ok %llu commit_mismatch %llu hits %llu evicted %llu "
                "no_view %llu value_mismatch %llu incoherent %llu\n", g_checks, g_fail,
                (unsigned long long)s.produced, (unsigned long long)s.commit_ok, (unsigned long long)s.commit_mismatch,
                (unsigned long long)s.hits, (unsigned long long)s.evicted, (unsigned long long)s.no_view,
                (unsigned long long)s.value_mismatch, (unsigned long long)s.incoherent);
    return g_fail ? 1 : 0;
}
