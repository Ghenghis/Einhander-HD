// Real GPU regression for the runtime's actual HD_FS, with its old shader as
// a negative control. Generated shader strings live next to this executable.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <GL/gl.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>
#include "hd_alpha_shaders.h"

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
    LOAD(pUniform1f,"glUniform1f"); LOAD(pUniform2f,"glUniform2f");
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
gl_Position=vec4(p*2.0-1.0,0,1);v_uv=vec2(p.x*3.0,p.y);v_uv_p=v_uv;
v_col=vec4(0.5);v_persp=0;v_raw=1;v_limits=ivec4(0,0,2,0);v_semi=1; }
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

static int check(GLuint p) {
    constexpr int W=96,H=16,S=16;
    GLuint tex=0;glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,0x812F);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,0x812F);
    std::vector<unsigned char> input(3*S*4),readback(W*H*4);
    int mismatches=0;
    pUseProgram(p);
    pUniform1i(pGetUniformLocation(p,"u_hd"),0);
    pUniform2f(pGetUniformLocation(p,"u_hd_off"),0,0);
    pUniform2f(pGetUniformLocation(p,"u_hd_dim"),3,1);
    pUniform1i(pGetUniformLocation(p,"u_maskset"),0);
    pUniform1i(pGetUniformLocation(p,"u_semimode"),0);
    for(int black_stp=0;black_stp<2;++black_stp){
        for(int x=0;x<3*S;++x){
            const int c=x/S;input[x*4]=c==0?200:0;
            input[x*4+1]=0;input[x*4+2]=c==1&&!black_stp?200:0;
            input[x*4+3]=c==0?127:c==1?255:0;
        }
        glTexImage2D(GL_TEXTURE_2D,0,0x8058,3*S,1,0,GL_RGBA,GL_UNSIGNED_BYTE,input.data());
        for(int filter=0;filter<2;++filter)for(int shift_case=0;shift_case<2;++shift_case)for(int pass=0;pass<3;++pass){
            const float shift=shift_case?0.5f/9.0f:0.0f;
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,filter?GL_LINEAR:GL_NEAREST);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,filter?GL_LINEAR:GL_NEAREST);
            pUniform1i(pGetUniformLocation(p,"u_filter"),filter);
            pUniform1i(pGetUniformLocation(p,"u_semipass"),pass);
            pUniform1f(pGetUniformLocation(p,"u_shift"),shift);
            glClearColor(19/255.f,37/255.f,61/255.f,51/255.f);glClear(GL_COLOR_BUFFER_BIT);
            glDrawArrays(GL_TRIANGLES,0,3);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,readback.data());
            for(int x=0;x<W;++x){
                int c=std::min(2,(int)std::floor(3.0f*(x+0.5f)/W+(filter?shift:0)));
                const bool discard=c==2||(pass==1&&c==1)||(pass==2&&c==0);
                const int expected=discard?51:c==1?255:0;
                if(readback[((H/2)*W+x)*4+3]!=expected)++mismatches;
            }
        }
    }
    return mismatches;
}

int main(){
    WNDCLASSA cls{};cls.style=CS_OWNDC;cls.lpfnWndProc=DefWindowProcA;
    cls.hInstance=GetModuleHandleA(nullptr);cls.lpszClassName="EinhanderAlphaRegression";
    if(!RegisterClassA(&cls))return 2;
    HWND window=CreateWindowA(cls.lpszClassName,"Hidden alpha regression",WS_POPUP,0,0,96,32,nullptr,nullptr,cls.hInstance,nullptr);
    HDC dc=GetDC(window);PIXELFORMATDESCRIPTOR pfd{};
    pfd.nSize=sizeof pfd;pfd.nVersion=1;pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL;
    pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=32;pfd.cAlphaBits=8;
    int fmt=ChoosePixelFormat(dc,&pfd);if(!fmt||!SetPixelFormat(dc,fmt,&pfd))return 3;
    HGLRC context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context)||!load())return 4;
    GLuint target=0,fbo=0,vao=0;glGenTextures(1,&target);glBindTexture(GL_TEXTURE_2D,target);
    glTexImage2D(GL_TEXTURE_2D,0,0x8058,96,16,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
    pGenFramebuffers(1,&fbo);pBindFramebuffer(0x8D40,fbo);
    pFramebufferTexture2D(0x8D40,0x8CE0,GL_TEXTURE_2D,target,0);
    if(pCheckFramebufferStatus(0x8D40)!=0x8CD5)return 5;
    pGenVertexArrays(1,&vao);pBindVertexArray(vao);glViewport(0,0,96,16);
    glDisable(GL_BLEND);glDisable(GL_DEPTH_TEST);glDisable(GL_DITHER);
    GLuint old_program=program(legacy_hd_fs),new_program=program(current_hd_fs);
    if(!old_program||!new_program)return 6;
    int before=check(old_program),after=check(new_program);
    std::printf("{\"gpu\":\"%s\",\"cases_per_shader\":24,\"legacy_class_mismatches\":%d,\"current_class_mismatches\":%d,\"pass\":%s}\n",
                glGetString(GL_RENDERER),before,after,(before>0&&after==0)?"true":"false");
    return before>0&&after==0?0:1;
}
