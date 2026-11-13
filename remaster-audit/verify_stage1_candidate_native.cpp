// Production pack loader/source matcher against the actual composed manifest.
// This checks admission, not image quality or in-game visibility. No GPU/game.
#include "hd_texture_pack.h"
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
namespace fs=std::filesystem;
static bool words(const fs::path &p,std::vector<uint16_t> &out,size_t count) {
    std::ifstream f(p,std::ios::binary);if(!f)return false;out.resize(count);
    for(auto &v:out){int l=f.get(),h=f.get();if(l<0||h<0)return false;v=(uint16_t)(l|(h<<8));}
    return f.get()==EOF;
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;fs::path root=argv[1];char error[512]{};HdTexturePack *pack=nullptr;
    if(!hd_texture_pack_create(root.string().c_str(),&pack,error,sizeof error)){std::puts(error);return 1;}
    HdTexturePackInfo info{};hd_texture_pack_get_info(pack,&info);
    if(info.unique_key_count!=(size_t)std::stoull(argv[2])||info.ambiguous_key_count){std::puts("pack key census mismatch");return 1;}
    std::ifstream manifest(root/"ExactRegions.tsv");std::string line;unsigned checks=0,failures=0;
    while(std::getline(manifest,line)) {
        if(line.empty()||line[0]=='#'||line=="EIN_EXACT_REGIONS_V1")continue;
        std::istringstream fields(line);std::string key;int x,y,w,h,depth,cx,cy;unsigned th,ph;
        if(!(fields>>key>>x>>y>>w>>h>>depth>>cx>>cy)||std::sscanf(key.c_str(),"%x-%x",&th,&ph)!=2)return 3;
        std::vector<uint16_t> raw,clut,vram(1024*512);
        if(!words(root/(key+".words.bin"),raw,(size_t)w*h)||!words(root/(key+".clut.bin"),clut,depth==0?16:depth==1?256:0))return 4;
        for(int row=0;row<h;++row)for(int col=0;col<w;++col)vram[(y+row)*1024+x+col]=raw[row*w+col];
        for(size_t i=0;i<clut.size();++i)vram[(cy&511)*1024+((cx+i)&1023)]=clut[i];
        HdTextureDrawQuery q{};q.page_x=x&~63;q.page_y=y&~255;q.depth=(uint8_t)depth;
        const int ppw=4>>depth,u=(x-q.page_x)*ppw,v=y-q.page_y;
        if(u+w*ppw>256||v+h>256)return 5;
        q.u_first=(uint8_t)u;q.u_last=(uint8_t)(u+w*ppw-1);q.v_first=(uint8_t)v;q.v_last=(uint8_t)(v+h-1);
        q.clut_x=cx;q.clut_y=cy;q.vram=vram.data();q.vram_word_count=vram.size();
        HdTextureSourceMatch m{};hd_texture_pack_reset_tracking(pack);
        const int found=hd_texture_pack_match_region(pack,&q,1,&m);
        const bool ok=found==HD_TEXTURE_LOOKUP_FOUND&&m.exact_region&&m.texture_hash==th&&m.palette_hash==ph;
        ++checks;failures+=!ok;if(!ok)std::printf("FAIL %s found=%d actual=%08X-%08X\n",key.c_str(),found,m.texture_hash,m.palette_hash);
    }
    std::printf("{\"keys\":%llu,\"region_checks\":%u,\"failures\":%u}\n",(unsigned long long)info.unique_key_count,checks,failures);
    hd_texture_pack_destroy(pack);return failures?1:0;
}
