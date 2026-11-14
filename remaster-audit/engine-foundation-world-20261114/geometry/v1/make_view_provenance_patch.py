#!/usr/bin/env python3
"""Build the PRIVATE opt-in GTE view-provenance patch (remix-provenance v1, claude-einhander).
Source generation only: no compile, no game, canonical files are read and never written.

Bases (canonical runtime, hash-asserted): src/gte.cpp, src/pgxp.cpp, include/pgxp.h.
Outputs: impl/src/gte.cpp, impl/src/pgxp.cpp, impl/include/pgxp.h, diffs/*.diff, patch-receipt.json.

What it adds (default OFF; nothing allocated or recorded until pgxp_set_view_payload(1)):
  * pgxp.h: PgxpViewInput / PgxpView / PgxpViewStats, PGXP_VIEW_* flags, the producer pgxp_gte_push_sxy_view, the ring
    commit pgxp_view_commit_rtp, the consumer pgxp_get_precise_vertex_view (DATAFLOW only), stats and test accessors.
  * pgxp.cpp: flag PGXP_F_VW (tag rode along intact) inside the existing 16-bit flags (no PGXPValue size change);
    lazily allocated parallel 32-bit tag arrays + a 64K view-record ring; every shadow struct copy goes through pv_copy
    (copies the tag only while the flag is set); every place that drops VZ for a stale/half-written word drops VW too;
    non-identity arithmetic rebuilds flags from scratch (so VW is dropped there by construction).
  * gte.cpp: the RTPS/RTPT producer passes the raw int64 MAC1..3 (TR*4096 + RT*V, unshifted, no saturation), V, H/OFX/OFY,
    sf/lm, IR/SZ/DIV/XY saturation, XY transport clamp, widescreen squash and dome flags, the RTPT lane (V0/V1/V2) and the
    predicted GTE ring identity; gte_rtp_record (after execute) validates and commits it; ring liveness/xform accessors.
"""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RT = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime")
BASES = {"src/gte.cpp": "0563d9a1da49c6c0538c1285f803939c1a9441b5485a16a4d6f7eff6f50656c0",
         "src/pgxp.cpp": "b3a6dae3c4087c50f0d173de4df5f3db1cdbcced287bbc9a45b9146e2d023b66",
         "include/pgxp.h": "b9bacf319e33c3787fbea010035f16043da6226047c7e549b85a6c14b0ec0485"}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def apply(text, edits, name):
    for i, e in enumerate(edits):
        old, new = e[0], e[1]
        want = e[2] if len(e) > 2 else 1
        n = text.count(old)
        if n != want:
            raise SystemExit(f"{name} edit {i}: anchor found {n} times (need {want}):\n{old[:400]}")
        text = text.replace(old, new)
    return text


