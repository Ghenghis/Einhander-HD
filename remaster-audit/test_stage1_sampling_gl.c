/* Extend the existing real-GL shader, alpha and cache regressions. Synthetic
 * fixtures establish sampler behavior, not game-source or artwork acceptance. */
#define facade_motion_gl_regression legacy_facade_motion_gl_regression
#include "test_facade_motion_gl.c"
#undef facade_motion_gl_regression

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
    /* The isolated fixture destroys its GL context immediately on return. */
    printf("WORLD_RESULT checks=%d failures=%d\n",fm_checks,fm_failures);
    return fm_failures?1:0;
}
