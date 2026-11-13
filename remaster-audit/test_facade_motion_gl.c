/* Production renderer is included to test the real sampler/cache without
 * exporting test controls or launching a game. Fixture outputs are synthetic. */
#ifndef HD_RENDERER_SOURCE
#define HD_RENDERER_SOURCE "../windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c"
#endif
#include HD_RENDERER_SOURCE
#include "facade_baseline_shader.h"

static int fm_checks,fm_failures;
static int fm_filter_mode=1,fm_native_edge=0; /* isolated fixture controls */
#define FM_CHECK(name,value) do { int fm_check_result_=!!(value); ++fm_checks; fm_failures+=!fm_check_result_; \
    printf("CHECK %s %s\n",name,fm_check_result_?"PASS":"FAIL"); fflush(stdout); } while(0)

static const char *FM_VS=
    "#version 330\n"
    "noperspective out vec2 v_uv; noperspective out vec4 v_col;\n"
    "smooth out vec2 v_uv_p; flat out int v_persp; flat out int v_raw;\n"
    "flat out ivec2 v_tpage; flat out ivec4 v_limits; flat out int v_semi;\n"
    "uniform vec2 phase; uniform float skew;\n"
    "void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);\n"
    "gl_Position=vec4(p*2.0-1.0,0,1);\n"
    "v_uv=vec2(phase.x+p.x*60.3+p.y*skew,phase.y+p.y*61.7);v_uv_p=v_uv;\n"
    "v_col=vec4(0.5);v_persp=0;v_raw=1;v_tpage=ivec2(768,0);\n"
    "v_limits=ivec4(0,0,63,63);v_semi=1;}\n";

static GLuint fm_program(const char *fs) {return build_program_ex(FM_VS,fs,1);}
static void fm_i(GLuint p,const char *name,int value){p_glUniform1i(p_glGetUniformLocation(p,name),value);}
static void fm_f(GLuint p,const char *name,float value){p_glUniform1f(p_glGetUniformLocation(p,name),value);}

static void fm_render(GLuint program,HdTexSlot *slot,int motion,float phase,float skew,int pass,unsigned char *out) {
    static GLuint target,fbo,vao;
    if(!target) {
        target=make_tex(GL_RGBA8,64,64,GL_RGBA,GL_UNSIGNED_BYTE);
        p_glGenFramebuffers(1,&fbo);p_glBindFramebuffer(PSXGL_FRAMEBUFFER,fbo);
        p_glFramebufferTexture2D(PSXGL_FRAMEBUFFER,PSXGL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,target,0);
        p_glGenVertexArrays(1,&vao);
    }
    p_glBindFramebuffer(PSXGL_FRAMEBUFFER,fbo);glViewport(0,0,64,64);
    glDisable(GL_BLEND);glDisable(GL_STENCIL_TEST);glDisable(GL_SCISSOR_TEST);glDisable(GL_DITHER);
    glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
    glClearColor(19/255.f,37/255.f,61/255.f,51/255.f);glClear(GL_COLOR_BUFFER_BIT);
    p_glUseProgram(program);p_glActiveTexture(PSXGL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,slot->tex);
    int active=hd_facade_motion_sampling(slot,motion);
    fm_i(program,"u_hd",0);fm_i(program,"u_hd_native_edge",fm_native_edge);
    fm_i(program,"u_hd_facade_motion",active);fm_i(program,"u_filter",fm_filter_mode);
    fm_i(program,"u_skin_enabled",0);fm_i(program,"u_skin_detail_enabled",0);
    fm_i(program,"u_semipass",pass);fm_i(program,"u_semimode",0);fm_i(program,"u_maskset",0);
    fm_f(program,"u_shift",0.5f/9.0f);
    p_glUniform2f(p_glGetUniformLocation(program,"u_hd_off"),0,0);
    p_glUniform2f(p_glGetUniformLocation(program,"u_hd_dim"),64,64);
    p_glUniform2f(p_glGetUniformLocation(program,"phase"),phase,0.125f);fm_f(program,"skew",skew);
    p_glBindVertexArray(vao);glDrawArrays(GL_TRIANGLES,0,3);
    glPixelStorei(GL_PACK_ALIGNMENT,1);glReadPixels(0,0,64,64,GL_RGBA,GL_UNSIGNED_BYTE,out);
    glPixelStorei(GL_PACK_ALIGNMENT,4);p_glBindFramebuffer(PSXGL_FRAMEBUFFER,0);
}

