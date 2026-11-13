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
    const uint32_t mk3[4]={0x724E77DAu,0xE2F3477Cu,0x8FE8B060u,0xC6E8710Bu};
    for(unsigned i=0;i<4;++i)CHECK("all verified MkIII hull keys accepted",hero_draw_key_for_craft(mk3[i],0x21FDE894u,0,3));
    CHECK("MkII unique hull does not enter MkIII geometry",!hero_draw_key_for_craft(0xB16492B1u,0x21FDE894u,0,3));
    const uint32_t ast[5][2]={{0x6ACFACE4u,0xEF213D7Fu},{0x8CD3F840u,0xEF213D7Fu},{0x0878817Du,0x9414AA42u},{0x8E818661u,0x9414AA42u},{0x0A0CE3A4u,0xDE4ECDD2u}};
    for(unsigned i=0;i<5;++i){
        CHECK("verified Astraea hull key accepted",hero_draw_key_for_craft(ast[i][0],ast[i][1],0,4));
        CHECK("wrong Astraea palette rejected",!hero_draw_key_for_craft(ast[i][0],ast[i][1]^1,0,4));
        CHECK("different source depth rejected",!hero_draw_key_for_craft(ast[i][0],ast[i][1],1,4));
    }
    CHECK("Astraea glint excluded",!hero_draw_key_for_craft(0x57FE8E03u,0x3D6CBEDEu,0,4));
    CHECK("unqualified canopy excluded",!hero_draw_key_for_craft(0xB9EB2209u,0x9414AA42u,0,4));
    CHECK("unknown source set rejected",!hero_draw_key_for_craft(0x724E77DAu,0x21FDE894u,0,9));
    hero_draw_observe_for_craft(&tracker,5,0x8FE8B060u,0x21FDE894u,0,x,next_y,next_area,3);
    hero_draw_snapshot(&tracker,5,1,&s);CHECK("source-set change starts its own union",s.source_set==3&&s.draws==1);
    memset(&tracker,0,sizeof(tracker));
    hero_draw_observe_for_craft(&tracker,20,0x724E77DAu,0x21FDE894u,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,20,1,&s);CHECK("automatic shared hull does not invent a craft",s.valid&&s.source_set==5);
    hero_draw_observe_for_craft(&tracker,20,0x8FE8B060u,0x21FDE894u,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,20,1,&s);CHECK("automatic unique MkIII part refines shared union",s.source_set==3&&s.draws==2);
    hero_draw_observe_for_craft(&tracker,21,0xE2F3477Cu,0x21FDE894u,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,21,1,&s);CHECK("fresh shared part retains observed unique identity",s.source_set==3&&s.draws==1);
    hero_draw_observe_for_craft(&tracker,35,0xE2F3477Cu,0x21FDE894u,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,35,1,&s);CHECK("stale unique identity is not retained",s.source_set==5);
    hero_draw_observe_for_craft(&tracker,36,0xB16492B1u,0x21FDE894u,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,36,1,&s);CHECK("automatic MkII unique part switches identity",s.source_set==2);
    hero_draw_observe_for_craft(&tracker,37,0x6ACFACE4u,0xEF213D7Fu,0,x,next_y,next_area,1);
    hero_draw_snapshot(&tracker,37,1,&s);CHECK("automatic Astraea uses its proven palette",s.valid&&s.source_set==4);
    CHECK("automatic observer rejects unknown art",!hero_draw_key_for_craft(0x57FE8E03u,0x3D6CBEDEu,0,1));
    GreifDrawClock clock={0};
    greif_draw_snapshot(&clock,100,1,&s);CHECK("missing Greif cannot invent a clock",!s.greif_valid);
    greif_draw_observe(&clock,100,0x1263A036u,0,64,256,x,next_y,next_area);
    greif_draw_snapshot(&clock,100,1,&s);CHECK("native Greif source starts a clock",s.greif_valid&&s.greif_first_frame==100&&s.greif_last_frame==100);
    greif_draw_observe(&clock,110,0x38DC02FEu,0,64,256,x,next_y,next_area);
    greif_draw_snapshot(&clock,122,1,&s);CHECK("second page retains encounter and bounded freshness",s.greif_valid&&s.greif_first_frame==100&&s.greif_age_frames==12);
    greif_draw_snapshot(&clock,123,1,&s);CHECK("old Greif not fresh",!s.greif_valid);
    greif_draw_observe(&clock,120,0x1263A036u,0,64,256,off_x,next_y,next_area);
    greif_draw_observe(&clock,120,0x1263A036u,1,64,256,x,next_y,next_area);
    greif_draw_observe(&clock,120,0x1263A036u,0,16,64,x,next_y,next_area);
    greif_draw_observe(&clock,120,0x724E77DAu,0,64,256,x,next_y,next_area);
    greif_draw_snapshot(&clock,120,1,&s);CHECK("wrong source geometry depth and offscreen excluded",s.greif_last_frame==110);
    greif_draw_observe(&clock,261,0x1263A036u,0,64,256,x,next_y,next_area);
    greif_draw_snapshot(&clock,261,1,&s);CHECK("absence starts new encounter",s.greif_valid&&s.greif_first_frame==261);
    greif_draw_observe(&clock,4,0x1263A036u,0,64,256,x,next_y,next_area);
    greif_draw_snapshot(&clock,4,0,&s);CHECK("reset restarts clock and optout stays invalid",!s.greif_valid&&s.greif_first_frame==4);
    printf("RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
