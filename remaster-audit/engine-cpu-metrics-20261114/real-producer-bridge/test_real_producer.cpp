#include "remix_mesh_packet.h"
/* test_pgxp_view_v2.cpp — host tests for PRIVATE view provenance v2
 * (claude-einhander). Links the FULL v2 gte.cpp, pgxp.cpp and
 * pgxp_view_census.cpp, plus gpu_census_harness.c which compiles the ACTUAL
 * code cut from the generated gpu.c (census arming, transport re-derive,
 * texture-correction predicate, census hooks) and debug_server.c (the
 * pgxp_view TCP handler and json_get_int). Debug tools ON: real ring commits.
 * Lines starting "JSON:" are TCP replies; run_host_test_v2.py parses and
 * checks them. Test harness output only. */

#include "cpu_state.h"
#include "pgxp.h"
#include "pgxp_hooks.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" {
uint64_t gte_rtp_ring_total(void);
int gte_rtp_ring_seq_live(uint64_t seq);
void gpu_view_census_set(int enabled);
int gpu_view_census_enabled(void);
void gpu_texture_correction_set(int enabled);
int gpu_texture_correction_enabled(void);
void gpu_pgxp_rederive_enable(void);
int gte_geometry_correction_enabled(void);
void harness_prepare_texture_triangle(int i0, int i1, int i2);
void harness_view_census_quad(const int *qi);
const char *harness_tcp(int id, const char *json);
void harness_texcorr(uint64_t *att, uint64_t *armed, uint64_t *off, uint64_t *nosrc, uint64_t *noz);
extern uint32_t gp0_cmd_buf[16];
extern uint32_t gp0_cmd_source_addr;
extern int g_persp_calls, g_persp_last_on;
extern float g_persp_last_q[3];
}

/* gte.cpp runtime dependencies outside the GTE (same set as the canonical
 * gte_register_access_test harness; gpu_pgxp_rederive_enable is the REAL
 * extracted gpu.c function here). */
extern "C" int gpu_ws_present_native_43(void) { return 0; }
extern "C" int gpu_ws_precise_nclip_enabled(void) { return 0; }
extern "C" uint32_t memory_get_ram_bytes(void) { return 2u * 1024u * 1024u; }
extern "C" void psx_ws_note_gte_project(int) {}
extern "C" uint32_t psx_read_word(uint32_t) { return 0; }
extern "C" { uint64_t s_frame_count = 0; }
extern "C" uint32_t psx_gte_cmd_latency(uint32_t cmd) { return 7u + (cmd & 0x3Fu); }
extern "C" void psx_gte_set(CPUState *cpu, uint32_t latency) { cpu->gte_ts_done += latency; }
extern "C" uint32_t psx_nd_wood_batch_ot(void) { return 0; }
extern "C" uint32_t psx_nd_sibling_ot_hint(void) { return 0; }

static int g_fail = 0, g_checks = 0;
#define CHECK(c)                                                                    \
    do {                                                                            \
        ++g_checks;                                                                 \
        if (!(c)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
                    ++g_fail; }                                                     \
    } while (0)

static uint32_t enc_i(uint32_t op, uint32_t rs, uint32_t rt, uint16_t imm) {
    return (op << 26) | (rs << 21) | (rt << 16) | imm;
}
#define SW(rt)   enc_i(0x2B, 1, rt, 0)
#define SH(rt)   enc_i(0x29, 1, rt, 0)
#define LW(rt)   enc_i(0x23, 1, rt, 0)
#define SWC2(rt) enc_i(0x3A, 1, rt, 0)

static const uint32_t RTPS1 = 0x00180001u, RTPS0 = 0x00100001u, RTPT1 = 0x00280030u;

