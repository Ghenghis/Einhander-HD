/* Compile the actual renderer in this translation unit so this regression can
 * force CPU cache eviction without adding test hooks to the runtime API. */
#ifndef HD_RENDERER_SOURCE
#define HD_RENDERER_SOURCE "../windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c"
#endif
#include HD_RENDERER_SOURCE

int hd_native_edge_regression(const char *root) {
    int checks=0,failures=0;
    printf("MODE native_cpu_authority=%d\n",s_cpu_auth_dual);
#define EDGE_CHECK(name,condition) do {int ok=!!(condition);++checks;failures+=!ok;printf("CHECK %s %s\n",name,ok?"PASS":"FAIL");} while(0)
    gpu_hd_texture_config(1,root,NULL);hd_ensure_pack();
    if(!s_hd_pack)return 2;
    hd_texture_pack_reset_tracking(s_hd_pack);
    s_hd_dump=1;snprintf(s_hd_dump_dir,sizeof s_hd_dump_dir,"%s/dump-%d",root,s_cpu_auth_dual?1:0);
    s_tex_filter=0;
    /* Production gpu_textured_triangle drains CPU uploads before entering the
     * private HD hook; preserve that ordering in this isolated harness too. */
    flush_cpu_upload();
    for(int case_index=0;case_index<4;++case_index){
        const int width=case_index==0?64:case_index==1?128:case_index==2?192:256;
        const int source_x=case_index==3?704:1024-width;
        const int source_y=256;
        for(int y=0;y<256;++y)for(int x=0;x<width;++x)s_vram[(source_y+y)*1024+source_x+x]=0x001f;
        hd_page_changed(&s_hd_pages,source_x,source_y,width,256,0);
        const int xs0[3]={20,20+width,20},ys0[3]={20,20,84};
        const int xs1[3]={20+width,20+width,20},ys1[3]={20,84,84};
        const int us0[3]={0,width,0},vs0[3]={0,0,64};
        const int us1[3]={width,width,0},vs1[3]={0,64,64};
        const int lim[4]={0,0,width-1,63};
        const float color[9]={1,1,1,1,1,1,1,1,1};
        const uint16_t page=(uint16_t)((source_x/64)|16);
        int drawn=0;
        for(int n=0;n<2000&&!drawn;++n){drawn=hd_on_textured_prim(xs0,ys0,us0,vs0,color,page,0,0,1,-1,lim,2);if(!drawn)SDL_Delay(1);}
        EDGE_CHECK("physical page asynchronous replacement admitted",drawn==1);
        EDGE_CHECK("second triangle replacement admitted",hd_on_textured_prim(xs1,ys1,us1,vs1,color,page,0,0,1,-1,lim,2)==1);
        uint16_t *readback=(uint16_t*)malloc((size_t)width*64*sizeof(uint16_t));
        int read_ok=readback&&gl_renderer_fbo_peek(20,20,width,64,readback),different=0;
        if(read_ok)for(int y=0;y<64;++y)for(int x=0;x<width;++x){
            const uint16_t expected=(uint16_t)((x%31+1)|((y%31+1)<<5)|(((x+y)%31+1)<<10));
            if(readback[y*width+x]!=expected)++different;
        }
        printf("UV width=%d read=%d mismatches=%d\n",width,read_ok,different);
        EDGE_CHECK("native UV to cropped replacement pixels exact",read_ok&&different==0);free(readback);
        if(width<256){
            int outside[4]={0,0,width,63},wrapped[4]={250,0,2,63};
            uint64_t queries=s_hd_proof_counts[1];
            EDGE_CHECK("UV beyond physical right edge rejected",hd_on_textured_prim(xs0,ys0,us0,vs0,color,page,0,0,1,-1,outside,2)==0&&s_hd_proof_counts[1]==queries);
            EDGE_CHECK("wrapped UV rejected before query",hd_on_textured_prim(xs0,ys0,us0,vs0,color,page,0,0,1,-1,wrapped,2)==0&&s_hd_proof_counts[1]==queries);
        }
        int sx[3]={source_x,source_x+10,source_x},sy[3]={256,256,266};
        EDGE_CHECK("self-referencing destination stays native",hd_on_textured_prim(sx,sy,us0,vs0,color,page,0,0,1,-1,lim,2)==0);
        s_tw_mask_x=1;
        EDGE_CHECK("texture-window query stays native",hd_on_textured_prim(xs0,ys0,us0,vs0,color,page,0,0,1,-1,lim,2)==0);
        s_tw_mask_x=0;
        EDGE_CHECK("framebuffer source page stays native",hd_on_textured_prim(xs0,ys0,us0,vs0,color,16,0,0,1,-1,lim,2)==0);
        if(width==64){
            /* Title-like full255px quad: only65destination columns survive
             * scissoring. The64word physical prefix uses its replacement;
             * the final wrapped column must equal an ordinary native draw. */
            const int tx0[3]={255,510,255},ty0[3]={20,20,84};
            const int tx1[3]={510,255,510},ty1[3]={20,84,84};
            const int tu0[3]={0,255,0},tu1[3]={255,0,255};
            const int tv0[3]={0,0,64},tv1[3]={0,64,64},tl[4]={0,0,254,63};
            uint16_t wrap[128];for(int n=0;n<128;++n)wrap[n]=0x03e0;
            for(int row=0;row<64;++row)for(int col=0;col<2;++col)s_vram[(256+row)*1024+col]=wrap[row*2+col];
            glBindTexture(GL_TEXTURE_2D,s_raw_tex);
            glTexSubImage2D(GL_TEXTURE_2D,0,0,256,2,64,PSXGL_RED_INTEGER,GL_UNSIGNED_SHORT,wrap);
            const int saved_area[4]={s_area_x1,s_area_y1,s_area_x2,s_area_y2};
            for(int filter=0;filter<2;++filter){
                s_tex_filter=filter;s_area_x1=0;s_area_x2=319;s_area_y1=20;s_area_y2=83;
                EDGE_CHECK("visible clipped title prefix admitted",hd_on_textured_prim(tx0,ty0,tu0,tv0,color,page,0,0,1,-1,tl,2)==1);
                EDGE_CHECK("visible clipped title second triangle admitted",hd_on_textured_prim(tx1,ty1,tu1,tv1,color,page,0,0,1,-1,tl,2)==1);
                uint16_t hybrid[65*64],control[65*64];
                int hy=gl_renderer_fbo_peek(255,20,65,64,hybrid);
                const int cy0[3]={120,120,184},cy1[3]={120,184,184};
                s_area_y1=120;s_area_y2=183;int saved_state=s_hd_state;s_hd_state=-1;
                gpu_textured_triangle(tx0,cy0,tu0,tv0,color,(uint16_t)(page|0x100),0,0,1,-1,tl);
                gpu_textured_triangle(tx1,cy1,tu1,tv1,color,(uint16_t)(page|0x100),0,0,1,-1,tl);
                s_hd_state=saved_state;
                int co=gl_renderer_fbo_peek(255,120,65,64,control),tail_exact=hy&&co,prefix_diff=0;
                for(int row=0;row<64;++row){
                    if(hybrid[row*65+64]!=control[row*65+64])tail_exact=0;
                    for(int col=0;col<64;++col)prefix_diff+=hybrid[row*65+col]!=control[row*65+col];
                }
                printf("TAIL filter=%d hybrid=%04x,%04x,%04x control=%04x,%04x,%04x\n",filter,hybrid[64],hybrid[32*65+64],hybrid[63*65+64],control[64],control[32*65+64],control[63*65+64]);
                EDGE_CHECK("wrapped visible column matches native renderer",tail_exact);
                EDGE_CHECK("visible physical prefix uses authored replacement",hy&&co&&prefix_diff>2000);
            }
            s_area_x1=saved_area[0];s_area_y1=saved_area[1];s_area_x2=saved_area[2];s_area_y2=saved_area[3];s_tex_filter=0;
        }
    }
    EDGE_CHECK("no native edge GL errors",glGetError()==GL_NO_ERROR);
    printf("RESULT checks=%d failures=%d\n",checks,failures);
    return failures?1:0;
#undef EDGE_CHECK
}

