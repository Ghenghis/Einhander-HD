#ifndef PSX_INTERP_PC_SAMPLER_H
#define PSX_INTERP_PC_SAMPLER_H
#include <stdint.h>
#include <string.h>

/* Host-only diagnostic. Samples actual interpreted RAM instruction attempts,
 * including delay slots, rather than charging a chain to its dispatch entry.
 * A private PRNG varies the stride to avoid locking onto one loop phase.
 * No guest state, allocation, I/O or clock reads in the observation path. */
#define INTERP_PC_SAMPLE_CAP 32768u
#define INTERP_PC_SAMPLE_TOP 64u
typedef struct { uint32_t pc; uint64_t samples; } InterpPcBucket;
typedef struct {
    int enabled;
    uint32_t countdown,rng,occupied;
    uint64_t observed,samples,dropped;
    InterpPcBucket buckets[INTERP_PC_SAMPLE_CAP];
} InterpPcSampler;
typedef struct {
    int enabled;
    uint32_t occupied;
    uint64_t observed,samples,dropped;
} InterpPcSampleStats;

static inline void interp_pc_sampler_init(InterpPcSampler *s,int enabled){
    memset(s,0,sizeof(*s));s->enabled=enabled!=0;s->rng=0x6D2B79F5u;s->countdown=1;
}
static inline void interp_pc_sampler_observe(InterpPcSampler *s,uint32_t pc){
    if(!s->enabled)return;
    uint32_t phys=pc&0x1FFFFFFFu;
    if(phys>=0x200000u||(phys&3u))return;
    ++s->observed;
    if(--s->countdown)return;
    uint32_t rng=s->rng;rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;s->rng=rng;
    s->countdown=512u+(rng&1023u);++s->samples;
    uint32_t bucket=phys&~15u,index=((bucket>>4)*2654435761u)&(INTERP_PC_SAMPLE_CAP-1u);
    for(uint32_t n=0;n<INTERP_PC_SAMPLE_CAP;++n){
        InterpPcBucket *slot=&s->buckets[(index+n)&(INTERP_PC_SAMPLE_CAP-1u)];
        if(!slot->samples){slot->pc=bucket;slot->samples=1;++s->occupied;return;}
        if(slot->pc==bucket){++slot->samples;return;}
    }
    ++s->dropped;
}
static inline int interp_pc_bucket_before(InterpPcBucket a,InterpPcBucket b){
    return a.samples>b.samples||(a.samples==b.samples&&a.pc<b.pc);
}
static inline unsigned interp_pc_sampler_top(const InterpPcSampler *s,InterpPcBucket *out,unsigned capacity){
    if(!out)return 0;if(capacity>INTERP_PC_SAMPLE_TOP)capacity=INTERP_PC_SAMPLE_TOP;
    unsigned count=0;
    for(unsigned i=0;i<INTERP_PC_SAMPLE_CAP&&capacity;++i){
        InterpPcBucket row=s->buckets[i];if(!row.samples)continue;
        if(count==capacity&&!interp_pc_bucket_before(row,out[count-1]))continue;
        unsigned at=count<capacity?count++:capacity-1;
        while(at&&interp_pc_bucket_before(row,out[at-1])){out[at]=out[at-1];--at;}
        out[at]=row;
    }
    return count;
}

#ifdef __cplusplus
extern "C" {
#endif
void dirty_ram_pc_profile_configure(int enabled,int reset);
unsigned dirty_ram_pc_profile_get(InterpPcSampleStats *stats,InterpPcBucket *rows,unsigned capacity);
#ifdef __cplusplus
}
#endif
#endif