struct Xf { int16_t rt[9]; int32_t tr[3]; uint16_t h; int32_t ofx, ofy; };
static uint32_t pk(int16_t lo, int16_t hi) { return (uint32_t)(uint16_t)lo | ((uint32_t)(uint16_t)hi << 16); }
static void load_xf(CPUState &c, const Xf &x) {
    c.gte_ctrl[0] = pk(x.rt[0], x.rt[1]); c.gte_ctrl[1] = pk(x.rt[2], x.rt[3]);
    c.gte_ctrl[2] = pk(x.rt[4], x.rt[5]); c.gte_ctrl[3] = pk(x.rt[6], x.rt[7]);
    c.gte_ctrl[4] = (uint32_t)(int32_t)x.rt[8];
    c.gte_ctrl[5] = (uint32_t)x.tr[0]; c.gte_ctrl[6] = (uint32_t)x.tr[1]; c.gte_ctrl[7] = (uint32_t)x.tr[2];
    c.gte_ctrl[24] = (uint32_t)x.ofx; c.gte_ctrl[25] = (uint32_t)x.ofy; c.gte_ctrl[26] = x.h;
}
static void set_v(CPUState &c, int lane, int16_t x, int16_t y, int16_t z) {
    c.gte_data[lane * 2] = pk(x, y);
    c.gte_data[lane * 2 + 1] = (uint32_t)(int32_t)z;
}
static const Xf XF = {{3547, 0, 2048, 0, 4096, 0, -2048, 0, 3547}, {17, -33, 1500}, 300, 160 << 16, 120 << 16};
static uint32_t swc2(const CPUState &c, int reg, uint32_t addr) {
    psx_pgxp_cop2(nullptr, SWC2(reg), c.gte_data[reg], addr);
    return c.gte_data[reg];
}
static PgxpViewCensus census() { PgxpViewCensus c; pgxp_view_census_get(&c); return c; }

/* one RTPS of V0 under x, stored at addr; returns the view (or flags 0xFFFF) */
static PgxpView project(const Xf &x, int16_t v0, int16_t v1, int16_t v2, uint32_t cmd, uint32_t addr) {
    CPUState c{};
    load_xf(c, x);
    set_v(c, 0, v0, v1, v2);
    gte_execute(&c, cmd);
    PgxpView v{};
    const uint32_t w = swc2(c, 14, addr);
    if (pgxp_get_precise_vertex_view(addr, w, &v) != PGXP_SRC_DATAFLOW) v.flags = 0xFFFF;
    return v;
}

/* ========================================================================== */
static void t_arming() {
    /* fail closed: payload allocation failure keeps the census off and the
     * transport follows the user's (all off) modes */
    gpu_pgxp_rederive_enable();
    CHECK(pgxp_enabled() == 0);
    pgxp_test_view_fail_next_alloc(1);
    gpu_view_census_set(1);
    CHECK(gpu_view_census_enabled() == 0 && pgxp_view_payload() == 0 && pgxp_enabled() == 0);

    /* census ring allocation failure: counters still work */
    pgxp_test_view_census_fail_ring_alloc(1);
    pgxp_set_cpu_mode(1);
    pgxp_set_tolerance(0.25f);
    gpu_view_census_set(1);
    CHECK(gpu_view_census_enabled() == 1 && pgxp_view_payload() == 1);
    CHECK(pgxp_enabled() == 1);                                   /* armed for collection */
    CHECK(gte_geometry_correction_enabled() == 0 && gpu_texture_correction_enabled() == 0);
    PgxpViewCensus c = census();
    CHECK(c.ring_cap == 0 && c.ring_alloc_fail == 1);
    PgxpViewCensusPrim r[2];
    CHECK(pgxp_view_census_recent(r, 2) == 0);

    /* disarm: transport off again (no user mode wants it); user tunables kept */
    gpu_view_census_set(0);
    CHECK(gpu_view_census_enabled() == 0 && pgxp_view_payload() == 0 && pgxp_enabled() == 0);
    CHECK(pgxp_cpu_mode() == 1 && pgxp_tolerance() == 0.25f);

    /* with the user's texture correction on, disarming keeps the transport */
    gpu_texture_correction_set(1);
    gpu_view_census_set(1);
    CHECK(pgxp_enabled() == 1 && pgxp_view_payload() == 1);
    CHECK(census().ring_cap == 4096u);                            /* ring allocated now */
    gpu_view_census_set(0);
    CHECK(pgxp_enabled() == 1 && gpu_texture_correction_enabled() == 1 && pgxp_view_payload() == 0);
    gpu_texture_correction_set(0);
    CHECK(pgxp_enabled() == 0);
    pgxp_set_cpu_mode(0);
    pgxp_set_tolerance(-1.0f);
    gpu_view_census_set(1);
    CHECK(pgxp_enabled() == 1 && gte_geometry_correction_enabled() == 0 && gpu_texture_correction_enabled() == 0);
}