static double fm_error(const unsigned char *image) {
    double total=0;unsigned n=0;
    for(int y=4;y<60;++y)for(int x=25;x<35;++x) {
        double d=(double)image[(y*64+x)*4]-128.0;total+=d*d;++n;
    }
    return sqrt(total/n);
}

static double fm_delta(const unsigned char *a,const unsigned char *b) {
    double total=0;unsigned n=0;
    for(int y=4;y<60;++y)for(int x=25;x<35;++x) {
        total+=abs((int)a[(y*64+x)*4]-(int)b[(y*64+x)*4]);++n;
    }
    return total/n;
}

static int fm_read_words(const char *root,const char *suffix,uint16_t *out,size_t count) {
    char path[2048];snprintf(path,sizeof path,"%s/52F33418-5E9B9AC3.%s",root,suffix);
    FILE *file=fopen(path,"rb");if(!file)return 0;
    for(size_t i=0;i<count;++i){int lo=fgetc(file),hi=fgetc(file);if(lo<0||hi<0){fclose(file);return 0;}out[i]=(uint16_t)(lo|(hi<<8));}
    int extra=fgetc(file);fclose(file);return extra==EOF;
}

static void fm_upload(int x,int y,int w,int h,const uint16_t *words) {
    gpu_write_gp0(0xA0000000);gpu_write_gp0((uint32_t)x|((uint32_t)y<<16));
    gpu_write_gp0((uint32_t)w|((uint32_t)h<<16));
    for(int i=0;i<w*h;i+=2)gpu_write_gp0((uint32_t)words[i]|((uint32_t)words[i+1]<<16));
}