int hd_gpu_cache_regression(const char *root) {
    int checks=0, failures=0;
#define CHECK(name, condition) do { int ok=!!(condition); ++checks; failures+=!ok; \
    printf("CHECK %s %s\n", name, ok ? "PASS" : "FAIL"); } while(0)
    gpu_hd_texture_config(1,root,NULL);
    hd_ensure_pack();
    if (!s_hd_pack) return 2;
    uint16_t words[4]={0x801f,0x801f,0x801f,0x801f};
    uint32_t hash=0;
    for(int y=0;y<2;++y)for(int x=0;x<2;++x)s_vram[(256+y)*1024+512+x]=words[y*2+x];
    hd_texture_pack_track_upload(s_hd_pack,512,256,2,2,words,4,&hash);
    const int xs[3]={20,36,20}, ys[3]={20,20,36};
    const int us[3]={0,1,0}, vs[3]={0,0,1}, lim[4]={0,0,1,1};
    const float col[9]={1,1,1,1,1,1,1,1,1};
#define DRAW() hd_on_textured_prim(xs,ys,us,vs,col,0x118,0,0,1,-1,lim,2)
    int drawn=0;
    for(int n=0;n<2000 && !drawn;++n){drawn=DRAW();if(!drawn)SDL_Delay(1);}
    CHECK("initial asynchronous replacement draw",drawn==1);
    unsigned char pixels[8*8*4]={0};
    GLuint texture=0;
    for(int i=0;i<HD_TEX_CACHE_MAX;++i)if(s_hd_tex[i].tex && s_hd_tex[i].th==hash && !s_hd_tex[i].ph)texture=s_hd_tex[i].tex;
    if(texture){glBindTexture(GL_TEXTURE_2D,texture);glGetTexImage(GL_TEXTURE_2D,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels);}
    int exact=texture!=0;
    for(int i=0;i<8*8;++i)if(pixels[i*4]!=17 || pixels[i*4+1]!=34 || pixels[i*4+2]!=51 || pixels[i*4+3]!=255)exact=0;
    CHECK("GPU owns exact replacement pixels",exact);
    hd_texture_pack_set_decode_budget(s_hd_pack,0);
    CHECK("CPU image evicted and decoding disabled",hd_texture_pack_request_decode(s_hd_pack,hash,0)==HD_TEXTURE_LOOKUP_ERROR);
    CHECK("resident replacement draws after CPU eviction",DRAW()==1);
    uint16_t changed[4]={0x83e0,0x83e0,0x83e0,0x83e0};
    hd_texture_pack_track_upload(s_hd_pack,512,256,2,2,changed,4,NULL);
    CHECK("different source key stays native",DRAW()==0);
    hd_texture_pack_track_upload(s_hd_pack,512,256,2,2,words,4,NULL);
    CHECK("original key reuses resident texture",DRAW()==1);
    for(int i=0;i<HD_TEX_CACHE_MAX;++i)if(s_hd_tex[i].tex){glDeleteTextures(1,&s_hd_tex[i].tex);memset(&s_hd_tex[i],0,sizeof s_hd_tex[i]);}
    CHECK("GPU eviction uses native until decoded",DRAW()==0);
    hd_texture_pack_set_decode_budget(s_hd_pack,1024*1024);
    drawn=0;
    for(int n=0;n<2000 && !drawn;++n){drawn=DRAW();if(!drawn)SDL_Delay(1);}
    CHECK("GPU eviction recovers via asynchronous decode",drawn==1);
    CHECK("no GL errors",glGetError()==GL_NO_ERROR);
    printf("RESULT checks=%d failures=%d\n",checks,failures);
    return failures ? 1 : 0;
#undef DRAW
#undef CHECK
}