static void t_mac_boundaries() {
    Xf x = XF;
    x.rt[0] = 4095; x.rt[1] = 0; x.rt[2] = 0; x.tr[0] = 0x7FFFFFFF;          /* mac1 = 2^43 - 1 */
    PgxpView v = project(x, 1, 0, 0, RTPS1, 0x80110000u);
    CHECK(v.flags != 0xFFFF && v.mac[0] == ((int64_t)1 << 43) - 1);
    CHECK(!(v.flags & PGXP_VIEW_MAC1_OVF44) && !(v.flags & PGXP_VIEW_MAC1_WRAP32));
    x.rt[0] = 4096;                                                          /* mac1 = 2^43 */
    v = project(x, 1, 0, 0, RTPS1, 0x80110004u);
    CHECK(v.mac[0] == ((int64_t)1 << 43));
    CHECK((v.flags & PGXP_VIEW_MAC1_OVF44) && (v.flags & PGXP_VIEW_MAC1_WRAP32));
    CHECK(!(v.flags & (PGXP_VIEW_MAC2_OVF44 | PGXP_VIEW_MAC3_OVF44 | PGXP_VIEW_MAC2_WRAP32 | PGXP_VIEW_MAC3_WRAP32)));
    CHECK((v.flags & PGXP_VIEW_NATIVE_DIVERGED) != 0);
    x.rt[0] = 0; x.tr[0] = (int32_t)0x80000000u;                             /* mac1 = -2^43 */
    v = project(x, 1, 0, 0, RTPS1, 0x80110008u);
    CHECK(v.mac[0] == -((int64_t)1 << 43));
    CHECK(!(v.flags & PGXP_VIEW_MAC1_OVF44) && !(v.flags & PGXP_VIEW_MAC1_WRAP32));
    x.rt[0] = -1;                                                            /* mac1 = -2^43 - 1 */
    v = project(x, 1, 0, 0, RTPS1, 0x8011000Cu);
    CHECK(v.mac[0] == -((int64_t)1 << 43) - 1);
    CHECK((v.flags & PGXP_VIEW_MAC1_OVF44) && (v.flags & PGXP_VIEW_MAC1_WRAP32));
    /* sf = 0: the 32-bit MAC register wraps at 2^31 without any 44-bit overflow */
    x = XF; x.rt[0] = -1; x.rt[1] = 0; x.rt[2] = 0; x.tr[0] = 1 << 19;       /* mac1 = 2^31 - 1 */
    v = project(x, 1, 0, 0, RTPS0, 0x80110010u);
    CHECK(v.mac[0] == 0x7FFFFFFFll && !(v.flags & PGXP_VIEW_MAC1_WRAP32) && !(v.flags & PGXP_VIEW_SF));
    x.rt[0] = 0;                                                             /* mac1 = 2^31 */
    v = project(x, 1, 0, 0, RTPS0, 0x80110014u);
    CHECK(v.mac[0] == 0x80000000ll && (v.flags & PGXP_VIEW_MAC1_WRAP32) && !(v.flags & PGXP_VIEW_MAC1_OVF44));
    v = project(x, 1, 0, 0, RTPS1, 0x80110018u);                             /* same MAC, sf = 1 */
    CHECK(!(v.flags & PGXP_VIEW_MAC1_WRAP32));
    /* axes 2 and 3 */
    x = XF; x.rt[3] = 0; x.rt[4] = 4096; x.rt[5] = 0; x.tr[1] = 0x7FFFFFFF;  /* mac2 = 2^43 + 4096*(V1-1) */
    v = project(x, 0, 1, 0, RTPS1, 0x8011001Cu);
    CHECK((v.flags & PGXP_VIEW_MAC2_OVF44) && (v.flags & PGXP_VIEW_MAC2_WRAP32) && !(v.flags & PGXP_VIEW_MAC1_OVF44));
    x = XF; x.rt[6] = 0; x.rt[7] = 0; x.rt[8] = 4096; x.tr[2] = 0x7FFFFFFF;  /* mac3 = 2^43 */
    v = project(x, 0, 0, 1, RTPS1, 0x80110020u);
    CHECK((v.flags & PGXP_VIEW_MAC3_OVF44) && (v.flags & PGXP_VIEW_MAC3_WRAP32));
    x.rt[8] = 0; x.tr[2] = 1 << 19;                                          /* mac3 = 2^31, sf = 0 */
    v = project(x, 0, 0, 1, RTPS0, 0x80110024u);
    CHECK((v.flags & PGXP_VIEW_MAC3_WRAP32) && !(v.flags & PGXP_VIEW_MAC3_OVF44));
    /* clean projection: nothing diverged */
    v = project(XF, -300, 120, 250, RTPS1, 0x80110028u);
    CHECK(v.flags != 0xFFFF && (v.flags & PGXP_VIEW_NATIVE_DIVERGED) == 0);
}

