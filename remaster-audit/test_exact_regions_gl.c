#ifndef HD_RENDERER_SOURCE
#define HD_RENDERER_SOURCE "../windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c"
#endif
#include HD_RENDERER_SOURCE
int exact_region_gl_regression(const char*root){
 int checks=0,failures=0;
#define CHECK(name,x) do{int ok=!!(x);++checks;failures+=!ok;printf("CHECK %s %s\n",name,ok?"PASS":"FAIL");}while(0)
 gpu_hd_texture_config(1,root,NULL);hd_ensure_pack();if(!s_hd_pack)return 2;
 hd_texture_pack_reset_tracking(s_hd_pack);s_tex_filter=0;flush_cpu_upload();
 gpu_fill(0,0,320,480,0x7c00);
 for(int y=256;y<512;++y)for(int x=448;x<512;++x)s_vram[y*1024+x]=0x7c00;
 gpu_fill(448,256,64,256,0x001f); /* GPU truth red; CPU deliberately stale blue. */
 const float white[9]={1,1,1,1,1,1,1,1,1};const int lim[4]={192,0,255,255};
 const int xa[3]={287,287,32},xb[3]={287,32,32},ua[3]={192,255,192},ub[3]={255,192,255},va[3]={0,0,255},vb[3]={0,255,255};
 for(int buffer=0;buffer<2;++buffer){
  const int top=88+buffer*240;int ya[3]={top,top+64,top},yb[3]={top+64,top,top+64};
  s_area_x1=0;s_area_x2=319;s_area_y1=buffer*240;s_area_y2=buffer*240+239;
  int drawn=0;for(int n=0;n<2000&&!drawn;++n){drawn=hd_on_textured_prim(xa,ya,ua,va,white,0x114,0,0,1,-1,lim,2);if(!drawn)SDL_Delay(1);}
  CHECK("rotated region admitted on alternating buffer",drawn==1);
  CHECK("dirty GPU source synchronized before admission",s_vram[300*1024+450]==0x001f);
  CHECK("rotated quad second triangle",hd_on_textured_prim(xb,yb,ub,vb,white,0x114,0,0,1,-1,lim,2)==1);
  uint16_t pixel=0;CHECK("region-relative UV samples authored green",gl_renderer_fbo_peek(160,top+32,1,1,&pixel)&&pixel==(uint16_t)(4|(24<<5)|(8<<10)));
  CHECK("STP clear texel stays opaque under semi mode",hd_on_textured_prim(xa,ya,ua,va,white,0x114,0,0,1,0,lim,2)==1&&hd_on_textured_prim(xb,yb,ub,vb,white,0x114,0,0,1,0,lim,2)==1&&gl_renderer_fbo_peek(160,top+32,1,1,&pixel)&&pixel==(uint16_t)(4|(24<<5)|(8<<10)));
  const float dim[9]={.25f,.25f,.25f,.25f,.25f,.25f,.25f,.25f,.25f};
  CHECK("raw mode ignores vertex modulation",hd_on_textured_prim(xa,ya,ua,va,dim,0x114,0,0,1,-1,lim,2)==1&&hd_on_textured_prim(xb,yb,ub,vb,dim,0x114,0,0,1,-1,lim,2)==1&&gl_renderer_fbo_peek(160,top+32,1,1,&pixel)&&pixel==(uint16_t)(4|(24<<5)|(8<<10)));
  CHECK("nonraw mode preserves vertex modulation",hd_on_textured_prim(xa,ya,ua,va,dim,0x114,0,0,0,-1,lim,2)==1&&hd_on_textured_prim(xb,yb,ub,vb,dim,0x114,0,0,0,-1,lim,2)==1&&gl_renderer_fbo_peek(160,top+32,1,1,&pixel)&&pixel==(uint16_t)(2|(12<<5)|(4<<10)));
  hd_on_textured_prim(xa,ya,ua,va,white,0x114,0,0,1,-1,lim,2);hd_on_textured_prim(xb,yb,ub,vb,white,0x114,0,0,1,-1,lim,2);
  gpu_write_gp0(0xE1000040);gpu_write_gp0(0x2A101010);
  gpu_write_gp0((uint32_t)top<<16);gpu_write_gp0(((uint32_t)top<<16)|319);
  gpu_write_gp0((uint32_t)(top+64)<<16);gpu_write_gp0(((uint32_t)(top+64)<<16)|319);
  CHECK("following native subtractive fade remains effective",gl_renderer_fbo_peek(160,top+32,1,1,&pixel)&&((pixel>>5)&31)<24&&((pixel>>5)&31)>0);
  s_area_x2=1023;s_area_y1=0;s_area_y2=511;
  int sx[3]={450,460,450},sy[3]={300,300,310};CHECK("actual source destination overlap stays native",hd_on_textured_prim(sx,sy,ua,va,white,0x114,0,0,1,-1,lim,2)==0);
 }
 uint64_t scans=hd_texture_pack_region_validation_count(s_hd_pack);
 for(int n=0;n<1000;++n){HdTextureDrawQuery q={256,256,2,192,255,0,255,0,0,s_vram,(size_t)VRAM_W*VRAM_H};HdTextureSourceMatch m;hd_texture_pack_match_region(s_hd_pack,&q,1,&m);}
 CHECK("GL stable binding validation cached",scans==hd_texture_pack_region_validation_count(s_hd_pack));
 s_tex_filter=0;s_area_x1=0;s_area_x2=1023;s_area_y1=0;s_area_y2=511;
 /* Exact reviewer repro: sample left half, overwrite the unsampled right half
  * of the same complete proof. The next full query must read the new GPU words
  * and reject the old proof rather than reusing its pre-draw positive cache. */
 gpu_fill(448,256,64,256,0x001f);
 const int partial_x[3]={480,512,480},partial_y[3]={300,300,332};
 const int partial_u[3]={192,223,192},partial_v[3]={0,0,255},partial_lim[4]={192,0,223,255};
 mark_prim_dirty(partial_x,partial_y,3,1);
 CHECK("partial query may overwrite disjoint part of its proof",hd_on_textured_prim(partial_x,partial_y,partial_u,partial_v,white,0x114,0,0,1,-1,partial_lim,2)==1);
 CHECK("pending HD destination retains GPU and pack dirty state",s_gpu_dirty&&s_pack_dirty.set&&hd_page_needs_cpu(&s_hd_pages,480,300,32,32));
 const int y0[3]={88,152,88};
 mark_prim_dirty(xa,y0,3,1);
 CHECK("next full query rejects overwritten complete proof",hd_on_textured_prim(xa,y0,ua,va,white,0x114,0,0,1,-1,lim,2)==0);
 CHECK("partial source write becomes authoritative GPU truth",s_vram[305*1024+484]!=(uint16_t)0x001f);
 CHECK("native fallback retains still-pending destination dirty state",s_gpu_dirty&&s_pack_dirty.set&&hd_page_needs_cpu(&s_hd_pages,32,88,255,64));
 gpu_fill(448,256,64,256,0x001f);
 CHECK("restored exact source can be admitted again",hd_on_textured_prim(xa,y0,ua,va,white,0x114,0,0,1,-1,lim,2)==1);
 gpu_fill(450,300,1,1,0x7c00); /* Change GPU only; a cached old proof must fail. */
 CHECK("modified region refuses stale replacement",hd_on_textured_prim(xa,y0,ua,va,white,0x114,0,0,1,-1,lim,2)==0);
 CHECK("changed source shadow reflects GPU truth",s_vram[300*1024+450]==0x7c00);
 CHECK("no GL errors",glGetError()==GL_NO_ERROR);
 printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;
#undef CHECK
}
