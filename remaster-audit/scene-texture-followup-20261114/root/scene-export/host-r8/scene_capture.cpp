#include "scene_capture.h"
#include <atomic>
#include <cstring>
namespace {
std::atomic<uint32_t> owner{0};
SceneCaptureSource source{};
SceneCaptureInfo info{};
ScenePrimitive records[SCENE_CAPACITY];
uint32_t armed_frame;
uint32_t generation;
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
    v.reason=SCENE_INVALID_ADDRESS;if(v.address&3u)return;
    v.reason=SCENE_LOOKUP_MISS;
    int lookup_rc;
    v.lookup_miss_reason=-1;
    if(source.lookup_reason)lookup_rc=source.lookup_reason(v.address,v.packet_word,&v.view,&v.lookup_miss_reason);
    else lookup_rc=source.lookup(v.address,v.packet_word,&v.view);
    if(lookup_rc!=PGXP_SRC_DATAFLOW)return;
    v.lookup_miss_reason=PGXP_VIEW_MISS_NONE;
    const auto &p=v.view;
    v.reason=SCENE_WORD_MISMATCH;if(p.packed!=v.packet_word)return;
    uint32_t lag=frame-p.frame;
    v.reason=SCENE_STALE;if(lag>1)return;v.lag=uint8_t(lag);
    v.reason=SCENE_UNCOMMITTED;if(!(p.flags&PGXP_VIEW_RTP_COMMITTED))return;
    v.reason=SCENE_DIVERGED;
    if(!(p.flags&PGXP_VIEW_SF)||(p.flags&(PGXP_VIEW_NATIVE_DIVERGED|PGXP_VIEW_WS_SQUASH|PGXP_VIEW_DOME))||!p.h||p.mac[2]<=0)return;
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
    if(generation==0x7fffffffu)return SCENE_BAD_STATE; /* never wrap an RPC generation */
    info={};info.mode=SCENE_ARMED;info.capacity=SCENE_CAPACITY;armed_frame=frame;info.generation=++generation;
    return SCENE_OK;
}
extern "C" int scene_capture_cancel(uint32_t token) {
    if(int e=guard(token))return e;
    if(info.mode==SCENE_DISABLED)return SCENE_BAD_STATE;
    info={};info.mode=SCENE_IDLE;info.capacity=SCENE_CAPACITY;info.generation=generation;return SCENE_OK;
}
extern "C" int scene_capture_tick(uint32_t token,uint32_t frame) {
    if(int e=guard(token))return e;
    if(info.mode==SCENE_ARMED&&frame!=armed_frame) {
        if(uint32_t(frame-armed_frame)!=1)++info.malformed;
        info.frame=frame;info.mode=SCENE_RECORDING;
    } else if(info.mode==SCENE_RECORDING&&frame!=info.frame) {
        info.mode=SCENE_SEALED;
        info.complete=uint8_t(!info.overflow&&!info.malformed&&uint32_t(frame-info.frame)==1);
        info.geometry_types_complete=uint32_t(info.complete&&!info.untextured_polygons&&!info.textured_sprites&&!info.untextured_rects&&!info.lines&&!info.vram_fills);
    }
    return SCENE_OK;
}
extern "C" int scene_capture_command(uint32_t token,uint32_t frame,const uint32_t *w,int n,const uint32_t *addresses,const SceneDrawState *state) {
    if(int e=guard(token))return e;
    scene_capture_tick(token,frame);
    if(info.mode!=SCENE_RECORDING)return SCENE_OK;
    if(!w||n<1){++info.malformed;return SCENE_BAD_ARGUMENT;}
    const uint8_t op=uint8_t(w[0]>>24);
    if(op<0x20||op>0x3f||!(op&4)) {
        if(op>=0x20&&op<=0x3f)++info.untextured_polygons;
        else if(op>=0x60&&op<=0x7f){if(op&4)++info.textured_sprites;else ++info.untextured_rects;}
        else if(op>=0x40&&op<=0x5f)++info.lines;
        else if(op==2)++info.vram_fills;
        else ++info.other_commands;
        return SCENE_OK;
    }
    ++info.textured_seen;
    if(n>SCENE_WORDS||!state||!addresses){++info.malformed;return SCENE_BAD_ARGUMENT;}
    const int verts=(op&8)?4:3, stride=(op&16)?3:2;
    const int expected=(op&16)?verts*3:1+verts*2;
    if(n!=expected) {
        ++info.malformed;return SCENE_BAD_ARGUMENT;
    }
    if(info.count==SCENE_CAPACITY){++info.overflow;return SCENE_OK;}
    auto &p=records[info.count++];p={};p.state=*state;p.source_address=addresses[0];
    p.frame=frame;p.ordinal=info.textured_seen-1;p.generation=info.generation;p.word_count=uint8_t(n);p.nverts=uint8_t(verts);p.opcode=op;
    std::memcpy(p.words,w,size_t(n)*sizeof(uint32_t));std::memcpy(p.word_sources,addresses,size_t(n)*sizeof(uint32_t));p.clut=uint16_t(w[2]>>16);
    p.tpage=uint16_t(w[(op&16)?5:4]>>16);
    p.depth=uint8_t((p.tpage>>7)&3);p.blend_mode=uint8_t((p.tpage>>5)&3);
    p.raw_texture=op&1;p.semi_trans=(op>>1)&1;p.qualified=1;
    p.triangle_count=uint8_t(verts-2);const uint8_t ix[6]={0,1,2,2,1,3};std::memcpy(p.indices,ix,verts==4?6:3);
    int first_valid_lag=-1;
    for(int i=0;i<verts;++i) {
        auto &v=p.vertex[i];int pos=1+i*stride;
        v.packet_word=w[pos];v.address=addresses[pos];
        v.native_x=int32_t(v.packet_word&0x7ffu);if(v.native_x&0x400)v.native_x-=0x800;
        v.native_y=int32_t((v.packet_word>>16)&0x7ffu);if(v.native_y&0x400)v.native_y-=0x800;
        v.rgb=w[(op&16)?i*3:0]&0xffffffu;v.u=uint8_t(w[pos+1]);v.v=uint8_t(w[pos+1]>>8);
        qualify(v,frame);
        if(v.reason==SCENE_VERTEX_OK) {
            if(v.lag)++info.lag1_vertices;else ++info.lag0_vertices;
            if(first_valid_lag<0)first_valid_lag=v.lag;
            else if(v.lag!=first_valid_lag)p.mixed_lag=1;
        }
        if(v.view.flags&PGXP_VIEW_WS_SQUASH)++info.ws_rejected_vertices;
        if(v.reason==SCENE_VERTEX_OK&&i&&p.vertex[0].reason==SCENE_VERTEX_OK) {
            const auto &first=p.vertex[0];
            if(std::memcmp(v.rt,first.rt,sizeof v.rt)||std::memcmp(v.tr,first.tr,sizeof v.tr)||
               v.view.h!=first.view.h||v.view.ofx!=first.view.ofx||v.view.ofy!=first.view.ofy)
                v.reason=SCENE_MIXED_TRANSFORM;
        }
        if(v.reason!=SCENE_VERTEX_OK){p.qualified=0;++info.missing_vertices;}
    }
    p.screen_mapping_known=state->native_screen_mapping;
    for(int t=0;t<p.triangle_count;++t) {
        int minx=0x7fffffff,maxx=-0x7fffffff,miny=0x7fffffff,maxy=-0x7fffffff;
        bool provenance=true;
        const auto &reference=p.vertex[p.indices[t*3]];
        for(int j=0;j<3;++j) {
            const auto &v=p.vertex[p.indices[t*3+j]];
            if(v.native_x<minx)minx=v.native_x;if(v.native_x>maxx)maxx=v.native_x;
            if(v.native_y<miny)miny=v.native_y;if(v.native_y>maxy)maxy=v.native_y;
            if(v.reason!=SCENE_VERTEX_OK)provenance=false;
            if(std::memcmp(v.rt,reference.rt,sizeof v.rt)||std::memcmp(v.tr,reference.tr,sizeof v.tr)||
               v.view.h!=reference.view.h||v.view.ofx!=reference.view.ofx||v.view.ofy!=reference.view.ofy)provenance=false;
        }
        if(maxx-minx>1023||maxy-miny>511)p.oversize_mask|=uint8_t(1u<<t);
        const bool outside=state->effective_left>state->effective_right||state->draw_top>state->draw_bottom||
                           int64_t(maxx)+state->draw_offset_x<state->effective_left||int64_t(minx)+state->draw_offset_x>state->effective_right||
                           int64_t(maxy)+state->draw_offset_y<state->draw_top||int64_t(miny)+state->draw_offset_y>state->draw_bottom;
        if(p.screen_mapping_known&&outside)p.clip_out_mask|=uint8_t(1u<<t);
        if(provenance&&p.screen_mapping_known&&!p.mixed_lag&&!(p.oversize_mask&(1u<<t))&&!(p.clip_out_mask&(1u<<t)))p.eligible_triangle_mask|=uint8_t(1u<<t);
    }
    if(p.mixed_lag)++info.mixed_lag_primitives;
    if(p.qualified)++info.qualified;
    return SCENE_OK;
}
extern "C" int scene_capture_info(uint32_t token,SceneCaptureInfo *out) {
    if(int e=guard(token))return e;
    if(!out)return SCENE_BAD_ARGUMENT;*out=info;return SCENE_OK;
}
extern "C" int scene_capture_get(uint32_t token,uint32_t index,uint32_t expected_generation,ScenePrimitive *out) {
    if(int e=guard(token))return e;
    if(!out)return SCENE_BAD_ARGUMENT;
    *out={};
    if(info.mode!=SCENE_SEALED||!info.complete||expected_generation!=info.generation||index>=info.count)return SCENE_BAD_STATE;
    *out=records[index];return SCENE_OK;
}
