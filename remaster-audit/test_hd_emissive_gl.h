/* Actual asynchronous loader, GL mask resource and production fragment shader. */
static int em_acquire(HdTexturePack *pack,uint32_t hash,HdTexturePixels *px){
    for(int i=0;i<2000;++i){
        int status=hd_texture_pack_request_decode(pack,hash,0);
        if(status==HD_TEXTURE_LOOKUP_ERROR)return status;
        if(hd_texture_pack_acquire_decoded(pack,hash,0,px)==HD_TEXTURE_LOOKUP_FOUND)return HD_TEXTURE_LOOKUP_FOUND;
        SDL_Delay(1);
    }
    return HD_TEXTURE_LOOKUP_NONE;
}
static const char *EM_VS=
    "#version 330\n"
    "noperspective out vec2 v_uv; noperspective out vec4 v_col;\n"
    "smooth out vec2 v_uv_p;flat out int v_persp;flat out int v_raw;\n"
    "flat out ivec2 v_tpage;flat out ivec4 v_limits;flat out int v_semi;\n"
    "uniform vec2 phase;uniform float skew;uniform int em_raw;uniform vec3 em_col;\n"
    "void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);\n"
    "gl_Position=vec4(p*2.0-1.0,0,1);v_uv=vec2(phase.x+p.x*60.3+p.y*skew,phase.y+p.y*61.7);v_uv_p=v_uv;\n"
    "v_col=vec4(em_col,1.0);v_persp=0;v_raw=em_raw;v_tpage=ivec2(768,0);v_limits=ivec4(0,0,63,63);v_semi=1;}\n";