# ----------------------------------------------------------------------------------------------------------------------
HEADER_API = r'''/* --- opt-in 3D view provenance (remix-provenance v1, default OFF) ---------- */

/* Exact, unshifted GTE accumulators of one projected vertex: mac = TR*4096 +
 * RT*V with V the signed 16-bit model-space vertex and RT carrying 12
 * fraction bits, so mac / 2^PGXP_VIEW_MAC_FRAC_BITS is the view-space
 * coordinate in model units with NO rounding or saturation (int64 holds the
 * full 44-bit hardware range). PS1 folds camera and object into RT/TR, so this
 * is view space, not world space. */
#define PGXP_VIEW_MAC_FRAC_BITS 12

enum {
    PGXP_VIEW_SF            = 1u << 0,  /* instruction sf bit                     */
    PGXP_VIEW_LM            = 1u << 1,  /* instruction lm bit                     */
    PGXP_VIEW_IR_SAT        = 1u << 2,  /* IR1/IR2 clamped: native X/Y used a     *
                                         * saturated numerator                    */
    PGXP_VIEW_SZ_SAT        = 1u << 3,  /* mac3>>12 outside 0..0xFFFF: SZ3 clamped */
    PGXP_VIEW_DIV_OVF       = 1u << 4,  /* UNR divide overflow (2*SZ3 <= H)       */
    PGXP_VIEW_XY_SAT        = 1u << 5,  /* guest SX2/SY2 saturated (+-0x400)      */
    PGXP_VIEW_XY_CLAMP      = 1u << 6,  /* 16.16 shadow transport clamped (4096)  */
    PGXP_VIEW_WS_SQUASH     = 1u << 7,  /* widescreen X-squash changed screen X   */
    PGXP_VIEW_DOME          = 1u << 8,  /* diagnostic dome expansion on screen X  */
    PGXP_VIEW_RTP_COMMITTED = 1u << 9,  /* the GTE ring record of this command was *
                                         * written and matched (lane, V, xform)   */
};

/* Producer input (gte.cpp, once per projected vertex). */
typedef struct PgxpViewInput {
    int64_t  mac[3];       /* TR*4096 + RT*V, unshifted                          */
    uint64_t rtp_seq;      /* identity the GTE ring record of this command gets  */
    int32_t  ofx, ofy;     /* projection parameters in force                     */
    uint32_t xform_hash;   /* FNV-1a of RT, TR, H, OFX, OFY                      */
    uint32_t frame;
    int16_t  v[3];         /* model-space vertex V                               */
    uint16_t h;
    uint16_t flags;        /* PGXP_VIEW_* known at projection time               */
    uint8_t  lane;         /* RTPS 0; RTPT 0/1/2 = V0/V1/V2                      */
    uint8_t  cmd;          /* 0x01 RTPS, 0x30 RTPT                               */
} PgxpViewInput;

/* Consumer output. */
typedef struct PgxpView {
    int64_t  mac[3];
    uint64_t rtp_seq;      /* meaningful only with PGXP_VIEW_RTP_COMMITTED; the  *
                            * ring may still have overwritten it: check          *
                            * gte_rtp_ring_seq_live(rtp_seq)                     */
    int32_t  ofx, ofy;
    int32_t  x16, y16;     /* the shadow's sub-pixel screen position            */
    uint32_t packed;       /* the guest SXY word (== the validated packet word) */
    uint32_t xform_hash;
    uint32_t frame;
    uint32_t tag;
    int16_t  v[3];
    uint16_t h;
    uint16_t sz3;
    uint16_t flags;
    uint8_t  lane, cmd;
} PgxpView;

typedef struct PgxpViewStats {
    uint64_t produced;            /* view records written                        */
    uint64_t records_overwritten; /* ring slots reused (older tags evicted)      */
    uint64_t commit_ok;
    uint64_t commit_mismatch;     /* ring record did not match pending records   */
    uint64_t lookups;
    uint64_t hits;
    uint64_t no_shadow;           /* disabled / unknown address / no live shadow */
    uint64_t value_mismatch;      /* shadow word != packet word                  */
    uint64_t no_view;             /* live validated shadow without a view tag    */
    uint64_t evicted;             /* tag's ring record was reused                */
    uint64_t incoherent;          /* record does not describe this shadow        */
    uint64_t alloc_fail;
    uint64_t seq_wraps;
    uint64_t record_bytes;        /* sizeof one ring record (actual, this build) */
    uint64_t alloc_bytes;         /* bytes currently allocated for view storage  */
} PgxpViewStats;

/* Opt in/out. Enabling lazily allocates the RAM tag array and the record ring;
 * on allocation failure it stays disabled (fail closed). Any toggle drops all
 * shadows (pgxp_invalidate_all) so no tag can outlive the mode that wrote it.
 * Disabling keeps the allocation for a later re-enable. */
void pgxp_set_view_payload(int enabled);
int  pgxp_view_payload(void);

/* Same as pgxp_gte_push_sxy plus an optional view payload (view may be NULL).
 * pgxp_gte_push_sxy(...) == pgxp_gte_push_sxy_view(..., NULL). */
void pgxp_gte_push_sxy_view(int32_t x16, int32_t y16, uint16_t sz3,
                            uint32_t packed, const PgxpViewInput *view);

/* gte.cpp gte_rtp_record, after execute: validates the records produced by the
 * command against the ring record (seq, cmd, lane count, per-lane V, xform
 * hash) and marks them committed. Returns the number of lanes committed. */
int pgxp_view_commit_rtp(uint64_t seq, uint8_t cmd, const int16_t v[3][3],
                         uint32_t xform_hash);

/* View payload for one GP0 vertex word: DATAFLOW tier only (address-keyed
 * shadow validated against the actual word; never the position-cache
 * fallback), plus a coherence check of the record against the shadow. Returns
 * PGXP_SRC_DATAFLOW with *out filled, else PGXP_SRC_NATIVE. */
int pgxp_get_precise_vertex_view(uint32_t addr, uint32_t packet_word,
                                 PgxpView *out);

void pgxp_get_view_stats(PgxpViewStats *out);

/* test accessors (always compiled; trivial) */
void     pgxp_test_view_fail_next_alloc(int count);
uint64_t pgxp_test_view_alloc_bytes(void);
void     pgxp_test_view_set_seq(uint32_t next_tag);
/* Transport invariant probe: 1 iff the RAM/scratch shadow at addr is live and
 * still carries the view flag (independent of the consumer's checks). */
int      pgxp_test_view_flag(uint32_t addr);

'''

