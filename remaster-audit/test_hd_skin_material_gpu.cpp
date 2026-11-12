// Real GPU regression for the runtime's actual HD_FS, with its old shader as
// a negative control. Generated shader strings live next to this executable.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <GL/gl.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
#include "hd_skin_material.h"
#include "hd_skin_detail.h"
#include "hd_skin_live.h"
#define STB_IMAGE_IMPLEMENTATION
#include "../windows-x64/psxrecomp/runtime/third_party/stb_image.h"
#include "hd_material_shaders.h"
#include "hd_material_png_fixtures.h"

#define PROC(ret,name,...) using name##Type=ret(APIENTRY*)(__VA_ARGS__); static name##Type name
PROC(GLuint,pCreateShader,GLenum);
PROC(void,pShaderSource,GLuint,GLsizei,const char*const*,const GLint*);
PROC(void,pCompileShader,GLuint);
PROC(void,pGetShaderiv,GLuint,GLenum,GLint*);
PROC(void,pGetShaderInfoLog,GLuint,GLsizei,GLsizei*,char*);
PROC(GLuint,pCreateProgram,void);
PROC(void,pAttachShader,GLuint,GLuint);
PROC(void,pBindFragDataLocationIndexed,GLuint,GLuint,GLuint,const char*);
PROC(void,pLinkProgram,GLuint);
PROC(void,pGetProgramiv,GLuint,GLenum,GLint*);
PROC(void,pGetProgramInfoLog,GLuint,GLsizei,GLsizei*,char*);
PROC(void,pUseProgram,GLuint);
PROC(GLint,pGetUniformLocation,GLuint,const char*);
PROC(void,pUniform1i,GLint,GLint);
PROC(void,pUniform1f,GLint,GLfloat);
PROC(void,pUniform2f,GLint,GLfloat,GLfloat);
PROC(void,pUniform3f,GLint,GLfloat,GLfloat,GLfloat);
PROC(void,pActiveTexture,GLenum);
PROC(void,pGenerateMipmap,GLenum);
PROC(void,pGenVertexArrays,GLsizei,GLuint*);
PROC(void,pBindVertexArray,GLuint);
PROC(void,pGenFramebuffers,GLsizei,GLuint*);
PROC(void,pBindFramebuffer,GLenum,GLuint);
PROC(void,pFramebufferTexture2D,GLenum,GLenum,GLenum,GLuint,GLint);
PROC(GLenum,pCheckFramebufferStatus,GLenum);

static bool load() {
#define LOAD(name,glname) name=(name##Type)wglGetProcAddress(glname); if(!name)return false
    LOAD(pCreateShader,"glCreateShader"); LOAD(pShaderSource,"glShaderSource");
    LOAD(pCompileShader,"glCompileShader"); LOAD(pGetShaderiv,"glGetShaderiv");
    LOAD(pGetShaderInfoLog,"glGetShaderInfoLog"); LOAD(pCreateProgram,"glCreateProgram");
    LOAD(pAttachShader,"glAttachShader"); LOAD(pBindFragDataLocationIndexed,"glBindFragDataLocationIndexed");
    LOAD(pLinkProgram,"glLinkProgram"); LOAD(pGetProgramiv,"glGetProgramiv");
    LOAD(pGetProgramInfoLog,"glGetProgramInfoLog"); LOAD(pUseProgram,"glUseProgram");
    LOAD(pGetUniformLocation,"glGetUniformLocation"); LOAD(pUniform1i,"glUniform1i");
    LOAD(pUniform1f,"glUniform1f"); LOAD(pUniform2f,"glUniform2f"); LOAD(pUniform3f,"glUniform3f"); LOAD(pActiveTexture,"glActiveTexture"); LOAD(pGenerateMipmap,"glGenerateMipmap");
    LOAD(pGenVertexArrays,"glGenVertexArrays"); LOAD(pBindVertexArray,"glBindVertexArray");
    LOAD(pGenFramebuffers,"glGenFramebuffers"); LOAD(pBindFramebuffer,"glBindFramebuffer");
    LOAD(pFramebufferTexture2D,"glFramebufferTexture2D"); LOAD(pCheckFramebufferStatus,"glCheckFramebufferStatus");
    return true;
}

