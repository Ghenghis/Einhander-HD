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
