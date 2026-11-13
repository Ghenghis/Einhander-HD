#include "threat_draw_tracker.h"
#include <stdio.h>
static unsigned checks,failures;
#define CHECK(label,c) do{++checks;if(!(c)){++failures;printf("FAIL %s\n",label);}}while(0)
static void observe(ThreatDrawState *s,uint64_t f,int x,int y,uint32_t t,uint32_t p,unsigned depth){
    int xs[3]={x,x+4,x},ys[3]={y,y,y+4},a[4]={0,240,319,463};
    threat_draw_observe(s,f,t,p,depth,xs,ys,a);
}
int main(void){
    ThreatDrawState s={0},out;
    observe(&s,10,20,260,0xC7502427u,0,0);
    CHECK("known tracer is normalized to active draw area",s.count==1&&s.boxes[0].bounds[1]==20&&s.boxes[0].family==3);
    observe(&s,10,24,260,0xC7502427u,0,0);
    CHECK("touching sprite triangles cluster",s.count==1&&s.boxes[0].bounds[2]==28);
    observe(&s,10,90,260,0xC7502427u,0,0);
    CHECK("distant actors never become one scene-wide union",s.count==2);
    observe(&s,10,20,260,0xC7502427u,1,0);
    CHECK("palette ownership stays separate",s.count==3);
    observe(&s,10,150,260,0x46D3938Eu,0,0);
    CHECK("Uhu family is collected",s.count==4&&s.boxes[3].family==2);
    observe(&s,10,200,260,0x6BB2A2A3u,0x527B28B9u,0);
    CHECK("audited fighter upload and palette are collected",s.count==5&&s.boxes[4].family==1);
    observe(&s,10,204,260,0x05C32A1Eu,0x527B28B9u,0);
    CHECK("touching fighter parts join across native uploads",s.count==5);
    observe(&s,10,230,260,0x2294438Fu,0x527B28B9u,0);
    CHECK("shared CLUT cannot turn background into fighter geometry",s.count==5);
    observe(&s,10,250,260,0x1263A036u,0,0);
    CHECK("audited Greif source is an aim target",s.count==6&&s.boxes[5].family==4);
    observe(&s,10,230,260,1,2,0);observe(&s,10,230,260,0xC7502427u,0,1);
    CHECK("unrelated source and depth rejected",s.count==6);
    observe(&s,10,-50,260,0xC7502427u,0,0);
    CHECK("wholly clipped geometry rejected",s.count==6);
    threat_draw_snapshot(&s,10,1,&out);CHECK("fresh snapshot has bounded boxes",out.enabled&&out.valid&&out.count==6);
    threat_draw_snapshot(&s,11,1,&out);CHECK("empty next frame does not retain stale threats",out.enabled&&!out.valid&&!out.count);
    threat_draw_snapshot(&s,10,0,&out);CHECK("default off returns no geometry",!out.enabled&&!out.valid&&!out.count);
    threat_draw_commit(&s,11,1,&out);CHECK("VBlank counter increment retains completed enemy data",out.valid&&out.count==6&&out.frame==10&&out.age_frames==1&&!s.count);
    threat_draw_commit(&s,12,1,&out);CHECK("consumed working set cannot resurrect enemies next present",!out.count&&!out.valid&&out.frame==12);
    observe(&s,12,20,260,0xAB58BBA4u,0,0);CHECK("new frame resets clusters",s.count==1&&s.frame==12);
    memset(&s,0,sizeof s);
    for(unsigned i=0;i<THREAT_DRAW_MAX+4;++i)observe(&s,20,10,250,0xC7502427u,i,0);
    CHECK("capacity never exceeds fixed array and reports overflow",s.count==THREAT_DRAW_MAX&&s.dropped==4);
    memset(&s,0,sizeof s);
    observe(&s,30,200,260,0x38DC02FEu,0x3F675C0Du,0);
    observe(&s,30,204,260,0x1263A036u,0x6E78D825u,0);
    observe(&s,30,204,260,0x1263A036u,0x724442F7u,0);
    CHECK("touching arm housing and mount retain separate target geometry",s.count==3&&s.boxes[0].family==5&&s.boxes[1].family==4&&s.boxes[2].family==6);
    observe(&s,30,208,260,0xE27E0D6Au,0x724442F7u,0);
    CHECK("mount page and audited strip join only their own component",s.count==3&&s.boxes[2].family==6&&s.boxes[2].bounds[2]==212);
    CHECK("arm palette mismatch stays generic",threat_draw_family(0x38DC02FEu,0x724442F7u,0)==4);
    CHECK("mount strip requires exact palette and depth",threat_draw_family(0xE27E0D6Au,0,0)==0&&threat_draw_family(0xE27E0D6Au,0x724442F7u,1)==0);
    CHECK("all audited mount strips map",threat_draw_family(0xA0FF13ADu,0x724442F7u,0)==6&&threat_draw_family(0x67F52663u,0x724442F7u,0)==6&&threat_draw_family(0x8EB9EAC9u,0x724442F7u,0)==6);
    CHECK("new families have stable public names",strcmp(threat_draw_family_name(5),"greif_arm")==0&&strcmp(threat_draw_family_name(6),"greif_mount")==0&&strcmp(threat_draw_family_name(99),"unknown")==0);
    printf("RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
