#include <cassert>
#include <cstdio>
#include "hd_visible_uv.h"
int main(){
    unsigned checks=0;int out[4];
    const int x[3]={255,510,255},y[3]={240,240,480};
    const int u[3]={0,255,0},v[3]={0,0,240};
    const int area[4]={0,248,319,471},lim[4]={0,0,254,239};
    assert(hd_visible_uv_limits(x,y,u,v,area,lim,out)==1);++checks;
    assert(out[0]==0&&out[1]==8&&out[2]==64&&out[3]==231);++checks;
    const int x2[3]={510,255,510},y2[3]={240,480,480},u2[3]={255,0,255},v2[3]={0,240,240};
    assert(hd_visible_uv_limits(x2,y2,u2,v2,area,lim,out)==1);++checks;
    assert(out[0]==0&&out[1]==8&&out[2]==64&&out[3]==231);++checks;
    const int narrower[4]={0,248,318,471};
    assert(hd_visible_uv_limits(x,y,u,v,narrower,lim,out)==1&&out[2]==63);++checks;
    const int full[4]={0,0,1023,511};
    assert(hd_visible_uv_limits(x,y,u,v,full,lim,out)==0);++checks;
    const int off[4]={0,0,100,100};
    assert(hd_visible_uv_limits(x,y,u,v,off,lim,out)==-1);++checks;
    const int skew_y[3]={240,241,480};
    assert(hd_visible_uv_limits(x,skew_y,u,v,area,lim,out)==0);++checks;
    const int skew_u[3]={0,254,1};
    assert(hd_visible_uv_limits(x,y,skew_u,v,area,lim,out)==0);++checks;
    const int wrapped[4]={250,0,2,239};
    assert(hd_visible_uv_limits(x,y,u,v,area,wrapped,out)==0);++checks;
    const int mx[3]={0,64,0},my[3]={0,0,64},mu[3]={65,1,65},mv[3]={0,0,64};
    const int ml[4]={1,0,64,63},ma[4]={16,0,47,63};
    assert(hd_visible_uv_limits(mx,my,mu,mv,ma,ml,out)==1);++checks;
    assert(out[0]==17&&out[2]==49);++checks;
    const int sx[3]={0,128,0},sy[3]={0,0,64},su[3]={0,64,0},sv[3]={0,0,64};
    const int sa[4]={32,0,95,63},sl[4]={0,0,63,63};
    assert(hd_visible_uv_limits(sx,sy,su,sv,sa,sl,out)==1&&out[0]==16&&out[2]==47);++checks;
    std::printf("{\"checks\":%u,\"failures\":0}\n",checks);
}
