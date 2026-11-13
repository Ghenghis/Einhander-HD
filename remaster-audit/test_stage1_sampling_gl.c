/* Extend the existing real-GL shader, alpha and cache regressions. Synthetic
 * fixtures establish sampler behavior, not game-source or artwork acceptance. */
#define facade_motion_gl_regression legacy_facade_motion_gl_regression
#include "test_facade_motion_gl.c"
#undef facade_motion_gl_regression
#include "test_hd_opaque_batch_gl.h"

int facade_motion_gl_regression(const char *root,int expected_world) {
    int world=s_hd_world_sampling;
    s_hd_world_sampling=0;
    int prior=legacy_facade_motion_gl_regression(root,0);
    s_hd_world_sampling=world;
    if(prior)return prior;
    FM_CHECK("world startup opt-in is explicit",world==expected_world);
    HdTextureSourceMatch m={0};HdTextureDrawQuery q={0};
    m.texture_hash=0x95A3BCF8u;m.palette_hash=0x723E222Cu;
    m.upload_width_words=64;m.upload_height=256;s_tex_filter=1;
    FM_CHECK("green atlas sampling follows world toggle",hd_stage1_world_sampling_match(&m,&q)==expected_world);
    m.palette_hash=0xE01F52F8u;
    FM_CHECK("admitted palette variants share sampling policy",hd_stage1_world_sampling_match(&m,&q)==expected_world);
    m.texture_hash=0x282438F3u;
    FM_CHECK("title and UI family excluded",!hd_stage1_world_sampling_match(&m,&q));
    m.texture_hash=0x95A3BCF8u;m.upload_height=64;
    FM_CHECK("different atlas geometry excluded",!hd_stage1_world_sampling_match(&m,&q));
    m.upload_height=256;q.depth=1;
    FM_CHECK("different native depth excluded",!hd_stage1_world_sampling_match(&m,&q));
    q.depth=0;s_tex_filter=0;
    FM_CHECK("nearest filtering preference preserved",!hd_stage1_world_sampling_match(&m,&q));s_tex_filter=1;
    memset(&m,0,sizeof m);m.exact_region=1;m.texture_hash=0x74EF95B7u;m.palette_hash=0xB30D16F0u;
    m.region_x=800;m.upload_width_words=16;m.upload_height=64;q.clut_x=16;q.clut_y=480;
    FM_CHECK("matched facade registered geometry allowed",hd_stage1_world_sampling_match(&m,&q)==expected_world);
    m.region_x=768;
    FM_CHECK("neighbor source geometry mismatch excluded",!hd_stage1_world_sampling_match(&m,&q));

    unsigned char *pixels=(unsigned char*)malloc(1024u*1024u*4u);
    unsigned char a[64*64*4],b[64*64*4];
    if(!pixels)return 2;
    for(int y=0;y<1024;++y)for(int x=0;x<1024;++x) {
        size_t i=((size_t)y*1024+x)*4;unsigned char v=((x^y)&1)?192:64;
        pixels[i]=pixels[i+1]=pixels[i+2]=v;pixels[i+3]=x<341?0:x<683?127:255;
    }
    HdTexturePixels px={0};px.rgba=pixels;px.width=px.height=1024;px.stride=4096;
    hd_tex_object(0x95A3BCF8u,0x723E222Cu,&px);
    HdTexSlot *slot=hd_tex_find(0x95A3BCF8u,0x723E222Cu);
    GLuint old_program=fm_program(facade_baseline_hd_fs),program=fm_program(HD_FS);
    FM_CHECK("world production shader compiles",old_program&&program);
    if(!old_program||!program){free(pixels);return 3;}
    fm_render(old_program,slot,0,0,0,0,a);
    fm_render(program,slot,expected_world,0,0,0,b);
    if(!expected_world) {
        FM_CHECK("world off remains byte-identical",!memcmp(a,b,sizeof a)&&!slot->facade_mips_ready);
    } else {
        FM_CHECK("world minification filtered without changing level-zero ownership",slot->facade_mips_ready&&fm_error(b)<2);
        int alpha_ok=1;
        for(int pass=0;pass<3;++pass) {
            fm_render(old_program,slot,0,0,0,pass,a);
            fm_render(program,slot,1,0,0,pass,b);
            for(int i=0;i<64*64;++i)if(a[i*4+3]!=b[i*4+3])alpha_ok=0;
        }
        FM_CHECK("world cutout and STP categorical classes unchanged",alpha_ok);
        fm_render(program,slot,0,0,0,0,a);fm_render(old_program,slot,0,0,0,0,b);
        FM_CHECK("nonmatching world draw restores legacy sampling",!memcmp(a,b,sizeof a)&&slot->facade_anisotropy==1);
    }
    hd_tex_release_slot(slot);free(pixels);
    /* Exercise the production draw adapter, not just the sampler helper. */
    uint16_t words[64*256],palette[16];char path[2048];int fixture_ok=1;
    snprintf(path,sizeof path,"%s/95A3BCF8-723E222C.words.bin",root);
    FILE *file=fopen(path,"rb");
    if(!file)fixture_ok=0;
    else {fixture_ok=fread(words,2,64*256,file)==64*256&&fgetc(file)==EOF;fclose(file);}
    snprintf(path,sizeof path,"%s/95A3BCF8-723E222C.clut.bin",root);file=fopen(path,"rb");
    if(!file)fixture_ok=0;
    else {fixture_ok&=fread(palette,2,16,file)==16&&fgetc(file)==EOF;fclose(file);}
    FM_CHECK("real green native source CRC",fixture_ok&&hd_texture_crc32_words_le(words,64*256)==0x95A3BCF8u&&hd_texture_crc32_words_le(palette,16)==0x723E222Cu);
    if(fixture_ok) {
        fm_upload(640,0,64,256,words);fm_upload(16,480,16,1,palette);flush_cpu_upload();
        const int xs[3]={20,52,20},ys[3]={20,20,52},us[3]={0,63,0},vs[3]={0,0,63},lim[4]={0,0,63,63};
        const float color[9]={1,1,1,1,1,1,1,1,1};int drawn=0;
        for(int i=0;i<2000&&!drawn;++i){drawn=hd_on_textured_prim(xs,ys,us,vs,color,10,16,480,1,-1,lim,0);if(!drawn)SDL_Delay(1);}
        slot=hd_tex_find(0x95A3BCF8u,0x723E222Cu);
        FM_CHECK("production green draw applies requested sampling",drawn&&slot&&slot->facade_mips_ready==expected_world);
        FM_CHECK("production green draw has no GL errors",glGetError()==GL_NO_ERROR);
    }
    GlHdCpuDiag cpu;
    gl_renderer_hd_cpu_diag_get(&cpu);
    FM_CHECK("CPU attribution disabled by default",!cpu.enabled&&!cpu.attempts&&!cpu.readbacks);
    /* Native observer: prove source identity through the production adapter,
     * while leaving native draw submission and CPU/GPU coherency untouched. */
    uint16_t hull[16*64];fixture_ok=1;
    snprintf(path,sizeof path,"%s/724E77DA-21FDE894.words.bin",root);file=fopen(path,"rb");
    if(!file)fixture_ok=0;
    else {fixture_ok=fread(hull,2,16*64,file)==16*64&&fgetc(file)==EOF;fclose(file);}
    snprintf(path,sizeof path,"%s/724E77DA-21FDE894.clut.bin",root);file=fopen(path,"rb");
    if(!file)fixture_ok=0;
    else {fixture_ok&=fread(palette,2,16,file)==16&&fgetc(file)==EOF;fclose(file);}
    FM_CHECK("audited hull source and palette CRC",fixture_ok&&hd_texture_crc32_words_le(hull,16*64)==0x724E77DAu&&hd_texture_crc32_words_le(palette,16)==0x21FDE894u);
    if(fixture_ok){
        fm_upload(864,256,16,64,hull);fm_upload(288,488,16,1,palette);flush_cpu_upload();
        glb_set_draw_area(0,0,319,239);s_player_draw_enabled=1;s_player_draw_only=1;
        s_hd_cpu_diag_enabled=1;memset(&s_hd_cpu_diag,0,sizeof(s_hd_cpu_diag));
        memset(&s_player_draw_tracker,0,sizeof(s_player_draw_tracker));
        memset(&s_player_draw_completed,0,sizeof(s_player_draw_completed));
        const int xs[3]={50,80,50},ys[3]={70,70,100},us[3]={128,191,128},vs[3]={0,0,63},lim[4]={128,0,191,63};
        const float color[9]={1,1,1,1,1,1,1,1,1};
        s_gpu_dirty=1;s_vram[5]=0xDEAD;
        int drawn=hd_on_textured_prim(xs,ys,us,vs,color,29,288,488,1,-1,lim,0);
        GlPlayerDrawState state;gl_renderer_player_draw_get(&state);
        FM_CHECK("partial frame is not published as the hull",!state.valid);
        player_draw_present_commit();gl_renderer_player_draw_get(&state);
        FM_CHECK("native observer reports the audited hull geometry",state.valid&&state.draws==1&&state.min_x==50&&state.max_x==80&&state.min_y==70&&state.max_y==100&&state.width==320&&state.height==240);
        FM_CHECK("native observer leaves native submission selected",!drawn&&!hd_tex_find(0x724E77DAu,0x21FDE894u));
        FM_CHECK("native observer never synchronizes CPU VRAM",s_gpu_dirty&&s_vram[5]==0xDEAD);
        gpu_copy_rect(0,0,960,128,4,4);
        gl_renderer_hd_cpu_diag_get(&cpu);
        FM_CHECK("native observer copy does not add HD tracking readback",!cpu.readbacks&&s_vram[5]==0xDEAD);
        FM_CHECK("native observer has no GL errors",glGetError()==GL_NO_ERROR);
        gl_renderer_hd_cpu_diag_get(&cpu);
        FM_CHECK("CPU observer attribution counts without decoding or drawing",cpu.enabled&&cpu.frequency&&cpu.attempts==1&&cpu.source_queries==1&&!cpu.submitted&&!cpu.decode_requests&&!cpu.readbacks&&!cpu.draw_ticks&&cpu.total_ticks>=cpu.source_ticks);
        HdTextureSourceMatch bad={0};HdTextureDrawQuery query={0};
        bad.texture_hash=0x724E77DAu;bad.palette_hash=0x21FDE894u;bad.upload_width_words=8;bad.upload_height=128;
        player_draw_on_source(&bad,&query,xs,ys);gl_renderer_player_draw_get(&state);
        FM_CHECK("different upload geometry cannot claim the hull",state.draws==1);
        palette[0]^=1;fm_upload(288,488,16,1,palette);flush_cpu_upload();
        drawn=hd_on_textured_prim(xs,ys,us,vs,color,29,288,488,1,-1,lim,0);
        player_draw_present_commit();gl_renderer_player_draw_get(&state);
        FM_CHECK("unproven palette does not take hull ownership",!drawn&&state.valid&&state.draws==1&&state.palette_hash==0x21FDE894u);
        s_player_draw_only=0;
        const int gus[3]={0,63,0},gvs[3]={0,0,63},glim[4]={0,0,63,63};
        drawn=hd_on_textured_prim(xs,ys,gus,gvs,color,10,16,480,1,-1,glim,0);
        gl_renderer_hd_cpu_diag_get(&cpu);
        FM_CHECK("CPU attribution separates resident GL draw work",drawn&&cpu.attempts==3&&cpu.submitted==1&&cpu.resident_hits==1&&!cpu.decode_requests&&cpu.draw_ticks>0);
        ensure_cpu();gl_renderer_hd_cpu_diag_get(&cpu);
        FM_CHECK("CPU attribution reports real readback wall time",cpu.readbacks==1&&cpu.readback_ticks>0&&!s_gpu_dirty);
    }
    fm_hd_opaque_batch_regression(root);
    /* The isolated fixture destroys its GL context immediately on return. */
    printf("WORLD_RESULT checks=%d failures=%d\n",fm_checks,fm_failures);
    return fm_failures?1:0;
}
