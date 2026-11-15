/* pgxp.cpp — PGXP value-propagation engine (ENHANCEMENTS.md G1.2/G1.3).
 *
 * CLEAN-ROOM implementation of the publicly documented PGXP technique
 * (psx-spx GTE docs + public design write-ups + our own G1 measurements).
 * The vendored duckstation/ (CC BY-NC-ND) and beetle-psx/ (GPL) trees are
 * black-box behavioral oracles only — no code from them appears here.
 *
 * Model
 * -----
 * Every 32-bit word of guest RAM/scratchpad, every GPR (plus HI/LO), and
 * every GTE data register owns a shadow slot recording the sub-pixel screen
 * position that word carries (16.16 X/Y + projected SZ depth), the exact
 * guest word it describes (`value`), and per-half validity flags. RTPS/RTPT
 * fill the SXY shadow FIFO with the pre-truncation projection; the
 * psx_pgxp_* hooks copy shadows along with the data (loads, stores, COP2
 * transfers, and — in cpu-mode — the arithmetic games use to repack vertex
 * halves); the GPU asks for the precise position of a GP0 vertex word by the
 * packet's RAM address.
 *
 * The single safety invariant: a shadow is only ever BELIEVED after
 * validation against the actual guest word it claims to describe. Anything
 * that writes guest state without a hook (DMA, memcpy loaders, un-hooked
 * instructions) simply leaves a stale shadow behind, and the next validation
 * drops it. We never model side effects — overwrite and validate only. The
 * one accepted hole (shared with the reference implementations): an untracked
 * writer storing the byte-identical word keeps the shadow alive, which is
 * harmless because the position it describes is still that word.
 *
 * Everything here is host-only and visual-only: guest-visible state is never
 * read back from shadows, shadows are dropped on savestate/rewind, and the
 * speculative native-validation bracket suppresses all recording.
 */

#include "pgxp.h"
#include "pgxp_hooks.h"
#include "cpu_state.h"

#include <cstdlib>
#include <cstring>

/* gte.cpp — position-cache fallback tier (ambiguity-gated, G1.4 exact table) */
extern "C" int gte_geometry_correction_lookup(uint32_t packed,
                                              int32_t *x16, int32_t *y16);

/* ------------------------------------------------------------------------- */
/* Shadow storage                                                             */
/* ------------------------------------------------------------------------- */

enum {
    PGXP_F_VX = 1u << 0,   /* low half  (screen X) tracked                    */
    PGXP_F_VY = 1u << 1,   /* high half (screen Y) tracked                    */
    PGXP_F_VZ = 1u << 2,   /* projected depth rode along intact               */
    PGXP_F_VW = 1u << 3,   /* opt-in view-provenance tag rode along intact    */
    PGXP_F_VXY = PGXP_F_VX | PGXP_F_VY,
};

struct PGXPValue {
    int32_t  x16, y16;   /* sub-pixel screen coords, 16.16                    */
    uint16_t z;          /* projected SZ depth (perspective source), 0 = none */
    uint16_t flags;
    uint32_t value;      /* the guest word this shadow describes              */
    uint32_t gen;        /* valid iff == s_gen (O(1) invalidate-all)          */
};

#define PGXP_RAM_WORDS     (0x200000u >> 2)   /* 2 MB RAM                     */
#define PGXP_SCRATCH_WORDS (0x400u >> 2)      /* 1 KB scratchpad              */
#define PGXP_REG_HI        32
#define PGXP_REG_LO        33

static PGXPValue *s_ram = nullptr;            /* lazily allocated, ~10 MB     */
static PGXPValue  s_scratch[PGXP_SCRATCH_WORDS];
static PGXPValue  s_gpr[34];                  /* 32 GPRs + HI + LO            */
static PGXPValue  s_gte[32];                  /* GTE data registers           */

static uint32_t s_gen = 1;
static int      s_enabled = 0;
static int      s_cpu_mode = 0;
static float    s_tolerance = 0.5f;   /* user-validated seam clamp (G1.10) */
static uint32_t s_suppress = 0;
static int      s_deferred_invalidate = 0;

/* Single hot-path gate for every hook. */
static int g_pgxp_active = 0;
static inline void recompute_active(void) {
    g_pgxp_active = (s_enabled && s_suppress == 0) ? 1 : 0;
}

static PGXPStats s_stats;

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

/* ------------------------------------------------------------------------- */
/* Lifecycle                                                                  */
/* ------------------------------------------------------------------------- */