HEADER_EDITS = [
    ("/* --- observability -------------------------------------------------------- */\n",
     HEADER_API + "/* --- observability -------------------------------------------------------- */\n"),
]

# ----------------------------------------------------------------------------------------------------------------------
PGXP_STORAGE = r'''
/* ------------------------------------------------------------------------- */
/* Opt-in view provenance (remix-provenance v1) — default OFF                 */
/* ------------------------------------------------------------------------- */
/* A shadow carries a view payload iff PGXP_F_VW is set; the payload is the
 * ring record named by the slot's parallel 32-bit tag. Tags move with the
 * shadow (pv_copy) and are trusted only while VW survives every rule that
 * keeps VXY+VZ honest; the consumer additionally re-checks that the record
 * describes this very shadow (word, x16, y16, sz3) and has not been reused. */
struct PgxpViewRec {
    int64_t  mac[3];
    uint64_t rtp_seq;
    uint32_t tag;             /* 0 = empty                                      */
    uint32_t packed;
    int32_t  x16, y16;
    int32_t  ofx, ofy;
    uint32_t xform_hash;
    uint32_t frame;
    int16_t  v[3];
    uint16_t sz3;
    uint16_t h;
    uint16_t flags;
    uint8_t  lane, cmd;
};

#define PGXP_VIEW_RING_CAP (1u << 16)          /* power of two                 */

static uint32_t    *s_vtag_ram = nullptr;      /* lazily allocated, opt-in      */
static uint32_t     s_vtag_scratch[PGXP_SCRATCH_WORDS];
static uint32_t     s_vtag_gpr[34];
static uint32_t     s_vtag_gte[32];
static PgxpViewRec *s_view_ring = nullptr;     /* lazily allocated, opt-in      */
static int          s_view_on = 0;
static uint32_t     s_view_seq = 1;            /* next tag; 0 = wrapped         */
static uint32_t     s_view_pending[3];
static int          s_view_pending_n = 0;
static int          s_view_fail_allocs = 0;    /* test injection                */
static PgxpViewStats s_vstats;

/* Parallel tag slot of a shadow. Only called while s_view_on (so the RAM tag
 * array exists whenever a RAM shadow can exist). */
static inline uint32_t *vtag_of(const PGXPValue *p) {
    const uintptr_t a = (uintptr_t)p;
    if (a >= (uintptr_t)s_gpr && a < (uintptr_t)(s_gpr + 34))
        return &s_vtag_gpr[p - s_gpr];
    if (a >= (uintptr_t)s_gte && a < (uintptr_t)(s_gte + 32))
        return &s_vtag_gte[p - s_gte];
    if (a >= (uintptr_t)s_scratch && a < (uintptr_t)(s_scratch + PGXP_SCRATCH_WORDS))
        return &s_vtag_scratch[p - s_scratch];
    return &s_vtag_ram[p - s_ram];
}

/* Every whole-shadow copy goes through here: identity copies keep the view. */
static inline void pv_copy(PGXPValue *dst, const PGXPValue *src) {
    *dst = *src;
    if (dst->flags & PGXP_F_VW) {
        if (s_view_on) *vtag_of(dst) = *vtag_of(src);
        else dst->flags &= (uint16_t)~PGXP_F_VW;
    }
}
'''

PUSH_OLD = r'''extern "C" void pgxp_gte_push_sxy(int32_t x16, int32_t y16, uint16_t sz3,
                                  uint32_t packed) {
    if (!g_pgxp_active) return;
    s_stats.produced++;
    s_gte[12] = s_gte[13];
    s_gte[13] = s_gte[14];
    PGXPValue *pv = &s_gte[14];
    pv->x16 = x16;
    pv->y16 = y16;
    pv->z = sz3;
    pv->flags = (uint16_t)(PGXP_F_VXY | (sz3 != 0 ? PGXP_F_VZ : 0));
    pv->value = packed;
    pv->gen = s_gen;
    s_gte[15] = *pv;                           /* SXYP mirrors SXY2           */
}
'''