/* Build a textured-triangle packet (vertex words at gp0 indices 1, 3, 5) whose
 * three words were SWC2'd from one RTPT to base + 4*index. */
static void packet_from_rtpt(uint32_t base, const int16_t vs[3][3]) {
    CPUState c{};
    load_xf(c, XF);
    for (int l = 0; l < 3; l++) set_v(c, l, vs[l][0], vs[l][1], vs[l][2]);
    gte_execute(&c, RTPT1);
    std::memset(gp0_cmd_buf, 0, 16 * sizeof(uint32_t));
    gp0_cmd_buf[0] = 0x24808080u;
    const int idx[3] = {1, 3, 5};
    for (int l = 0; l < 3; l++) gp0_cmd_buf[idx[l]] = swc2(c, 12 + l, base + 4u * (uint32_t)idx[l]);
    gp0_cmd_source_addr = base;
}

static void t_draw_unchanged() {
    /* The census call reads gp0 state only: the renderer sees the same calls and
     * the texture predicate takes the same decisions with the census on or off,
     * both with texture correction off and on. */
    const int16_t vs[3][3] = {{-30, 12, 250}, {40, -6, 300}, {50, 10, -40}};
    for (int tex = 0; tex <= 1; tex++) {
        gpu_texture_correction_set(tex);
        float q_on[3] = {0, 0, 0}, q_off[3] = {0, 0, 0};
        int last_on = -2, last_off = -3;
        uint64_t d_on[5], d_off[5];
        for (int census_on = 1; census_on >= 0; census_on--) {
            gpu_view_census_set(census_on);
            packet_from_rtpt(0x80120000u, vs);
            uint64_t a[5], b[5];
            harness_texcorr(&a[0], &a[1], &a[2], &a[3], &a[4]);
            const int calls0 = g_persp_calls;
            harness_prepare_texture_triangle(1, 3, 5);
            harness_texcorr(&b[0], &b[1], &b[2], &b[3], &b[4]);
            CHECK(g_persp_calls - calls0 == (tex ? 2 : 1));   /* reset call (+ arm call) */
            uint64_t *d = census_on ? d_on : d_off;
            for (int i = 0; i < 5; i++) d[i] = b[i] - a[i];
            (census_on ? last_on : last_off) = g_persp_last_on;
            std::memcpy(census_on ? q_on : q_off, g_persp_last_q, sizeof(q_on));
        }
        CHECK(std::memcmp(d_on, d_off, sizeof(d_on)) == 0);
        CHECK(last_on == last_off && std::memcmp(q_on, q_off, sizeof(q_on)) == 0);
        CHECK(tex ? (d_on[1] == 1 && last_on == 1) : (d_on[2] == 1 && last_on == 0));
    }
    gpu_texture_correction_set(0);
    gpu_view_census_set(1);
}

