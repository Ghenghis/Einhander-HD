/* Conservative visible source queries for affine axis-aligned 2D triangles.
 * This never changes vertices, texture coordinates, or raster limits. */
#ifndef PSXRECOMP_HD_VISIBLE_UV_H
#define PSXRECOMP_HD_VISIBLE_UV_H
#include <math.h>

static void hd_visible_axis(int origin,int span,int uv,int delta,int first,int end,
                            int low,int high,int *out_low,int *out_high) {
    const double a=uv+(double)(first-origin)*delta/span;
    const double b=uv+(double)(end-origin)*delta/span;
    int lo=(int)floor(a<b?a:b);
    /* Forward end is exclusive; a reversed first sample is inclusive. */
    int hi=((delta>0)==(span>0))?(int)ceil(a>b?a:b)-1:(int)floor(a>b?a:b);
    if(lo<low)lo=low;if(hi>high)hi=high;
    *out_low=lo;*out_high=hi;
}

/* 1=narrowed, 0=unchanged/not an axis-aligned affine rectangle triangle,
 * -1=fully outside the inclusive draw area. */
static int hd_visible_uv_limits(const int *xs,const int *ys,const int *us,const int *vs,
                                const int *area,const int *limits,int *out) {
    int x0=xs[0],x1=x0,y0=ys[0],y1=y0,ix=-1,iy=-1;
    for(int i=0;i<4;++i)out[i]=limits[i];
    for(int i=1;i<3;++i){if(xs[i]<x0)x0=xs[i];if(xs[i]>x1)x1=xs[i];
        if(ys[i]<y0)y0=ys[i];if(ys[i]>y1)y1=ys[i];
        if(xs[i]!=xs[0])ix=i;if(ys[i]!=ys[0])iy=i;}
    if(ix<0||iy<0||x0==x1||y0==y1||limits[0]>limits[2]||limits[1]>limits[3])return 0;
    const int dx=xs[ix]-xs[0],du=us[ix]-us[0],dy=ys[iy]-ys[0],dv=vs[iy]-vs[0];
    if(!du||!dv)return 0;
    for(int i=0;i<3;++i){
        if((xs[i]!=x0&&xs[i]!=x1)||(ys[i]!=y0&&ys[i]!=y1))return 0;
        if((long long)(us[i]-us[0])*dx!=(long long)(xs[i]-xs[0])*du||
           (long long)(vs[i]-vs[0])*dy!=(long long)(ys[i]-ys[0])*dv)return 0;
    }
    int a=x0>area[0]?x0:area[0],b=x1<area[2]+1?x1:area[2]+1;
    int c=y0>area[1]?y0:area[1],d=y1<area[3]+1?y1:area[3]+1;
    if(a>=b||c>=d)return -1;
    if(a==x0&&b==x1&&c==y0&&d==y1)return 0;
    hd_visible_axis(xs[0],dx,us[0],du,a,b,limits[0],limits[2],out,out+2);
    hd_visible_axis(ys[0],dy,vs[0],dv,c,d,limits[1],limits[3],out+1,out+3);
    if(out[0]>out[2]||out[1]>out[3])return -1;
    return out[0]!=limits[0]||out[1]!=limits[1]||out[2]!=limits[2]||out[3]!=limits[3];
}
#endif