static GLuint shader(GLenum kind,const char*source) {
    GLuint s=pCreateShader(kind);pShaderSource(s,1,&source,nullptr);pCompileShader(s);
    GLint ok=0;pGetShaderiv(s,0x8B81,&ok);
    if(!ok){char log[4096]{};pGetShaderInfoLog(s,sizeof log,nullptr,log);std::fprintf(stderr,"shader: %s\n",log);return 0;}
    return s;
}

static const char* vertex=R"GLSL(#version 330
noperspective out vec2 v_uv; noperspective out vec4 v_col;
smooth out vec2 v_uv_p; flat out int v_persp; flat out int v_raw;
flat out ivec4 v_limits; flat out int v_semi;
void main(){ vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);
gl_Position=vec4(p*2.0-1.0,0,1);v_uv=vec2(p.x*48.0,p.y);v_uv_p=v_uv;
v_col=vec4(0.5);v_persp=0;v_raw=1;v_limits=ivec4(0,0,47,0);v_semi=1; }
)GLSL";

static GLuint program(const char* fs) {
    GLuint v=shader(0x8B31,vertex),f=shader(0x8B30,fs);
    if(!v||!f)return 0;
    GLuint p=pCreateProgram();pAttachShader(p,v);pAttachShader(p,f);
    pBindFragDataLocationIndexed(p,0,0,"frag");
    pBindFragDataLocationIndexed(p,0,1,"blend_factor");pLinkProgram(p);
    GLint ok=0;pGetProgramiv(p,0x8B82,&ok);
    if(!ok){char log[4096]{};pGetProgramInfoLog(p,sizeof log,nullptr,log);std::fprintf(stderr,"program: %s\n",log);return 0;}
    return p;
}