static void t_classification() {
    pgxp_view_census_reset();
    const int16_t vs[3][3] = {{-300, 120, 250}, {40, -60, 900}, {500, 10, -400}};
    /* all-hit, one RTPT */
    packet_from_rtpt(0x80130000u, vs);
    harness_prepare_texture_triangle(1, 3, 5);
    PgxpViewCensus c = census();
    CHECK(c.kind[PGXP_VIEW_CENSUS_TRI].prims == 1 && c.kind[0].all_hit == 1 && c.kind[0].all_hit_one_command == 1);
    CHECK(c.kind[0].hit_committed == 3 && c.kind[0].hit_ring_live == 3 && c.kind[0].vert_hits == 3);
    PgxpViewCensusPrim rec[8];
    CHECK(pgxp_view_census_recent(rec, 8) == 1 && rec[0].hits == 3 && rec[0].lane[0] == 0 && rec[0].lane[2] == 2);
    CHECK(rec[0].vz[0] > 0 && rec[0].tag[0] != 0);
    /* quad: 4th vertex from a separate RTPS -> all-hit, not one command */
    CPUState c4{};
    load_xf(c4, XF);
    set_v(c4, 0, 77, 66, 300);
    gte_execute(&c4, RTPS1);
    gp0_cmd_buf[7] = swc2(c4, 14, 0x80130000u + 28u);
    const int qi[4] = {1, 3, 5, 7};
    harness_view_census_quad(qi);
    c = census();
    CHECK(c.kind[PGXP_VIEW_CENSUS_QUAD].prims == 1 && c.kind[1].all_hit == 1 && c.kind[1].all_hit_one_command == 0);
    /* value mismatch on one vertex: a DIFFERENT tracked projection was stored at
     * that packet slot after the packet word was built */
    packet_from_rtpt(0x80140000u, vs);
    CPUState c5{};
    load_xf(c5, XF);
    set_v(c5, 0, 123, 45, 600);
    gte_execute(&c5, RTPS1);
    CHECK(swc2(c5, 14, 0x80140000u + 12u) != gp0_cmd_buf[3]);
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].partial == 1 && c.kind[0].miss[PGXP_VIEW_MISS_VALUE_MISMATCH] == 1);
    /* untracked store over a slot: "known word, no precision" -> no_shadow */
    packet_from_rtpt(0x80160000u, vs);
    psx_pgxp_store(nullptr, SW(0), 0x80160000u + 20u, 0x12345678u);
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].partial == 2 && c.kind[0].miss[PGXP_VIEW_MISS_NO_SHADOW] == 1);
    /* half write: precision may survive, the view does not -> no_view */
    packet_from_rtpt(0x80150000u, vs);
    psx_pgxp_load(nullptr, LW(8), 0x80150000u + 4u, gp0_cmd_buf[1]);
    psx_pgxp_store(nullptr, SH(8), 0x80150000u + 4u, gp0_cmd_buf[1]);
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].miss[PGXP_VIEW_MISS_NO_VIEW] == 1 && c.kind[0].partial == 3);
    /* immediate GP0 (no packet address) */
    gp0_cmd_source_addr = 0xFFFFFFFFu;
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].none == 1 && c.kind[0].miss[PGXP_VIEW_MISS_NO_SOURCE] == 3);
    /* address never written */
    gp0_cmd_source_addr = 0x80170000u;
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].none == 2 && c.kind[0].miss[PGXP_VIEW_MISS_NO_SHADOW] == 4);
    /* evicted: > 64K projections later the first packet's records are reused */
    packet_from_rtpt(0x80180000u, vs);
    const uint32_t keep[3] = {gp0_cmd_buf[1], gp0_cmd_buf[3], gp0_cmd_buf[5]};
    CPUState cc{};
    load_xf(cc, XF);
    for (int i = 0; i < 65536 + 8; i++) { set_v(cc, 0, (int16_t)(i & 511), 3, 300); gte_execute(&cc, RTPS1); }
    gp0_cmd_buf[1] = keep[0]; gp0_cmd_buf[3] = keep[1]; gp0_cmd_buf[5] = keep[2];
    gp0_cmd_source_addr = 0x80180000u;
    harness_prepare_texture_triangle(1, 3, 5);
    c = census();
    CHECK(c.kind[0].miss[PGXP_VIEW_MISS_EVICTED] == 3);
    /* disabled: census module armed directly while the payload is off */
    pgxp_set_view_payload(0);
    pgxp_view_census_set(1);
    harness_view_census_quad(qi);
    c = census();
    CHECK(c.kind[1].miss[PGXP_VIEW_MISS_DISABLED] == 4);
    gpu_view_census_set(1);
    /* newest-first records */
    int got = pgxp_view_census_recent(rec, 8);
    CHECK(got == 8 && rec[0].kind == PGXP_VIEW_CENSUS_QUAD && rec[0].reason[0] == PGXP_VIEW_MISS_DISABLED);
    CHECK(rec[1].kind == PGXP_VIEW_CENSUS_TRI && rec[1].reason[1] == PGXP_VIEW_MISS_EVICTED);
}

static void t_tcp() {
    std::printf("JSON:%s\n", harness_tcp(1, "{\"cmd\":\"pgxp_view\"}"));
    std::printf("JSON:%s\n", harness_tcp(2, "{\"cmd\":\"pgxp_view\",\"recent\":5}"));
    std::printf("JSON:%s\n", harness_tcp(3, "{\"cmd\":\"pgxp_view\",\"recent\":999}"));
    std::printf("JSON:%s\n", harness_tcp(4, "{\"cmd\":\"pgxp_view\",\"census\":0}"));
    CHECK(pgxp_enabled() == 0 && gpu_view_census_enabled() == 0);
    std::printf("JSON:%s\n", harness_tcp(5, "{\"cmd\":\"pgxp_view\",\"census\":1,\"reset\":1}"));
    CHECK(pgxp_enabled() == 1 && gpu_view_census_enabled() == 1 && census().kind[0].prims == 0);
}

