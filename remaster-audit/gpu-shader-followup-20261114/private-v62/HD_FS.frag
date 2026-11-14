#version 330
noperspective in vec2 v_uv; noperspective in vec4 v_col;
smooth in vec2 v_uv_p; flat in int v_persp;
out vec4 frag; out vec4 blend_factor;
flat in int v_raw;
flat in ivec2 v_tpage;
flat in ivec4 v_limits;
flat in int v_semi;
uniform sampler2D u_hd;
uniform sampler2D u_hd_emissive;
uniform int u_hd_emissive_enabled;
uniform int u_hd_facade_motion; /* opt-in, exact facade RGB only */
uniform usampler2D u_hd_native;
uniform int u_hd_native_edge; /* physical prefix width;0=ordinary replacement */
uniform vec2 u_hd_off_uniform; /* upload-px coordinate of page uv (0,0) */
flat in vec2 v_hdoff;    /* same value per primitive (attrib batching) */
uniform int u_hd_attrib; /* 0: uniform offset (default); 1: per-vertex */
uniform vec2 u_hd_dim;   /* upload native px dims (w,h) */
uniform int u_semipass;
uniform int u_semimode;
uniform int u_maskset;
uniform int u_filter;    /* 1 = bilinear */
uniform float u_shift;
uniform int u_skin_enabled;
uniform vec3 u_skin_primary;
uniform vec3 u_skin_accent;
uniform float u_skin_strength;
uniform int u_skin_preserve_accents;
float hd_skin_accent_mask(vec3 source){
  return smoothstep(0.06,0.20,source.r-source.b)*smoothstep(0.05,0.18,source.g-source.b)*smoothstep(0.25,0.50,source.g/max(source.r,0.0001))*smoothstep(-0.06,-0.01,source.r-source.g);
}
vec3 hd_skin_material(vec3 source){
  if(u_skin_enabled == 0 || u_skin_strength <= 0.0) return source;
  float hi=max(source.r,max(source.g,source.b));
  float lo=min(source.r,min(source.g,source.b));
  float saturation=(hi-lo)/max(hi,0.0001);
  float paint=smoothstep(0.12,0.35,saturation)*smoothstep(0.04,0.16,hi);
  if(u_skin_preserve_accents!=0) paint*=1.0-hd_skin_accent_mask(source);
  float warm=smoothstep(0.03,0.18,source.r-source.b);
  vec3 color=mix(u_skin_primary,u_skin_accent,warm);
  vec3 weights=vec3(0.2126,0.7152,0.0722);
  float luma=dot(source,weights);
  vec3 target=color/max(dot(color,weights),0.0001);
  float extent=max(target.r,max(target.g,target.b))-1.0;
  float gamut=extent>0.0?clamp((1.0-luma)/max(luma*extent,0.0001),0.0,1.0):1.0;
  vec3 mapped=vec3(luma)+gamut*(luma*target-vec3(luma));
  return mix(source,mapped,paint*u_skin_strength);
}
uniform sampler2D u_skin_detail;
uniform int u_skin_detail_enabled;
uniform float u_skin_detail_strength;
uniform float u_skin_detail_scale;
vec3 hd_skin_detail_material(vec3 base,vec3 source,vec2 native_uv){
  if(u_skin_detail_enabled==0 || u_skin_detail_strength<=0.0) return base;
  float hi=max(source.r,max(source.g,source.b));
  float lo=min(source.r,min(source.g,source.b));
  float paint=smoothstep(0.12,0.35,(hi-lo)/max(hi,0.0001))*smoothstep(0.04,0.16,hi);
  if(u_skin_preserve_accents!=0) paint*=1.0-hd_skin_accent_mask(source);
  vec3 detail=texture(u_skin_detail,native_uv*(u_skin_detail_scale/64.0)).rgb;
  return clamp(base*(vec3(1.0)+(detail*2.0-vec3(1.0))*(u_skin_detail_strength*paint)),0.0,1.0);
}
int hd_edge_fetch(int u,int v){
  u=clamp(u & 255,v_limits.x,v_limits.z);v=clamp(v & 255,v_limits.y,v_limits.w);
  return int(texelFetch(u_hd_native,ivec2((v_tpage.x+u)&1023,(v_tpage.y+v)&511),0).r);
}
vec3 hd_edge_col(int c){return vec3(float(c&31),float((c>>5)&31),float((c>>10)&31))/31.0;}
vec4 hd_edge_sample(vec2 uv){
  if(u_filter==0){int c=hd_edge_fetch(int(floor(uv.x)),int(floor(uv.y)));
    if(c==0)return vec4(0.0);return vec4(hd_edge_col(c),(c&32768)!=0?1.0:127.0/255.0);}
  uv+=vec2(u_shift);ivec2 p=ivec2(floor(uv));vec2 f=uv-vec2(p)-vec2(0.5);
  ivec2 s=ivec2(f.x<0.0?-1:1,f.y<0.0?-1:1);f=abs(f);
  int a=hd_edge_fetch(p.x,p.y),b=hd_edge_fetch(p.x+s.x,p.y);
  int c=hd_edge_fetch(p.x,p.y+s.y),d=hd_edge_fetch(p.x+s.x,p.y+s.y);
  if(a==0)return vec4(0.0);
  vec4 w=vec4((1.0-f.x)*(1.0-f.y),f.x*(1.0-f.y),(1.0-f.x)*f.y,f.x*f.y);
  w*=vec4(a!=0?1.0:0.0,b!=0?1.0:0.0,c!=0?1.0:0.0,d!=0?1.0:0.0);
  float n=dot(w,vec4(1.0));
  vec3 rgb=(hd_edge_col(a)*w.x+hd_edge_col(b)*w.y+hd_edge_col(c)*w.z+hd_edge_col(d)*w.w)/n;
  float stp=dot(w,vec4(float((a>>15)&1),float((b>>15)&1),float((c>>15)&1),float((d>>15)&1)))/n;
  return vec4(rgb,stp>=0.5?1.0:127.0/255.0);
}
// PRIVATE RGB-only experiment. Alpha is still the separately selected PSX class.
uniform int u_hd_rgb_edges;
vec4 hd_visible_rgb(vec2 pos, int level) {
  ivec2 size = textureSize(u_hd,level);
  vec2 p = pos * vec2(size) - vec2(0.5);
  ivec2 b = ivec2(floor(p)); vec2 f = fract(p);
  vec4 a=texelFetch(u_hd,clamp(b,ivec2(0),size-ivec2(1)),level);
  vec4 c=texelFetch(u_hd,clamp(b+ivec2(1,0),ivec2(0),size-ivec2(1)),level);
  vec4 d=texelFetch(u_hd,clamp(b+ivec2(0,1),ivec2(0),size-ivec2(1)),level);
  vec4 e=texelFetch(u_hd,clamp(b+ivec2(1,1),ivec2(0),size-ivec2(1)),level);
  vec4 w=vec4((1.0-f.x)*(1.0-f.y),f.x*(1.0-f.y),(1.0-f.x)*f.y,f.x*f.y);
  w*=vec4(a.a>0.0?1.0:0.0,c.a>0.0?1.0:0.0,d.a>0.0?1.0:0.0,e.a>0.0?1.0:0.0);
  float n=dot(w,vec4(1.0));
  return vec4((a.rgb*w.x+c.rgb*w.y+d.rgb*w.z+e.rgb*w.w)/max(n,1e-8),n);
}
void main(){
  vec2 u_hd_off = (u_hd_attrib != 0) ? v_hdoff : u_hd_off_uniform;
  int stp; vec3 rgb; vec4 c;
  vec2 uv = (v_persp != 0) ? v_uv_p : v_uv;
  vec2 facade_dx=dFdx(uv)/u_hd_dim,facade_dy=dFdy(uv)/u_hd_dim;
  /* Alpha encodes discrete PS1 classes, never interpolated opacity.
   * The nearest replacement texel owns cutout/STP. Native-nearest
   * class maps retain the original result, while reconstructed glyph
   * contours can have sub-native detail. RGB filtering never blends classes. */
  vec2 class_uv = uv + (u_filter == 0 ? vec2(0.0) : vec2(u_shift));
  if (u_filter == 0) class_uv = floor(class_uv) + vec2(0.5);
  class_uv = mod(class_uv, vec2(256.0));
  class_uv = clamp(class_uv, vec2(v_limits.xy), vec2(v_limits.zw) + vec2(0.99999));
  vec2 authority_pos = (u_hd_off + class_uv) / u_hd_dim;
  vec2 rgb_pos=authority_pos;
  ivec2 hd_size = textureSize(u_hd, 0);
  ivec2 authority_px = clamp(ivec2(floor(authority_pos * vec2(hd_size))),
                             ivec2(0), hd_size - ivec2(1));
  float class_alpha = texelFetch(u_hd, authority_px, 0).a;
  bool native_edge=u_hd_native_edge>0 && int(floor(class_uv.x))>=u_hd_native_edge;
  if (u_filter == 0) {
    /* PS1 point sampling: exact texel, clamped to the prim's limits. */
    ivec2 iu;
    iu.x = int(floor(uv.x)) & 255;
    iu.y = int(floor(uv.y)) & 255;
    iu.x = clamp(iu.x, v_limits.x, v_limits.z);
    iu.y = clamp(iu.y, v_limits.y, v_limits.w);
    rgb_pos=(u_hd_off + vec2(iu) + 0.5) / u_hd_dim;
    c = texture(u_hd,rgb_pos);
  } else {
    /* Recentered bilinear footprint; hardware taps replace the 4-tap
     * software filter (RGBA replacement is already decoded). */
    vec2 suv = uv + vec2(u_shift);
    suv.x = mod(suv.x, 256.0);
    suv.y = mod(suv.y, 256.0);
    suv = clamp(suv, vec2(v_limits.x, v_limits.y),
                vec2(v_limits.z, v_limits.w) + 1.0);
    rgb_pos=(u_hd_off+suv)/u_hd_dim;
    if(u_hd_facade_motion!=0) {
      /* Derivatives precede wrap/clamp; partial UV bands must not
       * select a coarser mip merely because helper lanes cross an edge. */
      c = textureGrad(u_hd,(u_hd_off+suv)/u_hd_dim,
                      facade_dx,facade_dy);
    } else c = texture(u_hd, (u_hd_off + suv) / u_hd_dim);
  }
  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion==0 && !native_edge) {
    vec4 edge0=hd_visible_rgb(rgb_pos,0);
    if(edge0.a>1e-8 && edge0.a<0.999999)c.rgb=edge0.rgb;
  }
  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}
  if (class_alpha == 0.0) discard;
  stp = (class_alpha >= 0.5) ? 1 : 0;
  rgb = native_edge ? c.rgb : hd_skin_material(c.rgb);
  vec2 detail_uv=mod(uv+vec2(u_shift),vec2(256.0));
  detail_uv=clamp(detail_uv,vec2(v_limits.xy),vec2(v_limits.zw)+vec2(0.99999));
  if(!native_edge)rgb = hd_skin_detail_material(rgb,c.rgb,u_hd_off+detail_uv);
  if (u_semipass == 1 && stp == 1) discard;
  if (u_semipass == 2 && stp == 0) discard;
  if (v_raw == 0) {
    vec3 modulation=v_col.rgb*2.0;
    if(u_hd_emissive_enabled!=0 && !native_edge)
      modulation=mix(modulation,max(modulation,vec3(1.0)),texture(u_hd_emissive,rgb_pos).r);
    rgb=clamp(rgb*modulation,0.0,1.0);
  }
  float dst_factor = 0.0;
  if (u_semimode == 4 && v_semi != 0 && stp != 0) {
    dst_factor = v_semi == 1 ? 0.5 : 1.0;
    if (v_semi == 1) rgb *= 0.5; else if (v_semi == 4) rgb *= 0.25;
  }
  frag = vec4(rgb, (stp == 1 || u_maskset == 1) ? 1.0 : 0.0);
  blend_factor = vec4(0.0, 0.0, 0.0, dst_factor);
}
