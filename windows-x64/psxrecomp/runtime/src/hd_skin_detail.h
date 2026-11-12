/* Optional authored RGB surface detail, ein-material-v3.
 * This is a color/luminance layer, not a normal map or physical material.
 * The base HD image exclusively owns cutout/STP, blending and geometry. */
#ifndef PSXRECOMP_HD_SKIN_DETAIL_H
#define PSXRECOMP_HD_SKIN_DETAIL_H
#include "hd_skin_material.h"
#include <stdio.h>

#define HD_SKIN_DETAIL_DEFAULT_STRENGTH 0.12f
#define HD_SKIN_DETAIL_MAX_STRENGTH 0.35f
#define HD_SKIN_DETAIL_DEFAULT_SCALE 8.0f
#define HD_SKIN_DETAIL_MAX_SCALE 64.0f
#define HD_SKIN_DETAIL_MAX_EDGE 4096
#define HD_SKIN_DETAIL_MAX_FILE_BYTES (64u * 1024u * 1024u)

typedef struct {
    char path[1024];
    float strength, scale;
    int enabled;
} HdSkinDetailConfig;

static int hd_skin_detail_dimensions_valid(int width,int height,size_t encoded_bytes) {
    return width>0 && height>0 && width<=HD_SKIN_DETAIL_MAX_EDGE && height<=HD_SKIN_DETAIL_MAX_EDGE &&
        encoded_bytes>=8 && encoded_bytes<=HD_SKIN_DETAIL_MAX_FILE_BYTES;
}

typedef int (*HdSkinFixedInflate)(char*,int,const char*,int);
static uint32_t hd_skin_detail_be32(const unsigned char *p) {
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
}

/* Shared stb's normal PNG loader uses an expandable inflater. Preflight the
 * SAME immutable IDAT bytes through its fixed-buffer API first, so malformed
 * small-IHDR/huge-IDAT streams cannot grow allocations past scanline bounds.
 * This optional RGB layer deliberately supports only 8-bit RGB/RGBA,
 * noninterlaced PNGs. No global vendor allocator or other image path changes. */
static int hd_skin_detail_png_preflight(const unsigned char *png,size_t size,
        int *width,int *height,int *channels,HdSkinFixedInflate inflate_fixed) {
    size_t offset=8,idat_bytes=0,raw_bytes;
    uint32_t w,h;
    int components,ended=0,idat_closed=0,seen_idat=0;
    unsigned char *idat=NULL,*raw=NULL;
    if (!png || !width || !height || !channels || !inflate_fixed || size<33 ||
        size>HD_SKIN_DETAIL_MAX_FILE_BYTES || memcmp(png,"\x89PNG\r\n\x1a\n",8) ||
        hd_skin_detail_be32(png+8)!=13 || memcmp(png+12,"IHDR",4)) return 0;
    w=hd_skin_detail_be32(png+16); h=hd_skin_detail_be32(png+20);
    if (!w || !h || w>HD_SKIN_DETAIL_MAX_EDGE || h>HD_SKIN_DETAIL_MAX_EDGE ||
        png[24]!=8 || (png[25]!=2 && png[25]!=6) || png[26] || png[27] || png[28]) return 0;
    components=png[25]==2?3:4;
    while (offset<=size-12) {
        uint32_t length=hd_skin_detail_be32(png+offset);
        const unsigned char *type=png+offset+4;
        int i;
        if ((size_t)length>size-offset-12) return 0;
        for(i=0;i<4;++i)if(!((type[i]>='A'&&type[i]<='Z')||(type[i]>='a'&&type[i]<='z')))return 0;
        if (!memcmp(type,"IHDR",4)) { if(offset!=8 || length!=13)return 0; }
        else if (!memcmp(type,"IDAT",4)) {
            if(idat_closed || (size_t)length>HD_SKIN_DETAIL_MAX_FILE_BYTES-idat_bytes)return 0;
            idat_bytes+=(size_t)length; seen_idat=1;
        } else if (!memcmp(type,"IEND",4)) {
            if(length || !idat_bytes || offset+12!=size)return 0;
            ended=1; break;
        } else {
            if(type[0]>='A'&&type[0]<='Z')return 0; /* no CgBI/unknown critical mode */
            if(seen_idat)idat_closed=1;
        }
        offset+=(size_t)length+12;
    }
    if(!ended)return 0;
    raw_bytes=((size_t)w*(size_t)components+1u)*(size_t)h;
    idat=(unsigned char*)malloc(idat_bytes);
    raw=(unsigned char*)malloc(raw_bytes);
    if(!idat || !raw){free(idat);free(raw);return 0;}
    offset=8;idat_bytes=0;
    while(offset<=size-12){
        uint32_t length=hd_skin_detail_be32(png+offset);
        if(!memcmp(png+offset+4,"IDAT",4)){
            memcpy(idat+idat_bytes,png+offset+8,length);idat_bytes+=length;
        }
        if(!memcmp(png+offset+4,"IEND",4))break;
        offset+=(size_t)length+12;
    }
    {
        int actual=inflate_fixed((char*)raw,(int)raw_bytes,(const char*)idat,(int)idat_bytes);
        free(idat);free(raw);
        if(actual!=(int)raw_bytes)return 0;
    }
    *width=(int)w;*height=(int)h;*channels=components;
    return 1;
}

