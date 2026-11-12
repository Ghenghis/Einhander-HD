// Actual HD library + hidden OpenGL admission probe; never launches the game.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <GL/gl.h>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <thread>
#include <vector>
#include "hd_texture_pack.h"
#define STB_IMAGE_IMPLEMENTATION
#include "../windows-x64/psxrecomp/runtime/third_party/stb_image.h"

namespace fs = std::filesystem;
static std::vector<unsigned char> read_file(const fs::path &path) {
    std::ifstream file(path,std::ios::binary);
    return {std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()};
}
static bool parse_key(const std::string &key,uint32_t *texture,uint32_t *palette) {
    unsigned a,b;int used=0;
    if(key.size()!=17 || std::sscanf(key.c_str(),"%8X-%8X%n",&a,&b,&used)!=2 || used!=17)return false;
    *texture=a;*palette=b;return true;
}
static std::string escaped(const char *text) {
    std::string out;for(;text&&*text;++text){if(*text=='"'||*text=='\\')out+='\\';out+=*text;}return out;
}
int main(int argc,char **argv) {
    if(argc!=4)return 2;
    HdTexturePack *pack=nullptr;char error[256]={};
    if(!hd_texture_pack_create(argv[1],&pack,error,sizeof error)){std::fprintf(stderr,"pack: %s\n",error);return 3;}
    HdTexturePackInfo info{};hd_texture_pack_get_info(pack,&info);
    int failures=0,index_found=0,index_malformed=0;
    for(const auto &entry:fs::directory_iterator(info.replacement_root)) {
        if(!entry.is_regular_file() || entry.path().extension()!=".png")continue;
        uint32_t texture=0,palette=0;
        if(!parse_key(entry.path().stem().string(),&texture,&palette)){++index_malformed;continue;}
        if(hd_texture_pack_lookup(pack,texture,palette,nullptr)==HD_TEXTURE_LOOKUP_FOUND)++index_found;
        else ++failures;
    }
    if(info.unique_key_count!=1024 || info.ambiguous_key_count!=0 || index_found!=1024 || index_malformed)++failures;
    if(hd_texture_pack_lookup(pack,0xDEADBEEFu,0xDEADBEEFu,nullptr)!=HD_TEXTURE_LOOKUP_NONE)++failures;

    WNDCLASSA cls{};cls.style=CS_OWNDC;cls.lpfnWndProc=DefWindowProcA;
    cls.hInstance=GetModuleHandleA(nullptr);cls.lpszClassName="EinhanderGreifNativeAdmission";
    if(!RegisterClassA(&cls))return 4;
    HWND window=CreateWindowA(cls.lpszClassName,"Hidden Greif source admission",WS_POPUP,0,0,1,1,nullptr,nullptr,cls.hInstance,nullptr);
    HDC dc=GetDC(window);PIXELFORMATDESCRIPTOR pfd{};pfd.nSize=sizeof pfd;pfd.nVersion=1;
    pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL;pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=32;pfd.cAlphaBits=8;
    int format=ChoosePixelFormat(dc,&pfd);if(!format||!SetPixelFormat(dc,format,&pfd))return 5;
    HGLRC context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context))return 6;
    GLint maximum=0;glGetIntegerv(GL_MAX_TEXTURE_SIZE,&maximum);
    std::string gpu=escaped(reinterpret_cast<const char*>(glGetString(GL_RENDERER)));
    hd_texture_pack_set_decode_budget(pack,size_t{256}*1024*1024);
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(25);
    std::ifstream key_file(argv[2]);std::string key;int keys=0,decoded=0,uploaded=0,source_errors=0,pixel_errors=0,alpha_errors=0,gpu_errors=0,gpu_pixel_errors=0;
    std::string per_key;
    while(std::getline(key_file,key)) {
        if(key.empty())continue;
        uint32_t texture=0,palette_hash=0;if(!parse_key(key,&texture,&palette_hash)){++failures;continue;}++keys;
        if(hd_texture_pack_lookup(pack,texture,palette_hash,nullptr)!=HD_TEXTURE_LOOKUP_FOUND){++failures;continue;}
        HdTexturePixels pixels{};bool decode_ok=false;
        while(std::chrono::steady_clock::now()<deadline){
            int status=hd_texture_pack_request_decode(pack,texture,palette_hash);
            if(status<0)break;
            if(hd_texture_pack_acquire_decoded(pack,texture,palette_hash,&pixels)==HD_TEXTURE_LOOKUP_FOUND){decode_ok=true;break;}
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        if(!decode_ok){++failures;continue;}++decoded;
        auto words_raw=read_file(fs::path(argv[3])/(key+".words.bin"));
        auto palette_raw=read_file(fs::path(argv[3])/(key+".clut.bin"));
        auto valid=read_file(fs::path(argv[3])/(key+".valid.bin"));
        bool source_ok=words_raw.size()==32768&&palette_raw.size()==32&&valid.size()==16384&&
            std::all_of(valid.begin(),valid.end(),[](unsigned char v){return v==1;});
        std::vector<uint16_t> words(16384),palette(16);
        if(source_ok){
            for(size_t i=0;i<words.size();++i)words[i]=words_raw[i*2]|(unsigned(words_raw[i*2+1])<<8);
            for(size_t i=0;i<palette.size();++i)palette[i]=palette_raw[i*2]|(unsigned(palette_raw[i*2+1])<<8);
            source_ok=hd_texture_crc32_words_le(words.data(),words.size())==texture&&hd_texture_crc32_words_le(palette.data(),palette.size())==palette_hash;
        }
        if(!source_ok)++source_errors;
        if(pixels.width!=256 || pixels.height!=256 || pixels.stride!=1024){++failures;hd_texture_pixels_release(&pixels);continue;}
        if(source_ok)for(size_t i=0;i<65536;++i){
            uint16_t value=palette[(words[i/4]>>((i%4)*4))&15];
            const unsigned char expected[4]={static_cast<unsigned char>((value&31)<<3),static_cast<unsigned char>(((value>>5)&31)<<3),static_cast<unsigned char>(((value>>10)&31)<<3),static_cast<unsigned char>(value==0?0:(value&0x8000)?255:127)};
            const unsigned char *actual=pixels.rgba+i*4;
            for(int component=0;component<3;++component)if(actual[component]!=expected[component])++pixel_errors;
            if(actual[3]!=expected[3])++alpha_errors;
        }
        GLuint gpu_texture=0;glGenTextures(1,&gpu_texture);glBindTexture(GL_TEXTURE_2D,gpu_texture);
        while(glGetError()!=GL_NO_ERROR){}
        glTexImage2D(GL_TEXTURE_2D,0,0x8058,256,256,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.rgba);
        std::vector<unsigned char> returned(256*256*4);glGetTexImage(GL_TEXTURE_2D,0,GL_RGBA,GL_UNSIGNED_BYTE,returned.data());glFinish();
        GLenum gl_error=glGetError();if(gl_error!=GL_NO_ERROR)++gpu_errors;else ++uploaded;
        for(size_t i=0;i<returned.size();++i)if(returned[i]!=pixels.rgba[i])++gpu_pixel_errors;
        glDeleteTextures(1,&gpu_texture);
        if(!per_key.empty())per_key+=",";
        char row[240];std::snprintf(row,sizeof row,"{\"key\":\"%s\",\"source_crc_valid\":%s,\"decoded_size\":[256,256],\"gpu_error\":%u}",key.c_str(),source_ok?"true":"false",unsigned(gl_error));per_key+=row;
        hd_texture_pixels_release(&pixels);
    }
    if(keys!=60 || decoded!=60 || uploaded!=60)++failures;
    failures+=source_errors+pixel_errors+alpha_errors+gpu_errors+gpu_pixel_errors;
    std::printf("{\"gpu\":\"%s\",\"max_texture_edge\":%d,\"registry_keys\":%zu,\"registry_lookup_found\":%d,\"ambiguous_keys\":%zu,\"malformed_keys\":%d,\"greif_requested\":%d,\"greif_decoded\":%d,\"greif_uploaded_and_readback\":%d,\"source_crc_errors\":%d,\"decoded_rgb_mismatches\":%d,\"decoded_alpha_STP_mismatches\":%d,\"gpu_errors\":%d,\"gpu_readback_byte_mismatches\":%d,\"failures\":%d,\"files\":[%s],\"pass\":%s}\n",gpu.c_str(),maximum,info.unique_key_count,index_found,info.ambiguous_key_count,index_malformed,keys,decoded,uploaded,source_errors,pixel_errors,alpha_errors,gpu_errors,gpu_pixel_errors,failures,per_key.c_str(),failures?"false":"true");
    hd_texture_pack_destroy(pack);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(context);ReleaseDC(window,dc);DestroyWindow(window);UnregisterClassA(cls.lpszClassName,cls.hInstance);
    return failures?1:0;
}