int facade_motion_gl_regression(const char *root,int expected_enabled) {
    FM_CHECK("startup opt-in matches isolated process environment",s_hd_facade_motion.enabled==expected_enabled);
    HdFacadeMotion configured=s_hd_facade_motion;
    hd_facade_motion_parse(NULL,NULL);FM_CHECK("missing opt-in is disabled",!s_hd_facade_motion.enabled);
    hd_facade_motion_parse("true","nan");FM_CHECK("noncanonical opt-in and NaN fail closed",!s_hd_facade_motion.enabled&&s_hd_facade_motion.requested_anisotropy==1);
    hd_facade_motion_parse("1","64");FM_CHECK("finite AF request retained for capability clamp",s_hd_facade_motion.enabled&&s_hd_facade_motion.requested_anisotropy==64);
    s_hd_facade_motion=configured;s_tex_filter=1;
    HdTextureSourceMatch match={0};HdTextureDrawQuery query={0};
    match.exact_region=1;match.texture_hash=0x52F33418;match.palette_hash=0x5E9B9AC3;
    match.region_x=768;match.upload_width_words=16;match.upload_height=64;query.clut_y=480;
    FM_CHECK("exact key and geometry policy",hd_facade_motion_match(&match,&query)==expected_enabled);
    s_hd_facade_motion.enabled=1;
    match.exact_region=0;FM_CHECK("fullpage or upload alias is excluded",!hd_facade_motion_match(&match,&query));match.exact_region=1;
    match.texture_hash^=1;FM_CHECK("different key is excluded",!hd_facade_motion_match(&match,&query));match.texture_hash^=1;
    query.clut_x=16;FM_CHECK("different CLUT is excluded",!hd_facade_motion_match(&match,&query));query.clut_x=0;
    query.depth=1;FM_CHECK("different depth is excluded",!hd_facade_motion_match(&match,&query));query.depth=0;
    s_tex_filter=0;FM_CHECK("native nearest mode is excluded",!hd_facade_motion_match(&match,&query));s_tex_filter=1;
    s_hd_facade_motion=configured;

    const size_t bytes=(size_t)1024*1024*4;
    unsigned char *pixels=(unsigned char*)malloc(bytes),*again=(unsigned char*)malloc(bytes);
    unsigned char a[64*64*4],b[64*64*4],c[64*64*4];
    if(!pixels||!again)return 2;
    for(int y=0;y<1024;++y)for(int x=0;x<1024;++x) {
        size_t i=((size_t)y*1024+x)*4;unsigned char value=((x^y)&1)?192:64;
        pixels[i]=pixels[i+1]=pixels[i+2]=value;pixels[i+3]=x<341?0:x<683?127:255;
    }
    HdTexturePixels fixture={0};fixture.rgba=pixels;fixture.width=fixture.height=1024;fixture.stride=4096;
    GLuint texture=hd_tex_object(0x52F33418,0x5E9B9AC3,&fixture);
    HdTexSlot *slot=hd_tex_find(0x52F33418,0x5E9B9AC3);
    GLuint old_program=fm_program(facade_baseline_hd_fs),new_program=fm_program(HD_FS);
    FM_CHECK("baseline and current production shader compile",old_program&&new_program);
    if(!old_program||!new_program)return 3;
    fm_render(old_program,slot,0,0.0f,0.0f,0,a);
    fm_render(new_program,slot,0,0.0f,0.0f,0,b);
    FM_CHECK("default off shader is byte-identical to baseline",memcmp(a,b,sizeof a)==0&&!slot->facade_mips_ready);
    fm_render(new_program,slot,expected_enabled,0.0f,0.0f,0,c);
    if(expected_enabled) {
        FM_CHECK("mip chain generated once with bounded allocation",slot->facade_mips_ready&&slot->facade_mip_levels==11&&slot->facade_mip_bytes==1398100&&s_hd_facade_motion.generated==1);
        glBindTexture(GL_TEXTURE_2D,texture);glGetTexImage(GL_TEXTURE_2D,0,GL_RGBA,GL_UNSIGNED_BYTE,again);
        FM_CHECK("level zero RGB and categorical classes remain exact",memcmp(pixels,again,bytes)==0);
        if(s_hd_facade_motion.anisotropy_supported) {
            GLfloat actual_af=0;glGetTexParameterfv(GL_TEXTURE_2D,GL_TEXTURE_MAX_ANISOTROPY_EXT,&actual_af);
            FM_CHECK("AF request is applied within reported hardware limit",actual_af>=1&&actual_af<=s_hd_facade_motion.maximum_anisotropy&&actual_af==slot->facade_anisotropy);
        }
        int classes=1;
        for(int pass=0;pass<3;++pass) {
            fm_render(old_program,slot,0,0.0f,0.0f,pass,a);
            fm_render(new_program,slot,1,0.0f,0.0f,pass,b);
            for(int i=0;i<64*64;++i)if(a[i*4+3]!=b[i*4+3])classes=0;
        }
        FM_CHECK("minified 0/127/255 discard and STP pass ownership unchanged",classes);
        fm_render(old_program,slot,0,0.0f,0.0f,0,a);
        fm_render(new_program,slot,1,0.0f,0.0f,0,b);
        double before=fm_error(a),after=fm_error(b);
        printf("MINIFY baseline_rmse=%.6f mip_rmse=%.6f\n",before,after);
        FM_CHECK("minified checker energy converges to expected mean",before>5.0&&after<2.0&&after<before*.25);
        fm_render(new_program,slot,1,0.025f,5.0f,0,c);
        FM_CHECK("oblique shifted sampling retains filtered energy",fm_error(c)<2.0);
        double moving_baseline=0,moving_mips=0;
        unsigned char baseline_previous[64*64*4],mip_previous[64*64*4];
        fm_render(old_program,slot,0,0.0f,0.0f,0,baseline_previous);
        fm_render(new_program,slot,1,0.0f,0.0f,0,mip_previous);
        for(int frame=1;frame<=8;++frame) {
            fm_render(old_program,slot,0,frame*.0125f,0.0f,0,a);
            fm_render(new_program,slot,1,frame*.0125f,0.0f,0,b);
            moving_baseline+=fm_delta(a,baseline_previous);moving_mips+=fm_delta(b,mip_previous);
            memcpy(baseline_previous,a,sizeof a);memcpy(mip_previous,b,sizeof b);
        }
        printf("MOTION phases=9 baseline_delta=%.6f mip_delta=%.6f\n",moving_baseline/8,moving_mips/8);
        FM_CHECK("subpixel motion reduces checker shimmer",moving_baseline>8&&moving_mips<.5);
        unsigned generated=s_hd_facade_motion.generated;
        fm_render(new_program,slot,0,0.0f,0.0f,0,a);
        fm_render(old_program,slot,0,0.0f,0.0f,0,b);
        FM_CHECK("nonmatching draw restores exact original sampling",memcmp(a,b,sizeof a)==0&&slot->facade_anisotropy==1.0f);
        fm_render(new_program,slot,1,0.0f,0.0f,0,a);
        FM_CHECK("resident draw does not regenerate mip chain",s_hd_facade_motion.generated==generated);
        int support=s_hd_facade_motion.anisotropy_supported;
        fm_render(new_program,slot,0,0.0f,0.0f,0,a);
        s_hd_facade_motion.anisotropy_supported=0;
        fm_render(new_program,slot,1,0.0f,0.0f,0,a);
        FM_CHECK("unsupported AF retains trilinear without GL error",slot->facade_mips_ready&&glGetError()==GL_NO_ERROR);
        s_hd_facade_motion.anisotropy_supported=support;
        fixture.rgba=again;hd_tex_object(0x52F33418,0x5E9B9AC3,&fixture);
        slot=hd_tex_find(0x52F33418,0x5E9B9AC3);
        FM_CHECK("level zero reupload clears mip and memory state",!slot->facade_mips_ready&&s_hd_facade_motion.resident_mip_bytes==0);
        for(size_t i=0;i<bytes;i+=4)if(pixels[i+3]==255)pixels[i]=pixels[i+1]=pixels[i+2]=0;
        fixture.rgba=pixels;hd_tex_object(0x52F33418,0x5E9B9AC3,&fixture);
        slot=hd_tex_find(0x52F33418,0x5E9B9AC3);
        int black_classes=1;
        for(int pass=0;pass<3;++pass) {
            fm_render(old_program,slot,0,.025f,0.0f,pass,a);
            fm_render(new_program,slot,1,.025f,0.0f,pass,b);
            for(int i=0;i<64*64;++i)if(a[i*4+3]!=b[i*4+3])black_classes=0;
            if(pass!=1)for(int y=4;y<60;++y)for(int x=49;x<60;++x)
                if(b[(y*64+x)*4+3]!=255 || b[(y*64+x)*4]!=0)black_classes=0;
        }
        FM_CHECK("black STP remains visible with exact pass ownership under mips",black_classes);
    } else FM_CHECK("disabled opt-in never allocates mip levels",!slot->facade_mips_ready&&memcmp(b,c,sizeof b)==0);

    /* A full renderer admission uses the real source words and CLUT. */
    hd_tex_release_slot(slot);free(pixels);free(again);
    gpu_hd_texture_config(1,root,NULL);hd_ensure_pack();
    uint16_t words[1024],palette[16];
    FM_CHECK("exact facade proof fixture readable",fm_read_words(root,"words.bin",words,1024)&&fm_read_words(root,"clut.bin",palette,16));
    fm_upload(768,0,16,64,words);fm_upload(0,480,16,1,palette);flush_cpu_upload();
    hd_texture_pack_reset_tracking(s_hd_pack);
    const int xs[3]={20,52,20},ys[3]={20,20,52},us[3]={0,63,0},vs[3]={0,0,63},lim[4]={0,0,63,63};
    const float color[9]={1,1,1,1,1,1,1,1,1};
    int drawn=0;
#define FM_DRAW() hd_on_textured_prim(xs,ys,us,vs,color,12,0,480,1,-1,lim,0)
    for(int i=0;i<2000&&!drawn;++i){drawn=FM_DRAW();if(!drawn)SDL_Delay(1);}
    FM_CHECK("actual exact facade asynchronously admitted",drawn==1);
    slot=hd_tex_find(0x52F33418,0x5E9B9AC3);
    FM_CHECK("actual draw enables only scoped opt-in sampler",slot&&slot->facade_mips_ready==expected_enabled);
    hd_texture_pack_set_decode_budget(s_hd_pack,0);
    FM_CHECK("resident facade survives CPU eviction",FM_DRAW()==1);
    if(slot)hd_tex_release_slot(slot);
    FM_CHECK("GPU eviction falls back until asynchronous decode",FM_DRAW()==0);
    hd_texture_pack_set_decode_budget(s_hd_pack,16*1024*1024);drawn=0;
    for(int i=0;i<2000&&!drawn;++i){drawn=FM_DRAW();if(!drawn)SDL_Delay(1);}
    slot=hd_tex_find(0x52F33418,0x5E9B9AC3);
    FM_CHECK("decode recovery regenerates scoped mip state",drawn&&slot&&slot->facade_mips_ready==expected_enabled);
    palette[1]^=1;fm_upload(0,480,16,1,palette);flush_cpu_upload();
    FM_CHECK("palette change rejects stale facade and mip alias",FM_DRAW()==0);
    FM_CHECK("no GL errors",glGetError()==GL_NO_ERROR);
    printf("RESULT checks=%d failures=%d\n",fm_checks,fm_failures);
    return fm_failures?1:0;
#undef FM_DRAW
}
