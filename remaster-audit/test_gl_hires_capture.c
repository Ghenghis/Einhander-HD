/* Include the production renderer so the fixture can seed its real GL FBO
 * independently of the deliberately native software mirror. No game runs. */
#ifndef HD_RENDERER_SOURCE
#define HD_RENDERER_SOURCE "../windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c"
#endif
#include HD_RENDERER_SOURCE

#define QA_PACK_ROW_LENGTH 0x0D02
#define QA_PACK_SKIP_ROWS 0x0D03
#define QA_PACK_SKIP_PIXELS 0x0D04
#define QA_READ_FRAMEBUFFER_BINDING 0x8CAA

static int qa_checks, qa_failures;
#define QA_CHECK(name, condition) do { int ok=!!(condition); ++qa_checks; qa_failures+=!ok; \
    printf("CHECK %s %s\n",name,ok?"PASS":"FAIL"); } while(0)

static void qa_paint(int x,int y,int w,int h,uint32_t rgb) {
    p_glBindFramebuffer(PSXGL_DRAW_FRAMEBUFFER,s_hr_fbo);
    glEnable(GL_SCISSOR_TEST);glScissor(x,y,w,h);
    glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
    glClearColor((float)((rgb>>16)&255)/255.0f,(float)((rgb>>8)&255)/255.0f,
                 (float)(rgb&255)/255.0f,0.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glDisable(GL_SCISSOR_TEST);
    p_glBindFramebuffer(PSXGL_DRAW_FRAMEBUFFER,0);
}

static int qa_region(uint32_t *storage,int guard,int stride,int w,int h,
                     int origin_x,int origin_y,int wrap) {
    int mismatches=0;
    for(int row=0;row<h;++row)for(int col=0;col<w;++col){
        uint32_t expected=0xFF112233u;
        if(wrap){
            int left=col<s_scale,top=row<s_scale;
            expected=top?(left?0xFFFFFF00u:0xFF0000FFu):(left?0xFF00FF00u:0xFFFF0000u);
            if(row==3&&col==2)expected=0xFFDA1497u;
        }else{
            if(row==0)expected=0xFFD12149u;
            if(row==h-1)expected=0xFF135BDDu;
            if(row==3&&col==5)expected=0xFF29D047u;
        }
        if(storage[guard+row*stride+col]!=expected)++mismatches;
    }
    printf("PIXELS origin=(%d,%d) mismatches=%d/%d\n",origin_x,origin_y,mismatches,w*h);
    return mismatches==0;
}

static int qa_guards(const uint32_t *storage,int guard,int stride,int w,int h){
    for(int i=0;i<guard;++i)if(storage[i]!=0xDEADBEEFu)return 0;
    for(int row=0;row<h;++row)for(int col=w;col<stride;++col)
        if(storage[guard+row*stride+col]!=0xDEADBEEFu)return 0;
    for(int i=0;i<guard;++i)if(storage[guard+h*stride+i]!=0xDEADBEEFu)return 0;
    return 1;
}

int gl_hires_capture_regression(void) {
    const int S=9,guard=8,w=4*S,h=3*S,stride=w+5;
    const size_t words=(size_t)guard*2+(size_t)stride*h;
    uint32_t *storage=(uint32_t*)malloc(words*sizeof(uint32_t));
    if(!storage)return 2;
    for(size_t i=0;i<words;++i)storage[i]=0xDEADBEEFu;
    QA_CHECK("real GL scale nine with native SW mirror",s_raster_ok&&s_ctx&&s_scale==S&&sw_renderer_scale()==1);
    flush_tex_batch();flush_cpu_upload();
    qa_paint(0,0,VRAM_W*S,VRAM_H*S,0x112233);
    qa_paint(100*S,50*S,w,1,0xD12149);
    qa_paint(100*S,50*S+h-1,w,1,0x135BDD);
    qa_paint(100*S+5,50*S+3,1,1,0x29D047);
    /* Force a different native mirror so native resolve then upscale fails. */
    for(int y=50;y<53;++y)for(int x=100;x<104;++x)s_vram[y*VRAM_W+x]=0x7FFF;
    p_glBindFramebuffer(PSXGL_READ_FRAMEBUFFER,s_raw_fbo);
    glPixelStorei(GL_PACK_ALIGNMENT,8);
    glPixelStorei(QA_PACK_ROW_LENGTH,47);
    glPixelStorei(QA_PACK_SKIP_ROWS,2);
    glPixelStorei(QA_PACK_SKIP_PIXELS,3);
    int count=gr_render_display_hires(storage+guard,stride*4,100,50,4,3);
    QA_CHECK("complete supersampled subrectangle count",count==w*h);
    QA_CHECK("top-down ARGB and one-highres-pixel detail",qa_region(storage,guard,stride,w,h,100,50,0));
    QA_CHECK("byte-pitch row padding and outer guards",qa_guards(storage,guard,stride,w,h));
    GLint read_fbo=0,alignment=0,row_length=0,skip_rows=0,skip_pixels=0;
    glGetIntegerv(QA_READ_FRAMEBUFFER_BINDING,&read_fbo);
    glGetIntegerv(GL_PACK_ALIGNMENT,&alignment);
    glGetIntegerv(QA_PACK_ROW_LENGTH,&row_length);
    glGetIntegerv(QA_PACK_SKIP_ROWS,&skip_rows);
    glGetIntegerv(QA_PACK_SKIP_PIXELS,&skip_pixels);
    QA_CHECK("read FBO and all pack state restored",read_fbo==(GLint)s_raw_fbo&&alignment==8&&row_length==47&&skip_rows==2&&skip_pixels==3);
    p_glBindFramebuffer(PSXGL_READ_FRAMEBUFFER,0);
    glPixelStorei(GL_PACK_ALIGNMENT,4);glPixelStorei(QA_PACK_ROW_LENGTH,0);
    glPixelStorei(QA_PACK_SKIP_ROWS,0);glPixelStorei(QA_PACK_SKIP_PIXELS,0);
    free(storage);

    const int full_w=320*S,full_h=240*S;
    uint32_t *full=(uint32_t*)calloc((size_t)full_w*full_h,sizeof(uint32_t));
    if(!full)return 2;
    count=gr_render_display_hires(full,full_w*4,0,0,320,240);
    QA_CHECK("actual 2880 by 2160 display readback",count==full_w*full_h);
    QA_CHECK("4K readback retains unquantized GL RGB and alpha",full[0]==0xFF112233u&&full[(size_t)(50*S)*full_w+100*S]==0xFFD12149u&&full[(size_t)(50*S+3)*full_w+100*S+5]==0xFF29D047u&&full[(size_t)full_w*full_h-1]==0xFF112233u);
    free(full);

    qa_paint(0,0,S,S,0xFF0000);qa_paint((VRAM_W-1)*S,0,S,S,0x00FF00);
    qa_paint(0,(VRAM_H-1)*S,S,S,0x0000FF);
    qa_paint((VRAM_W-1)*S,(VRAM_H-1)*S,S,S,0xFFFF00);
    qa_paint((VRAM_W-1)*S+2,(VRAM_H-1)*S+3,1,1,0xDA1497);
    const int ww=2*S,hh=2*S,ws=ww+3;
    const size_t wrap_words=(size_t)guard*2+(size_t)ws*hh;
    storage=(uint32_t*)malloc(wrap_words*sizeof(uint32_t));
    if(!storage)return 2;
    for(int trial=0;trial<3;++trial){
        for(size_t i=0;i<wrap_words;++i)storage[i]=0xDEADBEEFu;
        int dx=trial==0?1023:trial==1?-1:2047,dy=trial==0?511:trial==1?-1:1023;
        count=gr_render_display_hires(storage+guard,ws*4,dx,dy,2,2);
        QA_CHECK("both VRAM axes wrap with positive modulo",count==ww*hh&&qa_region(storage,guard,ws,ww,hh,dx,dy,1));
        QA_CHECK("wrapped readback pitch guards",qa_guards(storage,guard,ws,ww,hh));
    }
    free(storage);

    uint32_t native[4]={0,0,0,0};
    s_vram[10*VRAM_W+10]=0x001F;s_vram[10*VRAM_W+11]=0x03E0;
    s_vram[11*VRAM_W+10]=0x7C00;s_vram[11*VRAM_W+11]=0x7FFF;
    int old_ok=s_raster_ok;s_raster_ok=0;
    count=gr_render_display_hires(native,8,10,10,2,2);s_raster_ok=old_ok;
    QA_CHECK("no GL native fallback retains native count and colors",count==4&&native[0]==0xFFFF0000u&&native[1]==0xFF00FF00u&&native[2]==0xFF0000FFu&&native[3]==0xFFFFFFFFu);
    gpu_write_gp1(0x08000010u);
    memset(native,0,sizeof native);
    count=gr_render_display_hires(native,8,10,10,2,2);
    QA_CHECK("depth24 fallback leaves native bytes authoritative",count==4&&native[0]==0xFFFF0000u&&native[1]==0xFF00FF00u&&native[2]==0xFF0000FFu&&native[3]==0xFFFFFFFFu);
    gpu_write_gp1(0x08000000u);
    QA_CHECK("invalid output arguments refused",gr_render_display_hires(NULL,16,0,0,2,2)==0&&gr_render_display_hires(native,8,0,0,2,2)==0&&gr_render_display_hires(native,16,0,0,0,1)==0&&gr_render_display_hires(native,16,0,0,1025,1)==0);
    QA_CHECK("no GL errors from highres capture",glGetError()==GL_NO_ERROR);
    printf("RESULT checks=%d failures=%d\n",qa_checks,qa_failures);
    return qa_failures?1:0;
}
