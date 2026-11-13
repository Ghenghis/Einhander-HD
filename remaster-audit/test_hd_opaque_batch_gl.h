/* Included after the production renderer, in a hidden GL fixture only. */
static void batch_hd_triangle(int variant,int semi,int narrow_uv) {
    int shift=variant?50:0;
    int xs[3]={20+shift,150+shift,20+shift},ys[3]={20+shift,20+shift,150+shift};
    int us[3]={narrow_uv?128:0,255,narrow_uv?128:0},vs[3]={0,0,255};
    int limits[4]={narrow_uv?128:0,0,255,255};
    float colors[9];
    for(int i=0;i<3;++i){colors[i*3]=variant?.2f:.8f;colors[i*3+1]=variant?.8f:.3f;colors[i*3+2]=.4f;}
    FM_CHECK("batch fixture source admitted",hd_on_textured_prim(xs,ys,us,vs,colors,10,16,480,0,semi,limits,0)==1);
}
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
    glb_set_mask_bits(0,0);glb_set_texture_filter(1);glb_set_draw_area(0,0,319,239);
    gpu_fill(0,0,320,240,0);
    if(which==5)glb_set_mask_bits(1,0);
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
static void fm_hd_opaque_batch_regression(const char *root) {
    FM_CHECK("opaque batch disabled by default",!hd_opaque_batch_enabled());
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
    for(int which=0;which<15;++which){
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
        s_hd_cpu_diag_enabled=1;s_hd_opaque_batch_enabled=1;
        for(int which=0;which<15;++which){
            s_hd_keep_bracket=0;batch_fixture_scene(which,&fixture);batch_fixture_read(a);
            s_hd_keep_bracket=1;batch_fixture_scene(which,&fixture);batch_fixture_read(b);
            char label[128];snprintf(label,sizeof label,"kept FBO pixel parity at native/HD boundary case %d",which);
            FM_CHECK(label,!memcmp(a,b,bytes));
            GLint framebuffer=-1;glGetIntegerv(0x8CA6 /*GL_DRAW_FRAMEBUFFER_BINDING*/,&framebuffer);
            FM_CHECK("kept FBO cannot leak beyond the immediate HD bracket",!s_hr_fbo_open&&!s_hr_keep_open&&framebuffer==0);
            FM_CHECK("kept FBO boundary has no GL error",glGetError()==GL_NO_ERROR);
        }
        FM_CHECK("real native-to-HD transitions skip owned FBO rebinds",s_hd_cpu_diag.hr_bracket_keeps>keeps&&s_hd_cpu_diag.hr_bracket_skips>skips);
        s_hd_keep_bracket=previous;s_hd_cpu_diag_enabled=old_diag;
    }
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