PUSH_NEW = r'''/* Restart the tag space after 2^32 tags: no old tag may alias a new one. */
static void view_restart(void) {
    pgxp_invalidate_all();
    for (uint32_t i = 0; i < PGXP_VIEW_RING_CAP; i++) s_view_ring[i].tag = 0;
    s_view_seq = 1;
    s_view_pending_n = 0;
    s_vstats.seq_wraps++;
}

static uint32_t view_record(const PgxpViewInput *in, int32_t x16, int32_t y16,
                            uint16_t sz3, uint32_t packed) {
    const uint32_t tag = s_view_seq++;
    PgxpViewRec *r = &s_view_ring[tag & (PGXP_VIEW_RING_CAP - 1u)];
    if (r->tag != 0) s_vstats.records_overwritten++;
    for (int i = 0; i < 3; i++) { r->mac[i] = in->mac[i]; r->v[i] = in->v[i]; }
    r->rtp_seq = in->rtp_seq;
    r->tag = tag;
    r->packed = packed;
    r->x16 = x16;
    r->y16 = y16;
    r->ofx = in->ofx;
    r->ofy = in->ofy;
    r->xform_hash = in->xform_hash;
    r->frame = in->frame;
    r->sz3 = sz3;
    r->h = in->h;
    r->flags = (uint16_t)(in->flags & ~PGXP_VIEW_RTP_COMMITTED);
    r->lane = in->lane;
    r->cmd = in->cmd;
    if (in->lane == 0) s_view_pending_n = 0;   /* a new command starts         */
    if (s_view_pending_n < 3) s_view_pending[s_view_pending_n++] = tag;
    s_vstats.produced++;
    return tag;
}

extern "C" void pgxp_gte_push_sxy_view(int32_t x16, int32_t y16, uint16_t sz3,
                                       uint32_t packed,
                                       const PgxpViewInput *view) {
    if (!g_pgxp_active) return;
    const int with_view = (view != nullptr) && s_view_on;
    if (with_view && s_view_seq == 0) view_restart();
    s_stats.produced++;
    pv_copy(&s_gte[12], &s_gte[13]);
    pv_copy(&s_gte[13], &s_gte[14]);
    PGXPValue *pv = &s_gte[14];
    pv->x16 = x16;
    pv->y16 = y16;
    pv->z = sz3;
    pv->flags = (uint16_t)(PGXP_F_VXY | (sz3 != 0 ? PGXP_F_VZ : 0));
    pv->value = packed;
    pv->gen = s_gen;
    if (with_view) {
        s_vtag_gte[14] = view_record(view, x16, y16, sz3, packed);
        pv->flags |= PGXP_F_VW;
    }
    pv_copy(&s_gte[15], pv);                   /* SXYP mirrors SXY2           */
}

extern "C" void pgxp_gte_push_sxy(int32_t x16, int32_t y16, uint16_t sz3,
                                  uint32_t packed) {
    pgxp_gte_push_sxy_view(x16, y16, sz3, packed, nullptr);
}

extern "C" int pgxp_view_commit_rtp(uint64_t seq, uint8_t cmd,
                                    const int16_t v[3][3], uint32_t xform_hash) {
    if (!s_view_on || s_suppress != 0) { s_view_pending_n = 0; return 0; }
    const int need = (cmd == 0x30) ? 3 : 1;
    int ok = (s_view_pending_n == need);
    for (int i = 0; ok && i < need; i++) {
        const uint32_t tag = s_view_pending[i];
        const PgxpViewRec *r = &s_view_ring[tag & (PGXP_VIEW_RING_CAP - 1u)];
        ok = r->tag == tag && r->rtp_seq == seq && r->cmd == cmd && r->lane == i &&
             r->xform_hash == xform_hash &&
             r->v[0] == v[i][0] && r->v[1] == v[i][1] && r->v[2] == v[i][2];
    }
    if (ok) {
        for (int i = 0; i < need; i++)
            s_view_ring[s_view_pending[i] & (PGXP_VIEW_RING_CAP - 1u)].flags |=
                PGXP_VIEW_RTP_COMMITTED;
        s_vstats.commit_ok++;
    } else {
        s_vstats.commit_mismatch++;
    }
    s_view_pending_n = 0;
    return ok ? need : 0;
}
'''