static float luma(const float* p){return p[0]*0.2126f+p[1]*0.7152f+p[2]*0.0722f;}
static int check_cpu(double* largest_error){
    HdSkinConfig c{},e{};int failures=0;
    if(hd_skin_config_parse(&c,nullptr,nullptr,nullptr)!=0||c.enabled)++failures;
    if(hd_skin_config_parse(&c,"stock",nullptr,nullptr)!=0||c.enabled)++failures;
    if(hd_skin_config_parse(&c,"aurora-teal",nullptr,nullptr)!=1||c.key_count!=5)++failures;
    if(hd_skin_config_parse_channel(&e,"crimson-red",nullptr,nullptr,1)!=1||e.key_count!=6)++failures;
    if(hd_skin_material_matches(&c,0x3594C110,0x527B28B9)||hd_skin_material_matches(&e,0x5CC44E5F,0x053D9A00))++failures;
    if(hd_skin_config_parse(&c,"aurora-teal","724E77DA-21FDE894","0.75")!=1||c.key_count!=1||hd_skin_material_matches(&c,0x5CC44E5F,0x053D9A00))++failures;
    const char* invalid_keys[]={"00000000-00000000","5CC44E5F-053D9A00,","3594C110-527B28B9","5CC44E5F-053D9A01","5CC44E5F-053D9A00garbage","E584DC41-21FDE894"};
    for(auto key:invalid_keys)if(hd_skin_config_parse(&c,"aurora-teal",key,nullptr)!=-1||c.enabled)++failures;
    const char* invalid_amount[]={"-1","1.1","nan","inf","0.4junk"," "};
    for(auto value:invalid_amount)if(hd_skin_config_parse(&c,"aurora-teal",nullptr,value)!=-1||c.enabled)++failures;
    if(hd_skin_config_parse(&c,"missing-profile",nullptr,nullptr)!=-1||c.enabled)++failures;
    if(hd_skin_config_parse(&c,"aurora-teal",nullptr,"0")!=0||c.enabled)++failures;
    if(hd_skin_config_parse(&c,"aurora-teal"," 5cc44e5f-053d9a00, 724e77da-21fde894 ","1")!=1||c.key_count!=2)++failures;
    HdSkinDetailConfig detail{};
    if(hd_skin_detail_parse(&detail,nullptr,nullptr,nullptr)!=0||detail.enabled)++failures;
    if(hd_skin_detail_parse(&detail,"example.png",nullptr,nullptr)!=1||detail.strength!=0.12f||detail.scale!=8.f)++failures;
    const char* invalid_detail_amount[]={"-1","0.36","nan","inf","0.2junk"};
    for(auto value:invalid_detail_amount)if(hd_skin_detail_parse(&detail,"example.png",value,nullptr)!=-1||detail.enabled)++failures;
    const char* invalid_scale[]={"0","65","nan","inf","8junk"};
    for(auto value:invalid_scale)if(hd_skin_detail_parse(&detail,"example.png",nullptr,value)!=-1||detail.enabled)++failures;
    if(hd_skin_detail_parse(&detail,"example.png","0",nullptr)!=0||detail.enabled)++failures;
    hd_skin_config_parse(&c,"stock",nullptr,nullptr);
    if(!hd_skin_detail_source_bounds(&c,0x5CC44E5F,0x053D9A00,64,64)||hd_skin_detail_source_bounds(&c,0x5CC44E5F,0x053D9A00,256,256))++failures;
    hd_skin_config_parse_channel(&e,"stock",nullptr,nullptr,1);
    if(!hd_skin_detail_source_bounds(&e,0x3594C110,0x527B28B9,256,8)||hd_skin_detail_source_bounds(&e,0x3594C110,0x527B28B9,256,256)||hd_skin_detail_source_bounds(&e,0x2294438F,0x527B28B9,256,256))++failures;
    if(!hd_skin_detail_dimensions_valid(1254,1254,4000000)||!hd_skin_detail_dimensions_valid(4096,4096,64000000)||hd_skin_detail_dimensions_valid(4097,4096,1000)||hd_skin_detail_dimensions_valid(0,12,1000)||hd_skin_detail_dimensions_valid(12,12,HD_SKIN_DETAIL_MAX_FILE_BYTES+1u))++failures;
    int png_w=0,png_h=0,png_c=0;
    if(!hd_skin_detail_png_preflight(detail_png_valid_rgb,sizeof detail_png_valid_rgb,&png_w,&png_h,&png_c,stbi_zlib_decode_buffer)||png_w!=1||png_h!=1||png_c!=3)++failures;
    if(!hd_skin_detail_png_preflight(detail_png_valid_rgba,sizeof detail_png_valid_rgba,&png_w,&png_h,&png_c,stbi_zlib_decode_buffer)||png_c!=4)++failures;
#define REJECT_PNG(name) if(hd_skin_detail_png_preflight(detail_png_##name,sizeof detail_png_##name,&png_w,&png_h,&png_c,stbi_zlib_decode_buffer))++failures
    REJECT_PNG(bomb);REJECT_PNG(short);REJECT_PNG(sixteen_bit);REJECT_PNG(interlaced);REJECT_PNG(chunk_length);REJECT_PNG(truncated);
#undef REJECT_PNG
    uint32_t seed=23;*largest_error=0;
    for(int profile=0;profile<HD_SKIN_PROFILE_COUNT;++profile)for(int sample=0;sample<4096;++sample){
        float source[4],out[4];
        for(int i=0;i<4;++i){seed=seed*1664525u+1013904223u;source[i]=(seed>>24)/255.f;}
        if(sample%16==0)source[0]=source[1]=source[2]=source[0];
        hd_skin_material_reference(&hd_skin_profiles[profile],1.f,source,out);
        double error=std::abs(luma(source)-luma(out));*largest_error=std::max(*largest_error,error);
        if(error>0.00001||out[3]!=source[3])++failures;
        for(int i=0;i<3;++i)if(out[i]<-0.000001f||out[i]>1.000001f)++failures;
        if(sample%16==0)for(int i=0;i<3;++i)if(out[i]!=source[i])++failures;
        hd_skin_material_reference(&hd_skin_profiles[profile],0.f,source,out);
        if(std::memcmp(source,out,sizeof source))++failures;
        float tile[4]={0.9f,0.6f,0.1f,0.f};
        hd_skin_detail_reference(source,tile,0.35f,out);
        if(out[3]!=source[3])++failures;
        if(sample%16==0)for(int i=0;i<3;++i)if(out[i]!=source[i])++failures;
    }
    const float stripe[4]={0.95f,0.62f,0.04f,0.5f}, blue[4]={0.05f,0.20f,0.75f,1.0f};
    float protected_color[4],changed_blue[4],tile[4]={0.9f,0.1f,0.3f,0.0f};
    hd_skin_material_reference_ex(&hd_skin_profiles[0],1.f,1,stripe,protected_color);
    if(std::memcmp(stripe,protected_color,sizeof stripe))++failures;
    hd_skin_detail_reference_ex(stripe,tile,1,0.35f,protected_color);
    if(std::memcmp(stripe,protected_color,sizeof stripe))++failures;
    hd_skin_material_reference_ex(&hd_skin_profiles[0],1.f,1,blue,changed_blue);
    if(!std::memcmp(blue,changed_blue,sizeof blue)||changed_blue[3]!=blue[3])++failures;
    return failures;
}

