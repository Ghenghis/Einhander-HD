#ifndef PGXP_H
#define PGXP_H

/* PGXP value-propagation engine — runtime-internal API (pgxp.cpp).
 *
 * The engine shadows every 32-bit word of guest RAM/scratchpad, every GPR,
 * and every GTE data register with the sub-pixel projection it carries
 * (screen X/Y in 16.16 plus the projected SZ depth). The GTE fills shadows at
 * RTPS/RTPT; the psx_pgxp_* hooks (pgxp_hooks.h) move them along with the
 * data; the GPU asks for the precise position of each GP0 vertex word by the
 * packet's RAM address, validated against the actual word — never guessed
 * from the rounded position (the measured G1.4 dead end).
 *
 * Guest-visible state is NEVER touched: shadows are host-only, dropped on
 * savestate/rewind, and suppressed during speculative validation passes.
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- lifecycle / configuration ------------------------------------------ */

/* Master arm. Allocates the RAM shadow lazily; fails closed (stays disabled)
 * if the allocation fails. Idempotent. */
void pgxp_set_enabled(int enabled);
int  pgxp_enabled(void);

/* Tier-2 propagation through CPU arithmetic (default off, like the reference
 * implementations' default). Off is SAFE — value validation already stops
 * stale shadows — it only bounds coverage. Live-tunable (TCP). */
void pgxp_set_cpu_mode(int enabled);
int  pgxp_cpu_mode(void);

/* Reject a precise position whose sub-pixel offset from the native integer
 * position exceeds this many pixels. < 0 disables the clamp (default). */
void  pgxp_set_tolerance(float pixels);
float pgxp_tolerance(void);

/* Drop all shadows (savestate load, raw RAM restore, timeline breaks).
 * O(1) via generation bump. Deferred while suppressed. */
void pgxp_invalidate_all(void);

/* Counted suppression bracket for speculative native-validation passes and
 * the GTE replay sandbox: hooks and producers no-op inside it. */
void pgxp_suppress_begin(void);
void pgxp_suppress_end(void);

/* --- GTE producer (gte.cpp) ---------------------------------------------- */

/* Called at the RTPS/RTPT projection with the pre-truncation 16.16 screen
 * coordinates, the projected depth (SZ3), and the packed SXY word the guest
 * sees. Shifts the shadow FIFO exactly like push_sxy (regs 12..15). */
void pgxp_gte_push_sxy(int32_t x16, int32_t y16, uint16_t sz3, uint32_t packed);

/* Current SXY FIFO shadow (index 0..3 selects GTE data regs 12..15).
 * Returns nonzero when the shadow is live and carries X/Y precision. */
int pgxp_get_gte_sxy(uint32_t index, int32_t *x16, int32_t *y16);
/* Validate-on-read variant: check!=0 additionally requires the shadow's packed
 * word to equal expect (the live guest SXY word). Sign consumers must use this
 * form so stale FIFO shadows fail closed to native integer behavior. */
int pgxp_get_gte_sxy_checked(uint32_t index, uint32_t expect, int check,
                             int32_t *x16, int32_t *y16);

/* Guest write to a GTE data register outside gte_execute (MTC2/CTC2 handled
 * by psx_pgxp_cop2; this is for direct gte_write_data paths): reg 15 performs
 * the SXYP FIFO push on the shadows, others just invalidate/overwrite. */
void pgxp_gte_reg_written(int reg, uint32_t value);

/* --- GPU consumer (gpu.c) ------------------------------------------------ */

enum {
    PGXP_SRC_NATIVE   = 0,   /* no shadow — caller uses the parsed integers  */
    PGXP_SRC_FALLBACK = 1,   /* position-cache fallback (never carries depth)*/
    PGXP_SRC_DATAFLOW = 2,   /* address-keyed shadow, value-validated        */
};

/* Precise position for one GP0 vertex word.
 *   addr        guest address the word was DMA'd from, or 0xFFFFFFFF if
 *               unknown (immediate GP0 writes) — skips the dataflow tier.
 *   packet_word the actual word (validation key).
 *   int_x/int_y the natively parsed 11-bit positions (pre-draw-offset).
 * On DATAFLOW/FALLBACK, *x16/*y16 hold the sub-pixel position (16.16, same
 * coordinate space as the packet halves); *sz is the projected depth or 0.
 * Safeguards applied here: the integer part must match the native parse
 * (truncation agreement) and the tolerance clamp. */
int pgxp_get_precise_vertex(uint32_t addr, uint32_t packet_word,
                            int32_t int_x, int32_t int_y,
                            int32_t *x16, int32_t *y16, uint16_t *sz);

/* --- opt-in 3D view provenance (remix-provenance v1, default OFF) ---------- */

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
#define PGXP_VIEW_NATIVE_DIVERGED                                              \
    (PGXP_VIEW_IR_SAT | PGXP_VIEW_SZ_SAT | PGXP_VIEW_DIV_OVF |                 \
     PGXP_VIEW_XY_SAT | PGXP_VIEW_XY_CLAMP |                                   \
     PGXP_VIEW_MAC1_OVF44 | PGXP_VIEW_MAC2_OVF44 | PGXP_VIEW_MAC3_OVF44 |      \
     PGXP_VIEW_MAC1_WRAP32 | PGXP_VIEW_MAC2_WRAP32 | PGXP_VIEW_MAC3_WRAP32)

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
    uint64_t no_shadow;           /* disabled / no live shadow                   */
    uint64_t no_source;           /* immediate GP0 word: no packet address (v2)  */
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