CONSUMER = r'''
/* ------------------------------------------------------------------------- */
/* View provenance: lifecycle + consumer                                      */
/* ------------------------------------------------------------------------- */

extern "C" void pgxp_set_view_payload(int enabled) {
    if (enabled && (!s_vtag_ram || !s_view_ring)) {
        if (s_view_fail_allocs > 0) {
            --s_view_fail_allocs;
            enabled = 0;
            s_vstats.alloc_fail++;
        } else {
            uint32_t *t = s_vtag_ram ? s_vtag_ram
                : (uint32_t *)std::calloc(PGXP_RAM_WORDS, sizeof(uint32_t));
            PgxpViewRec *r = s_view_ring ? s_view_ring
                : (PgxpViewRec *)std::calloc(PGXP_VIEW_RING_CAP, sizeof(PgxpViewRec));
            if (!t || !r) {                    /* fail closed: stay disabled   */
                if (t && t != s_vtag_ram) std::free(t);
                if (r && r != s_view_ring) std::free(r);
                enabled = 0;
                s_vstats.alloc_fail++;
            } else {
                s_vtag_ram = t;
                s_view_ring = r;
            }
        }
    }
    const int want = enabled ? 1 : 0;
    if (s_view_on == want) return;
    s_view_on = want;
    s_view_pending_n = 0;
    pgxp_invalidate_all();                     /* no tag outlives its mode     */
}

extern "C" int pgxp_view_payload(void) { return s_view_on; }

extern "C" int pgxp_get_precise_vertex_view(uint32_t addr, uint32_t packet_word,
                                            PgxpView *out) {
    s_vstats.lookups++;
    if (!s_enabled || !s_view_on || addr == 0xFFFFFFFFu) {
        s_vstats.no_shadow++;
        return PGXP_SRC_NATIVE;
    }
    const PGXPValue *pv = pgxp_ptr(addr);
    if (!pv || pv->gen != s_gen || (pv->flags & PGXP_F_VXY) != PGXP_F_VXY) {
        s_vstats.no_shadow++;
        return PGXP_SRC_NATIVE;
    }
    if (pv->value != packet_word) {
        s_vstats.value_mismatch++;
        return PGXP_SRC_NATIVE;
    }
    if (!(pv->flags & PGXP_F_VW)) {
        s_vstats.no_view++;
        return PGXP_SRC_NATIVE;
    }
    const uint32_t tag = *vtag_of(pv);
    const PgxpViewRec *r = &s_view_ring[tag & (PGXP_VIEW_RING_CAP - 1u)];
    if (tag == 0 || r->tag != tag) {
        s_vstats.evicted++;
        return PGXP_SRC_NATIVE;
    }
    if (r->packed != pv->value || r->x16 != pv->x16 || r->y16 != pv->y16 ||
        r->sz3 != pv->z) {
        s_vstats.incoherent++;
        return PGXP_SRC_NATIVE;
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
    return PGXP_SRC_DATAFLOW;
}

extern "C" void pgxp_get_view_stats(PgxpViewStats *out) {
    if (!out) return;
    *out = s_vstats;
    out->record_bytes = sizeof(PgxpViewRec);
    out->alloc_bytes = pgxp_test_view_alloc_bytes();
}

extern "C" void pgxp_test_view_fail_next_alloc(int count) { s_view_fail_allocs = count; }

extern "C" uint64_t pgxp_test_view_alloc_bytes(void) {
    return (s_vtag_ram ? (uint64_t)PGXP_RAM_WORDS * sizeof(uint32_t) : 0) +
           (s_view_ring ? (uint64_t)PGXP_VIEW_RING_CAP * sizeof(PgxpViewRec) : 0);
}

extern "C" void pgxp_test_view_set_seq(uint32_t next_tag) { s_view_seq = next_tag; }

extern "C" int pgxp_test_view_flag(uint32_t addr) {
    const PGXPValue *pv = pgxp_ptr(addr);
    return (pv && pv->gen == s_gen && (pv->flags & PGXP_F_VW)) ? 1 : 0;
}
'''

