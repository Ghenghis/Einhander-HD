#!/usr/bin/env python3
"""Build the PRIVATE view-provenance v2 patch (remix-provenance, claude-einhander). Source generation only: no compile,
no game; canonical files are read and never written; the delivered v1 folder (../impl) is read, never written.

v2 = v1 (edit lists imported from the hash-pinned v1 generator) + Codex review msg_9eabf5c84a0f3ff2 / msg_a1d476554fb161fb:
  * gte.cpp: per-axis MAC overflow metadata — MACn_OVF44 (raw TR*4096+RT*V outside the signed 44-bit accumulator range)
    and MACn_WRAP32 (MAC >> sf*12 outside int32: the 32-bit MAC register, hence IR, wrapped; axis 3 also for the
    always->>12 SZ path); PGXP_VIEW_NATIVE_DIVERGED mask (pinhole re-projection must not be trusted).
  * pgxp.cpp/.h: consumer reports a per-vertex MISS REASON (no_source / disabled / no_shadow / value_mismatch / no_view /
    evicted / incoherent); new stat no_source.
  * NEW src/pgxp_view_census.cpp: per-primitive census (triangles and quads): prims, all-hit / partial / none, per-vertex
    miss reasons, hits with a validated ring commit, hits whose ring record is STILL live (independent re-check through
    gte_rtp_ring_seq_live), hits whose native X/Y diverged, all-hit primitives from one GTE command; lazily allocated ring
    of the newest 4096 primitive records (fails closed to counters only).
  * gpu.c: opt-in census flag; it ARMS the PGXP transport for collection without geometry or texture correction, and
    disarming re-derives the transport from the user's own modes; census hooks at every textured triangle
    (prepare_texture_triangle) and every textured quad (before the rect fast path). No renderer state is touched.
  * gpu.h: gpu_view_census_set / gpu_view_census_enabled.
  * debug_server.c: TCP verb "pgxp_view" (arm/disarm, reset, state, payload stats, census, newest records). No printf.
Outputs keep each base's line endings and BOM. diffs/ are LF unified diffs against the canonical bases.
"""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1GEN = HERE.parent / "impl" / "make_view_provenance_patch.py"
V1GEN_SHA = "b30505a54b2b17d085df375e5304887665105e230222549388786dbe4a99bca4"
RT = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime")
BASES = {"src/gte.cpp": "0563d9a1da49c6c0538c1285f803939c1a9441b5485a16a4d6f7eff6f50656c0",
         "src/pgxp.cpp": "b3a6dae3c4087c50f0d173de4df5f3db1cdbcced287bbc9a45b9146e2d023b66",
         "include/pgxp.h": "b9bacf319e33c3787fbea010035f16043da6226047c7e549b85a6c14b0ec0485",
         "src/gpu.c": "8eade36e1c446da242c4aae8e2054770ab3124710a23a6903c4391b5bfe6de8f",
         "include/gpu.h": "f36519ed9f2f7afd696ab14cc2e1419728bbea82289b9b329aefa69531372805",
         "src/debug_server.c": "86ce765bab0ef633f8feaefbf5e9de8eb5068102a66dbfa43b01d7aa777fc883"}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_v1():
    if sha(V1GEN.read_bytes()) != V1GEN_SHA:
        raise SystemExit("v1 generator changed; refusing")
    spec = importlib.util.spec_from_file_location("v1gen", V1GEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------------------------------------------------------- pgxp.h
H_FLAGS_OLD = """    PGXP_VIEW_RTP_COMMITTED = 1u << 9,  /* the GTE ring record of this command was *
                                         * written and matched (lane, V, xform)   */
};
"""
H_FLAGS_NEW = """    PGXP_VIEW_RTP_COMMITTED = 1u << 9,  /* the GTE ring record of this command was *
                                         * written and matched (lane, V, xform)   */
    /* v2: per-axis accumulator overflow / 32-bit MAC register wrap */
    PGXP_VIEW_MAC1_OVF44    = 1u << 10, /* raw MAC1 outside signed 44 bits        */
    PGXP_VIEW_MAC2_OVF44    = 1u << 11,
    PGXP_VIEW_MAC3_OVF44    = 1u << 12,
    PGXP_VIEW_MAC1_WRAP32   = 1u << 13, /* MAC1 >> sf*12 outside int32: the MAC  *
                                         * register and IR1 came from a wrapped  *
                                         * value                                 */
    PGXP_VIEW_MAC2_WRAP32   = 1u << 14,
    PGXP_VIEW_MAC3_WRAP32   = 1u << 15, /* (axis 3 also feeds SZ3 via >> 12)    */
};

/* Any of these: the native screen position did not follow the payload, so a
 * pinhole re-projection of the payload must not be treated as the native
 * vertex (and vice versa). WS_SQUASH / DOME are deliberate screen-X changes
 * and are reported separately. */
#define PGXP_VIEW_NATIVE_DIVERGED                                              \\
    (PGXP_VIEW_IR_SAT | PGXP_VIEW_SZ_SAT | PGXP_VIEW_DIV_OVF |                 \\
     PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP |                                   \\
     PGXP_VIEW_MAC1_OVF44 | PGXP_VIEW_MAC2_OVF44 | PGXP_VIEW_MAC3_OVF44 |      \\
     PGXP_VIEW_MAC1_WRAP32 | PGXP_VIEW_MAC2_WRAP32 | PGXP_VIEW_MAC3_WRAP32)
"""

H_STATS_OLD = "    uint64_t no_shadow;           /* disabled / unknown address / no live shadow */\n"
H_STATS_NEW = ("    uint64_t no_shadow;           /* disabled / no live shadow                   */\n"
               "    uint64_t no_source;           /* immediate GP0 word: no packet address (v2)  */\n")

H_API_OLD = "void pgxp_get_view_stats(PgxpViewStats *out);\n"
H_API_NEW = r'''void pgxp_get_view_stats(PgxpViewStats *out);

/* --- v2: miss reasons + per-primitive census (gpu.c textured primitives) --- */
enum {
    PGXP_VIEW_MISS_NONE = 0,
    PGXP_VIEW_MISS_NO_SOURCE,        /* immediate GP0 word: no packet address   */
    PGXP_VIEW_MISS_DISABLED,         /* transport or view payload off           */
    PGXP_VIEW_MISS_NO_SHADOW,        /* no live, fully tracked shadow at addr   */
    PGXP_VIEW_MISS_VALUE_MISMATCH,   /* shadow describes a different word       */
    PGXP_VIEW_MISS_NO_VIEW,          /* precision but no view (non-identity op, *
                                      * half write, produced while view off)    */
    PGXP_VIEW_MISS_EVICTED,          /* record reused by a newer projection     */
    PGXP_VIEW_MISS_INCOHERENT,       /* record does not describe this shadow    */
    PGXP_VIEW_MISS_COUNT
};

/* pgxp_get_precise_vertex_view plus the reason of a miss (may be NULL). */
int pgxp_get_precise_vertex_view_ex(uint32_t addr, uint32_t packet_word,
                                    PgxpView *out, int *miss_reason);

typedef struct PgxpViewCensusKind {
    uint64_t prims;                  /* primitives seen                         */
    uint64_t all_hit;                /* every vertex carried a view             */
    uint64_t partial;
    uint64_t none;
    uint64_t verts, vert_hits;
    uint64_t miss[PGXP_VIEW_MISS_COUNT];  /* per-vertex miss reasons            */
    uint64_t hit_committed;          /* hits whose ring commit was validated    */
    uint64_t hit_ring_live;          /* ...and whose ring record is still live  *
                                      * at draw time (independent re-check)     */
    uint64_t hit_diverged;           /* hits with PGXP_VIEW_NATIVE_DIVERGED     */
    uint64_t all_hit_one_command;    /* all-hit and every vertex committed from *
                                      * the same GTE command (one rtp_seq)      */
} PgxpViewCensusKind;

enum { PGXP_VIEW_CENSUS_TRI = 0, PGXP_VIEW_CENSUS_QUAD = 1 };

typedef struct PgxpViewCensus {
    int      enabled;
    uint32_t ring_cap;               /* records kept (0 if the ring is absent)  */
    uint64_t ring_total;             /* records written since reset             */
    uint64_t ring_alloc_fail;
    PgxpViewCensusKind kind[2];      /* [TRI], [QUAD]                           */
} PgxpViewCensus;

typedef struct PgxpViewCensusPrim {
    uint32_t frame;
    uint8_t  kind, nverts, hits, reserved;
    uint8_t  reason[4];              /* PGXP_VIEW_MISS_* per vertex             */
    uint8_t  lane[4];
    uint32_t tag[4];
    int32_t  vz[4];                  /* view z = MAC3 >> 12 of hits (clamped)   */
} PgxpViewCensusPrim;

/* Counters work without the record ring; the ring is lazily allocated on the
 * first enable and its failure is counted, never fatal. */
void pgxp_view_census_set(int on);
int  pgxp_view_census_enabled(void);
void pgxp_view_census_reset(void);
/* kind PGXP_VIEW_CENSUS_TRI/QUAD; words = the GP0 vertex words; addrs = their
 * packet addresses (0xFFFFFFFF = immediate); n = 3 or 4. */
void pgxp_view_census_prim(int kind, const uint32_t *words,
                           const uint32_t *addrs, int n);
void pgxp_view_census_get(PgxpViewCensus *out);
/* Copies up to max newest records, newest first; returns the count. */
int  pgxp_view_census_recent(PgxpViewCensusPrim *out, int max);
void pgxp_test_view_census_fail_ring_alloc(int count);
'''

# -------------------------------------------------------------------------------------------------------------- pgxp.cpp
CONSUMER_V2 = r'''static int view_lookup(uint32_t addr, uint32_t packet_word, PgxpView *out) {
    if (!s_enabled || !s_view_on) {
        s_vstats.no_shadow++;
        return PGXP_VIEW_MISS_DISABLED;
    }
    if (addr == 0xFFFFFFFFu) {
        s_vstats.no_source++;
        return PGXP_VIEW_MISS_NO_SOURCE;
    }
    const PGXPValue *pv = pgxp_ptr(addr);
    if (!pv || pv->gen != s_gen || (pv->flags & PGXP_F_VXY) != PGXP_F_VXY) {
        s_vstats.no_shadow++;
        return PGXP_VIEW_MISS_NO_SHADOW;
    }
    if (pv->value != packet_word) {
        s_vstats.value_mismatch++;
        return PGXP_VIEW_MISS_VALUE_MISMATCH;
    }
    if (!(pv->flags & PGXP_F_VW)) {
        s_vstats.no_view++;
        return PGXP_VIEW_MISS_NO_VIEW;
    }
    const uint32_t tag = *vtag_of(pv);
    const PgxpViewRec *r = &s_view_ring[tag & (PGXP_VIEW_RING_CAP - 1u)];
    if (tag == 0 || r->tag != tag) {
        s_vstats.evicted++;
        return PGXP_VIEW_MISS_EVICTED;
    }
    if (r->packed != pv->value || r->x16 != pv->x16 || r->y16 != pv->y16 ||
        r->sz3 != pv->z) {
        s_vstats.incoherent++;
        return PGXP_VIEW_MISS_INCOHERENT;
    }
    if (out) {
        for (int i = 0; i < 3; i++) { out->mac[i] = r->mac[i]; out->v[i] = r->v[i]; }
        out->rtp_seq = r->rtp_seq;
        out->ofx = r->ofx;
        out->ofy = r->ofy;
        out->x16 = r->x16;
        out->y16 = r->y16;
        out->packed = r->packed;
        out->xform_hash = r->xform_hash;
        out->frame = r->frame;
        out->tag = r->tag;
        out->h = r->h;
        out->sz3 = r->sz3;
        out->flags = r->flags;
        out->lane = r->lane;
        out->cmd = r->cmd;
    }
    s_vstats.hits++;
    return PGXP_VIEW_MISS_NONE;
}

extern "C" int pgxp_get_precise_vertex_view_ex(uint32_t addr, uint32_t packet_word,
                                               PgxpView *out, int *miss_reason) {
    s_vstats.lookups++;
    const int why = view_lookup(addr, packet_word, out);
    if (miss_reason) *miss_reason = why;
    return why == PGXP_VIEW_MISS_NONE ? PGXP_SRC_DATAFLOW : PGXP_SRC_NATIVE;
}

extern "C" int pgxp_get_precise_vertex_view(uint32_t addr, uint32_t packet_word,
                                            PgxpView *out) {
    return pgxp_get_precise_vertex_view_ex(addr, packet_word, out, nullptr);
}

'''

CENSUS_TU = r'''/* pgxp_view_census.cpp — opt-in per-primitive census of the 3D view payload
 * (remix-provenance v2, PRIVATE, default OFF). gpu.c hands every textured
 * triangle / quad's vertex words and packet addresses here when the census is
 * armed; the census asks the DATAFLOW-only view consumer for each vertex and
 * keeps counters plus a ring of the newest primitive records for the TCP
 * debug server ("pgxp_view"). Host-only and visual-only: it never touches
 * guest state or renderer state. No printf, no files. */

#include "pgxp.h"

#include <cstdlib>
#include <cstring>

extern "C" { extern uint64_t s_frame_count; }
extern "C" int gte_rtp_ring_seq_live(uint64_t seq);

#define PGXP_VIEW_CENSUS_RING (1u << 12)       /* power of two                 */

static int                 s_census_on = 0;
static PgxpViewCensus      s_census;
static PgxpViewCensusPrim *s_census_ring = nullptr;   /* lazy, opt-in         */
static uint64_t            s_census_ring_seq = 0;
static int                 s_census_fail_ring = 0;    /* test injection        */

extern "C" void pgxp_view_census_set(int on) {
    if (on && !s_census_ring) {
        if (s_census_fail_ring > 0) {
            --s_census_fail_ring;
            s_census.ring_alloc_fail++;
        } else {
            s_census_ring = (PgxpViewCensusPrim *)std::calloc(PGXP_VIEW_CENSUS_RING,
                                                              sizeof(PgxpViewCensusPrim));
            if (!s_census_ring) s_census.ring_alloc_fail++;   /* counters only */
        }
    }
    s_census_on = on ? 1 : 0;
}

extern "C" int pgxp_view_census_enabled(void) { return s_census_on; }

extern "C" void pgxp_view_census_reset(void) {
    const uint64_t fails = s_census.ring_alloc_fail;
    std::memset(&s_census, 0, sizeof(s_census));
    s_census.ring_alloc_fail = fails;
    s_census_ring_seq = 0;
}

extern "C" void pgxp_view_census_prim(int kind, const uint32_t *words,
                                      const uint32_t *addrs, int n) {
    if (!s_census_on || kind < 0 || kind > 1 || n < 1 || n > 4 || !words || !addrs)
        return;
    PgxpViewCensusKind *k = &s_census.kind[kind];
    PgxpViewCensusPrim rec;
    std::memset(&rec, 0, sizeof(rec));
    rec.frame = (uint32_t)s_frame_count;
    rec.kind = (uint8_t)kind;
    rec.nverts = (uint8_t)n;
    int hits = 0, one_command = 1;
    uint64_t seq0 = 0;
    for (int i = 0; i < n; i++) {
        PgxpView v;
        int why = PGXP_VIEW_MISS_NONE;
        k->verts++;
        if (pgxp_get_precise_vertex_view_ex(addrs[i], words[i], &v, &why) ==
            PGXP_SRC_DATAFLOW) {
            k->vert_hits++;
            const int committed = (v.flags & PGXP_VIEW_RTP_COMMITTED) != 0;
            if (committed) {
                k->hit_committed++;
                if (gte_rtp_ring_seq_live(v.rtp_seq)) k->hit_ring_live++;
            }
            if (v.flags & PGXP_VIEW_NATIVE_DIVERGED) k->hit_diverged++;
            if (!committed || (hits > 0 && v.rtp_seq != seq0)) one_command = 0;
            if (hits == 0) seq0 = v.rtp_seq;
            hits++;
            const int64_t z = v.mac[2] >> 12;
            rec.vz[i] = z > 0x7FFFFFFF ? 0x7FFFFFFF : (z < -0x7FFFFFFF ? -0x7FFFFFFF : (int32_t)z);
            rec.tag[i] = v.tag;
            rec.lane[i] = v.lane;
            rec.reason[i] = PGXP_VIEW_MISS_NONE;
        } else {
            if (why < 0 || why >= PGXP_VIEW_MISS_COUNT) why = PGXP_VIEW_MISS_NO_SHADOW;
            k->miss[why]++;
            rec.reason[i] = (uint8_t)why;
            one_command = 0;
        }
    }
    rec.hits = (uint8_t)hits;
    k->prims++;
    if (hits == n) {
        k->all_hit++;
        if (one_command) k->all_hit_one_command++;
    } else if (hits > 0) {
        k->partial++;
    } else {
        k->none++;
    }
    if (s_census_ring)
        s_census_ring[s_census_ring_seq & (PGXP_VIEW_CENSUS_RING - 1u)] = rec;
    s_census_ring_seq++;
}

extern "C" void pgxp_view_census_get(PgxpViewCensus *out) {
    if (!out) return;
    *out = s_census;
    out->enabled = s_census_on;
    out->ring_cap = s_census_ring ? PGXP_VIEW_CENSUS_RING : 0u;
    out->ring_total = s_census_ring_seq;
}

extern "C" int pgxp_view_census_recent(PgxpViewCensusPrim *out, int max) {
    if (!out || max <= 0 || !s_census_ring) return 0;
    uint64_t avail = s_census_ring_seq < PGXP_VIEW_CENSUS_RING
                         ? s_census_ring_seq : PGXP_VIEW_CENSUS_RING;
    int n = (uint64_t)max < avail ? max : (int)avail;
    for (int i = 0; i < n; i++)
        out[i] = s_census_ring[(s_census_ring_seq - 1u - (uint64_t)i) &
                               (PGXP_VIEW_CENSUS_RING - 1u)];
    return n;
}

extern "C" void pgxp_test_view_census_fail_ring_alloc(int count) {
    s_census_fail_ring = count;
}
'''

# --------------------------------------------------------------------------------------------------------------- gte.cpp
GTE_MAC_OLD = "            if (vw_dome) vf |= PGXP_VIEW_DOME;\n"
GTE_MAC_NEW = r'''            if (vw_dome) vf |= PGXP_VIEW_DOME;
            {
                /* v2: per-axis 44-bit accumulator overflow and 32-bit MAC
                 * register wrap (IR, and for axis 3 the >>12 SZ path, then
                 * came from a wrapped value). */
                const int64_t m44 = (int64_t)1 << 43;
                const int64_t i32_max = 0x7FFFFFFFll, i32_min = -0x80000000ll;
                const int64_t macs[3] = { mac1, mac2, mac3 };
                for (int a = 0; a < 3; a++) {
                    if (macs[a] >= m44 || macs[a] < -m44)
                        vf |= (uint16_t)(PGXP_VIEW_MAC1_OVF44 << a);
                    /* sf=1: this is also the SZ path (mac3 >> 12); sf=0: the
                     * unshifted value wraps whenever its >>12 view would. */
                    const int64_t r = macs[a] >> shift;
                    if (r > i32_max || r < i32_min)
                        vf |= (uint16_t)(PGXP_VIEW_MAC1_WRAP32 << a);
                }
            }
'''

# ----------------------------------------------------------------------------------------------------------------- gpu.c
GPU_EDITS = [
    ("static int s_texture_correction_enabled = 0;\n",
     "static int s_texture_correction_enabled = 0;\n"
     "/* remix-provenance v2: opt-in per-primitive view census. Arms the PGXP\n"
     " * transport for collection only; geometry/texture correction (and so every\n"
     " * draw) stay exactly as the user configured them. */\n"
     "static int s_view_census = 0;\n"),
    ("    pgxp_set_enabled(s_texture_correction_enabled ||\n"
     "                     gte_geometry_correction_enabled() ||\n"
     "                     ws_precise_nclip_cfg);\n",
     "    pgxp_set_enabled(s_texture_correction_enabled ||\n"
     "                     gte_geometry_correction_enabled() ||\n"
     "                     ws_precise_nclip_cfg ||\n"
     "                     s_view_census);\n"),
    ("int gpu_texture_correction_enabled(void) {\n    return s_texture_correction_enabled;\n}\n",
     "int gpu_texture_correction_enabled(void) {\n    return s_texture_correction_enabled;\n}\n"
     "\n"
     "/* Arm/disarm the view census. Allocation failure of the view payload fails\n"
     " * closed (census stays off). Disarming re-derives the transport from the\n"
     " * user's own geometry/texture/NCLIP modes, which are never changed here. */\n"
     "void gpu_view_census_set(int enabled) {\n"
     "    int want = enabled ? 1 : 0;\n"
     "    pgxp_set_view_payload(want);\n"
     "    if (want && !pgxp_view_payload()) want = 0;\n"
     "    s_view_census = want;\n"
     "    pgxp_view_census_set(want);\n"
     "    gpu_pgxp_rederive_enable();\n"
     "}\n"
     "\n"
     "int gpu_view_census_enabled(void) {\n    return s_view_census;\n}\n"),
    ("static void prepare_texture_triangle(int i0, int i1, int i2) {\n"
     "    gr_set_perspective_triangle(0, 0.0f, 0.0f, 0.0f);\n",
     "/* remix-provenance v2: one textured primitive's GP0 vertex words -> view\n"
     " * census (DATAFLOW only). Reads gp0 state; touches no renderer state. */\n"
     "static void view_census_gp0(int kind, const int *idx, int n) {\n"
     "    uint32_t words[4], addrs[4];\n"
     "    for (int i = 0; i < n; i++) {\n"
     "        words[i] = gp0_cmd_buf[idx[i]];\n"
     "        addrs[i] = (gp0_cmd_source_addr == 0xFFFFFFFFu)\n"
     "                       ? 0xFFFFFFFFu\n"
     "                       : gp0_cmd_source_addr + (uint32_t)idx[i] * 4u;\n"
     "    }\n"
     "    pgxp_view_census_prim(kind, words, addrs, n);\n"
     "}\n"
     "\n"
     "static void prepare_texture_triangle(int i0, int i1, int i2) {\n"
     "    if (s_view_census) {\n"
     "        const int ti[3] = { i0, i1, i2 };\n"
     "        view_census_gp0(PGXP_VIEW_CENSUS_TRI, ti, 3);\n"
     "    }\n"
     "    gr_set_perspective_triangle(0, 0.0f, 0.0f, 0.0f);\n"),
    ("    setup_textured_draw(color24, semi_trans, raw_texture);\n\n    if (vy[0] == vy[1] && vy[2] == vy[3] &&\n",
     "    setup_textured_draw(color24, semi_trans, raw_texture);\n"
     "    if (s_view_census) {                 /* before the rect fast path */\n"
     "        const int qi[4] = { 1, 3, 5, 7 };\n"
     "        view_census_gp0(PGXP_VIEW_CENSUS_QUAD, qi, 4);\n"
     "    }\n"
     "\n    if (vy[0] == vy[1] && vy[2] == vy[3] &&\n"),
    ("    gr_set_semi_transparency(semi_trans, (int)semi_transparency);\n"
     "    if (!rej_a) {\n"
     "        int32_t tx[3] = { vx[0], vx[1], vx[2] };\n"
     "        int32_t ty[3] = { vy[0], vy[1], vy[2] };\n"
     "        prepare_precise_triangle(1, 4, 7, tx, ty);\n",
     "    gr_set_semi_transparency(semi_trans, (int)semi_transparency);\n"
     "    if (s_view_census) {\n"
     "        const int qi[4] = { 1, 4, 7, 10 };\n"
     "        view_census_gp0(PGXP_VIEW_CENSUS_QUAD, qi, 4);\n"
     "    }\n"
     "    if (!rej_a) {\n"
     "        int32_t tx[3] = { vx[0], vx[1], vx[2] };\n"
     "        int32_t ty[3] = { vy[0], vy[1], vy[2] };\n"
     "        prepare_precise_triangle(1, 4, 7, tx, ty);\n"),
]

GPUH_EDITS = [
    ("void gpu_texture_correction_stats(uint64_t *attempts, uint64_t *armed,\n"
     "                                  uint64_t *no_correction,\n"
     "                                  uint64_t *no_source, uint64_t *no_depth);\n",
     "void gpu_texture_correction_stats(uint64_t *attempts, uint64_t *armed,\n"
     "                                  uint64_t *no_correction,\n"
     "                                  uint64_t *no_source, uint64_t *no_depth);\n"
     "/* remix-provenance v2 (private, default off): per-primitive 3D view census.\n"
     " * Arming enables the PGXP transport for collection without geometry or\n"
     " * texture correction; disarming restores the transport the user's modes\n"
     " * imply. Read it with the TCP verb pgxp_view. */\n"
     "void gpu_view_census_set(int enabled);\n"
     "int  gpu_view_census_enabled(void);\n"),
]

# --------------------------------------------------------------------------------------------------------- debug_server.c
TCP_HANDLER = r'''/* pgxp_view — opt-in 3D view-provenance census (remix-provenance v2, private).
 *   {"cmd":"pgxp_view"}               state + payload stats + per-primitive census
 *   {"cmd":"pgxp_view","census":1|0}  arm / disarm. Arming enables the PGXP
 *       transport for collection WITHOUT geometry or texture correction (draws
 *       unchanged); disarming re-derives it from the user's own modes.
 *   {"cmd":"pgxp_view","reset":1}     zero the census counters
 *   {"cmd":"pgxp_view","recent":N}    N (<= 64) newest primitive records
 * Free-running totals: sample twice and diff for a per-window rate. */
static void handle_pgxp_view(int id, const char *json)
{
    static const char *const kMiss[PGXP_VIEW_MISS_COUNT] = {
        "none", "no_source", "disabled", "no_shadow", "value_mismatch",
        "no_view", "evicted", "incoherent" };
    int census = json_get_int(json, "census", -1);
    if (census >= 0)
        gpu_view_census_set(census != 0);
    if (json_get_int(json, "reset", 0) != 0)
        pgxp_view_census_reset();
    int recent = json_get_int(json, "recent", 0);
    if (recent < 0) recent = 0;
    if (recent > 64) recent = 64;

    PgxpViewStats vs;
    pgxp_get_view_stats(&vs);
    PgxpViewCensus c;
    pgxp_view_census_get(&c);

    char buf[32768];
    int n = 0;
#define PV_APPEND(...)                                                         \
    do {                                                                       \
        if (n >= 0 && (size_t)n < sizeof(buf))                                 \
            n += snprintf(buf + n, sizeof(buf) - (size_t)n, __VA_ARGS__);      \
    } while (0)
    PV_APPEND("{\"id\":%d,\"ok\":true,\"census\":%d,\"view_payload\":%d,"
              "\"pgxp_enabled\":%d,\"geometry_correction\":%d,"
              "\"texture_correction\":%d,",
              id, gpu_view_census_enabled(), pgxp_view_payload(), pgxp_enabled(),
              gte_geometry_correction_enabled(), gpu_texture_correction_enabled());
    PV_APPEND("\"payload\":{\"produced\":%llu,\"records_overwritten\":%llu,"
              "\"commit_ok\":%llu,\"commit_mismatch\":%llu,\"lookups\":%llu,"
              "\"hits\":%llu,\"no_shadow\":%llu,\"no_source\":%llu,"
              "\"value_mismatch\":%llu,\"no_view\":%llu,\"evicted\":%llu,"
              "\"incoherent\":%llu,\"alloc_fail\":%llu,\"seq_wraps\":%llu,"
              "\"record_bytes\":%llu,\"alloc_bytes\":%llu},",
              (unsigned long long)vs.produced, (unsigned long long)vs.records_overwritten,
              (unsigned long long)vs.commit_ok, (unsigned long long)vs.commit_mismatch,
              (unsigned long long)vs.lookups, (unsigned long long)vs.hits,
              (unsigned long long)vs.no_shadow, (unsigned long long)vs.no_source,
              (unsigned long long)vs.value_mismatch, (unsigned long long)vs.no_view,
              (unsigned long long)vs.evicted, (unsigned long long)vs.incoherent,
              (unsigned long long)vs.alloc_fail, (unsigned long long)vs.seq_wraps,
              (unsigned long long)vs.record_bytes, (unsigned long long)vs.alloc_bytes);
    PV_APPEND("\"ring\":{\"cap\":%u,\"total\":%llu,\"alloc_fail\":%llu},",
              (unsigned)c.ring_cap, (unsigned long long)c.ring_total,
              (unsigned long long)c.ring_alloc_fail);
    for (int k = 0; k < 2; k++) {
        const PgxpViewCensusKind *q = &c.kind[k];
        PV_APPEND("\"%s\":{\"prims\":%llu,\"all_hit\":%llu,\"partial\":%llu,"
                  "\"none\":%llu,\"verts\":%llu,\"vert_hits\":%llu,"
                  "\"hit_committed\":%llu,\"hit_ring_live\":%llu,"
                  "\"hit_diverged\":%llu,\"all_hit_one_command\":%llu,\"miss\":{",
                  k == PGXP_VIEW_CENSUS_TRI ? "triangles" : "quads",
                  (unsigned long long)q->prims, (unsigned long long)q->all_hit,
                  (unsigned long long)q->partial, (unsigned long long)q->none,
                  (unsigned long long)q->verts, (unsigned long long)q->vert_hits,
                  (unsigned long long)q->hit_committed,
                  (unsigned long long)q->hit_ring_live,
                  (unsigned long long)q->hit_diverged,
                  (unsigned long long)q->all_hit_one_command);
        for (int r = 1; r < PGXP_VIEW_MISS_COUNT; r++)
            PV_APPEND("%s\"%s\":%llu", r == 1 ? "" : ",", kMiss[r],
                      (unsigned long long)q->miss[r]);
        PV_APPEND("}},");
    }
    PgxpViewCensusPrim rec[64];
    int got = pgxp_view_census_recent(rec, recent);
    PV_APPEND("\"recent\":[");
    for (int i = 0; i < got; i++) {
        const PgxpViewCensusPrim *p = &rec[i];
        PV_APPEND("%s{\"frame\":%u,\"kind\":\"%s\",\"hits\":%u,\"v\":[",
                  i == 0 ? "" : ",", (unsigned)p->frame,
                  p->kind == PGXP_VIEW_CENSUS_TRI ? "tri" : "quad", (unsigned)p->hits);
        for (int v = 0; v < p->nverts && v < 4; v++) {
            const int r = p->reason[v] < PGXP_VIEW_MISS_COUNT ? p->reason[v] : 0;
            PV_APPEND("%s{\"r\":\"%s\",\"lane\":%u,\"tag\":%u,\"vz\":%d}",
                      v == 0 ? "" : ",", kMiss[r], (unsigned)p->lane[v],
                      (unsigned)p->tag[v], (int)p->vz[v]);
        }
        PV_APPEND("]}");
    }
    PV_APPEND("]}");
#undef PV_APPEND
    if (n < 0 || (size_t)n >= sizeof(buf)) {
        send_err(id, "pgxp_view reply too large");
        return;
    }
    send_fmt("%s", buf);
}

'''

DBG_EDITS = [
    ("/* pgxp — live-tune the value-propagation engine for one-toggle isolation runs\n",
     TCP_HANDLER + "/* pgxp — live-tune the value-propagation engine for one-toggle isolation runs\n"),
    ("    { \"pgxp\",              handle_pgxp },\n",
     "    { \"pgxp\",              handle_pgxp },\n    { \"pgxp_view\",         handle_pgxp_view },\n"),
]


def split_consumer(text):
    a = text.index('extern "C" int pgxp_get_precise_vertex_view(uint32_t addr, uint32_t packet_word,\n')
    b = text.index('extern "C" void pgxp_get_view_stats(PgxpViewStats *out) {\n')
    if text.count('extern "C" int pgxp_get_precise_vertex_view(') != 1:
        raise SystemExit("v1 consumer anchor not unique")
    return text[:a] + CONSUMER_V2 + text[b:]


def main():
    v1 = load_v1()
    receipt = dict(v1_generator=dict(path=str(V1GEN), sha256=V1GEN_SHA), bases={}, outputs={},
                   generator_sha256=sha(Path(__file__).read_bytes()))
    raw, fmt, text = {}, {}, {}
    for rel, want in BASES.items():
        b = (RT / rel).read_bytes()
        if sha(b) != want:
            raise SystemExit(f"base {rel} changed ({sha(b)}); refusing")
        bom = b.startswith(b"\xef\xbb\xbf")
        s = b.decode("utf-8-sig" if bom else "utf-8")
        crlf = "\r\n" in s
        fmt[rel] = (bom, crlf)
        raw[rel] = s.replace("\r\n", "\n")
        receipt["bases"][rel] = dict(path=str(RT / rel), sha256=want, bom=bom, crlf=crlf)
    t = {}
    t["include/pgxp.h"] = v1.apply(raw["include/pgxp.h"], v1.HEADER_EDITS, "pgxp.h(v1)")
    t["include/pgxp.h"] = v1.apply(t["include/pgxp.h"], [(H_FLAGS_OLD, H_FLAGS_NEW), (H_STATS_OLD, H_STATS_NEW),
                                                         (H_API_OLD, H_API_NEW)], "pgxp.h(v2)")
    t["src/pgxp.cpp"] = split_consumer(v1.apply(raw["src/pgxp.cpp"], v1.PGXP_EDITS, "pgxp.cpp(v1)"))
    t["src/gte.cpp"] = v1.apply(v1.apply(raw["src/gte.cpp"], v1.GTE_EDITS, "gte.cpp(v1)"),
                                [(GTE_MAC_OLD, GTE_MAC_NEW)], "gte.cpp(v2)")
    t["src/gpu.c"] = v1.apply(raw["src/gpu.c"], GPU_EDITS, "gpu.c")
    t["include/gpu.h"] = v1.apply(raw["include/gpu.h"], GPUH_EDITS, "gpu.h")
    t["src/debug_server.c"] = v1.apply(raw["src/debug_server.c"], DBG_EDITS, "debug_server.c")
    (HERE / "diffs").mkdir(exist_ok=True)
    for rel, s in t.items():
        bom, crlf = fmt[rel]
        out = s.replace("\n", "\r\n") if crlf else s
        data = (b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8")
        p = HERE / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        d = "".join(difflib.unified_diff(raw[rel].splitlines(True), s.splitlines(True),
                                         f"a/windows-x64/psxrecomp/runtime/{rel}", f"b/windows-x64/psxrecomp/runtime/{rel}"))
        dp = HERE / "diffs" / (Path(rel).name + ".diff")
        dp.write_text(d, encoding="utf-8", newline="\n")
        receipt["outputs"][rel] = dict(path=str(p), sha256=sha(data), bom=bom, crlf=crlf,
                                       diff=dict(path=str(dp), sha256=sha(dp.read_bytes()), lines=d.count("\n")))
    p = HERE / "src/pgxp_view_census.cpp"
    p.write_bytes(CENSUS_TU.replace("\n", "\r\n").encode("utf-8"))
    receipt["outputs"]["src/pgxp_view_census.cpp"] = dict(path=str(p), sha256=sha(p.read_bytes()), new_file=True, crlf=True)
    (HERE / "patch-receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (v["sha256"][:16], v.get("diff", {}).get("lines")) for k, v in receipt["outputs"].items()}, indent=1))


if __name__ == "__main__":
    main()