/* v3: per-flag hit split indices (PgxpViewCensusKind.hit_flag) */
enum {
    PGXP_VIEW_CENSUS_FLAG_XY_SAT = 0, PGXP_VIEW_CENSUS_FLAG_XY_CLAMP, PGXP_VIEW_CENSUS_FLAG_IR_SAT,
    PGXP_VIEW_CENSUS_FLAG_DIV_OVF, PGXP_VIEW_CENSUS_FLAG_SZ_SAT, PGXP_VIEW_CENSUS_FLAG_WS_SQUASH,
    PGXP_VIEW_CENSUS_FLAG_DOME, PGXP_VIEW_CENSUS_FLAG_MAC_OVF44, PGXP_VIEW_CENSUS_FLAG_MAC_WRAP32,
    PGXP_VIEW_CENSUS_FLAG_COUNT
};

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
    /* v3 */
    uint64_t lag[5];                 /* hits by draw frame - view frame, mod   *
                                      * 2^32: [0]=0 [1]=1 [2]=2 [3]=>=3         *
                                      * [4]=future (view frame after the draw) */
    uint64_t lag_wrapped;            /* past lags that crossed the 32-bit      *
                                      * frame-counter wrap (also in [0..3])    */
    uint64_t hit_flag[PGXP_VIEW_CENSUS_FLAG_COUNT]; /* hits carrying each flag */
    uint64_t hit_xform_match;        /* committed hits whose LIVE ring record  *
                                      * re-hashes to the view's xform_hash     */
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

/* gte.cpp GTE projection ring accessors (records exist only in builds with
 * debug tools; every accessor returns 0 for a record that was never written or
 * has been overwritten). v3 adds the xform re-hash: FNV-1a over RT, TR, H,
 * OFX, OFY of the live record, the same function the producer stores in
 * PgxpView.xform_hash. */
int gte_rtp_ring_seq_live(uint64_t seq);
int gte_rtp_ring_get_xform(uint64_t seq, int16_t rt[9], int32_t tr[3],
                           uint32_t *frame, uint32_t *caller_ra);
int gte_rtp_ring_xform_hash(uint64_t seq, uint32_t *hash);
int gte_rtp_ring_get_projection(uint64_t seq, uint16_t *h, int32_t *ofx,
                                int32_t *ofy);

/* test accessors (always compiled; trivial) */
void     pgxp_test_view_fail_next_alloc(int count);
uint64_t pgxp_test_view_alloc_bytes(void);
void     pgxp_test_view_set_seq(uint32_t next_tag);
/* Transport invariant probe: 1 iff the RAM/scratch shadow at addr is live and
 * still carries the view flag (independent of the consumer's checks). */
int      pgxp_test_view_flag(uint32_t addr);

/* --- observability -------------------------------------------------------- */

typedef struct PGXPStats {
    uint64_t lookups;            /* pgxp_get_precise_vertex calls            */
    uint64_t dataflow_hit;
    uint64_t fallback_hit;
    uint64_t native;
    uint64_t value_mismatch;     /* shadow present but wrong word (stale)    */
    uint64_t trunc_reject;       /* integer part disagreed with native parse */
    uint64_t tolerance_reject;
    uint64_t w_valid;            /* lookups that also carried a usable depth */
    uint64_t produced;           /* RTPS/RTPT projections pushed into shadows */
    uint64_t swc2_stores;        /* GTE reg shadows copied to RAM shadows     */
} PGXPStats;

void pgxp_get_stats(PGXPStats *out);

/* --- gte.cpp forwarding surface (v14 ABI compat) -------------------------- */

/* SWC2 site: copy the GTE register shadow (regs 12..15) to the RAM shadow. */
void pgxp_store_gte_reg(uint32_t addr, uint8_t reg);

/* Address-keyed precise-word lookup (perspective texturing path). Returns
 * nonzero when the tracked word matches `packed` AND carries a depth. */
int pgxp_load_precise_word(uint32_t addr, uint32_t packed,
                           int32_t *x16, int32_t *y16, uint16_t *z);

/* --- test accessors (always compiled; trivial) ---------------------------- */

/* index 0..3 selects the SXY0..SXYP register shadow (GTE data regs 12..15). */
void pgxp_test_seed_gte_sxy(uint32_t index, uint32_t packed,
                            int32_t x16, int32_t y16, uint16_t z, int valid);
void pgxp_test_get_gte_sxy(uint32_t index, uint32_t *packed,
                           int32_t *x16, int32_t *y16, uint16_t *z,
                           uint8_t *valid);
uint32_t pgxp_test_generation(void);
uint32_t pgxp_test_suppress_depth(void);
int      pgxp_test_active(void);
void     pgxp_test_set_generation(uint32_t gen);

#ifdef __cplusplus
}
#endif

#endif /* PGXP_H */
