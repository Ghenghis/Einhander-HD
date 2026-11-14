#include "scene_capture.h"
#include <cstdarg>
#include <cstdio>
extern "C" int scene_capture_json(uint32_t token,uint32_t index,char *out,size_t cap) {
    if(!out||!cap)return SCENE_BAD_ARGUMENT;
    out[0]=0;
    ScenePrimitive p{};int rc=scene_capture_get(token,index,&p);if(rc)return rc;
    size_t used=0;bool good=true;
    auto add=[&](const char *fmt,...) {
        if(!good)return;
        va_list ap;va_start(ap,fmt);int n=std::vsnprintf(out+used,cap-used,fmt,ap);va_end(ap);
        if(n<0||size_t(n)>=cap-used){good=false;out[0]=0;return;}used+=size_t(n);
    };
    add("{\"frame\":%u,\"ordinal\":%u,\"source\":%u,\"opcode\":%u,\"geometry_qualified\":%s,\"nverts\":%u,\"words\":[",p.frame,p.ordinal,p.source_address,p.opcode,p.qualified?"true":"false",p.nverts);
    for(int i=0;i<p.word_count;++i)add("%s%u",i?",":"",p.words[i]);
    add("],\"word_sources\":[");for(int i=0;i<p.word_count;++i)add("%s%u",i?",":"",p.word_sources[i]);
    add("],\"indices\":[");for(int i=0;i<p.triangle_count*3;++i)add("%s%u",i?",":"",p.indices[i]);
    add("],\"material\":{\"clut\":%u,\"tpage\":%u,\"depth\":%u,\"blend\":%u,\"raw\":%u,\"semi\":%u,\"window\":%u,\"set_mask\":%u,\"check_mask\":%u},",p.clut,p.tpage,p.depth,p.blend_mode,p.raw_texture,p.semi_trans,p.state.texture_window,p.state.set_mask,p.state.check_mask);
    add("\"draw_offset\":[%d,%d],\"draw_area\":[%u,%u,%u,%u],\"vertices\":[",p.state.draw_offset_x,p.state.draw_offset_y,p.state.draw_left,p.state.draw_top,p.state.draw_right,p.state.draw_bottom);
    for(int i=0;i<p.nverts;++i) {
        const auto &v=p.vertex[i];const auto &q=v.view;
        add("%s{\"address\":%u,\"word\":%u,\"rgb\":%u,\"uv\":[%u,%u],\"reason\":%u,\"lag\":%u,\"source_frame\":%u,\"rtp_seq_hex\":\"%016llx\",\"tag\":%u,\"flags\":%u,\"cmd\":%u,\"lane\":%u,\"model\":[%d,%d,%d],",i?",":"",v.address,v.packet_word,v.rgb,v.u,v.v,v.reason,v.lag,q.frame,(unsigned long long)q.rtp_seq,q.tag,q.flags,q.cmd,q.lane,q.v[0],q.v[1],q.v[2]);
        add("\"screen16\":[%d,%d],\"packed\":%u,\"mac\":[%lld,%lld,%lld],\"h\":%u,\"of\":[%d,%d],\"sz3\":%u,\"xform_hash\":%u,\"caller_ra\":%u,\"combined_rt\":[",q.x16,q.y16,q.packed,(long long)q.mac[0],(long long)q.mac[1],(long long)q.mac[2],q.h,q.ofx,q.ofy,q.sz3,q.xform_hash,v.caller_ra);
        for(int a=0;a<9;++a)add("%s%d",a?",":"",v.rt[a]);
        add("],\"combined_tr\":[%d,%d,%d]}",v.tr[0],v.tr[1],v.tr[2]);
    }
    add("]}");return good?SCENE_OK:SCENE_BAD_ARGUMENT;
}