static void em_gate(GLuint program,int enabled,int raw){
    p_glUseProgram(program);fm_i(program,"u_hd_emissive",3);fm_i(program,"u_hd_emissive_enabled",enabled);fm_i(program,"em_raw",raw);
    p_glUniform3f(p_glGetUniformLocation(program,"em_col"),.25f,.25f,.25f);
}
static void fm_emissive_regression(const char *root){
    char path[2048],error[512]={0};snprintf(path,sizeof path,"%s/../emissive-pack",root);
    uint32_t hashes[3];uint16_t raw[1024];
    for(int k=0;k<3;++k){for(int i=0;i<1024;++i)raw[i]=(uint16_t)(0x1111*(k+1));hashes[k]=hd_texture_crc32_words_le(raw,1024);}
    HdTexturePack *pack=NULL;HdTexturePixels pixels={0};
    _putenv_s("PSXRECOMP_HD_EMISSIVE","");
    int created=hd_texture_pack_create(path,&pack,error,sizeof error);
    FM_CHECK("unmasked pack opens with mask companions ignored as keys",created&&pack);
    if(!pack)return;
    hd_texture_pack_set_decode_budget(pack,64*64*4);
    int ready=em_acquire(pack,hashes[0],&pixels);
    FM_CHECK("startup off keeps original RGBA-only budget and no mask",ready==HD_TEXTURE_LOOKUP_FOUND&&!pixels.emissive&&pixels.width==64);
    hd_texture_pixels_release(&pixels);hd_texture_pack_destroy(pack);pack=NULL;
    _putenv_s("PSXRECOMP_HD_EMISSIVE","1");
    created=hd_texture_pack_create(path,&pack,error,sizeof error);FM_CHECK("masked pack opens",created&&pack);
    if(!pack)return;
    ready=em_acquire(pack,hashes[0],&pixels);
    FM_CHECK("worker decodes grayscale mask into shared lease",ready==HD_TEXTURE_LOOKUP_FOUND&&pixels.emissive&&pixels.emissive_stride==64&&pixels.emissive[0]==0&&pixels.emissive[32]==128&&pixels.emissive[63]==255);
    for(int k=1;k<3;++k){
        HdTexturePixels invalid={0};int found=em_acquire(pack,hashes[k],&invalid);
        FM_CHECK("wrong dimensions or RGB mask cannot affect replacement",found==HD_TEXTURE_LOOKUP_FOUND&&!invalid.emissive&&invalid.rgba);
        hd_texture_pixels_release(&invalid);
    }
    if(ready!=HD_TEXTURE_LOOKUP_FOUND||!pixels.emissive){hd_texture_pixels_release(&pixels);hd_texture_pack_destroy(pack);return;}
    p_glActiveTexture(PSXGL_TEXTURE0);hd_tex_object(hashes[0],0,&pixels);HdTexSlot *slot=hd_tex_find(hashes[0],0);
    FM_CHECK("GL uploads a mask companion for the admitted replacement",slot&&slot->emissive_tex&&glIsTexture(slot->emissive_tex));
    /* Exercise the production adapter, including its per-key uniform reset. */
    HdTexturePack *prior_pack=s_hd_pack;int prior_enabled=s_hd_emissive_enabled;
    s_hd_pack=pack;s_hd_emissive_enabled=1;glb_set_draw_area(0,0,319,239);
    typedef void (APIENTRY *EmUniformGet)(GLuint,GLint,GLint*);
    EmUniformGet get_uniform=(EmUniformGet)SDL_GL_GetProcAddress("glGetUniformiv");
    const int xs[3]={20,52,20},ys[3]={20,20,52},us[3]={0,15,0},vs[3]={0,0,63},lim[4]={0,0,15,63};
    const float colours[9]={.25f,.25f,.25f,.25f,.25f,.25f,.25f,.25f,.25f};
    for(int k=0;k<2;++k){
        for(int i=0;i<1024;++i)raw[i]=(uint16_t)(0x1111*(k+1));
        fm_upload(832,0,16,64,raw);flush_cpu_upload();
        int drawn=hd_on_textured_prim(xs,ys,us,vs,colours,13,0,0,0,-1,lim,2);flush_hd_batch();
        GLint gate=-1;if(get_uniform)get_uniform(s_hd_prog,s_hd_uEmissiveEnabled,&gate);
        FM_CHECK("production draw binds masked key and resets gate on next unmasked key",drawn&&gate==(k==0));
        if(!k){GLint bound=0;p_glActiveTexture(PSXGL_TEXTURE0+3);glGetIntegerv(GL_TEXTURE_BINDING_2D,&bound);p_glActiveTexture(PSXGL_TEXTURE0);
            FM_CHECK("production draw binds its admitted companion texture",slot&&bound==(GLint)slot->emissive_tex);}
    }
    s_hd_pack=prior_pack;s_hd_emissive_enabled=prior_enabled;
    hd_texture_pack_destroy(pack);pack=NULL;
    FM_CHECK("mask lease survives pack destruction",pixels.emissive[32]==128&&pixels.rgba[0]==100);
    if(slot&&slot->emissive_tex){
        GLuint program=build_program_ex(EM_VS,HD_FS,1),baseline=build_program_ex(EM_VS,facade_baseline_hd_fs,1);
        FM_CHECK("emissive production and original shaders compile",program&&baseline);
        if(program&&baseline){
            unsigned char a[64*64*4],b[64*64*4],old[64*64*4];
            p_glActiveTexture(PSXGL_TEXTURE0+3);glBindTexture(GL_TEXTURE_2D,slot->emissive_tex);
            for(int filter=0;filter<=1;++filter){
                fm_filter_mode=filter;em_gate(baseline,0,0);fm_render(baseline,slot,0,0,0,0,old);
                em_gate(program,0,0);fm_render(program,slot,0,0,0,0,a);
                FM_CHECK("unmasked shader remains byte-identical under modulation",!memcmp(a,old,sizeof a));
                em_gate(program,1,0);fm_render(program,slot,0,0,0,0,b);
                const int left=(32*64+8)*4,mid=(32*64+32)*4,right=(32*64+52)*4;
                FM_CHECK("zero mask preserves dark wall",!memcmp(a+left,b+left,4)&&abs((int)b[left]-50)<=1);
                FM_CHECK("half mask interpolates vertex modulation",abs((int)b[mid]-75)<=1&&abs((int)b[mid+1]-113)<=1&&abs((int)b[mid+2]-150)<=1);
                FM_CHECK("full mask preserves authored lit colour",abs((int)b[right]-100)<=1&&abs((int)b[right+1]-150)<=1&&abs((int)b[right+2]-200)<=1);
                int classes_same=1;for(int i=3;i<(int)sizeof a;i+=4)if(a[i]!=b[i])classes_same=0;
                FM_CHECK("mask leaves cutout and STP classes unchanged",classes_same);
                em_gate(program,0,0);p_glUniform3f(p_glGetUniformLocation(program,"em_col"),.75f,.25f,.5f);
                fm_render(program,slot,0,0,0,0,a);
                em_gate(program,1,0);p_glUniform3f(p_glGetUniformLocation(program,"em_col"),.75f,.25f,.5f);
                fm_render(program,slot,0,0,0,0,b);
                FM_CHECK("mask retains above-neutral channels while lifting shaded channels",abs((int)b[right]-150)<=1&&abs((int)b[right+1]-150)<=1&&abs((int)b[right+2]-200)<=1&&a[right]==b[right]&&a[right+2]==b[right+2]);
                FM_CHECK("partial mask cannot dim above-neutral vertex lighting",abs((int)b[mid]-150)<=1&&abs((int)b[mid+1]-113)<=1&&abs((int)b[mid+2]-200)<=1);
                em_gate(program,0,1);fm_render(program,slot,0,0,0,0,a);
                em_gate(program,1,1);fm_render(program,slot,0,0,0,0,b);
                FM_CHECK("raw primitive ignores emissive modulation",!memcmp(a,b,sizeof a));
                for(int pass=1;pass<=2;++pass){
                    em_gate(program,0,0);fm_render(program,slot,0,0,0,pass,a);
                    em_gate(program,1,0);fm_render(program,slot,0,0,0,pass,b);
                    classes_same=1;for(int i=3;i<(int)sizeof a;i+=4)if(a[i]!=b[i])classes_same=0;
                    FM_CHECK("each semitransparency pass retains native classes",classes_same);
                }
            }
            uint16_t native[64*64];for(int i=0;i<64*64;++i)native[i]=0x4210;
            fm_upload(768,0,64,64,native);flush_cpu_upload();
            p_glActiveTexture(PSXGL_TEXTURE0+2);glBindTexture(GL_TEXTURE_2D,s_raw_tex);fm_native_edge=32;
            p_glUseProgram(program);fm_i(program,"u_hd_native",2);
            em_gate(program,0,0);fm_render(program,slot,0,0,0,0,a);
            em_gate(program,1,0);fm_render(program,slot,0,0,0,0,b);
            FM_CHECK("native edge fallback stays modulated despite mask",!memcmp(a+(32*64+52)*4,b+(32*64+52)*4,4)&&abs((int)b[(32*64+52)*4]-66)<=1);
            fm_native_edge=0;fm_filter_mode=1; /* programs die with this hidden GL context */
        }
        hd_tex_release_slot(slot);FM_CHECK("mask GL resource and byte budget released with owning slot",!slot->tex&&!slot->emissive_tex&&!s_hd_emissive_bytes);
    }
    hd_texture_pixels_release(&pixels);
    created=hd_texture_pack_create(path,&pack,error,sizeof error);
    if(created&&pack){hd_texture_pack_set_decode_budget(pack,64*64*4);int found=em_acquire(pack,hashes[0],&pixels);
        FM_CHECK("mask bytes count against unchanged decode budget",found==HD_TEXTURE_LOOKUP_ERROR);hd_texture_pixels_release(&pixels);hd_texture_pack_destroy(pack);}
    _putenv_s("PSXRECOMP_HD_EMISSIVE","");p_glActiveTexture(PSXGL_TEXTURE0);
    FM_CHECK("emissive fixture ends without GL errors",glGetError()==GL_NO_ERROR);
}
