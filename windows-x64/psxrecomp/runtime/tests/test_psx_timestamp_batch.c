/* Real clock/deadline functions against batched and explicitly published time.
 * Reuse the existing deterministic device stubs and causality check. */
#include "cpu_state.h"
#include <string.h>
#define main existing_deadline_boundary_test
#include "test_psx_cycle_event_boundaries.c"
#undef main
extern void psx_cycles_reset_for_boot(void);
static unsigned checks,failures;
#define CHECK(name,condition) do{++checks;if(!(condition)){++failures;fprintf(stderr,"FAIL %s\n",name);}}while(0)
static void reset_case(CPUState *cpu){
    memset(cpu,0,sizeof(*cpu));psx_cycles_reset_for_boot();
    s_cd_ready=1;s_cd_cycles_remaining=0;s_dma_ready_cycles=0;s_spu_next_sample=UINT32_MAX;i_mask=0;
}
static void pending(uint32_t cycles){g_psx_cyc_batch=cycles;g_psx_cyc_batch_limit=64;}
static void invoke(CPUState *cpu,unsigned operation,unsigned latency){
    switch(operation){
    case 0:psx_muldiv_set(cpu,latency);break;
    case 1:psx_muldiv_stall(cpu);break;
    case 2:psx_gte_set(cpu,latency);break;
    case 3:psx_gte_stall(cpu);break;
    case 4:psx_gte_read(cpu,7);break;
    }
}
int main(void){
    if(existing_deadline_boundary_test())return 1;
    CPUState cpu;
    reset_case(&cpu);psx_advance_cycles(7);psx_muldiv_set(&cpu,37);
    CHECK("unbatched MULT/DIV deadline unchanged",cpu.muldiv_ts_done==44);
    reset_case(&cpu);pending(7);psx_muldiv_set(&cpu,37);
    CHECK("batched issue matches published issue time",cpu.muldiv_ts_done==44&&psx_cycle_count==7&&!g_psx_cyc_batch);
    reset_case(&cpu);uint32_t local=5;g_psx_cyc_local_acc=&local;pending(3);psx_muldiv_set(&cpu,37);
    CHECK("local and global pending charges published exactly once",cpu.muldiv_ts_done==45&&psx_cycle_count==8&&!local&&!g_psx_cyc_batch);
    g_psx_cyc_local_acc=NULL;
    reset_case(&cpu);cpu.muldiv_ts_done=10;cpu.read_absorb[0]=20;pending(7);psx_muldiv_stall(&cpu);
    CHECK("MFLO stalls only for latency remaining after pending time",psx_cycle_count==10&&cpu.read_absorb[0]==17);
    reset_case(&cpu);cpu.muldiv_ts_done=7;pending(6);psx_muldiv_stall(&cpu);
    CHECK("one-cycle retract uses the current published clock",psx_cycle_count==6&&cpu.muldiv_ts_done==6);
    reset_case(&cpu);cpu.gte_ts_done=5;pending(8);psx_gte_set(&cpu,10);
    CHECK("expired prior GTE command does not create extra stall",psx_cycle_count==8&&cpu.gte_ts_done==18);
    reset_case(&cpu);pending(4);psx_gte_set(&cpu,10);
    CHECK("GTE deadline matches the instruction issue point",psx_cycle_count==4&&cpu.gte_ts_done==14);
    reset_case(&cpu);cpu.gte_ts_done=5;pending(2);psx_gte_read(&cpu,3);
    CHECK("MFC2 gives back only the actual remaining stall",psx_cycle_count==5&&cpu.ld_absorb==3&&cpu.ld_which_t==3);
    reset_case(&cpu);cpu.gte_ts_done=5;pending(7);psx_gte_read(&cpu,4);
    CHECK("completed GTE read has no phantom give-back",psx_cycle_count==7&&!cpu.ld_absorb&&cpu.ld_which_t==4);
    reset_case(&cpu);cpu.gte_ts_done=5;pending(7);psx_gte_stall(&cpu);
    CHECK("GTE stall observes pending elapsed time",psx_cycle_count==7);
    reset_case(&cpu);s_cd_ready=0;s_cd_cycles_remaining=5;pending(5);psx_muldiv_set(&cpu,37);
    CHECK("publishing preserves the exact device deadline",s_cd_ready&&s_dma_ready_cycles==1&&psx_cycle_count==5&&cpu.muldiv_ts_done==42);
    unsigned mismatches=0,cases=0;
    for(unsigned batch=0;batch<=64;++batch)for(unsigned deadline=0;deadline<=64;deadline+=7)for(unsigned operation=0;operation<5;++operation){
        CPUState expected;uint64_t expected_clock;
        reset_case(&cpu);cpu.muldiv_ts_done=deadline;cpu.gte_ts_done=deadline;cpu.read_absorb[0]=20;
        psx_advance_cycles(batch);invoke(&cpu,operation,37);expected=cpu;expected_clock=psx_get_cycle_count();
        reset_case(&cpu);cpu.muldiv_ts_done=deadline;cpu.gte_ts_done=deadline;cpu.read_absorb[0]=20;
        pending(batch);invoke(&cpu,operation,37);
        if(memcmp(&cpu,&expected,sizeof(cpu))||psx_get_cycle_count()!=expected_clock||g_psx_cyc_batch)++mismatches;
        ++cases;
    }
    CHECK("batched timing equals explicitly published timing across all five APIs",!mismatches&&cases==3250);
    fprintf(stderr,"RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