PGXP_EDITS = [
    ("    PGXP_F_VZ = 1u << 2,   /* projected depth rode along intact               */\n",
     "    PGXP_F_VZ = 1u << 2,   /* projected depth rode along intact               */\n"
     "    PGXP_F_VW = 1u << 3,   /* opt-in view-provenance tag rode along intact    */\n"),
    ("static PGXPStats s_stats;\n", "static PGXPStats s_stats;\n" + PGXP_STORAGE),
    # stale halves / partial writes drop the view exactly where they drop the depth
    ("        pv->flags &= (uint16_t)~(PGXP_F_VX | PGXP_F_VZ);\n",
     "        pv->flags &= (uint16_t)~(PGXP_F_VX | PGXP_F_VZ | PGXP_F_VW);\n"),
    ("        pv->flags &= (uint16_t)~(PGXP_F_VY | PGXP_F_VZ);\n",
     "        pv->flags &= (uint16_t)~(PGXP_F_VY | PGXP_F_VZ | PGXP_F_VW);\n"),
    ("        dst->flags &= (uint16_t)~((hi_half ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ);\n",
     "        dst->flags &= (uint16_t)~((hi_half ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ | PGXP_F_VW);\n"),
    ("        dst->flags &= (uint16_t)~(((addr & 2u) ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ);\n",
     "        dst->flags &= (uint16_t)~(((addr & 2u) ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ | PGXP_F_VW);\n"),
    # identity copies (LW, SW, LWC2, SWC2)
    ("            *dst = *src;\n", "            pv_copy(dst, src);\n", 4),
    ("                s_gpr[rt] = *src;\n", "                pv_copy(&s_gpr[rt], src);\n"),            # MFC2
    ("                pv_validate(&s_gpr[rt], value);\n                *dst = s_gpr[rt];\n",           # MTC2
     "                pv_validate(&s_gpr[rt], value);\n                pv_copy(dst, &s_gpr[rt]);\n"),
    ("                *hl = s_gpr[rs];\n", "                pv_copy(hl, &s_gpr[rs]);\n"),                # MTHI/MTLO
    ("                *dst = s_gpr[PGXP_REG_HI];\n", "                pv_copy(dst, &s_gpr[PGXP_REG_HI]);\n"),
    ("                *dst = s_gpr[PGXP_REG_LO];\n", "                pv_copy(dst, &s_gpr[PGXP_REG_LO]);\n"),
    ("                    pv_validate(&s_gpr[rs], result);\n                    *dst = s_gpr[rs];\n",     # op rd,rs,$0
     "                    pv_validate(&s_gpr[rs], result);\n                    pv_copy(dst, &s_gpr[rs]);\n"),
    ("                    pv_validate(&s_gpr[rt], result);\n                    *dst = s_gpr[rt];\n",     # op rd,$0,rt
     "                    pv_validate(&s_gpr[rt], result);\n                    pv_copy(dst, &s_gpr[rt]);\n"),
    ("                pv_validate(&s_gpr[rs], result);\n                *dst = s_gpr[rs];\n",             # addiu move
     "                pv_validate(&s_gpr[rs], result);\n                pv_copy(dst, &s_gpr[rs]);\n"),
    (PUSH_OLD, PUSH_NEW),
    ("    s_stats.swc2_stores++;\n    *dst = *src;\n", "    s_stats.swc2_stores++;\n    pv_copy(dst, src);\n"),
    ("extern \"C\" void pgxp_test_set_generation(uint32_t gen) { s_gen = gen; }\n",
     "extern \"C\" void pgxp_test_set_generation(uint32_t gen) { s_gen = gen; }\n" + CONSUMER),
]

# ----------------------------------------------------------------------------------------------------------------------
GTE_RING_HELPERS = r'''
/* remix-provenance v1: identity of the transform in force for one projection
 * (FNV-1a over RT, TR, H, OFX, OFY). Pins a view record to the ring record the
 * same command writes after execute. */
static uint32_t gte_view_xform_hash(const int16_t rt[3][3], const int32_t tr[3],
                                    uint16_t h, int32_t ofx, int32_t ofy) {
    uint32_t x = 2166136261u;
    auto mix = [&x](uint32_t w) {
        for (int i = 0; i < 4; i++) { x ^= (w >> (8 * i)) & 0xFFu; x *= 16777619u; }
    };
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++) mix((uint32_t)(uint16_t)rt[r][c]);
    for (int i = 0; i < 3; i++) mix((uint32_t)tr[i]);
    mix(h);
    mix((uint32_t)ofx);
    mix((uint32_t)ofy);
    return x;
}

/* 1 iff ring record `seq` was written and has not been overwritten since. The
 * ring only exists in builds with debug tools (gte_execute records it). */
extern "C" int gte_rtp_ring_seq_live(uint64_t seq) {
    if (!s_gte_rtp_ring || seq >= s_gte_rtp_seq) return 0;
    if (s_gte_rtp_seq - seq > GTE_RTP_RING_CAP) return 0;
    return s_gte_rtp_ring[seq % GTE_RTP_RING_CAP].seq == (uint32_t)seq;
}

/* Model transform of a live ring record (row-major RT); 0 if not live. */
extern "C" int gte_rtp_ring_get_xform(uint64_t seq, int16_t rt[9], int32_t tr[3],
                                      uint32_t *frame, uint32_t *caller_ra) {
    if (!gte_rtp_ring_seq_live(seq)) return 0;
    const GteRtpRec *e = &s_gte_rtp_ring[seq % GTE_RTP_RING_CAP];
    for (int i = 0; i < 9; i++) rt[i] = e->RT[i];
    for (int i = 0; i < 3; i++) tr[i] = e->TR[i];
    if (frame) *frame = e->frame;
    if (caller_ra) *caller_ra = e->caller_ra;
    return 1;
}
'''

