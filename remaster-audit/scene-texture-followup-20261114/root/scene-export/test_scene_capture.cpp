#include "scene_capture.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <initializer_list>
static int checks, failures, calls;
#define CHECK(x) do { ++checks; if(!(x)){++failures;std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);} } while(0)
static PgxpView views[4];
static uint32_t addresses[4];
static int16_t rt[4][9];static int32_t tr[4][3];
static uint32_t transform_frame[4];static bool miss, missing_transform;
static uint32_t words[12];static int count;
static SceneDrawState state{0xabcde,-13,21,0,0,319,239,1,1,0,319,1};
static uint32_t hash(int i) {
    uint32_t h=2166136261u;
    auto mix=[&](uint32_t x){for(int j=0;j<4;++j){h^=(x>>(8*j))&255;h*=16777619u;}};
    for(auto x:rt[i])mix(uint16_t(x));for(auto x:tr[i])mix(uint32_t(x));
    mix(views[i].h);mix(uint32_t(views[i].ofx));mix(uint32_t(views[i].ofy));return h;
}
static void fix(int i) {
    views[i].xform_hash=hash(i);
    for(int a=0;a<3;++a){views[i].mac[a]=int64_t(tr[i][a])*4096;for(int b=0;b<3;++b)views[i].mac[a]+=int64_t(rt[i][a*3+b])*views[i].v[b];}
}
static int lookup(uint32_t a,uint32_t,PgxpView *out) {
    ++calls;if(miss)return PGXP_SRC_NATIVE;
    for(int i=0;i<4;++i)if(a==addresses[i]){*out=views[i];return PGXP_SRC_DATAFLOW;}
    return PGXP_SRC_NATIVE;
}
static int lookup_reason(uint32_t a,uint32_t w,PgxpView *out,int *why) {
    int rc=lookup(a,w,out);*why=rc==PGXP_SRC_DATAFLOW?PGXP_VIEW_MISS_NONE:PGXP_VIEW_MISS_NO_VIEW;return rc;
}
static int transform(uint64_t seq,int16_t out_rt[9],int32_t out_tr[3],uint32_t *frame,uint32_t *ra) {
    if(missing_transform||seq<1||seq>4)return 0;int i=int(seq)-1;
    std::memcpy(out_rt,rt[i],sizeof rt[i]);std::memcpy(out_tr,tr[i],sizeof tr[i]);*frame=transform_frame[i];*ra=0x80012340+i*4;return 1;
}
static void seed(uint8_t op,uint32_t frame=101) {
    std::memset(words,0,sizeof words);std::memset(views,0,sizeof views);std::memset(rt,0,sizeof rt);std::memset(tr,0,sizeof tr);
    const int n=(op&8)?4:3,stride=(op&16)?3:2;
    count=(op&16)?n*3:1+n*2;words[0]=(uint32_t(op)<<24)|0x123456;
    for(int i=0;i<n;++i){int p=1+i*stride;words[p]=uint32_t(160+i*4)|(uint32_t(120+(i&1)*8)<<16);
        words[p+1]=uint32_t(5+i*3)|(uint32_t(10+i*4)<<8);if(i&&(op&16))words[i*3]=0x654321+i;
        addresses[i]=0x1000+uint32_t(p)*4;auto &v=views[i];v.packed=words[p];v.frame=frame;v.rtp_seq=i+1;
        v.v[0]=int16_t(i*16);v.v[1]=int16_t((i&1)*32);v.v[2]=1024;v.h=256;v.ofx=160<<16;v.ofy=120<<16;
        v.x16=(160+i*4)<<16;v.y16=(120+(i&1)*8)<<16;v.sz3=1024;v.tag=uint32_t(i+1);
        v.flags=PGXP_VIEW_RTP_COMMITTED|PGXP_VIEW_SF;v.cmd=1;v.lane=0;rt[i][0]=rt[i][4]=rt[i][8]=4096;transform_frame[i]=frame;fix(i);}
    words[2]|=0x3210u<<16;words[(op&16)?5:4]|=0x01e5u<<16;miss=false;missing_transform=false;
}
// Existing contiguous controls plus explicit scatter/decrement cases below.
static int command_at(uint32_t token,uint32_t frame,const uint32_t *w,int count0,uint32_t base,const SceneDrawState *st) {
    uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=base==0xffffffffu?base:base+uint32_t(j)*4;
    return scene_capture_command(token,frame,w,count0,sources,st);
}
static int test_get(uint32_t token,uint32_t index,ScenePrimitive *out) {
    SceneCaptureInfo i{};if(int rc=scene_capture_info(token,&i))return rc;
    return scene_capture_get(token,index,i.generation,out);
}
static int test_json(uint32_t token,uint32_t index,char *out,size_t cap) {
    SceneCaptureInfo i{};if(int rc=scene_capture_info(token,&i))return rc;
    return scene_capture_json(token,index,i.generation,out,cap);
}
static void arm(uint32_t frame=100) { CHECK(scene_capture_cancel(7)==SCENE_OK);CHECK(scene_capture_arm(7,frame)==SCENE_OK); }
static ScenePrimitive capture(uint32_t frame=101,uint32_t address=0x1000) {
    CHECK(command_at(7,frame,words,count,address,&state)==SCENE_OK);
    CHECK(scene_capture_tick(7,frame+1)==SCENE_OK);ScenePrimitive p{};CHECK(test_get(7,0,&p)==SCENE_OK);return p;
}
static void expect_reason(int why) {
    auto p=capture();CHECK(!p.qualified);CHECK(p.vertex[0].reason==why);
}
int main(int argc,char **) {
    SceneCaptureSource src{lookup,transform,lookup_reason};CHECK(scene_capture_init(7,argc>1?0:1,&src)==SCENE_OK);
    if(argc>1){CHECK(scene_capture_arm(7,0)==SCENE_BAD_STATE);seed(0x24);CHECK(command_at(7,1,words,count,0x1000,&state)==SCENE_OK);CHECK(calls==0);
        SceneCaptureInfo i{};CHECK(scene_capture_info(7,&i)==SCENE_OK);CHECK(i.mode==SCENE_DISABLED);std::printf("checks %d failures %d\n",checks,failures);return failures?1:0;}
    CHECK(scene_capture_init(7,1,&src)==SCENE_BAD_STATE);
    CHECK(scene_capture_arm(8,0)==SCENE_WRONG_THREAD);
    for(int op=0x24;op<=0x3f;++op)if(op&4){seed(uint8_t(op));arm();ScenePrimitive p{};
        CHECK(test_get(7,0,&p)==SCENE_BAD_STATE);CHECK(command_at(7,100,words,count,0x1000,&state)==SCENE_OK);CHECK(calls==0);
        auto x=capture();CHECK(x.qualified);CHECK(x.opcode==op);CHECK(x.clut==0x3210&&x.tpage==0x1e5);CHECK(x.depth==3&&x.blend_mode==3);
        CHECK(x.raw_texture==(op&1)&&x.semi_trans==((op>>1)&1));CHECK(x.nverts==((op&8)?4:3));CHECK(x.word_count==count);
        CHECK(!std::memcmp(x.words,words,size_t(count)*4));CHECK(!std::memcmp(&x.state,&state,sizeof state));
        CHECK(x.indices[0]==0&&x.indices[1]==1&&x.indices[2]==2);if(op&8)CHECK(x.indices[3]==2&&x.indices[4]==1&&x.indices[5]==3);
        for(int j=0;j<x.nverts;++j){CHECK(x.vertex[j].address==addresses[j]);CHECK(x.vertex[j].caller_ra==0x80012340u+uint32_t(j)*4);}
        SceneCaptureInfo i{};CHECK(scene_capture_info(7,&i)==0);CHECK(i.complete&&i.count==1&&i.qualified==1);calls=0;}
    seed(0x24,100);arm();auto lag=capture();CHECK(lag.qualified&&lag.vertex[0].lag==1);
    seed(0x24,0xffffffffu);arm(0xffffffffu);auto wrap=capture(0);CHECK(wrap.qualified&&wrap.vertex[0].lag==1);
    seed(0x24,99);arm();expect_reason(SCENE_STALE);
    seed(0x24,102);arm();expect_reason(SCENE_STALE);
    seed(0x24);arm();views[0].packed^=1;expect_reason(SCENE_WORD_MISMATCH);
    seed(0x24);arm();views[0].flags=0;expect_reason(SCENE_UNCOMMITTED);
    for(uint32_t flag:{uint32_t(PGXP_VIEW_XY_SAT),uint32_t(PGXP_VIEW_MAC1_WRAP32),uint32_t(PGXP_VIEW_DOME)}) {
        seed(0x24);arm();views[0].flags|=uint16_t(flag);expect_reason(SCENE_DIVERGED);}
    seed(0x24);arm();views[0].lane=1;expect_reason(SCENE_COMMAND);
    seed(0x24);arm();missing_transform=true;expect_reason(SCENE_TRANSFORM_MISSING);
    seed(0x24);arm();transform_frame[0]--;expect_reason(SCENE_TRANSFORM_FRAME);
    seed(0x24);arm();views[0].xform_hash^=1;expect_reason(SCENE_TRANSFORM_HASH);
    seed(0x24);arm();views[0].mac[0]++;expect_reason(SCENE_MAC_MISMATCH);
    seed(0x24);arm();tr[1][0]++;fix(1);auto mixed=capture();CHECK(!mixed.qualified&&mixed.vertex[1].reason==SCENE_MIXED_TRANSFORM);
    seed(0x24);arm();miss=true;expect_reason(SCENE_LOOKUP_MISS);
    seed(0x24);arm();auto immediate=capture(101,0xffffffffu);CHECK(!immediate.qualified&&immediate.vertex[0].reason==SCENE_IMMEDIATE);
    seed(0x24);arm();CHECK(command_at(7,101,words,count-1,0x1000,&state)==SCENE_BAD_ARGUMENT);CHECK(scene_capture_tick(7,102)==0);
    SceneCaptureInfo i{};CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete&&i.malformed==1&&i.count==0);
    seed(0x24);arm();for(int j=0;j<SCENE_CAPACITY+1;++j)CHECK(command_at(7,101,words,count,0x1000,&state)==0);
    CHECK(scene_capture_tick(7,102)==0);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete&&i.overflow==1&&i.count==SCENE_CAPACITY);
    auto before=i;std::thread other([&]{SceneCaptureInfo wrong{};CHECK(scene_capture_cancel(8)==SCENE_WRONG_THREAD);CHECK(scene_capture_info(8,&wrong)==SCENE_WRONG_THREAD);});other.join();
    CHECK(scene_capture_info(7,&i)==0);CHECK(!std::memcmp(&before,&i,sizeof i));
    ScenePrimitive last{};CHECK(test_get(7,SCENE_CAPACITY-1,&last)==SCENE_BAD_STATE);CHECK(last.word_count==0);
    CHECK(test_get(7,SCENE_CAPACITY,&last)==SCENE_BAD_STATE);CHECK(last.word_count==0);
    seed(0x24);arm();command_at(7,103,words,count,0x1000,&state);scene_capture_tick(7,104);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete&&i.malformed==1);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);
    seed(0x24);arm();uint32_t env=0xe1000000;CHECK(command_at(7,101,&env,1,0xffffffffu,nullptr)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(scene_capture_info(7,&i)==0);CHECK(i.complete&&i.count==0&&i.other_commands==1);
    seed(0x3c);arm();capture();
    char json[8192];CHECK(test_json(7,0,json,sizeof json)==0);std::printf("RECORD %s\n",json);
    char tiny[2]={'x','x'};CHECK(test_json(7,0,tiny,sizeof tiny)==SCENE_BAD_ARGUMENT);CHECK(tiny[0]==0);
    CHECK(test_json(7,1,json,sizeof json)==SCENE_BAD_STATE);CHECK(json[0]==0);
    CHECK(test_json(7,0,nullptr,100)==SCENE_BAD_ARGUMENT);
    // A GP0 primitive may span linked-list nodes or decrementing DMA.
    // Never derive individual vertex addresses from its first word.
    for(int kind=0;kind<3;++kind) {
        seed(0x3c);arm();uint32_t sources[12];
        for(int j=0;j<12;++j)sources[j]=kind==0?0x4000-uint32_t(j)*4:0x4000+uint32_t(j)*0x100;
        if(kind==2)sources[0]=0xffffffffu; // immediate header, but tracked vertices
        for(int j=0;j<4;++j)addresses[j]=sources[1+j*3];
        CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
        ScenePrimitive q{};CHECK(test_get(7,0,&q)==0);CHECK(q.qualified);
        CHECK(!std::memcmp(q.word_sources,sources,size_t(count)*4));
        for(int j=0;j<4;++j)CHECK(q.vertex[j].address==addresses[j]);
    }
    seed(0x24);arm();uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=0x1000+uint32_t(j)*4;
    sources[3]=0xffffffffu;
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    ScenePrimitive partial{};CHECK(test_get(7,0,&partial)==0);CHECK(!partial.qualified&&partial.vertex[1].reason==SCENE_IMMEDIATE);
    seed(0x24);arm();sources[3]=0x100d;
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&partial)==0);CHECK(!partial.qualified&&partial.vertex[1].reason==SCENE_INVALID_ADDRESS);
    // Generation, complete-only reads and lifecycle boundaries.
    seed(0x24);arm();SceneCaptureInfo gen{};CHECK(scene_capture_info(7,&gen)==0);
    CHECK(scene_capture_arm(7,100)==SCENE_BAD_STATE);
    CHECK(command_at(7,101,words,count,0x1000,&state)==0);
    CHECK(scene_capture_arm(7,101)==SCENE_BAD_STATE);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);
    CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,0,&last)==0);CHECK(last.eligible_triangle_mask==1);
    const uint32_t old_generation=gen.generation;
    arm();CHECK(command_at(7,101,words,count,0x1000,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(scene_capture_get(7,0,old_generation,&last)==SCENE_BAD_STATE);CHECK(last.word_count==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.generation!=old_generation);
    seed(0x24);arm();views[0].flags&=uint16_t(~PGXP_VIEW_SF);expect_reason(SCENE_DIVERGED);
    for(int depth=0;depth<3;++depth)for(int blend=0;blend<4;++blend) {
        seed(0x34);arm();words[5]=(words[5]&0xffffu)|(uint32_t((depth<<7)|(blend<<5))<<16);
        auto q=capture();CHECK(q.depth==depth&&q.blend_mode==blend);
        for(int j=0;j<3;++j){CHECK(q.vertex[j].u==5+j*3&&q.vertex[j].v==10+j*4);CHECK(q.vertex[j].rgb==(j?0x654321u+uint32_t(j):0x123456u));}
    }
    // Per-half oversize and native signed 11-bit coordinates, independent of provenance.
    seed(0x2c);arm();const int xs[4]={-600,600,-600,-500};
    for(int j=0;j<4;++j){words[1+j*2]=(words[1+j*2]&0xffff0000u)|uint16_t(xs[j]);views[j].packed=words[1+j*2];}
    auto oversize=capture();CHECK(oversize.oversize_mask==3&&oversize.eligible_triangle_mask==0);CHECK(oversize.vertex[0].native_x==-600);
    seed(0x2c);arm();words[7]=(words[7]&0xffff0000u)|uint16_t(-1000);views[3].packed=words[7];
    auto half=capture();CHECK(half.oversize_mask==2&&half.eligible_triangle_mask==1);
    seed(0x24);arm();SceneDrawState outside=state;outside.effective_left=500;outside.effective_right=700;
    CHECK(command_at(7,101,words,count,0x1000,&outside)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.clip_out_mask==1&&last.eligible_triangle_mask==0);
    seed(0x24);arm();outside=state;outside.native_screen_mapping=0;
    CHECK(command_at(7,101,words,count,0x1000,&outside)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.screen_mapping_known==0&&last.eligible_triangle_mask==0);
    // Mixed valid ages are explicit and ineligible for rendering until qualified.
    seed(0x24);arm();views[0].frame=100;transform_frame[0]=100;
    auto mixed_age=capture();CHECK(mixed_age.qualified&&mixed_age.mixed_lag&&mixed_age.eligible_triangle_mask==0);
    CHECK(scene_capture_info(7,&i)==0);CHECK(i.lag0_vertices==2&&i.lag1_vertices==1&&i.mixed_lag_primitives==1);
    // Omitted drawing families cannot silently become full geometry coverage.
    seed(0x24);arm();for(int op:{0x20,0x64,0x60,0x48,0x02}) {
        uint32_t cmd=uint32_t(op)<<24;CHECK(command_at(7,101,&cmd,1,0xffffffffu,nullptr)==0);
    }
    CHECK(scene_capture_tick(7,102)==0);CHECK(scene_capture_info(7,&i)==0);
    CHECK(i.complete&&!i.geometry_types_complete&&i.untextured_polygons==1&&i.textured_sprites==1&&i.untextured_rects==1&&i.lines==1&&i.vram_fills==1);
    seed(0x24);arm();for(int j=0;j<SCENE_CAPACITY;++j)CHECK(command_at(7,101,words,count,0x1000,&state)==0);
    CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,SCENE_CAPACITY-1,&last)==0);
    seed(0x24);arm();CHECK(command_at(7,101,words,13,0x1000,&state)==SCENE_BAD_ARGUMENT);CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);
    seed(0x24);arm();CHECK(command_at(7,101,words,count,0x1000,nullptr)==SCENE_BAD_ARGUMENT);
    CHECK(scene_capture_tick(7,99)==0);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete);
    seed(0x3c,100);arm();for(int j=0;j<12;++j)sources[j]=0x1000+uint32_t(j)*4;sources[1]=0xffffffffu;
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(!last.qualified&&!last.mixed_lag&&last.eligible_triangle_mask==2);
    seed(0x3c,100);arm();tr[3][0]++;fix(3);
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.eligible_triangle_mask==0);
    std::printf("checks %d failures %d record_bytes %zu bounded_storage %zu\n",checks,failures,sizeof(ScenePrimitive),sizeof(ScenePrimitive)*SCENE_CAPACITY);
    return failures?1:0;
}