// Actual CPU GTE/PGXP producer -> transport -> CPU SDK-layout staging.
// Synthetic guest instructions and dummy material; not a game/SDK render.
extern "C" int gte_rtp_ring_get_xform(uint64_t,int16_t[9],int32_t[3],uint32_t*,uint32_t*);
static int bridge_lookups=0,bridge_transforms=0;
static int bridge_lookup(void*,uint32_t address,uint32_t word,PgxpView* view) {
    ++bridge_lookups;
    return pgxp_get_precise_vertex_view(address,word,view);
}
static int bridge_transform(void*,uint64_t sequence,int16_t rt[9],int32_t tr[3],uint32_t* frame,uint32_t* ra) {
    ++bridge_transforms;
    return gte_rtp_ring_get_xform(sequence,rt,tr,frame,ra);
}
static void t_real_producer_bridge() {
    using namespace einhd;
    gpu_texture_correction_set(0);gpu_view_census_set(1);pgxp_view_census_reset();
    s_frame_count=4242;
    const uint32_t base=0x801E0000u;
    const int idx[3]={1,3,5};
    const int16_t points[3][3]={{0,0,0},{20,0,0},{0,20,0}};
    MeshInput input;input.frame=4242;input.material_identity=0xEE1234u;
    input.material=reinterpret_cast<remixapi_MaterialHandle>(uintptr_t(0x100));
    for(int i=0;i<3;++i){input.packet_address[i]=base+4u*uint32_t(idx[i]);input.sdk_vertex_color[i]=0xFF808080u;input.uv[i][0]=i==1?1.f:0.f;input.uv[i][1]=i==2?1.f:0.f;}
    auto project_packet=[&](int32_t translation_x){
        CPUState cpu{};Xf x=XF;x.tr[0]=translation_x;load_xf(cpu,x);
        for(int lane=0;lane<3;++lane)set_v(cpu,lane,points[lane][0],points[lane][1],points[lane][2]);
        gte_execute(&cpu,RTPT1);
        gp0_cmd_buf[0]=0x24808080u;gp0_cmd_source_addr=base;
        for(int lane=0;lane<3;++lane){input.packet_word[lane]=swc2(cpu,12+lane,input.packet_address[lane]);gp0_cmd_buf[idx[lane]]=input.packet_word[lane];}
    };
    project_packet(XF.tr[0]);
    PgxpView views[3]{};
    for(int i=0;i<3;++i){CHECK(pgxp_get_precise_vertex_view(input.packet_address[i],input.packet_word[i],&views[i])==PGXP_SRC_DATAFLOW);CHECK(views[i].cmd==0x30&&views[i].lane==i);}
    CHECK(views[0].rtp_seq==views[1].rtp_seq&&views[0].rtp_seq==views[2].rtp_seq);
    MeshSource source{nullptr,bridge_lookup,bridge_transform};MeshPacket packet;
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::None);
    CHECK(bridge_lookups==3&&bridge_transforms==3);
    CHECK(packet.mesh.surfaces_values==&packet.surface&&packet.surface.vertices_values==packet.vertices);
    for(int i=0;i<3;++i)for(int axis=0;axis<3;++axis)CHECK(packet.vertices[i].position[axis]==points[i][axis]);
    CHECK(std::memcmp(packet.combined_rt,XF.rt,sizeof XF.rt)==0&&std::memcmp(packet.combined_tr,XF.tr,sizeof XF.tr)==0);
    CHECK(packet.projection_h==XF.h&&packet.projection_ofx==XF.ofx&&packet.projection_ofy==XF.ofy);
    const uint64_t hash=packet.mesh.hash;
    harness_prepare_texture_triangle(1,3,5);CHECK(census().kind[0].all_hit==1&&census().kind[0].hit_committed==3);
    project_packet(XF.tr[0]+10);
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::None&&packet.mesh.hash==hash&&packet.combined_tr[0]==XF.tr[0]+10);
    input.frame++;CHECK(build_mesh_packet(input,source,packet)==MeshReject::StaleFrame);
    CHECK(packet.mesh.surfaces_count==0&&packet.surface.vertices_values==nullptr);input.frame--;
    // Actual shadow invalidation by a partial write must deny the CPU bridge.
    psx_pgxp_store(nullptr,SH(8),input.packet_address[0],input.packet_word[0]);
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::DataflowMiss);
    CHECK(packet.mesh.surfaces_count==0&&packet.surface.vertices_values==nullptr);
    gpu_view_census_set(0);
}

int main() {
    t_arming();
    t_mac_boundaries();
    t_draw_unchanged();
    t_classification();
    t_tcp();
    t_real_producer_bridge();
    std::printf("checks %d failures %d\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