GTE_PRODUCER_OLD = r'''        pgxp_gte_push_sxy((int32_t)cx16, (int32_t)cy16, gte->SZ[3],
                          (uint32_t)gte->SXY[2]);
    }
'''

GTE_PRODUCER_NEW = r'''        if (pgxp_view_payload()) {
            /* remix-provenance v1: exact unshifted accumulators + the facts
             * needed to know when native X/Y did not follow them. */
            PgxpViewInput vin;
            vin.mac[0] = mac1;
            vin.mac[1] = mac2;
            vin.mac[2] = mac3;
            vin.v[0] = V[0];
            vin.v[1] = V[1];
            vin.v[2] = V[2];
            vin.h = gte->H;
            vin.ofx = gte->OFX;
            vin.ofy = gte->OFY;
            uint16_t vf = 0;
            if (shift) vf |= PGXP_VIEW_SF;
            if (lm) vf |= PGXP_VIEW_LM;
            if (vw_ir_sat) vf |= PGXP_VIEW_IR_SAT;
            if (vw_sz_sat) vf |= PGXP_VIEW_SZ_SAT;
            if ((uint32_t)gte->SZ[3] * 2 <= (uint32_t)gte->H) vf |= PGXP_VIEW_DIV_OVF;
            if (sx < -0x400 || sx > 0x3FF || sy < -0x400 || sy > 0x3FF)
                vf |= PGXP_VIEW_XY_SAT;
            if (cx16 != sx16 || cy16 != sy16) vf |= PGXP_VIEW_XY_CLAMP;
            if (do_squash) vf |= PGXP_VIEW_WS_SQUASH;
            if (vw_dome) vf |= PGXP_VIEW_DOME;
            vin.flags = vf;
            vin.lane = (V == gte->V0) ? 0 : (V == gte->V1) ? 1 : 2;
            vin.cmd = (uint8_t)(instr & 0x3Fu);
            vin.rtp_seq = s_gte_rtp_seq;   /* the record this command writes  */
            vin.xform_hash = gte_view_xform_hash(gte->RT, gte->TR, gte->H,
                                                 gte->OFX, gte->OFY);
            vin.frame = (uint32_t)s_frame_count;
            pgxp_gte_push_sxy_view((int32_t)cx16, (int32_t)cy16, gte->SZ[3],
                                   (uint32_t)gte->SXY[2], &vin);
        } else {
            pgxp_gte_push_sxy((int32_t)cx16, (int32_t)cy16, gte->SZ[3],
                              (uint32_t)gte->SXY[2]);
        }
    }
'''

