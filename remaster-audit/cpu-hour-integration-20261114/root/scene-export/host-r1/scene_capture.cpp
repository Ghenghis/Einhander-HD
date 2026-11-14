#include "scene_capture.h"
#include <atomic>
#include <cstring>
namespace {
std::atomic<uint32_t> owner{0};
SceneCaptureSource source{};
SceneCaptureInfo info{};
ScenePrimitive records[SCENE_CAPACITY];
uint32_t armed_frame;
bool initialized;
int guard(uint32_t token) {
    return token && owner.load(std::memory_order_acquire)==token ? SCENE_OK : SCENE_WRONG_THREAD;
}
uint32_t xform_hash(const SceneVertex &v) {
    uint32_t h=2166136261u;
    auto mix=[&](uint32_t w){for(int i=0;i<4;++i){h^=(w>>(i*8))&255u;h*=16777619u;}};
    for(auto w:v.rt)mix(uint16_t(w));
    for(auto w:v.tr)mix(uint32_t(w));
    mix(v.view.h);mix(uint32_t(v.view.ofx));mix(uint32_t(v.view.ofy));return h;
}
void qualify(SceneVertex &v,uint32_t frame) {
    v.reason=SCENE_IMMEDIATE;
    if(v.address==0xffffffffu)return;
    v.reason=SCENE_LOOKUP_MISS;
    if(source.lookup(v.address,v.packet_word,&v.view)!=PGXP_SRC_DATAFLOW)return;
    const auto &p=v.view;
    v.reason=SCENE_WORD_MISMATCH;if(p.packed!=v.packet_word)return;
    uint32_t lag=frame-p.frame;
    v.reason=SCENE_STALE;if(lag>1)return;v.lag=uint8_t(lag);
    v.reason=SCENE_UNCOMMITTED;if(!(p.flags&PGXP_VIEW_RTP_COMMITTED))return;
    v.reason=SCENE_DIVERGED;
    if((p.flags&(PGXP_VIEW_NATIVE_DIVERGED|PGXP_VIEW_WS_SQUASH|PGXP_VIEW_DOME))||!p.h||p.mac[2]<=0)return;
    v.reason=SCENE_COMMAND;if(!((p.cmd==1&&p.lane==0)||(p.cmd==0x30&&p.lane<3)))return;
    uint32_t transform_frame=0;
    v.reason=SCENE_TRANSFORM_MISSING;
    if(!source.transform(p.rtp_seq,v.rt,v.tr,&transform_frame,&v.caller_ra))return;
    v.reason=SCENE_TRANSFORM_FRAME;if(transform_frame!=p.frame)return;
    v.reason=SCENE_TRANSFORM_HASH;if(xform_hash(v)!=p.xform_hash)return;
    v.reason=SCENE_MAC_MISMATCH;
    for(int a=0;a<3;++a) {
        int64_t mac=int64_t(v.tr[a])*4096;
        for(int b=0;b<3;++b)mac+=int64_t(v.rt[a*3+b])*p.v[b];
        if(mac!=p.mac[a])return;
    }
    v.reason=SCENE_VERTEX_OK;
}
}
extern "C" int scene_capture_init(uint32_t token,int enabled,const SceneCaptureSource *s) {
    if(!token||(enabled!=0&&enabled!=1)||!s||!s->lookup||!s->transform)return SCENE_BAD_ARGUMENT;
    uint32_t expected=0;
    if(!owner.compare_exchange_strong(expected,token,std::memory_order_acq_rel)&&expected!=token)return SCENE_WRONG_THREAD;
    if(initialized)return SCENE_BAD_STATE; /* no source mutation / mode-reset race */
    source=*s;info={};info.mode=enabled?SCENE_IDLE:SCENE_DISABLED;info.capacity=SCENE_CAPACITY;
    initialized=true;return SCENE_OK;
}
extern "C" int scene_capture_arm(uint32_t token,uint32_t frame) {
    if(int e=guard(token))return e;
    if(!initialized||info.mode==SCENE_DISABLED||info.mode==SCENE_ARMED||info.mode==SCENE_RECORDING)return SCENE_BAD_STATE;
    info={};info.mode=SCENE_ARMED;info.capacity=SCENE_CAPACITY;armed_frame=frame;
    return SCENE_OK;
}
extern "C" int scene_capture_cancel(uint32_t token) {
    if(int e=guard(token))return e;
    if(info.mode==SCENE_DISABLED)return SCENE_BAD_STATE;
    info={};info.mode=SCENE_IDLE;info.capacity=SCENE_CAPACITY;return SCENE_OK;
}
extern "C" int scene_capture_tick(uint32_t token,uint32_t frame) {
    if(int e=guard(token))return e;
    if(info.mode==SCENE_ARMED&&frame!=armed_frame) {
        if(uint32_t(frame-armed_frame)!=1)++info.malformed;
        info.frame=frame;info.mode=SCENE_RECORDING;
    } else if(info.mode==SCENE_RECORDING&&frame!=info.frame) {
        info.mode=SCENE_SEALED;
        info.complete=uint8_t(!info.overflow&&!info.malformed&&uint32_t(frame-info.frame)==1);
    }
    return SCENE_OK;
}
extern "C" int scene_capture_command(uint32_t token,uint32_t frame,const uint32_t *w,int n,uint32_t address,const SceneDrawState *state) {
    if(int e=guard(token))return e;
    scene_capture_tick(token,frame);
    if(info.mode!=SCENE_RECORDING)return SCENE_OK;
    if(!w||n<1){++info.malformed;return SCENE_BAD_ARGUMENT;}
    const uint8_t op=uint8_t(w[0]>>24);
    if(op<0x20||op>0x3f||!(op&4)){++info.other_commands;return SCENE_OK;}
    ++info.textured_seen;
    if(n>SCENE_WORDS||!state){++info.malformed;return SCENE_BAD_ARGUMENT;}
    const int verts=(op&8)?4:3, stride=(op&16)?3:2;
    const int expected=(op&16)?verts*3:1+verts*2;
    if(n!=expected||(address!=0xffffffffu&&((address&3u)||address>0xffffffd3u))) {
        ++info.malformed;return SCENE_BAD_ARGUMENT;
    }
    if(info.count==SCENE_CAPACITY){++info.overflow;return SCENE_OK;}
    auto &p=records[info.count++];p={};p.state=*state;p.source_address=address;
    p.frame=frame;p.ordinal=info.textured_seen-1;p.word_count=uint8_t(n);p.nverts=uint8_t(verts);p.opcode=op;
    std::memcpy(p.words,w,size_t(n)*sizeof(uint32_t));p.clut=uint16_t(w[2]>>16);
    p.tpage=uint16_t(w[(op&16)?5:4]>>16);
    p.depth=uint8_t((p.tpage>>7)&3);p.blend_mode=uint8_t((p.tpage>>5)&3);
    p.raw_texture=op&1;p.semi_trans=(op>>1)&1;p.qualified=1;
    p.triangle_count=uint8_t(verts-2);const uint8_t ix[6]={0,1,2,2,1,3};std::memcpy(p.indices,ix,verts==4?6:3);
    for(int i=0;i<verts;++i) {
        auto &v=p.vertex[i];int pos=1+i*stride;
        v.packet_word=w[pos];v.address=address==0xffffffffu?address:address+uint32_t(pos)*4;
        v.rgb=w[(op&16)?i*3:0]&0xffffffu;v.u=uint8_t(w[pos+1]);v.v=uint8_t(w[pos+1]>>8);
        qualify(v,frame);
        if(v.reason==SCENE_VERTEX_OK&&i&&p.vertex[0].reason==SCENE_VERTEX_OK) {
            const auto &first=p.vertex[0];
            if(std::memcmp(v.rt,first.rt,sizeof v.rt)||std::memcmp(v.tr,first.tr,sizeof v.tr)||
               v.view.h!=first.view.h||v.view.ofx!=first.view.ofx||v.view.ofy!=first.view.ofy)
                v.reason=SCENE_MIXED_TRANSFORM;
        }
        if(v.reason!=SCENE_VERTEX_OK){p.qualified=0;++info.missing_vertices;}
    }
    if(p.qualified)++info.qualified;
    return SCENE_OK;
}
extern "C" int scene_capture_info(uint32_t token,SceneCaptureInfo *out) {
    if(int e=guard(token))return e;
    if(!out)return SCENE_BAD_ARGUMENT;*out=info;return SCENE_OK;
}
extern "C" int scene_capture_get(uint32_t token,uint32_t index,ScenePrimitive *out) {
    if(int e=guard(token))return e;
    if(!out)return SCENE_BAD_ARGUMENT;
    *out={};
    if(info.mode!=SCENE_SEALED||index>=info.count)return SCENE_BAD_STATE;
    *out=records[index];return SCENE_OK;
}
