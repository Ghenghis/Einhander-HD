#version 330
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=2) in vec4 a_col;
layout(location=3) in vec2 a_tpage;
layout(location=4) in vec2 a_clut;
layout(location=5) in float a_depth;
layout(location=6) in float a_raw;
layout(location=7) in vec4 a_limits;
layout(location=8) in float a_semi;
layout(location=9) in float a_q;   /* persp weight; 0 = affine (default) */
layout(location=10) in vec2 a_hdoff; /* HD upload-px offset (attrib batching) */
uniform float u_shift;
uniform float u_xoff;   /* native-wide x translation (px); 0 canonical */
uniform float u_xhalf;  /* x clip half-extent (px); 512 canonical */
uniform float u_xscale; /* native-wide 2D-backdrop x-stretch; 1 canonical */
uniform float u_xcenter;/* stretch centre in VRAM px; 0 canonical */
noperspective out vec2 v_uv; noperspective out vec4 v_col;
smooth out vec2 v_uv_p;  /* perspective-correct UV (used when v_persp!=0) */
flat out int v_persp;
flat out ivec2 v_tpage; flat out ivec2 v_clut; flat out int v_depth;
flat out int v_raw; flat out ivec4 v_limits; flat out int v_semi;
flat out vec2 v_hdoff;
void main(){ v_uv = a_uv; v_uv_p = a_uv; v_col = a_col; v_hdoff = a_hdoff;
  v_persp = (a_q > 0.0) ? 1 : 0;
  v_tpage = ivec2(a_tpage + 0.5); v_clut = ivec2(a_clut + 0.5);
  v_depth = int(a_depth + 0.5); v_raw = int(a_raw + 0.5);
  v_semi = int(a_semi + 0.5);
  v_limits = ivec4(floor(a_limits + 0.5));
  /* u_shift: align GL's center-sample grid with the PS1 integer grid (see
   * GEO_VS) so interpolated uv at a fragment equals the PS1 DDA value. */
  float xb = a_pos.x;
  if (u_xscale < 0.0) {
    float s = -u_xscale; float h = u_xhalf / s;
    float l = u_xcenter - h, r = u_xcenter + h;
    if (xb < l) xb = l + (xb-l)*s; else if (xb > r) xb = r + (xb-r)*s;
  } else xb = (xb - u_xcenter)*u_xscale + u_xcenter;
  /* Perspective-correct UV rides the standard w divide: emit clip coords
   * pre-multiplied by w = 1/q so the post-divide NDC is unchanged while
   * the rasterizer interpolates the smooth varying hyperbolically. With
   * a_q == 0 (feature off) w is exactly 1.0 and this is the old expression. */
  float w = (a_q > 0.0) ? (1.0 / a_q) : 1.0;
  vec2 ndc = vec2((xb+u_shift+u_xoff)/u_xhalf - 1.0, (a_pos.y+u_shift)/256.0 - 1.0);
  gl_Position = vec4(ndc * w, 0.0, w); }
