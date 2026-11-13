#ifndef EIN_HERO_DRAW_TRACKER_H
#define EIN_HERO_DRAW_TRACKER_H
#include <stdint.h>
#include <string.h>
#include "gpu_gl_renderer.h"

/* Proven Mk.II hull uploads and their observed native palette. Engine/Gunpod
 * keys are absent: moving parts do not define the hull centre. */
typedef struct {
    uint64_t frame;
    unsigned draws;
    uint32_t texture_hash,palette_hash;
    int area[4], bounds[4];
} HeroDrawTracker;

static int hero_draw_key(uint32_t texture,uint32_t palette,unsigned depth) {
    if(depth!=0 || palette!=0x21FDE894u)return 0;
    return texture==0x724E77DAu || texture==0x7E3ADD56u ||
           texture==0xE2F3477Cu || texture==0xB16492B1u;
}
static void hero_draw_observe(HeroDrawTracker *s,uint64_t frame,
        uint32_t texture,uint32_t palette,unsigned depth,
        const int xs[3],const int ys[3],const int area[4]) {
    int b[4]={xs[0],ys[0],xs[0],ys[0]};
    if(!hero_draw_key(texture,palette,depth))return;
    if(area[0]<0 || area[1]<0 || area[2]>1023 || area[3]>511 ||
       area[2]-area[0]+1<128 || area[3]-area[1]+1<128)return;
    for(int i=1;i<3;++i){
        if(xs[i]<b[0])b[0]=xs[i];if(xs[i]>b[2])b[2]=xs[i];
        if(ys[i]<b[1])b[1]=ys[i];if(ys[i]>b[3])b[3]=ys[i];
    }
    if(b[2]<area[0] || b[0]>area[2] || b[3]<area[1] || b[1]>area[3])return;
    if(!s->draws || frame!=s->frame || memcmp(area,s->area,sizeof(s->area))){
        s->frame=frame;s->draws=0;memcpy(s->area,area,sizeof(s->area));
        memcpy(s->bounds,b,sizeof(b));
    }else{
        if(b[0]<s->bounds[0])s->bounds[0]=b[0];if(b[1]<s->bounds[1])s->bounds[1]=b[1];
        if(b[2]>s->bounds[2])s->bounds[2]=b[2];if(b[3]>s->bounds[3])s->bounds[3]=b[3];
    }
    ++s->draws;
    s->texture_hash=texture;s->palette_hash=palette;
}
static void hero_draw_snapshot(const HeroDrawTracker *s,uint64_t frame,int enabled,
        GlPlayerDrawState *out) {
    memset(out,0,sizeof(*out));out->enabled=enabled;
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