extern "C" void pgxp_invalidate_all(void) {
    if (s_suppress != 0) { s_deferred_invalidate = 1; return; }
    if (++s_gen == 0) {
        /* generation wrapped: physically clear so stale slots can't revive */
        if (s_ram) std::memset(s_ram, 0, PGXP_RAM_WORDS * sizeof(PGXPValue));
        std::memset(s_scratch, 0, sizeof(s_scratch));
        std::memset(s_gpr, 0, sizeof(s_gpr));
        std::memset(s_gte, 0, sizeof(s_gte));
        s_gen = 1;
    }
}

extern "C" void pgxp_set_enabled(int enabled) {
    int resized = 0;
    if (enabled && !s_ram) {
        s_ram = (PGXPValue *)std::calloc(PGXP_RAM_WORDS, sizeof(PGXPValue));
        if (s_ram)
            resized = 1;
        else
            enabled = 0;                      /* fail closed: stay faithful   */
    }
    /* Re-applying configuration must not invalidate every live shadow. */
    if (s_enabled == (enabled ? 1 : 0) && !resized)
        return;
    s_enabled = enabled ? 1 : 0;
    pgxp_invalidate_all();
    recompute_active();
}

extern "C" int pgxp_enabled(void) { return s_enabled; }

extern "C" void pgxp_set_cpu_mode(int enabled) { s_cpu_mode = enabled ? 1 : 0; }
extern "C" int  pgxp_cpu_mode(void) { return s_cpu_mode; }

extern "C" void  pgxp_set_tolerance(float pixels) { s_tolerance = pixels; }
extern "C" float pgxp_tolerance(void) { return s_tolerance; }

extern "C" void pgxp_suppress_begin(void) {
    ++s_suppress;
    recompute_active();
}

extern "C" void pgxp_suppress_end(void) {
    if (s_suppress != 0 && --s_suppress == 0) {
        if (s_deferred_invalidate) {
            s_deferred_invalidate = 0;
            pgxp_invalidate_all();
        }
        recompute_active();
    }
}

extern "C" void pgxp_get_stats(PGXPStats *out) {
    if (out) *out = s_stats;
}

/* ------------------------------------------------------------------------- */
/* Address mapping + validation                                               */
/* ------------------------------------------------------------------------- */

/* Guest address -> shadow slot, or NULL for BIOS/MMIO/KSEG2 (untrackable). */
static inline PGXPValue *pgxp_ptr(uint32_t addr) {
    uint32_t m = addr & 0x1FFFFFFFu;
    if (m < 0x00800000u)                       /* RAM + its mirrors           */
        return s_ram ? &s_ram[(m & 0x1FFFFCu) >> 2] : nullptr;
    if ((m & 0xFFFFFC00u) == 0x1F800000u)      /* scratchpad                  */
        return &s_scratch[(m & 0x3FCu) >> 2];
    return nullptr;
}

static inline int pv_live(const PGXPValue *pv) {
    return pv && pv->gen == s_gen && (pv->flags & PGXP_F_VXY) != 0;
}

/* Drop whichever tracked halves no longer match the actual guest word; the
 * depth belongs to the whole vertex, so any half going stale kills it too. */
static inline void pv_validate(PGXPValue *pv, uint32_t actual) {
    if (pv->gen != s_gen) return;
    uint32_t diff = pv->value ^ actual;
    if ((pv->flags & PGXP_F_VX) && (diff & 0x0000FFFFu))
        pv->flags &= (uint16_t)~(PGXP_F_VX | PGXP_F_VZ | PGXP_F_VW);
    if ((pv->flags & PGXP_F_VY) && (diff & 0xFFFF0000u))
        pv->flags &= (uint16_t)~(PGXP_F_VY | PGXP_F_VZ | PGXP_F_VW);
    pv->value = actual;
}

/* Mark a slot as "known word, no precision" — keeps `value` current so later
 * half-merges stay keyed correctly. */
static inline void pv_reset(PGXPValue *pv, uint32_t value) {
    pv->x16 = 0; pv->y16 = 0; pv->z = 0;
    pv->flags = 0;
    pv->value = value;
    pv->gen = s_gen;
}

static inline void pv_kill(PGXPValue *pv) { pv->gen = 0; }

/* ------------------------------------------------------------------------- */
/* Instruction field helpers                                                  */
/* ------------------------------------------------------------------------- */