struct GpuResult{int rgb_errors=0,alpha_errors=0,draws=0,comparisons=0,changed=0;};
static GpuResult check_gpu(GLuint p){
    constexpr int W=48,H=8;GpuResult result;
    const unsigned char colors[16][3]={{14,62,191},{32,180,240},{200,24,20},{240,160,12},
        {24,120,52},{60,20,190},{125,125,125},{250,250,250},{0,0,0},{6,4,10},
        {40,42,44},{221,45,145},{22,201,125},{120,63,26},{75,80,193},{250,255,240}};
    std::vector<unsigned char> input(W*4),readback(W*H*4);
    for(int x=0;x<W;++x){for(int k=0;k<3;++k)input[x*4+k]=colors[x%16][k];input[x*4+3]=x/16==0?127:x/16==1?255:0;}
    GLuint tex=0;glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,0x812F);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,0x812F);
    glTexImage2D(GL_TEXTURE_2D,0,0x8058,W,1,0,GL_RGBA,GL_UNSIGNED_BYTE,input.data());
    pUseProgram(p);pUniform1i(pGetUniformLocation(p,"u_hd"),0);
    pUniform2f(pGetUniformLocation(p,"u_hd_off"),0,0);pUniform2f(pGetUniformLocation(p,"u_hd_dim"),W,1);
    pUniform1i(pGetUniformLocation(p,"u_maskset"),0);pUniform1i(pGetUniformLocation(p,"u_semimode"),0);
    pUniform1f(pGetUniformLocation(p,"u_shift"),0);
    const uint32_t texture_keys[]={0x5CC44E5F,0x3594C110,0x12345678,0x5CC44E5F};
    const uint32_t palette_keys[]={0x053D9A00,0x527B28B9,0x053D9A00,0xDEADBEEF};
    HdSkinConfig player{},enemy{};
    hd_skin_config_parse(&player,"stock",nullptr,nullptr);
    hd_skin_config_parse_channel(&enemy,"stock",nullptr,nullptr,1);
    for(int preserve=0;preserve<2;++preserve)for(int profile=-1;profile<HD_SKIN_PROFILE_COUNT;++profile){
        if(hd_skin_live_commit(&player,&enemy,1,profile<0?"stock":hd_skin_profiles[profile].id,75,
                profile<0?"stock":hd_skin_profiles[(profile+4)%HD_SKIN_PROFILE_COUNT].id,75)){++result.rgb_errors;continue;}
        for(int key=0;key<4;++key){
            const HdSkinConfig* config=hd_skin_material_matches(&player,texture_keys[key],palette_keys[key])?&player:
                hd_skin_material_matches(&enemy,texture_keys[key],palette_keys[key])?&enemy:nullptr;
            pUniform1i(pGetUniformLocation(p,"u_skin_enabled"),config!=nullptr);
            pUniform1i(pGetUniformLocation(p,"u_skin_preserve_accents"),preserve);
            if(config){float a[3],b[3];hd_skin_color_components(config->profile->primary_rgb,a);hd_skin_color_components(config->profile->accent_rgb,b);
                pUniform3f(pGetUniformLocation(p,"u_skin_primary"),a[0],a[1],a[2]);pUniform3f(pGetUniformLocation(p,"u_skin_accent"),b[0],b[1],b[2]);pUniform1f(pGetUniformLocation(p,"u_skin_strength"),config->strength);}
            for(int filter=0;filter<2;++filter)for(int pass=0;pass<3;++pass){
                glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,filter?GL_LINEAR:GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,filter?GL_LINEAR:GL_NEAREST);
                pUniform1i(pGetUniformLocation(p,"u_filter"),filter);pUniform1i(pGetUniformLocation(p,"u_semipass"),pass);
                glClearColor(17/255.f,19/255.f,23/255.f,51/255.f);glClear(GL_COLOR_BUFFER_BIT);
                glDrawArrays(GL_TRIANGLES,0,3);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,readback.data());++result.draws;
                for(int x=0;x<W;++x){
                    const bool stp=x/16==1;const bool discard=x/16==2||(pass==1&&stp)||(pass==2&&!stp);
                    float source[4],expected[4];for(int i=0;i<4;++i)source[i]=input[x*4+i]/255.f;
                    hd_skin_material_reference_ex(config?config->profile:nullptr,config?config->strength:0.f,preserve,source,expected);
                    auto* actual=&readback[((H/2)*W+x)*4];
                    for(int k=0;k<3;++k){int wanted=discard?(k==0?17:k==1?19:23):int(std::round(expected[k]*255));
                        if(std::abs(int(actual[k])-wanted)>(config?1:0))++result.rgb_errors;
                        if(!discard&&config&&std::abs(wanted-int(input[x*4+k]))>1)++result.changed;}
                    int wanted_alpha=discard?51:stp?255:0;if(actual[3]!=wanted_alpha)++result.alpha_errors;++result.comparisons;
                }
            }
        }
    }
    pUniform1i(pGetUniformLocation(p,"u_skin_preserve_accents"),0);
    return result;
}

