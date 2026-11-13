#ifndef EIN_THREAT_DRAW_TRACKER_H
#define EIN_THREAT_DRAW_TRACKER_H
#include <stdint.h>
#include <string.h>

/* Source-query bounds, not object identity, occlusion or collision geometry.
 * Only audited source families are collected. Coverage is intentionally partial.
 * Frame-local clustering joins touching triangles without joining distant actors.
 * No RAM access, allocation, GPU calls, retained pointers or disk I/O. */
#define THREAT_DRAW_MAX 64
typedef struct { int family,bounds[4];uint32_t texture,palette; } ThreatDrawBox;
typedef struct {
    uint64_t frame,age_frames;
    int enabled,valid,width,height;
    unsigned count,dropped;
    ThreatDrawBox boxes[THREAT_DRAW_MAX];
} ThreatDrawState;

static int threat_draw_family(uint32_t texture,uint32_t palette,unsigned depth) {
    if(depth)return 0;
    if(texture==0x1263A036u||texture==0x38DC02FEu)return 4; /* Greif target, not a body-contact hazard. */
    if(texture==0x46D3938Eu||texture==0x87C52FC0u)return 2; /* Uhu */
    if(texture==0xC7502427u||texture==0xAB58BBA4u)return 3; /* tracer */
    /* This CLUT is shared with a full-page background interpretation. Only
     * independently observed fighter upload strips qualify, never CLUT alone. */
    if(palette==0x527B28B9u && (texture==0x6BB2A2A3u||texture==0x05C32A1Eu||
       texture==0xDEA9D15Cu||texture==0x3FE0776Du||texture==0x3594C110u||texture==0x784BFD39u))return 1;
    return 0;
}
static int threat_boxes_touch(const int a[4],const int b[4]) {
    return a[0]<=b[2]+2&&a[2]+2>=b[0]&&a[1]<=b[3]+2&&a[3]+2>=b[1];
}
static void threat_box_union(int a[4],const int b[4]) {
    if(b[0]<a[0])a[0]=b[0];if(b[1]<a[1])a[1]=b[1];
    if(b[2]>a[2])a[2]=b[2];if(b[3]>a[3])a[3]=b[3];
}
static void threat_draw_observe(ThreatDrawState *s,uint64_t frame,uint32_t texture,
        uint32_t palette,unsigned depth,const int xs[3],const int ys[3],const int area[4]) {
    int family=threat_draw_family(texture,palette,depth);if(!family)return;
    if(area[0]<0||area[1]<0||area[2]>1023||area[3]>511||
       area[2]-area[0]+1<128||area[3]-area[1]+1<128)return;
    int b[4]={xs[0],ys[0],xs[0],ys[0]};
    for(int i=0;i<3;++i){
        if(xs[i]<-4096||xs[i]>4095||ys[i]<-4096||ys[i]>4095)return;
        if(xs[i]<b[0])b[0]=xs[i];if(xs[i]>b[2])b[2]=xs[i];
        if(ys[i]<b[1])b[1]=ys[i];if(ys[i]>b[3])b[3]=ys[i];
    }
    if(((int64_t)xs[1]-xs[0])*(ys[2]-ys[0])==((int64_t)xs[2]-xs[0])*(ys[1]-ys[0])||
       b[2]<area[0]||b[0]>area[2]||b[3]<area[1]||b[1]>area[3])return;
    if(b[0]<area[0])b[0]=area[0];if(b[1]<area[1])b[1]=area[1];
    if(b[2]>area[2])b[2]=area[2];if(b[3]>area[3])b[3]=area[3];
    b[0]-=area[0];b[2]-=area[0];b[1]-=area[1];b[3]-=area[1];
    if(b[0]>=b[2]||b[1]>=b[3])return;
    int width=area[2]-area[0]+1,height=area[3]-area[1]+1;
    if(s->frame!=frame||s->width!=width||s->height!=height){
        memset(s,0,sizeof(*s));s->frame=frame;s->width=width;s->height=height;
    }
    /* Merge transitively, including bridges between two earlier triangles. */
    for(unsigned i=0;i<s->count;){
        ThreatDrawBox *box=s->boxes+i;
        if(box->family==family&&(family!=3||(box->texture==texture&&box->palette==palette))&&threat_boxes_touch(b,box->bounds)){
            threat_box_union(b,box->bounds);s->boxes[i]=s->boxes[--s->count];i=0;
        }else ++i;
    }
    if(s->count==THREAT_DRAW_MAX){++s->dropped;return;}
    ThreatDrawBox *box=s->boxes+s->count++;box->family=family;box->texture=texture;box->palette=palette;
    memcpy(box->bounds,b,sizeof b);
}
static void threat_draw_snapshot(const ThreatDrawState *s,uint64_t frame,int enabled,ThreatDrawState *out) {
    memset(out,0,sizeof(*out));out->enabled=enabled;out->frame=frame;
    /* Empty frames stay empty; stale obstacles must not be resurrected. */
    if(!enabled||s->frame!=frame)return;
    *out=*s;out->enabled=enabled;out->valid=1;out->age_frames=0;
}
void gl_renderer_threat_draw_get(ThreatDrawState *out);
static void threat_draw_commit(ThreatDrawState *working,uint64_t frame,int enabled,ThreatDrawState *out){
    memset(out,0,sizeof(*out));out->enabled=enabled;out->frame=frame;
    /* VBlank can advance the public guest clock before presentation. Preserve
     * the source frame's timestamp, then consume the working set exactly once. */
    if(enabled&&working->count&&working->frame<=frame&&frame-working->frame<=12){
        *out=*working;out->enabled=1;out->valid=1;out->age_frames=frame-working->frame;
    }
    memset(working,0,sizeof(*working));
}
#endif
