#ifndef EIN_HERO_DRAW_TRACKER_H
#define EIN_HERO_DRAW_TRACKER_H
#include <stdint.h>
#include <string.h>
#include "gpu_gl_renderer.h"

/* Proven starter hull uploads and their observed native palettes. Engine/Gunpod
 * keys are absent: moving parts do not define the hull centre. */
typedef struct {
    uint64_t frame;
    unsigned draws;
    uint32_t texture_hash,palette_hash;
    int area[4], bounds[4],source_set;
} HeroDrawTracker;

/* A draw-clock landmark, not enemy visibility or collision geometry. Source
 * CRCs identify the two audited Greif pages; colour phases share ownership. */
typedef struct { uint64_t first,last;int seen; } GreifDrawClock;
static void greif_draw_observe(GreifDrawClock *s,uint64_t frame,uint32_t texture,
        unsigned depth,unsigned width,unsigned height,const int xs[3],const int ys[3],const int area[4]) {
    if(depth || width!=64 || height!=256 ||
       (texture!=0x1263A036u && texture!=0x38DC02FEu))return;
    if(area[0]<0 || area[1]<0 || area[2]>1023 || area[3]>511 ||
       area[2]-area[0]+1<128 || area[3]-area[1]+1<128)return;
    int l=xs[0],r=xs[0],t=ys[0],b=ys[0];
    for(int i=0;i<3;++i){
        if(xs[i]<-4096 || xs[i]>4095 || ys[i]<-4096 || ys[i]>4095)return;
        if(xs[i]<l)l=xs[i];if(xs[i]>r)r=xs[i];if(ys[i]<t)t=ys[i];if(ys[i]>b)b=ys[i];
    }
    if(r<area[0] || l>area[2] || b<area[1] || t>area[3] ||
       ((int64_t)xs[1]-xs[0])*(ys[2]-ys[0])==((int64_t)xs[2]-xs[0])*(ys[1]-ys[0]))return;
    if(!s->seen || frame<s->last || frame-s->last>150)s->first=frame;
    s->last=frame;s->seen=1;
}
static void greif_draw_snapshot(const GreifDrawClock *s,uint64_t frame,int enabled,GlPlayerDrawState *out) {
    out->greif_first_frame=s->first;out->greif_last_frame=s->last;
    out->greif_age_frames=s->seen&&frame>=s->last?frame-s->last:UINT64_MAX;
    out->greif_valid=enabled&&s->seen&&out->greif_age_frames<=12;
}

static int hero_draw_key(uint32_t texture,uint32_t palette,unsigned depth) {
    if(depth!=0 || palette!=0x21FDE894u)return 0;
    return texture==0x724E77DAu || texture==0x7E3ADD56u ||
           texture==0xE2F3477Cu || texture==0xB16492B1u;
}
static int hero_draw_key_for_craft(uint32_t texture,uint32_t palette,unsigned depth,int craft) {
    if(craft==2)return hero_draw_key(texture,palette,depth);
    if(depth!=0)return 0;
    if(craft==3)return palette==0x21FDE894u &&
        (texture==0x724E77DAu || texture==0xE2F3477Cu || texture==0x8FE8B060u || texture==0xC6E8710Bu);
    if(craft==4)return
        (palette==0xEF213D7Fu && (texture==0x6ACFACE4u || texture==0x8CD3F840u)) ||
        (palette==0x9414AA42u && (texture==0x0878817Du || texture==0x8E818661u)) ||
        (palette==0xDE4ECDD2u && texture==0x0A0CE3A4u);
    return 0;
}
static void hero_draw_observe_for_craft(HeroDrawTracker *s,uint64_t frame,
        uint32_t texture,uint32_t palette,unsigned depth,
        const int xs[3],const int ys[3],const int area[4],int craft) {
    int b[4]={xs[0],ys[0],xs[0],ys[0]};
    if(!hero_draw_key_for_craft(texture,palette,depth,craft))return;
    if(area[0]<0 || area[1]<0 || area[2]>1023 || area[3]>511 ||
       area[2]-area[0]+1<128 || area[3]-area[1]+1<128)return;
    for(int i=1;i<3;++i){
        if(xs[i]<b[0])b[0]=xs[i];if(xs[i]>b[2])b[2]=xs[i];
        if(ys[i]<b[1])b[1]=ys[i];if(ys[i]>b[3])b[3]=ys[i];
    }
    if(b[2]<area[0] || b[0]>area[2] || b[3]<area[1] || b[1]>area[3])return;
    if(!s->draws || frame!=s->frame || s->source_set!=craft || memcmp(area,s->area,sizeof(s->area))){
        s->frame=frame;s->draws=0;memcpy(s->area,area,sizeof(s->area));
        memcpy(s->bounds,b,sizeof(b));
        s->source_set=craft;
    }else{
        if(b[0]<s->bounds[0])s->bounds[0]=b[0];if(b[1]<s->bounds[1])s->bounds[1]=b[1];
        if(b[2]>s->bounds[2])s->bounds[2]=b[2];if(b[3]>s->bounds[3])s->bounds[3]=b[3];
    }
    ++s->draws;
    s->texture_hash=texture;s->palette_hash=palette;
}
static void hero_draw_observe(HeroDrawTracker *s,uint64_t frame,
        uint32_t texture,uint32_t palette,unsigned depth,
        const int xs[3],const int ys[3],const int area[4]) {
    hero_draw_observe_for_craft(s,frame,texture,palette,depth,xs,ys,area,2);
}
static void hero_draw_snapshot(const HeroDrawTracker *s,uint64_t frame,int enabled,
        GlPlayerDrawState *out) {
    memset(out,0,sizeof(*out));out->enabled=enabled;out->source_set=s->source_set;
    if(!s->draws)return;
    out->frame=s->frame;out->age_frames=frame>=s->frame?frame-s->frame:UINT64_MAX;
    out->draws=s->draws;out->width=s->area[2]-s->area[0]+1;out->height=s->area[3]-s->area[1]+1;
    out->texture_hash=s->texture_hash;out->palette_hash=s->palette_hash;
    out->min_x=s->bounds[0]-s->area[0];out->min_y=s->bounds[1]-s->area[1];
    out->max_x=s->bounds[2]-s->area[0];out->max_y=s->bounds[3]-s->area[1];
    out->valid=enabled && out->age_frames<=12 &&
        out->max_x>out->min_x && out->max_x-out->min_x<out->width/2 &&
        out->max_y>out->min_y && out->max_y-out->min_y<out->height/2;
}
#endif
