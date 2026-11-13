/* Included after the production renderer, in a hidden GL fixture only. */
enum { HD_BATCH_CASES=22 };
static void batch_hd_triangle_mode(int variant,int semi,int narrow_uv,int rawtex) {
    int shift=variant?50:0;
    int xs[3]={20+shift,150+shift,20+shift},ys[3]={20+shift,20+shift,150+shift};
    int us[3]={narrow_uv?128:0,255,narrow_uv?128:0},vs[3]={0,0,255};
    int limits[4]={narrow_uv?128:0,0,255,255};
    float colors[9];
    for(int i=0;i<3;++i){colors[i*3]=variant?.2f:.8f;colors[i*3+1]=variant?.8f:.3f;colors[i*3+2]=.4f;}
    FM_CHECK("batch fixture source admitted",hd_on_textured_prim(xs,ys,us,vs,colors,10,16,480,rawtex,semi,limits,0)==1);
}
static void batch_hd_triangle(int variant,int semi,int narrow_uv) {batch_hd_triangle_mode(variant,semi,narrow_uv,0);}
static void batch_native_triangle(void) {
    gpu_triangle(55,55,0x001f,180,55,0x001f,55,180,0x001f,-1);
}
static void batch_native_texture(void) {
    const int xs[3]={55,180,55},ys[3]={55,55,180},us[3]={0,63,0},vs[3]={0,0,63};
    const float colors[9]={1,1,1,1,1,1,1,1,1};
    gpu_textured_triangle(xs,ys,us,vs,colors,11,16,480,1,-1,NULL);
}
static void batch_fixture_scene(int which,const HdTexturePixels *fixture) {
    GlSkinMaterialState state;char error[256];
    gl_renderer_skin_material_configure("stock",0,"stock",0,"configured","configured",1,&state,error,sizeof error);
    glb_set_precise_triangle(0,0,0,0,0,0,0);glb_set_perspective_triangle(0,0,0,0);
    glb_set_mask_bits(0,0);glb_set_texture_filter(1);glb_set_draw_area(0,0,319,239);glb_set_draw_offset(0,0);
    gpu_fill(0,0,320,240,0);
    if(which==5||which==17)glb_set_mask_bits(1,0);
    if(which==10){
        glb_set_precise_triangle(1,20*65536+8192,20*65536+4096,150*65536+24576,20*65536+8192,20*65536+8192,150*65536+24576);
        glb_set_perspective_triangle(1,.8f,1.2f,1.0f);
    }
    batch_hd_triangle(0,-1,0);
    switch(which){
    case 2:batch_native_triangle();break;
    case 3:batch_native_texture();break;
    case 4:batch_hd_triangle(1,0,0);break;
    case 5:glb_set_mask_bits(0,0);break;
    case 6:glb_set_draw_area(0,0,119,239);break;
    case 7:{uint16_t data[16];memcpy(data,s_vram+480*VRAM_W+16,sizeof data);fm_upload(16,480,16,1,data);flush_cpu_upload();break;}
    case 8:gpu_copy_rect(0,0,120,120,64,64);break;
    case 9:
        FM_CHECK("live material change accepted",gl_renderer_skin_material_configure("aurora-teal",75,"stock",0,"95A3BCF8-723E222C","configured",1,&state,error,sizeof error));break;
    case 10:
        glb_set_precise_triangle(1,70*65536+16384,70*65536+12288,200*65536+4096,70*65536+8192,70*65536+8192,200*65536+16384);
        glb_set_perspective_triangle(1,1.1f,.7f,1.0f);break;
    case 11:for(int i=1;i<HD_OPAQUE_BATCH_MAX+1;++i)batch_hd_triangle(i&1,-1,0);break;
    case 12:{HdTexSlot *slot=hd_tex_find(0x95A3BCF8u,0x723E222Cu);hd_tex_release_slot(slot);hd_tex_object(0x95A3BCF8u,0x723E222Cu,fixture);break;}
    case 13:ensure_cpu();break;
    case 14:glb_set_draw_area(0,0,319,239);glb_set_draw_offset(s_off_x,s_off_y);break;
    case 15:
        gl_renderer_present_vram(0,0,320,240,1,0);
        FM_CHECK("present drains queued HD work",!s_hd_batch_n&&!s_hr_fbo_open);break;
    case 16:glb_set_draw_offset(7,-9);break;
    case 17:
        batch_hd_triangle(1,0,0); /* retained opaque-to-semi split, then mask test */
        glb_set_mask_bits(0,1);break;
    case 18:{
        uint16_t data[16*16];for(int i=0;i<16*16;++i)data[i]=0x001f;
        fm_upload(64,64,16,16,data);flush_cpu_upload();break;}
    case 19:gpu_fill(48,48,40,40,0x03e0);break;
    case 20:{
        uint16_t snapshot[8*8];glb_vram_transfer_out(32,32,8,8,snapshot);
        FM_CHECK("snapshot VRAM transfer drains HD work",!s_hd_batch_n&&!s_hr_fbo_open);break;}
    case 21:batch_hd_triangle_mode(1,-1,0,1);break;
    default:break;
    }
    if(which!=11)batch_hd_triangle(1,which==4?1:-1,which==1);
    if(which==5){glb_set_mask_bits(0,1);batch_native_triangle();}
    flush_flat_batch();flush_tex_batch();flush_cpu_upload();
}
static void batch_fixture_read(unsigned char *out) {
    p_glBindFramebuffer(PSXGL_READ_FRAMEBUFFER,s_hr_fbo);
    glReadPixels(0,0,VRAM_W*s_scale,VRAM_H*s_scale,GL_RGBA,GL_UNSIGNED_BYTE,out);
    p_glBindFramebuffer(PSXGL_READ_FRAMEBUFFER,0);
}
/* Case A (review add-on): an HD-eligible 16bpp draw whose source page P
 * (x=384) was GPU-written earlier and already packed, so it is pack-clean but
 * CPU-stale. Its page-fallback key needs CPU words, so ensure_cpu() runs INSIDE
 * hd_on_textured_prim while an opaque HD batch is still pending. Both draws use
 * the real gpu_textured_triangle entry (flush_cpu_upload, flush_pack_if_sampling,
 * mark_prim_dirty). Evidence: readback count, pending-batch count, CPU VRAM
 * words under the pending batch, and full hr-FBO pixels. */