/* Empty path is stock. Numbers must be finite and within conservative bounds.
 * Loading/decoding happens once at renderer initialization, never per draw. */
static int hd_skin_detail_parse(HdSkinDetailConfig *out, const char *path,
                                const char *strength, const char *scale) {
    char *end = NULL;
    float amount = HD_SKIN_DETAIL_DEFAULT_STRENGTH;
    float repeats = HD_SKIN_DETAIL_DEFAULT_SCALE;
    if (!out) return -1;
    memset(out,0,sizeof(*out));
    if (!path || !path[0]) return 0;
    if (strlen(path)>=sizeof(out->path)) return -1;
    if (strength && strength[0]) {
        amount=strtof(strength,&end);
        if (!end || end==strength || *end || !isfinite(amount) || amount<0.0f || amount>HD_SKIN_DETAIL_MAX_STRENGTH) return -1;
    }
    if (scale && scale[0]) {
        repeats=strtof(scale,&end);
        if (!end || end==scale || *end || !isfinite(repeats) || repeats<1.0f || repeats>HD_SKIN_DETAIL_MAX_SCALE) return -1;
    }
    snprintf(out->path,sizeof(out->path),"%s",path);
    out->strength=amount; out->scale=repeats; out->enabled=amount>0.0f;
    return out->enabled;
}

/* The keyed source upload also needs its independently observed dimensions.
 * Native page fallbacks and unknown-sized atlases are not detail surfaces. */
static int hd_skin_detail_source_bounds(const HdSkinConfig *material,
                                         uint32_t texture, uint32_t palette,
                                         unsigned width, unsigned height) {
    if (!material || material->diagnostic_scope || !hd_skin_key_matches(material,texture,palette)) return 0;
    if (palette==0x053D9A00u || palette==0x21FDE894u) return width==64 && height==64;
    if (palette==0x527B28B9u) return width==256 && height==8;
    return 0;
}

/* native_uv is a continuous atlas-pixel coordinate AFTER page wrapping and
 * primitive-limit clamping, plus the matched upload offset. Density is tied
 * to 64 native pixels, so a 256x8 strip is not stretched into a square.
 * The sampler uses mirrored repeat; coordinates are intentionally unfractured.
 * Detail alpha is intentionally never read. Palette-only output is exactly
 * preserved when this optional layer is disabled or its strength is zero. */
#define HD_SKIN_DETAIL_GLSL \
    "uniform sampler2D u_skin_detail;\n" \
    "uniform int u_skin_detail_enabled;\n" \
    "uniform float u_skin_detail_strength;\n" \
    "uniform float u_skin_detail_scale;\n" \
    "vec3 hd_skin_detail_material(vec3 base,vec3 source,vec2 native_uv){\n" \
    "  if(u_skin_detail_enabled==0 || u_skin_detail_strength<=0.0) return base;\n" \
    "  float hi=max(source.r,max(source.g,source.b));\n" \
    "  float lo=min(source.r,min(source.g,source.b));\n" \
    "  float paint=smoothstep(0.12,0.35,(hi-lo)/max(hi,0.0001))*smoothstep(0.04,0.16,hi);\n" \
    "  if(u_skin_preserve_accents!=0) paint*=1.0-hd_skin_accent_mask(source);\n" \
    "  vec3 detail=texture(u_skin_detail,native_uv*(u_skin_detail_scale/64.0)).rgb;\n" \
    "  return clamp(base*(vec3(1.0)+(detail*2.0-vec3(1.0))*(u_skin_detail_strength*paint)),0.0,1.0);\n" \
    "}\n"

/* CPU reference for shader parity checks; no image files are rewritten. */
static void hd_skin_detail_reference_ex(const float source[4], const float detail[4],
                                     int preserve_accents,
                                     float strength, float in_out[4]) {
    const float hi=fmaxf(source[0],fmaxf(source[1],source[2]));
    const float lo=fminf(source[0],fminf(source[1],source[2]));
    float paint=hd_skin_smoothstep(0.12f,0.35f,(hi-lo)/fmaxf(hi,0.0001f))*hd_skin_smoothstep(0.04f,0.16f,hi);
    if(preserve_accents)paint*=1.0f-hd_skin_accent_mask_reference(source);
    int i;
    if (strength<=0.0f) return;
    for (i=0;i<3;++i) {
        float value=in_out[i]*(1.0f+(detail[i]*2.0f-1.0f)*strength*paint);
        in_out[i]=fminf(1.0f,fmaxf(0.0f,value));
    }
}
static void hd_skin_detail_reference(const float source[4], const float detail[4],
                                     float strength, float in_out[4]) {
    hd_skin_detail_reference_ex(source,detail,0,strength,in_out);
}
#endif
