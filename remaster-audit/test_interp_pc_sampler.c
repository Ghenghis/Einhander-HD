#include "interp_pc_sampler.h"
#include <stdio.h>
static unsigned checks,failures;
#define CHECK(name,condition) do{++checks;if(!(condition)){++failures;printf("FAIL %s\n",name);}}while(0)
static InterpPcSampler state;
int main(void){
    InterpPcBucket rows[INTERP_PC_SAMPLE_TOP];
    interp_pc_sampler_init(&state,0);
    for(unsigned i=0;i<100000;++i)interp_pc_sampler_observe(&state,0x80010000);
    CHECK("disabled observation changes no counts",!state.observed&&!state.samples&&!state.occupied);
    interp_pc_sampler_init(&state,1);
    interp_pc_sampler_observe(&state,0xBFC00000);interp_pc_sampler_observe(&state,0x80010001);
    CHECK("ROM and unaligned attempts excluded",!state.observed&&!state.samples);
    for(unsigned i=0;i<1000000;++i)interp_pc_sampler_observe(&state,0x80010000+16*(i%4));
    unsigned n=interp_pc_sampler_top(&state,rows,INTERP_PC_SAMPLE_TOP);
    CHECK("bounded randomized stride gives expected sample volume",state.samples>600&&state.samples<2000);
    CHECK("actual loop phases sampled across four instruction buckets",n==4&&rows[3].samples>100&&rows[0].samples-rows[3].samples<200);
    CHECK("RAM attempts counted independently from samples",state.observed==1000000);
    uint64_t sum=0;for(unsigned i=0;i<n;++i)sum+=rows[i].samples;
    CHECK("histogram retains every sample without overflow",sum==state.samples&&!state.dropped);
    for(unsigned i=1;i<n;++i)CHECK("top rows sorted",!interp_pc_bucket_before(rows[i],rows[i-1]));
    interp_pc_sampler_init(&state,1);
    /* Every dispatch may start at an epilogue, but the subsequent loop owns
     * almost all executed instructions. Entry attribution must not win. */
    for(unsigned i=0;i<1000000;++i)interp_pc_sampler_observe(&state,i%256?0x80050000:0x80026714);
    n=interp_pc_sampler_top(&state,rows,2);
    CHECK("real loop dominates a frequently encountered chain entry",n==2&&rows[0].pc==0x50000&&rows[0].samples>state.samples*98/100);
    interp_pc_sampler_init(&state,1);
    for(unsigned i=0;i<INTERP_PC_SAMPLE_CAP+32;++i){state.countdown=1;interp_pc_sampler_observe(&state,16*i);}
    CHECK("capacity bounded with explicit dropped count",state.occupied==INTERP_PC_SAMPLE_CAP&&state.dropped==32&&state.samples==INTERP_PC_SAMPLE_CAP+32);
    n=interp_pc_sampler_top(&state,rows,9999);
    CHECK("export capacity clamped",n==INTERP_PC_SAMPLE_TOP);
    CHECK("empty export supported",interp_pc_sampler_top(&state,0,64)==0&&interp_pc_sampler_top(&state,rows,0)==0);
    interp_pc_sampler_init(&state,0);
    CHECK("reset clears a full histogram",!state.occupied&&!state.observed&&!state.samples&&!state.dropped);
    printf("RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