enum { ALIAS_X=20, ALIAS_Y=20, ALIAS_W=131, ALIAS_H=131 };
typedef struct { unsigned pending_before,pending_after; uint64_t readbacks,splits_retained; uint16_t cpu[ALIAS_W*ALIAS_H]; } BatchAliasResult;
static void batch_alias_scene(int batch,BatchAliasResult *out) {
    GlSkinMaterialState state;char error[256];
    s_hd_opaque_batch_enabled=batch;
    gl_renderer_skin_material_configure("stock",0,"stock",0,"configured","configured",1,&state,error,sizeof error);
    glb_set_precise_triangle(0,0,0,0,0,0,0);glb_set_perspective_triangle(0,0,0,0);
    glb_set_mask_bits(0,0);glb_set_texture_filter(1);glb_set_draw_area(0,0,319,239);glb_set_draw_offset(0,0);
    gpu_fill(0,0,320,240,0);
    gpu_fill(400,10,40,40,0x7c1f);   /* render-to-texture into page P: marks CPU-stale rows */
    pack_flush();                     /* realised (as by any earlier sampling/present); P stays CPU-stale */
    const int axs[3]={20,150,20},ays[3]={20,20,150},aus[3]={0,255,0},avs[3]={0,0,255};
    float acol[9];for(int i=0;i<3;++i){acol[i*3]=.8f;acol[i*3+1]=.3f;acol[i*3+2]=.4f;}
    gpu_textured_triangle(axs,ays,aus,avs,acol,10,16,480,0,-1,NULL);   /* HD, batchable */
    out->pending_before=s_hd_batch_n;
    const uint64_t readbacks=s_hd_cpu_diag.readbacks;
    const int bxs[3]={160,300,160},bys[3]={160,160,230},bus[3]={0,63,0},bvs[3]={0,0,63};
    const float bcol[9]={1,1,1,1,1,1,1,1,1};
    gpu_textured_triangle(bxs,bys,bus,bvs,bcol,(uint16_t)(6|(2<<7)),0,0,1,-1,NULL); /* samples P */
    out->readbacks=s_hd_cpu_diag.readbacks-readbacks;
    out->pending_after=s_hd_batch_n;
    for(int y=0;y<ALIAS_H;++y)memcpy(out->cpu+y*ALIAS_W,s_vram+(size_t)(ALIAS_Y+y)*VRAM_W+ALIAS_X,ALIAS_W*sizeof(uint16_t));
    flush_flat_batch();flush_tex_batch();flush_cpu_upload();
}
static void fm_hd_batch_alias_readback_case(unsigned char *a,unsigned char *b,size_t bytes) {
    static BatchAliasResult off,on;
    const int old_diag=s_hd_cpu_diag_enabled,old_keep=s_hd_keep_bracket;
    s_hd_cpu_diag_enabled=1;
    for(int keep=0;keep<2;++keep){
        s_hd_keep_bracket=keep;
        batch_alias_scene(0,&off);batch_fixture_read(a);
        batch_alias_scene(1,&on);batch_fixture_read(b);
        FM_CHECK("alias case: reference draws the first HD prim immediately",off.pending_before==0);
        FM_CHECK("alias case: batching leaves the first HD prim pending",on.pending_before==1);
        FM_CHECK("alias case: exactly one readback happens inside the second draw handler",off.readbacks==1&&on.readbacks==1);
        FM_CHECK("alias case: the in-handler readback drains the pending HD batch",on.pending_after==0);
        int nonzero=0;for(int i=0;i<ALIAS_W*ALIAS_H;++i)nonzero|=on.cpu[i]!=0;
        FM_CHECK("alias case: pending HD pixels reach CPU VRAM through the in-handler readback",nonzero&&!memcmp(off.cpu,on.cpu,sizeof on.cpu));
        FM_CHECK(keep?"alias case: hr-FBO pixel parity with kept bracket":"alias case: hr-FBO pixel parity",!memcmp(a,b,bytes));
        FM_CHECK("alias case: no retained-bracket leak",s_hd_cpu_diag.hr_kept_leaks==0&&!s_hr_fbo_open&&!s_hr_keep_open);
        FM_CHECK("alias case: no GL error",glGetError()==GL_NO_ERROR);
    }
    s_hd_keep_bracket=old_keep;s_hd_cpu_diag_enabled=old_diag;s_hd_opaque_batch_enabled=0;
}
/* Case B (review add-on): gl_renderer_shutdown() with an opaque HD batch
 * pending. Shutdown must realise the batch through ensure_cpu() before the
 * context is deleted. Reference = the same scene flushed explicitly, then
 * ensure_cpu(). Must be the LAST GL use of the process: after shutdown no GL
 * call is made (only CPU VRAM is compared). Own source upload + resident
 * texture so it does not depend on earlier tracking state. */