static float mirrored(float value){value=std::fmod(value,2.f);if(value<0)value+=2.f;return value>1.f?2.f-value:value;}
static void sample_detail(const unsigned char* data,int width,int height,float u,float v,float out[4]){
    float fx=mirrored(u)*width-0.5f,fy=mirrored(v)*height-0.5f;
    int x=int(std::floor(fx)),y=int(std::floor(fy));float ax=fx-x,ay=fy-y;
    for(int c=0;c<4;++c){out[c]=0;for(int j=0;j<2;++j)for(int i=0;i<2;++i){
        int xx=std::max(0,std::min(width-1,x+i)),yy=std::max(0,std::min(height-1,y+j));
        out[c]+=data[(yy*width+xx)*4+c]/255.f*(i?ax:1-ax)*(j?ay:1-ay);
    }}
}

static GpuResult check_detail_gpu(GLuint p,int argc,char**argv,bool automatic_lod){
    constexpr int W=48,H=8;GpuResult result;
    const unsigned char colors[16][3]={{14,62,191},{32,180,240},{200,24,20},{240,160,12},
        {24,120,52},{60,20,190},{125,125,125},{250,250,250},{0,0,0},{6,4,10},
        {40,42,44},{221,45,145},{22,201,125},{120,63,26},{75,80,193},{250,255,240}};
    std::vector<unsigned char> input(W*4),readback(W*H*4);
    for(int x=0;x<W;++x){for(int k=0;k<3;++k)input[x*4+k]=colors[x%16][k];input[x*4+3]=x/16==0?127:x/16==1?255:0;}
    GLuint base_texture=0;pActiveTexture(0x84C0);glGenTextures(1,&base_texture);glBindTexture(GL_TEXTURE_2D,base_texture);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,0x812F);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,0x812F);
    glTexImage2D(GL_TEXTURE_2D,0,0x8058,W,1,0,GL_RGBA,GL_UNSIGNED_BYTE,input.data());
    pUseProgram(p);pUniform1i(pGetUniformLocation(p,"u_hd"),0);pUniform1i(pGetUniformLocation(p,"u_skin_detail"),1);
    pUniform2f(pGetUniformLocation(p,"u_hd_off"),0,0);pUniform2f(pGetUniformLocation(p,"u_hd_dim"),W,1);
    pUniform1i(pGetUniformLocation(p,"u_semimode"),0);pUniform1f(pGetUniformLocation(p,"u_shift"),0);
    for(int map=0;map<argc;++map){
        unsigned char fixture[4]={215,174,58,0};unsigned char* data=fixture;
        int width=1,height=1,components=4;
        if(map){
            FILE* file=std::fopen(argv[map],"rb");if(!file){++result.rgb_errors;continue;}
            std::fseek(file,0,SEEK_END);long size=std::ftell(file);std::fseek(file,0,SEEK_SET);
            if(size<8||(unsigned long)size>HD_SKIN_DETAIL_MAX_FILE_BYTES){std::fclose(file);++result.rgb_errors;continue;}
            std::vector<unsigned char> encoded((size_t)size);size_t got=std::fread(encoded.data(),1,encoded.size(),file);std::fclose(file);
            if(got!=encoded.size()||!hd_skin_detail_png_preflight(encoded.data(),encoded.size(),&width,&height,&components,stbi_zlib_decode_buffer)){++result.rgb_errors;continue;}
            data=stbi_load_from_memory(encoded.data(),(int)encoded.size(),&width,&height,&components,4);if(!data){++result.rgb_errors;continue;}
        }
        GLuint detail_texture=0;pActiveTexture(0x84C1);glGenTextures(1,&detail_texture);glBindTexture(GL_TEXTURE_2D,detail_texture);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,0x8370);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,0x8370);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,automatic_lod?0x2703:GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
        glTexImage2D(GL_TEXTURE_2D,0,0x8058,width,height,0,GL_RGBA,GL_UNSIGNED_BYTE,data);
        if(automatic_lod){
            pGenerateMipmap(GL_TEXTURE_2D);
            if(width>1){GLint mip_width=0;glGetTexLevelParameteriv(GL_TEXTURE_2D,1,GL_TEXTURE_WIDTH,&mip_width);if(mip_width!=width/2)++result.rgb_errors;}
        }
        if(glGetError()!=GL_NO_ERROR)++result.rgb_errors;
        pActiveTexture(0x84C0);
        for(int preserve=0;preserve<2;++preserve)for(int scenario=0;scenario<10;++scenario){
            const bool stock=scenario==7||scenario==8;
            const bool enemy_case=scenario==1||scenario==8;
            HdSkinConfig player{},enemy{};
            hd_skin_config_parse(&player,stock?"stock":"aurora-gilt",nullptr,"0.75");
            hd_skin_config_parse_channel(&enemy,stock?"stock":"gold-obsidian",nullptr,"0.75",1);
            uint32_t th=enemy_case?0x3594C110:0x724E77DA,ph=enemy_case?0x527B28B9:0x21FDE894;
            if(scenario==2)th=0x12345678;if(scenario==3)ph=0xDEADBEEF;
            const HdSkinConfig* material=hd_skin_key_matches(&player,th,ph)?&player:hd_skin_key_matches(&enemy,th,ph)?&enemy:nullptr;
            const bool palette=material&&material->enabled&&material->profile;
            const unsigned native_width=enemy_case?256:64,native_height=scenario==4?256:enemy_case?8:64;
            const bool detail=material&&hd_skin_detail_source_bounds(material,th,ph,native_width,native_height)&&scenario!=5&&scenario!=6&&scenario!=9;
            const float strength=enemy_case?0.23f:0.12f,scale=8.f;
            pUniform1i(pGetUniformLocation(p,"u_skin_enabled"),palette);
            pUniform1i(pGetUniformLocation(p,"u_skin_preserve_accents"),preserve);
            if(palette){float a[3],b[3];hd_skin_color_components(material->profile->primary_rgb,a);hd_skin_color_components(material->profile->accent_rgb,b);
                pUniform3f(pGetUniformLocation(p,"u_skin_primary"),a[0],a[1],a[2]);pUniform3f(pGetUniformLocation(p,"u_skin_accent"),b[0],b[1],b[2]);pUniform1f(pGetUniformLocation(p,"u_skin_strength"),material->strength);}
            pUniform1i(pGetUniformLocation(p,"u_skin_detail_enabled"),detail);
            pUniform1f(pGetUniformLocation(p,"u_skin_detail_strength"),scenario==6?0.f:strength);
            pUniform1f(pGetUniformLocation(p,"u_skin_detail_scale"),scale);
            for(int filter=0;filter<2;++filter)for(int pass=0;pass<3;++pass)for(int mask=0;mask<2;++mask){
                glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,filter?GL_LINEAR:GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,filter?GL_LINEAR:GL_NEAREST);
                pUniform1i(pGetUniformLocation(p,"u_filter"),filter);pUniform1i(pGetUniformLocation(p,"u_semipass"),pass);pUniform1i(pGetUniformLocation(p,"u_maskset"),mask);
                glClearColor(17/255.f,19/255.f,23/255.f,51/255.f);glClear(GL_COLOR_BUFFER_BIT);
                glDrawArrays(GL_TRIANGLES,0,3);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,readback.data());++result.draws;
                for(int x=0;x<W;++x){
                    const bool stp=x/16==1,discard=x/16==2||(pass==1&&stp)||(pass==2&&!stp);
                    float source[4],expected[4],without_detail[4],texel[4];for(int k=0;k<4;++k)source[k]=input[x*4+k]/255.f;
                    hd_skin_material_reference_ex(palette?material->profile:nullptr,palette?material->strength:0.f,preserve,source,expected);
                    std::memcpy(without_detail,expected,sizeof expected);
                    if(detail){sample_detail(data,width,height,(x+0.5f)*scale/64.f,((H/2+0.5f)/H)*scale/64.f,texel);hd_skin_detail_reference_ex(source,texel,preserve,strength,expected);}
                    auto* actual=&readback[((H/2)*W+x)*4];
                    for(int k=0;k<3;++k){int wanted=discard?(k==0?17:k==1?19:23):int(std::round(expected[k]*255));
                        float hi=std::max(source[0],std::max(source[1],source[2])),lo=std::min(source[0],std::min(source[1],source[2]));
                        const bool neutral=(hi-lo)/std::max(hi,0.0001f)<=0.12f;
                        if((!automatic_lod||!detail||!map||neutral||discard)&&std::abs(int(actual[k])-wanted)>((palette||detail)?2:0))++result.rgb_errors;
                        if(!discard&&detail&&std::abs(int(actual[k])-int(std::round(without_detail[k]*255)))>1)++result.changed;}
                    int wanted_alpha=discard?51:stp||mask?255:0;if(actual[3]!=wanted_alpha)++result.alpha_errors;++result.comparisons;
                }
            }
        }
        pActiveTexture(0x84C1);glDeleteTextures(1,&detail_texture);pActiveTexture(0x84C0);if(map)stbi_image_free(data);
    }
    pUniform1i(pGetUniformLocation(p,"u_skin_detail_enabled"),0);
    pUniform1i(pGetUniformLocation(p,"u_skin_preserve_accents"),0);
    return result;
}

