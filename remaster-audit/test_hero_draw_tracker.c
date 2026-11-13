/* Draw identity, viewport normalization and freshness; no game/GPU required. */
#include "hero_draw_tracker.h"
#include <stdio.h>
static unsigned checks,failures;
#define CHECK(label,condition) do{++checks;if(!(condition)){++failures;printf("FAIL %s\n",label);}}while(0)
int main(void){
    HeroDrawTracker tracker={0};GlPlayerDrawState s;
    int area[4]={0,256,319,495};
    int x[3]={40,60,45},y[3]={350,360,370};
    hero_draw_snapshot(&tracker,100,1,&s);
    CHECK("empty tracker cannot invent a hero",!s.valid&&!s.draws);
    CHECK("unproven palette cannot claim the hull",!hero_draw_key(0x724E77DAu,0x053D9A00u,0));
    CHECK("wrong depth rejected",!hero_draw_key(0x724E77DAu,0x21FDE894u,1));
    CHECK("other source rejected",!hero_draw_key(0x95A3BCF8u,0x21FDE894u,0));
    CHECK("engine effect excluded",!hero_draw_key(0x5CC44E5Fu,0x053D9A00u,0));
    for(unsigned i=0;i<4;++i){
        const uint32_t key[4]={0x724E77DAu,0x7E3ADD56u,0xE2F3477Cu,0xB16492B1u};
        CHECK("all four audited hull uploads accepted",hero_draw_key(key[i],0x21FDE894u,0));
    }
    hero_draw_observe(&tracker,100,0x724E77DAu,0x21FDE894u,0,x,y,area);
    hero_draw_snapshot(&tracker,100,1,&s);
    CHECK("second framebuffer normalized",s.valid&&s.min_x==40&&s.max_x==60&&s.min_y==94&&s.max_y==114&&s.width==320&&s.height==240);
    CHECK("one source match counted once",s.draws==1);
    CHECK("source identity retained",s.texture_hash==0x724E77DAu&&s.palette_hash==0x21FDE894u);
    x[0]=20;x[1]=50;x[2]=35;y[0]=340;
    hero_draw_observe(&tracker,100,0xB16492B1u,0x21FDE894u,0,x,y,area);
    hero_draw_snapshot(&tracker,100,1,&s);
    CHECK("hull parts union within one frame",s.draws==2&&s.min_x==20&&s.min_y==84&&s.max_x==60&&s.max_y==114);
    hero_draw_snapshot(&tracker,112,1,&s);CHECK("bounded blink grace",s.valid&&s.age_frames==12);
    hero_draw_snapshot(&tracker,113,1,&s);CHECK("stale geometry invalid",!s.valid&&s.age_frames==13);
    hero_draw_snapshot(&tracker,99,1,&s);CHECK("frame reversal invalid instead of underflow",!s.valid&&s.age_frames==UINT64_MAX);
    hero_draw_snapshot(&tracker,100,0,&s);CHECK("disabled telemetry invalid",!s.valid&&!s.enabled);
    int next_area[4]={0,0,319,239},next_y[3]={50,60,70};
    hero_draw_observe(&tracker,101,0x7E3ADD56u,0x21FDE894u,0,x,next_y,next_area);
    hero_draw_snapshot(&tracker,101,1,&s);CHECK("new frame replaces old union",s.valid&&s.draws==1&&s.min_y==50&&s.max_x==50);
    int off_x[3]={400,410,420};
    hero_draw_observe(&tracker,102,0x724E77DAu,0x21FDE894u,0,off_x,next_y,next_area);
    hero_draw_snapshot(&tracker,102,1,&s);CHECK("offscreen draw does not refresh hero",s.frame==101&&s.draws==1);
    int tiny[4]={0,0,63,63};
    hero_draw_observe(&tracker,102,0x724E77DAu,0x21FDE894u,0,x,next_y,tiny);
    hero_draw_snapshot(&tracker,102,1,&s);CHECK("small staging area excluded",s.frame==101);
    hero_draw_observe(&tracker,5,0x724E77DAu,0x21FDE894u,0,x,next_y,next_area);
    hero_draw_snapshot(&tracker,5,1,&s);CHECK("fresh geometry after reset starts new history",s.valid&&s.frame==5&&s.draws==1);
    printf("RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