static inline uint32_t f_op(uint32_t i)    { return i >> 26; }
static inline uint32_t f_rs(uint32_t i)    { return (i >> 21) & 31u; }
static inline uint32_t f_rt(uint32_t i)    { return (i >> 16) & 31u; }
static inline uint32_t f_rd(uint32_t i)    { return (i >> 11) & 31u; }
static inline uint32_t f_shamt(uint32_t i) { return (i >> 6) & 31u; }
static inline uint32_t f_funct(uint32_t i) { return i & 63u; }
static inline int32_t  f_simm(uint32_t i)  { return (int32_t)(int16_t)(i & 0xFFFFu); }

/* ------------------------------------------------------------------------- */
/* Memory-mode hooks: loads / stores                                          */
/* ------------------------------------------------------------------------- */

extern "C" void psx_pgxp_load(struct CPUState *cpu, uint32_t instr,
                              uint32_t addr, uint32_t value) {
    (void)cpu;
    if (!g_pgxp_active) return;
    uint32_t rt = f_rt(instr);
    if (rt == 0) return;
    PGXPValue *dst = &s_gpr[rt];

    switch (f_op(instr)) {
    case 0x23: {                               /* LW                          */
        PGXPValue *src = pgxp_ptr(addr);
        if (src && src->gen == s_gen) {
            pv_validate(src, value);
            pv_copy(dst, src);
        } else {
            pv_reset(dst, value);
        }
        return;
    }
    case 0x21:                                 /* LH                          */
    case 0x25: {                               /* LHU                         */
        PGXPValue *src = pgxp_ptr(addr);
        int hi_half = (addr >> 1) & 1;
        pv_reset(dst, value);
        /* The high half of the extended GPR is a known-exact constant
         * (0/-1 for LH, 0 for LHU): track it so re-packing via sll/or in
         * cpu-mode keeps working. */
        dst->y16 = ((int32_t)value >> 16) << 16;
        dst->flags = PGXP_F_VY;
        if (src && src->gen == s_gen) {
            uint32_t actual_half = (value & 0xFFFFu) << (hi_half ? 16 : 0);
            uint32_t mask = hi_half ? 0xFFFF0000u : 0x0000FFFFu;
            uint16_t want = hi_half ? PGXP_F_VY : PGXP_F_VX;
            if ((src->flags & want) && ((src->value ^ actual_half) & mask) == 0) {
                dst->x16 = hi_half ? src->y16 : src->x16;
                dst->flags |= PGXP_F_VX;
            }
        }
        return;
    }
    default:                                   /* LB/LBU/LWL/LWR: untrackable */
        pv_reset(dst, value);
        return;
    }
}