GTE_EDITS = [
    ("#define GTE_RTP_RING_CAP (1u << 18)   /* 256K raw entries (~a few seconds) */\n"
     "static GteRtpRec* s_gte_rtp_ring = nullptr;\nstatic uint64_t   s_gte_rtp_seq  = 0;\n",
     "#define GTE_RTP_RING_CAP (1u << 18)   /* 256K raw entries (~a few seconds) */\n"
     "static GteRtpRec* s_gte_rtp_ring = nullptr;\nstatic uint64_t   s_gte_rtp_seq  = 0;\n" + GTE_RING_HELPERS),
    ("    e->FLAG=g->FLAG;\n    s_gte_rtp_seq++;\n",
     "    e->FLAG=g->FLAG;\n"
     "    if (pgxp_view_payload()) {\n"
     "        const int16_t vv[3][3] = {{g->V0[0], g->V0[1], g->V0[2]},\n"
     "                                  {g->V1[0], g->V1[1], g->V1[2]},\n"
     "                                  {g->V2[0], g->V2[1], g->V2[2]}};\n"
     "        pgxp_view_commit_rtp(s_gte_rtp_seq, (uint8_t)(cmd & 0x3Fu), vv,\n"
     "                             gte_view_xform_hash(g->RT, g->TR, g->H, g->OFX, g->OFY));\n"
     "    }\n"
     "    s_gte_rtp_seq++;\n"),
    ("    gte->IR1 = gte->saturate_ir(gte->MAC1, 1, lm);\n    gte->IR2 = gte->saturate_ir(gte->MAC2, 2, lm);\n"
     "    // IR3 quirk",
     "    /* remix-provenance v1: read-only observations of the same values. */\n"
     "    const int32_t vw_ir_lo = lm ? 0 : -0x8000;\n"
     "    const bool vw_ir_sat = gte->MAC1 < vw_ir_lo || gte->MAC1 > 0x7FFF ||\n"
     "                           gte->MAC2 < vw_ir_lo || gte->MAC2 > 0x7FFF;\n"
     "    const int32_t vw_z12 = static_cast<int32_t>(mac3 >> 12);\n"
     "    const bool vw_sz_sat = vw_z12 < 0 || vw_z12 > 0xFFFF;\n"
     "    bool vw_dome = false;\n"
     "    gte->IR1 = gte->saturate_ir(gte->MAC1, 1, lm);\n    gte->IR2 = gte->saturate_ir(gte->MAC2, 2, lm);\n"
     "    // IR3 quirk"),
    ("        if (sz >= s_ws_far_threshold) {\n            xterm = xterm * s_ws_dome_num / s_ws_dome_den;\n",
     "        if (sz >= s_ws_far_threshold) {\n            xterm = xterm * s_ws_dome_num / s_ws_dome_den;\n"
     "            vw_dome = true;\n"),
    (GTE_PRODUCER_OLD, GTE_PRODUCER_NEW),
]


def main():
    out = {}
    receipt = dict(bases={}, outputs={}, generator_sha256=sha(Path(__file__).read_bytes()))
    for rel, want in BASES.items():
        raw = (RT / rel).read_bytes()
        got = sha(raw)
        if got != want:
            raise SystemExit(f"base {rel} sha256 {got} != expected {want} (canonical changed; re-review before patching)")
        receipt["bases"][rel] = dict(path=str(RT / rel), sha256=got, crlf=b"\r\n" in raw)
        out[rel] = raw.decode("utf-8").replace("\r\n", "\n")
    new = {"include/pgxp.h": apply(out["include/pgxp.h"], HEADER_EDITS, "pgxp.h"),
           "src/pgxp.cpp": apply(out["src/pgxp.cpp"], PGXP_EDITS, "pgxp.cpp"),
           "src/gte.cpp": apply(out["src/gte.cpp"], GTE_EDITS, "gte.cpp")}
    # every whole-struct shadow copy must now go through pv_copy (except inside pv_copy itself)
    leftovers = [ln for ln in new["src/pgxp.cpp"].splitlines()
                 if ("= *src;" in ln or "= s_gpr[" in ln or "= s_gte[" in ln or "= *pv;" in ln) and "pv_copy" not in ln
                 and "*dst = *src;" != ln.strip()]
    if leftovers:
        raise SystemExit("unconverted shadow copies:\n" + "\n".join(leftovers))
    (HERE / "diffs").mkdir(exist_ok=True)
    for rel, text in new.items():
        p = HERE / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        receipt["outputs"][rel] = dict(path=str(p), sha256=sha(p.read_bytes()))
        d = "".join(difflib.unified_diff(out[rel].splitlines(True), text.splitlines(True),
                                         f"a/windows-x64/psxrecomp/runtime/{rel}", f"b/windows-x64/psxrecomp/runtime/{rel}"))
        dp = HERE / "diffs" / (Path(rel).name + ".diff")
        dp.write_text(d, encoding="utf-8", newline="\n")
        receipt["outputs"][rel]["diff"] = dict(path=str(dp), sha256=sha(dp.read_bytes()))
    (HERE / "patch-receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=1))


if __name__ == "__main__":
    main()
