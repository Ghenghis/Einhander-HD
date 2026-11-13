// CPU-only production PNG index/decode probe. No GL context or guest state.
#include <chrono>
#include <cstdio>
#include <thread>
#include "hd_texture_pack.h"
#define STB_IMAGE_IMPLEMENTATION
#include "../windows-x64/psxrecomp/runtime/third_party/stb_image.h"
int main(int argc,char **argv){
    if(argc<3)return 2;
    for(int i=2;i<argc;++i){
        unsigned texture=0,palette=0;int used=0;
        if(std::sscanf(argv[i],"%8X-%8X%n",&texture,&palette,&used)!=2||used!=17||argv[i][used])return 2;
    }
    HdTexturePack *pack=nullptr;char error[256]={0};
    if(!hd_texture_pack_create(argv[1],&pack,error,sizeof error)){std::fprintf(stderr,"%s\n",error);return 3;}
    hd_texture_pack_set_decode_budget(pack,size_t{256}*1024*1024);
    HdTexturePackInfo info{};hd_texture_pack_get_info(pack,&info);
    std::printf("{\"keys\":%zu,\"ambiguous\":%zu,\"entries\":[",info.unique_key_count,info.ambiguous_key_count);
    int failures=0;
    for(int i=2;i<argc;++i){
        unsigned texture=0,palette=0;int used=0;
        if(std::sscanf(argv[i],"%8X-%8X%n",&texture,&palette,&used)!=2||used!=17||argv[i][used]){++failures;continue;}
        auto start=std::chrono::steady_clock::now();int lookup=hd_texture_pack_lookup(pack,texture,palette,nullptr),status=0;
        HdTexturePixels pixels{};
        do{
            status=hd_texture_pack_request_decode(pack,texture,palette);
            if(status<0||hd_texture_pack_acquire_decoded(pack,texture,palette,&pixels)==HD_TEXTURE_LOOKUP_FOUND)break;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }while(std::chrono::steady_clock::now()-start<std::chrono::seconds(10));
        double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
        std::printf("%s{\"key\":\"%s\",\"lookup\":%d,\"decode_status\":%d,\"width\":%u,\"height\":%u,\"milliseconds\":%.3f}",i>2?",":"",argv[i],lookup,status,pixels.width,pixels.height,ms);
        if(!pixels.rgba||lookup!=HD_TEXTURE_LOOKUP_FOUND)++failures;
        hd_texture_pixels_release(&pixels);
    }
    std::printf("],\"failures\":%d}\n",failures);hd_texture_pack_destroy(pack);return failures?1:0;
}