static void batch_shutdown_scene(int draw_hd) {
    glb_set_precise_triangle(0,0,0,0,0,0,0);glb_set_perspective_triangle(0,0,0,0);
    glb_set_mask_bits(0,0);glb_set_texture_filter(1);glb_set_draw_area(0,0,319,239);glb_set_draw_offset(0,0);
    gpu_fill(0,0,320,240,0);
    if(!draw_hd)return;
    const int us[3]={0,63,0},vs[3]={0,0,63};
    const float col[9]={1,1,1,1,1,1,1,1,1};
    const int x1[3]={20,150,20},y1[3]={20,20,150},x2[3]={70,200,70},y2[3]={70,70,200};
    gpu_textured_triangle(x1,y1,us,vs,col,(uint16_t)(14|16),0,490,1,-1,NULL);
    gpu_textured_triangle(x2,y2,us,vs,col,(uint16_t)(14|16),0,490,1,-1,NULL);
}
static void fm_hd_batch_shutdown_case(void) {
    static uint16_t words[64*256],clut[16],reference[1024*512],base[1024*512];
    for(int i=0;i<64*256;++i)words[i]=(uint16_t)(((i*37)>>3)&0xFFFF);
    for(int i=0;i<16;++i)clut[i]=(uint16_t)(0x8000|(i*0x0842));
    fm_upload(896,256,64,256,words);fm_upload(0,490,16,1,clut);flush_cpu_upload();
    const uint32_t th=hd_texture_crc32_words_le(words,64*256);
    const uint32_t ph=hd_texture_hash_clut(s_vram,(size_t)VRAM_W*VRAM_H,0,490,0);
    unsigned char *rgba=(unsigned char*)malloc(256u*256u*4u);
    if(!rgba){FM_CHECK("shutdown case allocation",0);return;}
    for(unsigned y=0;y<256;++y)for(unsigned x=0;x<256;++x){unsigned char *p=rgba+((size_t)y*256+x)*4;
        p[0]=(unsigned char)(40+x%200);p[1]=(unsigned char)(30+y%200);p[2]=(unsigned char)(90+(x^y)%150);p[3]=255;}
    HdTexturePixels px={0};px.rgba=rgba;px.width=px.height=256;px.stride=1024;
    hd_tex_object(th,ph,&px);
    GlSkinMaterialState state;char error[256];
    gl_renderer_skin_material_configure("stock",0,"stock",0,"configured","configured",1,&state,error,sizeof error);
    s_hd_cpu_diag_enabled=1;s_hd_opaque_batch_enabled=1;s_player_draw_only=0;
    const int attrib_saved=s_hd_batch_attrib;
    s_hd_batch_attrib=0;                          /* reference: uniform-offset path */
    batch_shutdown_scene(0);flush_tex_batch();ensure_cpu();
    memcpy(base,s_vram,sizeof base);              /* same scene without the HD prims */
    batch_shutdown_scene(1);
    FM_CHECK("shutdown case: both HD prims are admitted and pending in one batch",s_hd_batch_n==2);
    flush_tex_batch();ensure_cpu();
    memcpy(reference,s_vram,sizeof reference);
    FM_CHECK("shutdown case: the HD batch changes CPU VRAM (non-vacuous reference)",memcmp(base,reference,sizeof reference)!=0);
    s_hd_batch_attrib=attrib_saved;               /* shut down under the selected mode */
    batch_shutdown_scene(1);
    FM_CHECK("shutdown case: batch pending again before shutdown",s_hd_batch_n==2&&s_gpu_dirty);
    FM_CHECK("shutdown case: no GL error before shutdown",glGetError()==GL_NO_ERROR);
    const uint64_t readbacks=s_hd_cpu_diag.readbacks;
    gl_renderer_shutdown();                       /* no GL call after this line */
    FM_CHECK("shutdown case: context deleted",s_ctx==NULL&&!s_raster_ok);
    FM_CHECK("shutdown case: shutdown realised the pending batch",s_hd_batch_n==0&&s_hd_cpu_diag.readbacks==readbacks+1);
    FM_CHECK("shutdown case: CPU VRAM after shutdown equals explicit-flush reference",!memcmp(s_vram,reference,sizeof reference));
    s_hd_opaque_batch_enabled=0;
    free(rgba);   /* GL texture already released by shutdown; pixels are host-owned */
}
/* Attrib batching (review add-on): consecutive HD prims that share texture,
 * palette and GL state but differ only in texture page, CLUT position or
 * upload offset. Uniform-offset batching splits them; attrib batching must
 * merge them with byte-identical pixels. Sources are real uploads whose CRC
 * keys resolve to resident replacement textures. */
