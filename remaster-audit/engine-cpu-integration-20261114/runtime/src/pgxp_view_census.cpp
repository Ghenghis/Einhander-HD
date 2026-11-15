/* pgxp_view_census.cpp — opt-in per-primitive census of the 3D view payload
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