int main(int argc,char**argv){
    double luma_error=0;int cpu_failures=check_cpu(&luma_error);
    WNDCLASSA cls{};cls.style=CS_OWNDC;cls.lpfnWndProc=DefWindowProcA;cls.hInstance=GetModuleHandleA(nullptr);cls.lpszClassName="EinhanderMaterialRegression";
    if(!RegisterClassA(&cls))return 2;
    HWND window=CreateWindowA(cls.lpszClassName,"Hidden material regression",WS_POPUP,0,0,48,8,nullptr,nullptr,cls.hInstance,nullptr);
    HDC dc=GetDC(window);PIXELFORMATDESCRIPTOR pfd{};pfd.nSize=sizeof pfd;pfd.nVersion=1;pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL;pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=32;pfd.cAlphaBits=8;
    int fmt=ChoosePixelFormat(dc,&pfd);if(!fmt||!SetPixelFormat(dc,fmt,&pfd))return 3;
    HGLRC context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context)||!load())return 4;
    GLuint target=0,fbo=0,vao=0;glGenTextures(1,&target);glBindTexture(GL_TEXTURE_2D,target);glTexImage2D(GL_TEXTURE_2D,0,0x8058,48,8,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
    pGenFramebuffers(1,&fbo);pBindFramebuffer(0x8D40,fbo);pFramebufferTexture2D(0x8D40,0x8CE0,GL_TEXTURE_2D,target,0);if(pCheckFramebufferStatus(0x8D40)!=0x8CD5)return 5;
    pGenVertexArrays(1,&vao);pBindVertexArray(vao);glViewport(0,0,48,8);glDisable(GL_BLEND);glDisable(GL_DEPTH_TEST);glDisable(GL_DITHER);
    GLuint p=program(current_hd_fs);if(!p)return 6;GpuResult g=check_gpu(p);
    GpuResult d=check_detail_gpu(p,argc,argv,false),m=check_detail_gpu(p,argc,argv,true);
    bool passed=!cpu_failures&&!g.rgb_errors&&!g.alpha_errors&&g.changed>0&&!d.rgb_errors&&!d.alpha_errors&&d.changed>0&&!m.rgb_errors&&!m.alpha_errors&&m.changed>0;
    std::printf("{\"contract\":\"%s\",\"gpu\":\"%s\",\"profile_count\":%d,\"cpu_color_cases\":%d,\"cpu_failures\":%d,\"maximum_palette_luma_error\":%.9f,\"gpu_draws\":%d,\"gpu_pixel_comparisons\":%d,\"rgb_mismatches\":%d,\"alpha_class_mismatches\":%d,\"changed_components\":%d,\"detail_draws\":%d,\"detail_pixel_comparisons\":%d,\"detail_rgb_mismatches\":%d,\"detail_alpha_mismatches\":%d,\"detail_changed_components\":%d,\"automatic_lod_draws\":%d,\"automatic_lod_pixel_comparisons\":%d,\"automatic_lod_stock_rgb_mismatches\":%d,\"automatic_lod_alpha_mismatches\":%d,\"automatic_lod_changed_components\":%d,\"authored_png_maps_tested\":%d,\"stock_colors_plus_detail\":true,\"dual_profiles\":true,\"detail_maps\":true,\"pass\":%s}\n",HD_SKIN_MATERIAL_CONTRACT,glGetString(GL_RENDERER),HD_SKIN_PROFILE_COUNT,HD_SKIN_PROFILE_COUNT*4096,cpu_failures,luma_error,g.draws,g.comparisons,g.rgb_errors,g.alpha_errors,g.changed,d.draws,d.comparisons,d.rgb_errors,d.alpha_errors,d.changed,m.draws,m.comparisons,m.rgb_errors,m.alpha_errors,m.changed,argc-1,passed?"true":"false");
    return passed?0:1;
}