static void attrib_hd_prim(int slot,uint16_t texpage,uint16_t cx,uint16_t cy) {
    const int x0=12+(slot%8)*36,y0=12+(slot/8%6)*36;
    int xs[3]={x0,x0+44,x0},ys[3]={y0,y0,y0+44};
    const int us[3]={0,63,0},vs[3]={0,0,63},limits[4]={0,0,63,63};
    float colors[9];for(int i=0;i<3;++i){colors[i*3]=.4f+.05f*(slot%5);colors[i*3+1]=.6f;colors[i*3+2]=.5f;}
    const int drawn=hd_on_textured_prim(xs,ys,us,vs,colors,texpage,cx,cy,0,-1,limits,0);
    if(slot<48)FM_CHECK("attrib fixture prim admitted",drawn==1);   /* timing runs stay unprinted */
    else if(drawn!=1)FM_CHECK("attrib timing prim admitted",0);
}
typedef struct { uint64_t flushes,merges,offset_splits,us; } AttribRun;
static AttribRun attrib_scene(int which,int attrib,int prims) {
    GlSkinMaterialState state;char error[256];
    gl_renderer_skin_material_configure("stock",0,"stock",0,"configured","configured",1,&state,error,sizeof error);
    glb_set_precise_triangle(0,0,0,0,0,0,0);glb_set_perspective_triangle(0,0,0,0);
    glb_set_mask_bits(0,0);glb_set_texture_filter(1);glb_set_draw_area(0,0,319,239);glb_set_draw_offset(0,0);
    gpu_fill(0,0,320,240,0);flush_tex_batch();glFinish();
    s_hd_batch_attrib=attrib;
    const uint64_t f0=s_hd_cpu_diag.batch_flushes,m0=s_hd_cpu_diag.hd_attrib_merges,o0=s_hd_cpu_diag.hd_split_reason[6];
    const uint64_t t0=SDL_GetPerformanceCounter();
    for(int i=0;i<prims;++i){
        const int alt=i&1;
        if(which==0)attrib_hd_prim(i,(uint16_t)(alt?(10|16):10),16,480);          /* page (640,0)/(640,256) */
        else if(which==1)attrib_hd_prim(i,(uint16_t)(alt?(13|16):(12|16)),16,480);/* offset 0 / 256 px */
        else if(which==2)attrib_hd_prim(i,10,16,(uint16_t)(alt?481:480));         /* CLUT row 480 / 481 */
        else attrib_hd_prim(i,(uint16_t)(i%3==0?10:i%3==1?(10|16):(11|16)),16,(uint16_t)(480+(i%2)));
    }
    flush_flat_batch();flush_tex_batch();flush_cpu_upload();glFinish();
    AttribRun r;r.us=(SDL_GetPerformanceCounter()-t0)*1000000u/SDL_GetPerformanceFrequency();
    r.flushes=s_hd_cpu_diag.batch_flushes-f0;r.merges=s_hd_cpu_diag.hd_attrib_merges-m0;
    r.offset_splits=s_hd_cpu_diag.hd_split_reason[6]-o0;
    s_hd_batch_attrib=0;
    return r;
}
static void fm_hd_batch_attrib_merge_cases(const HdTexturePixels *fixture,unsigned char *a,unsigned char *b,size_t bytes) {
    static uint16_t page[64*256],wide[128*256],clut[16];
    for(int y=0;y<256;++y)memcpy(page+y*64,s_vram+(size_t)y*VRAM_W+640,64*sizeof(uint16_t));
    memcpy(clut,s_vram+(size_t)480*VRAM_W+16,sizeof clut);
    FM_CHECK("attrib fixture reuses the resident 95A3BCF8 source",hd_texture_crc32_words_le(page,64*256)==0x95A3BCF8u&&
        hd_texture_crc32_words_le(clut,16)==0x723E222Cu);
    for(int y=0;y<256;++y){memcpy(wide+y*128,page+y*64,64*sizeof(uint16_t));memcpy(wide+y*128+64,page+y*64,64*sizeof(uint16_t));}
    fm_upload(640,256,64,256,page);           /* same source at a second texture page */
    fm_upload(704,256,64,256,page);           /* and a third */
    fm_upload(768,256,128,256,wide);          /* one upload spanning pages 12/13 (offset varies) */
    fm_upload(16,481,16,1,clut);              /* same palette at a second CLUT row */
    flush_cpu_upload();
    hd_tex_object(hd_texture_crc32_words_le(wide,128*256),0x723E222Cu,fixture);
    const int old_diag=s_hd_cpu_diag_enabled,old_keep=s_hd_keep_bracket;
    s_hd_cpu_diag_enabled=1;s_hd_opaque_batch_enabled=1;
    static const char *names[4]={"page","offset","clut","mixed"};
    for(int keep=0;keep<2;++keep)for(int which=0;which<4;++which){
        s_hd_keep_bracket=keep;
        AttribRun off=attrib_scene(which,0,24);batch_fixture_read(a);
        AttribRun on=attrib_scene(which,1,24);batch_fixture_read(b);
        char label[160];
        snprintf(label,sizeof label,"attrib %s alternation keep=%d: pixel parity",names[which],keep);FM_CHECK(label,!memcmp(a,b,bytes));
        snprintf(label,sizeof label,"attrib %s alternation keep=%d: uniform path splits on offset/page/CLUT only",names[which],keep);
        FM_CHECK(label,off.offset_splits>0&&off.merges==0);
        const int eligible=!s_hd_facade_motion.enabled&&!s_hd_world_sampling;
        snprintf(label,sizeof label,"attrib %s alternation keep=%d: merge or conservative sampling fallback",names[which],keep);
        FM_CHECK(label,eligible?(on.merges>0&&on.offset_splits==0&&on.flushes<off.flushes):
            (on.merges==0&&on.offset_splits>0&&on.flushes==off.flushes));
        printf("ATTRIB %s keep=%d flushes off=%llu on=%llu merges=%llu\n",names[which],keep,
            (unsigned long long)off.flushes,(unsigned long long)on.flushes,(unsigned long long)on.merges);
        FM_CHECK("attrib scene leaves no pending batch or GL error",!s_hd_batch_n&&glGetError()==GL_NO_ERROR);
    }
    {   /* fixture time, 2000 alternating prims incl. glFinish, off vs on */
        s_hd_keep_bracket=0;
        for(int rep=0;rep<3;++rep){
            AttribRun off=attrib_scene(3,0,2000);AttribRun on=attrib_scene(3,1,2000);
            printf("ATTRIB timing mixed 2000 prims rep%d: off=%llu us (%llu flushes) on=%llu us (%llu flushes)\n",rep,
                (unsigned long long)off.us,(unsigned long long)off.flushes,(unsigned long long)on.us,(unsigned long long)on.flushes);
        }
    }
    s_hd_keep_bracket=old_keep;s_hd_cpu_diag_enabled=old_diag;s_hd_opaque_batch_enabled=0;
}
static void fm_hd_opaque_batch_regression(const char *root) {
    FM_CHECK("opaque batch disabled by default",!hd_opaque_batch_enabled());
    FM_CHECK("attrib batching disabled by default",!hd_batch_attrib_enabled());
    unsigned char *pixels=(unsigned char*)malloc(1024u*1024u*4u);
    size_t bytes=(size_t)VRAM_W*VRAM_H*s_scale*s_scale*4;
    unsigned char *a=(unsigned char*)malloc(bytes),*b=(unsigned char*)malloc(bytes);
    if(!pixels||!a||!b){FM_CHECK("bounded batch fixture allocation",0);free(pixels);free(a);free(b);return;}
    for(unsigned y=0;y<1024;++y)for(unsigned x=0;x<1024;++x){
        size_t i=((size_t)y*1024+x)*4;
        pixels[i]=(unsigned char)(48+(x*13+y*3)%160);
        pixels[i+1]=(unsigned char)(32+(x*7+y*11)%160);
        pixels[i+2]=(unsigned char)(48+(x*3+y*5)%160);
        pixels[i+3]=x<341?0:x<683?127:255;
    }
    HdTexturePixels fixture={0};fixture.rgba=pixels;fixture.width=fixture.height=1024;fixture.stride=4096;
    hd_tex_object(0x95A3BCF8u,0x723E222Cu,&fixture);
    uint16_t native[16*64];for(int i=0;i<16*64;++i)native[i]=0x2222;
    fm_upload(704,0,16,64,native);flush_cpu_upload();
    s_player_draw_only=0;
    for(int which=0;which<HD_BATCH_CASES;++which){
        s_hd_opaque_batch_enabled=0;batch_fixture_scene(which,&fixture);batch_fixture_read(a);
        s_hd_opaque_batch_enabled=1;batch_fixture_scene(which,&fixture);batch_fixture_read(b);
        char label[128];snprintf(label,sizeof label,"opaque batch pixel parity case %d",which);
        FM_CHECK(label,!memcmp(a,b,bytes));
        FM_CHECK("no pending geometry after a flush boundary",!s_hd_batch_n);
        FM_CHECK("batch scene has no GL errors",glGetError()==GL_NO_ERROR);
    }
    {
        const int previous=s_hd_keep_bracket,old_diag=s_hd_cpu_diag_enabled;
        const uint64_t keeps=s_hd_cpu_diag.hr_bracket_keeps,skips=s_hd_cpu_diag.hr_bracket_skips;
        const uint64_t splits=s_hd_cpu_diag.hd_split_retains;
        s_hd_cpu_diag_enabled=1;s_hd_opaque_batch_enabled=1;
        for(int which=0;which<HD_BATCH_CASES;++which){
            s_hd_keep_bracket=0;batch_fixture_scene(which,&fixture);batch_fixture_read(a);
            s_hd_keep_bracket=1;batch_fixture_scene(which,&fixture);batch_fixture_read(b);
            char label[128];snprintf(label,sizeof label,"kept FBO pixel parity at native/HD boundary case %d",which);
            FM_CHECK(label,!memcmp(a,b,bytes));
            GLint framebuffer=-1;glGetIntegerv(0x8CA6 /*GL_DRAW_FRAMEBUFFER_BINDING*/,&framebuffer);
            FM_CHECK("kept FBO cannot leak beyond the immediate HD bracket",!s_hr_fbo_open&&!s_hr_keep_open&&framebuffer==0);
            FM_CHECK("kept FBO boundary has no GL error",glGetError()==GL_NO_ERROR);
            FM_CHECK("retained bracket never escapes its primitive handler",s_hd_cpu_diag.hr_kept_leaks==0);
        }
        FM_CHECK("real native-to-HD transitions skip owned FBO rebinds",s_hd_cpu_diag.hr_bracket_keeps>keeps&&s_hd_cpu_diag.hr_bracket_skips>skips);
        FM_CHECK("HD key and capacity splits retain the immediately reused FBO",s_hd_cpu_diag.hd_split_retains>splits);
        s_hd_keep_bracket=previous;s_hd_cpu_diag_enabled=old_diag;
    }
    fm_hd_batch_alias_readback_case(a,b,bytes);
    /* Every boundary scene with batching on: uniform offset vs attrib offset. */
    {
        const int previous=s_hd_keep_bracket;
        s_hd_opaque_batch_enabled=1;
        for(int keep=0;keep<2;++keep)for(int which=0;which<HD_BATCH_CASES;++which){
            s_hd_keep_bracket=keep;
            s_hd_batch_attrib=0;batch_fixture_scene(which,&fixture);batch_fixture_read(a);
            s_hd_batch_attrib=1;batch_fixture_scene(which,&fixture);batch_fixture_read(b);
            s_hd_batch_attrib=0;
            char label[128];snprintf(label,sizeof label,"attrib pixel parity keep=%d case %d",keep,which);
            FM_CHECK(label,!memcmp(a,b,bytes));
            FM_CHECK("attrib boundary scene drains and has no GL error",!s_hd_batch_n&&glGetError()==GL_NO_ERROR);
        }
        s_hd_keep_bracket=previous;s_hd_opaque_batch_enabled=0;
    }
    s_hd_batch_attrib=1;fm_hd_batch_alias_readback_case(a,b,bytes);s_hd_batch_attrib=0;   /* case A under attrib */
    fm_hd_batch_attrib_merge_cases(&fixture,a,b,bytes);
    uint16_t exact[1024],palette[16];
    int exact_ok=fm_read_words(root,"words.bin",exact,1024)&&fm_read_words(root,"clut.bin",palette,16);
    FM_CHECK("batch exact-region fixture readable",exact_ok);
    if(exact_ok){
        GlSkinMaterialState state;char error[256];
        gl_renderer_skin_material_configure("stock",0,"stock",0,"configured","configured",1,&state,error,sizeof error);
        fm_upload(768,0,16,64,exact);fm_upload(0,480,16,1,palette);flush_cpu_upload();
        hd_texture_pack_reset_tracking(s_hd_pack);
        for(int mode=0;mode<2;++mode){
            s_hd_opaque_batch_enabled=mode;glb_set_mask_bits(0,0);
            glb_set_precise_triangle(0,0,0,0,0,0,0);glb_set_perspective_triangle(0,0,0,0);
            gpu_fill(0,0,320,240,0);gpu_fill(0,256,320,224,0);
            for(int buffer=0;buffer<2;++buffer){
                glb_set_draw_area(0,buffer*256,319,buffer*256+223);
                for(int part=0;part<2;++part){
                    int xs[3]={20+part*50,150+part*50,20+part*50};
                    int ys[3]={20+buffer*256,20+buffer*256,150+buffer*256};
                    const int us[3]={0,63,0},vs[3]={0,0,63},lim[4]={0,0,63,63};
                    const float colors[9]={1,1,1,1,1,1,1,1,1};
                    FM_CHECK("batched exact-region draw admitted",hd_on_textured_prim(xs,ys,us,vs,colors,12,0,480,1,-1,lim,0)==1);
                }
            }
            flush_tex_batch();batch_fixture_read(mode?b:a);
        }
        FM_CHECK("exact region and both framebuffer origins remain pixel-identical",!memcmp(a,b,bytes));
    }
    GlHdCpuDiag cpu;gl_renderer_hd_cpu_diag_get(&cpu);
    FM_CHECK("real GL groups multiple HD primitives",cpu.batch_flushes&&cpu.batched_primitives>cpu.batch_flushes&&cpu.max_batch_primitives==HD_OPAQUE_BATCH_MAX);
    FM_CHECK("identical draw state does not split a compatible batch",cpu.batch_state_skips>0);
    s_hd_opaque_batch_enabled=0;
    HdTexSlot *slot=hd_tex_find(0x95A3BCF8u,0x723E222Cu);if(slot)hd_tex_release_slot(slot);
    free(pixels);free(a);free(b);
}