extern "C" void psx_pgxp_store(struct CPUState *cpu, uint32_t instr,
                               uint32_t addr, uint32_t value) {
    (void)cpu;
    if (!g_pgxp_active) return;
    PGXPValue *dst = pgxp_ptr(addr);
    if (!dst) return;
    uint32_t rt = f_rt(instr);
    PGXPValue *src = (rt != 0) ? &s_gpr[rt] : nullptr;

    switch (f_op(instr)) {
    case 0x2B: {                               /* SW                          */
        if (src && src->gen == s_gen) {
            pv_validate(src, value);
            pv_copy(dst, src);
        } else {
            pv_reset(dst, value);
        }
        return;
    }
    case 0x29: {                               /* SH                          */
        int hi_half = (addr >> 1) & 1;
        uint32_t half = value & 0xFFFFu;
        if (dst->gen != s_gen) pv_reset(dst, half << (hi_half ? 16 : 0));
        /* Patch the stored half into the tracked word; the other half's
         * validity (if any) survives untouched. Depth never survives a
         * half-write — the vertex it described no longer exists whole. */
        if (hi_half) dst->value = (dst->value & 0x0000FFFFu) | (half << 16);
        else         dst->value = (dst->value & 0xFFFF0000u) | half;
        dst->flags &= (uint16_t)~((hi_half ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ | PGXP_F_VW);
        dst->z = 0;
        if (src && src->gen == s_gen && (src->flags & PGXP_F_VX) &&
            ((src->value ^ value) & 0xFFFFu) == 0) {
            if (hi_half) { dst->y16 = src->x16; dst->flags |= PGXP_F_VY; }
            else         { dst->x16 = src->x16; dst->flags |= PGXP_F_VX; }
        }
        return;
    }
    case 0x28: {                               /* SB                          */
        if (dst->gen != s_gen) return;         /* nothing tracked: stay dead  */
        uint32_t shift = (addr & 3u) * 8u;
        dst->value = (dst->value & ~(0xFFu << shift)) |
                     ((value & 0xFFu) << shift);
        dst->flags &= (uint16_t)~(((addr & 2u) ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ | PGXP_F_VW);
        dst->z = 0;
        return;
    }
    default:                                   /* SWL/SWR: forget the word    */
        pv_kill(dst);
        return;
    }
}

/* ------------------------------------------------------------------------- */
/* Memory-mode hooks: COP2 transfers                                          */
/* ------------------------------------------------------------------------- */

extern "C" void psx_pgxp_cop2(struct CPUState *cpu, uint32_t instr,
                              uint32_t value, uint32_t addr) {
    (void)cpu;
    if (!g_pgxp_active) return;

    switch (f_op(instr)) {
    case 0x32: {                               /* LWC2: gte[rt] <- [addr]     */
        PGXPValue *src = pgxp_ptr(addr);
        PGXPValue *dst = &s_gte[f_rt(instr)];
        if (src && src->gen == s_gen) {
            pv_validate(src, value);
            pv_copy(dst, src);
        } else {
            pv_reset(dst, value);
        }
        return;
    }
    case 0x3A: {                               /* SWC2: [addr] <- gte[rt]     */
        PGXPValue *dst = pgxp_ptr(addr);
        if (!dst) return;
        PGXPValue *src = &s_gte[f_rt(instr)];
        if (src->gen == s_gen) {
            pv_validate(src, value);
            pv_copy(dst, src);
        } else {
            pv_reset(dst, value);
        }
        return;
    }
    case 0x12: {                               /* COP2 register transfers     */
        switch (f_rs(instr)) {
        case 0x00: {                           /* MFC2: gpr[rt] <- gte[rd]    */
            uint32_t rt = f_rt(instr);
            if (rt == 0) return;
            PGXPValue *src = &s_gte[f_rd(instr)];
            if (src->gen == s_gen) {
                pv_validate(src, value);
                pv_copy(&s_gpr[rt], src);
            } else {
                pv_reset(&s_gpr[rt], value);
            }
            return;
        }
        case 0x04: {                           /* MTC2: gte[rd] <- gpr[rt]    */
            uint32_t rt = f_rt(instr);
            PGXPValue *dst = &s_gte[f_rd(instr)];
            if (rt != 0 && s_gpr[rt].gen == s_gen) {
                pv_validate(&s_gpr[rt], value);
                pv_copy(dst, &s_gpr[rt]);
            } else {
                pv_reset(dst, value);
            }
            /* An SXYP write (rd==15) shifts the hardware FIFO; we do not
             * model it — regs 12..14 now describe words they no longer
             * match, and validation drops them on next use. */
            return;
        }
        case 0x02: {                           /* CFC2: control regs carry no
                                                  positions                   */
            uint32_t rt = f_rt(instr);
            if (rt != 0) pv_reset(&s_gpr[rt], value);
            return;
        }
        default:                               /* CTC2: nothing shadowed      */
            return;
        }
    }
    default:
        return;
    }
}

/* ------------------------------------------------------------------------- */
/* CPU-mode hooks: arithmetic (tier 2, default off)                           */
/* ------------------------------------------------------------------------- */

/* One 16-bit operand component in 16.16: a tracked half contributes its
 * sub-pixel value; an untracked half contributes its exact integer value
 * (adding an exact offset to a tracked coordinate keeps the fraction). */
static inline int32_t comp16(const PGXPValue *pv, uint32_t value, int hi_half) {
    if (pv && pv->gen == s_gen) {
        if (!hi_half && (pv->flags & PGXP_F_VX) &&
            ((pv->value ^ value) & 0x0000FFFFu) == 0)
            return pv->x16;
        if (hi_half && (pv->flags & PGXP_F_VY) &&
            ((pv->value ^ value) & 0xFFFF0000u) == 0)
            return pv->y16;
    }
    return ((int32_t)(int16_t)(hi_half ? (value >> 16) : value)) << 16;
}

static inline int comp_tracked(const PGXPValue *pv, uint32_t value, int hi_half) {
    if (!pv || pv->gen != s_gen) return 0;
    if (!hi_half)
        return (pv->flags & PGXP_F_VX) &&
               ((pv->value ^ value) & 0x0000FFFFu) == 0;
    return (pv->flags & PGXP_F_VY) &&
           ((pv->value ^ value) & 0xFFFF0000u) == 0;
}

/* Half-wise add/sub is only meaningful when the guest result shows no carry
 * crossed the half boundary; otherwise the halves did not combine
 * independently and the shadow must not pretend they did. */
static inline int halves_independent(uint32_t a, uint32_t b, uint32_t r, int sub) {
    uint32_t lo = sub ? ((a & 0xFFFFu) - (b & 0xFFFFu))
                      : ((a & 0xFFFFu) + (b & 0xFFFFu));
    return ((lo ^ r) & 0xFFFFu) == 0 &&
           ((((sub ? a - b : a + b)) ^ r) == 0) &&
           ((lo >> 16) == 0);                  /* no carry/borrow out of low  */
}

extern "C" void psx_pgxp_alu(struct CPUState *cpu, uint32_t instr,
                             uint32_t result, uint32_t s1, uint32_t s2) {
    (void)cpu;
    if (!g_pgxp_active) return;

    uint32_t op = f_op(instr);
    uint32_t dst_reg;
    PGXPValue *a = nullptr, *b = nullptr;      /* source shadows (may be 0)   */

    if (op == 0) {                             /* SPECIAL                     */
        dst_reg = f_rd(instr);
        uint32_t rs = f_rs(instr), rt = f_rt(instr);
        uint32_t funct = f_funct(instr);
        if (funct == 0x11 || funct == 0x13) {  /* MTHI / MTLO                 */
            PGXPValue *hl = &s_gpr[funct == 0x11 ? PGXP_REG_HI : PGXP_REG_LO];
            if (s_cpu_mode && rs != 0 && s_gpr[rs].gen == s_gen) {
                pv_validate(&s_gpr[rs], result);
                pv_copy(hl, &s_gpr[rs]);
            } else pv_reset(hl, result);
            return;
        }
        if (dst_reg == 0) return;
        PGXPValue *dst = &s_gpr[dst_reg];

        switch (funct) {
        case 0x10:                             /* MFHI                        */
            if (s_cpu_mode && s_gpr[PGXP_REG_HI].gen == s_gen) {
                pv_validate(&s_gpr[PGXP_REG_HI], result);
                pv_copy(dst, &s_gpr[PGXP_REG_HI]);
            } else pv_reset(dst, result);
            return;
        case 0x12:                             /* MFLO                        */
            if (s_cpu_mode && s_gpr[PGXP_REG_LO].gen == s_gen) {
                pv_validate(&s_gpr[PGXP_REG_LO], result);
                pv_copy(dst, &s_gpr[PGXP_REG_LO]);
            } else pv_reset(dst, result);
            return;
        case 0x00: case 0x02: case 0x03:       /* SLL / SRL / SRA             */
        case 0x04: case 0x06: case 0x07: {     /* SLLV / SRLV / SRAV          */
            uint32_t sh = (funct < 4) ? f_shamt(instr) : (s2 & 31u);
            uint32_t src_reg = rt;
            PGXPValue *src = (src_reg != 0) ? &s_gpr[src_reg] : nullptr;
            int right = (funct & 3u) != 0;
            if (!s_cpu_mode || sh != 16 || !src || src->gen != s_gen) {
                pv_reset(dst, result);
                return;
            }
            pv_validate(src, s1);
            pv_reset(dst, result);
            if (!right) {                      /* << 16: low comp -> Y        */
                if (src->flags & PGXP_F_VX) {
                    dst->y16 = src->x16;
                    dst->flags |= PGXP_F_VY;
                }
                dst->x16 = 0;
                dst->flags |= PGXP_F_VX;       /* low half exactly zero       */
            } else {                           /* >> 16: high comp -> X       */
                if (src->flags & PGXP_F_VY) {
                    dst->x16 = src->y16;
                    dst->flags |= PGXP_F_VX;
                }
                dst->y16 = ((int32_t)result >> 16) << 16;  /* 0 or sign fill  */
                dst->flags |= PGXP_F_VY;
            }
            return;
        }
        case 0x20: case 0x21:                  /* ADD / ADDU                  */
        case 0x22: case 0x23:                  /* SUB / SUBU                  */
        case 0x25: {                           /* OR                          */
            /* MOVE idioms first — they matter even without full cpu-mode
             * arithmetic, and they are exact. */
            int is_or = (funct == 0x25);
            int is_sub = (funct == 0x22 || funct == 0x23);
            if ((is_or || !is_sub) && rt == 0) {   /* op rd, rs, $zero        */
                if (rs != 0 && s_gpr[rs].gen == s_gen) {
                    pv_validate(&s_gpr[rs], result);
                    pv_copy(dst, &s_gpr[rs]);
                } else pv_reset(dst, result);
                return;
            }
            if ((is_or || !is_sub) && rs == 0) {   /* op rd, $zero, rt        */
                if (rt != 0 && s_gpr[rt].gen == s_gen) {
                    pv_validate(&s_gpr[rt], result);
                    pv_copy(dst, &s_gpr[rt]);
                } else pv_reset(dst, result);
                return;
            }
            if (!s_cpu_mode) { pv_reset(dst, result); return; }
            a = (rs != 0) ? &s_gpr[rs] : nullptr;
            b = (rt != 0) ? &s_gpr[rt] : nullptr;
            if (is_or) {
                /* Merge disjoint halves (the lhu/sll/or repack pattern). */
                if ((s1 & s2) != 0) { pv_reset(dst, result); return; }
                pv_reset(dst, result);
                const PGXPValue *xsrc; uint32_t xval;
                if ((s1 & 0xFFFFu) != 0) { xsrc = a; xval = s1; }
                else                     { xsrc = b; xval = s2; }
                const PGXPValue *ysrc; uint32_t yval;
                if ((s1 & 0xFFFF0000u) != 0) { ysrc = a; yval = s1; }
                else                         { ysrc = b; yval = s2; }
                if (comp_tracked(xsrc, xval, 0)) {
                    dst->x16 = xsrc->x16; dst->flags |= PGXP_F_VX;
                } else if ((result & 0xFFFFu) == 0) {
                    dst->x16 = 0; dst->flags |= PGXP_F_VX;
                }
                if (comp_tracked(ysrc, yval, 1)) {
                    dst->y16 = ysrc->y16; dst->flags |= PGXP_F_VY;
                } else if ((result & 0xFFFF0000u) == 0) {
                    dst->y16 = 0; dst->flags |= PGXP_F_VY;
                }
                return;
            }
            /* add/sub: require at least one tracked component and halves
             * that combined independently (no cross-half carry). */
            if (!halves_independent(s1, s2, result, is_sub) ||
                (!comp_tracked(a, s1, 0) && !comp_tracked(a, s1, 1) &&
                 !comp_tracked(b, s2, 0) && !comp_tracked(b, s2, 1))) {
                pv_reset(dst, result);
                return;
            }
            pv_reset(dst, result);
            dst->x16 = is_sub ? comp16(a, s1, 0) - comp16(b, s2, 0)
                              : comp16(a, s1, 0) + comp16(b, s2, 0);
            dst->y16 = is_sub ? comp16(a, s1, 1) - comp16(b, s2, 1)
                              : comp16(a, s1, 1) + comp16(b, s2, 1);
            dst->flags = PGXP_F_VXY;
            return;
        }
        default:
            pv_reset(dst, result);
            return;
        }
    }

    /* immediates */
    dst_reg = f_rt(instr);
    if (dst_reg == 0) return;
    PGXPValue *dst = &s_gpr[dst_reg];
    uint32_t rs = f_rs(instr);

    switch (op) {
    case 0x0F: {                               /* LUI: both halves exact      */
        pv_reset(dst, result);
        dst->x16 = 0;
        dst->y16 = ((int32_t)result >> 16) << 16;
        dst->flags = PGXP_F_VXY;
        return;
    }
    case 0x08: case 0x09: {                    /* ADDI / ADDIU                */
        int32_t imm = f_simm(instr);
        if (imm == 0) {                        /* MOVE idiom                  */
            if (rs != 0 && s_gpr[rs].gen == s_gen) {
                pv_validate(&s_gpr[rs], result);
                pv_copy(dst, &s_gpr[rs]);
            } else pv_reset(dst, result);
            return;
        }
        a = (rs != 0) ? &s_gpr[rs] : nullptr;
        /* A negative immediate is a subtraction of its magnitude: checking
         * carry on the sign-extended form would reject nearly every -N. */
        {
            int neg = imm < 0;
            uint32_t mag = (uint32_t)(neg ? -imm : imm);
            if (!s_cpu_mode ||
                !halves_independent(s1, mag, result, neg) ||
                (!comp_tracked(a, s1, 0) && !comp_tracked(a, s1, 1))) {
                pv_reset(dst, result);
                return;
            }
            int32_t dx = (int32_t)(mag & 0xFFFFu) << 16;
            pv_reset(dst, result);
            dst->x16 = comp16(a, s1, 0) + (neg ? -dx : dx);
            dst->y16 = comp16(a, s1, 1);   /* no carry crossed: Y untouched  */
            dst->flags = PGXP_F_VXY;
        }
        return;
    }
    case 0x0D: {                               /* ORI                         */
        uint32_t imm = instr & 0xFFFFu;
        if (imm == 0 || (s_cpu_mode && (s1 & 0xFFFFu) == 0)) {
            a = (rs != 0) ? &s_gpr[rs] : nullptr;
            pv_reset(dst, result);
            if (comp_tracked(a, s1, 1)) {
                dst->y16 = a->y16; dst->flags |= PGXP_F_VY;
            }
            if (imm == 0) {
                if (comp_tracked(a, s1, 0)) {
                    dst->x16 = a->x16; dst->flags |= PGXP_F_VX;
                }
            } else {                           /* exact constant low half     */
                dst->x16 = ((int32_t)(int16_t)imm) << 16;
                dst->flags |= PGXP_F_VX;
            }
            return;
        }
        pv_reset(dst, result);
        return;
    }
    default:                                   /* ANDI/XORI/SLTI/...          */
        pv_reset(dst, result);
        return;
    }
}

extern "C" void psx_pgxp_muldiv(struct CPUState *cpu, uint32_t instr,
                                uint32_t hi, uint32_t lo,
                                uint32_t s1, uint32_t s2) {
    (void)cpu; (void)instr; (void)s1; (void)s2;
    if (!g_pgxp_active) return;
    /* Products/quotients of screen coordinates are not screen coordinates:
     * record the results as known-but-imprecise so MFHI/MFLO stay honest. */
    pv_reset(&s_gpr[PGXP_REG_HI], hi);
    pv_reset(&s_gpr[PGXP_REG_LO], lo);
}

/* ------------------------------------------------------------------------- */
/* GTE producer                                                               */
/* ------------------------------------------------------------------------- */

/* Restart the tag space after 2^32 tags: no old tag may alias a new one. */
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

extern "C" int pgxp_get_gte_sxy(uint32_t index, int32_t *x16, int32_t *y16) {
    return pgxp_get_gte_sxy_checked(index, 0u, 0, x16, y16);
}

extern "C" int pgxp_get_gte_sxy_checked(uint32_t index, uint32_t expect,
                                        int check, int32_t *x16, int32_t *y16) {
    if (index >= 4) return 0;
    const PGXPValue *pv = &s_gte[12 + index];
    if (!pv_live(pv) || (pv->flags & PGXP_F_VXY) != PGXP_F_VXY)
        return 0;
    if (check && pv->value != expect)
        return 0;
    if (x16) *x16 = pv->x16;
    if (y16) *y16 = pv->y16;
    return 1;
}

extern "C" void pgxp_gte_reg_written(int reg, uint32_t value) {
    /* Invalidation-class bookkeeping: runs even with the engine disarmed so
     * seeded/leftover shadows can never outlive a guest register write. Only
     * the suppression bracket skips it (the speculative pass rolls the
     * machine state back, so its writes must not stick to the shadows). */
    if (s_suppress != 0) return;
    if (reg < 0 || reg > 31) return;
    pv_kill(&s_gte[reg]);
    pv_reset(&s_gte[reg], value);
}

/* ------------------------------------------------------------------------- */
/* GPU consumer                                                               */
/* ------------------------------------------------------------------------- */

extern "C" int pgxp_get_precise_vertex(uint32_t addr, uint32_t packet_word,
                                       int32_t int_x, int32_t int_y,
                                       int32_t *x16, int32_t *y16,
                                       uint16_t *sz) {
    s_stats.lookups++;

    int32_t px = 0, py = 0;
    uint16_t pz = 0;
    int have = 0;

    if (s_enabled && addr != 0xFFFFFFFFu) {
        PGXPValue *pv = pgxp_ptr(addr);
        if (pv && pv->gen == s_gen && (pv->flags & PGXP_F_VXY) != 0) {
            if (pv->value == packet_word &&
                (pv->flags & PGXP_F_VXY) == PGXP_F_VXY) {
                px = pv->x16;
                py = pv->y16;
                pz = (pv->flags & PGXP_F_VZ) ? pv->z : 0;
                have = PGXP_SRC_DATAFLOW;
            } else {
                s_stats.value_mismatch++;
            }
        }
    }

    if (!have && gte_geometry_correction_lookup(packet_word, &px, &py)) {
        pz = 0;                                /* fallback never carries depth */
        have = PGXP_SRC_FALLBACK;
    }

    if (have) {
        /* Truncation agreement: the GPU parsed 11-bit integers out of the
         * packet; a precise position whose integer part disagrees (a
         * wrapped/CPU-modified coordinate) must not be believed. */
        if ((px >> 16) != int_x || (py >> 16) != int_y) {
            s_stats.trunc_reject++;
            have = 0;
        } else if (s_tolerance >= 0.0f) {
            float dx = (float)(px - (int_x << 16)) * (1.0f / 65536.0f);
            float dy = (float)(py - (int_y << 16)) * (1.0f / 65536.0f);
            if (dx > s_tolerance || dy > s_tolerance) {
                s_stats.tolerance_reject++;
                have = 0;
            }
        }
    }

    if (!have) {
        s_stats.native++;
        *x16 = int_x << 16;
        *y16 = int_y << 16;
        *sz = 0;
        return PGXP_SRC_NATIVE;
    }

    if (have == PGXP_SRC_DATAFLOW) s_stats.dataflow_hit++;
    else                           s_stats.fallback_hit++;
    if (pz != 0) s_stats.w_valid++;
    *x16 = px;
    *y16 = py;
    *sz = pz;
    return have;
}

/* ------------------------------------------------------------------------- */
/* Legacy v14 SWC2 tracker — kept as the base-flavour feed                    */
/* ------------------------------------------------------------------------- */

/* Emitted at every swc2 since ABI v14 (all flavours, all backends, overlay
 * DLLs). In the pgxp flavour psx_pgxp_cop2 supersedes it for the same swc2 —
 * the double write is idempotent (same source shadow, same destination). */
extern "C" void pgxp_store_gte_reg(uint32_t addr, uint8_t reg) {
    if (!g_pgxp_active) return;
    PGXPValue *dst = pgxp_ptr(addr);
    if (!dst) return;
    const PGXPValue *src = &s_gte[reg & 31u];
    if (src->gen != s_gen) return;
    s_stats.swc2_stores++;
    pv_copy(dst, src);
}

/* ------------------------------------------------------------------------- */
/* Test accessors                                                             */
/* ------------------------------------------------------------------------- */

extern "C" void pgxp_test_seed_gte_sxy(uint32_t index, uint32_t packed,
                                       int32_t x16, int32_t y16, uint16_t z,
                                       int valid) {
    if (index >= 4) return;
    PGXPValue *pv = &s_gte[12 + index];
    pv->x16 = x16;
    pv->y16 = y16;
    pv->z = z;
    pv->value = packed;
    pv->flags = (uint16_t)(PGXP_F_VXY | (z != 0 ? PGXP_F_VZ : 0));
    pv->gen = valid ? s_gen : 0;
}

extern "C" void pgxp_test_get_gte_sxy(uint32_t index, uint32_t *packed,
                                      int32_t *x16, int32_t *y16, uint16_t *z,
                                      uint8_t *valid) {
    if (index >= 4) return;
    const PGXPValue *pv = &s_gte[12 + index];
    if (packed) *packed = pv->value;
    if (x16) *x16 = pv->x16;
    if (y16) *y16 = pv->y16;
    if (z) *z = pv->z;
    if (valid) *valid = pv_live(pv) ? 1 : 0;
}

extern "C" uint32_t pgxp_test_generation(void) { return s_gen; }

extern "C" uint32_t pgxp_test_suppress_depth(void) { return s_suppress; }
extern "C" int pgxp_test_active(void) { return g_pgxp_active; }

extern "C" void pgxp_test_set_generation(uint32_t gen) { s_gen = gen; }

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

/* Address-keyed depth lookup for the shipped perspective-texturing path
 * (gpu.c prepare_texture_triangle). Same contract as the retired hashed
 * table: hit only when the tracked word matches the packet word exactly. */
extern "C" int pgxp_load_precise_word(uint32_t addr, uint32_t packed,
                                      int32_t *x16, int32_t *y16, uint16_t *z) {
    if (!s_enabled) return 0;
    PGXPValue *pv = pgxp_ptr(addr);
    if (!pv || pv->gen != s_gen || pv->value != packed ||
        (pv->flags & PGXP_F_VXY) != PGXP_F_VXY)
        return 0;
    if (x16) *x16 = pv->x16;
    if (y16) *y16 = pv->y16;
    if (z) *z = (pv->flags & PGXP_F_VZ) ? pv->z : 0;
    return (pv->flags & PGXP_F_VZ) && pv->z != 0;
}
