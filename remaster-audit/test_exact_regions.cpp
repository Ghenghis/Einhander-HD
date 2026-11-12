#include "hd_texture_pack.h"
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>
#include <chrono>
namespace fs=std::filesystem;
static int checks,failures;
#define CHECK(name,x) do{bool ok=!!(x);++checks;failures+=!ok;std::printf("CHECK %s %s\n",name,ok?"PASS":"FAIL");}while(0)
int main(int argc,char**argv){
 if(argc!=2)return 2;fs::path root=argv[1];char error[512]{};HdTexturePack*pack=nullptr;
 CHECK("valid alternate-region manifest",hd_texture_pack_create((root/"valid").string().c_str(),&pack,error,sizeof error)&&hd_texture_pack_region_count(pack)==3);
 if(!pack){std::puts(error);return 2;}
 std::vector<uint16_t> vram(1024*512),raw(64*256,0x001f);
 for(int y=0;y<256;++y)for(int x=0;x<64;++x)vram[(y+256)*1024+x+448]=raw[y*64+x];
 HdTextureDrawQuery q{};q.page_x=256;q.page_y=256;q.depth=2;q.u_first=192;q.u_last=255;q.v_last=255;q.vram=vram.data();q.vram_word_count=vram.size();
 HdTextureSourceMatch m{};HdTextureRegionCandidate region{};
 CHECK("manifest is not an invented upload",hd_texture_pack_match_source(pack,&q,&m)==HD_TEXTURE_LOOKUP_NONE&&hd_texture_pack_tracking_upload_count(pack)==0);
 CHECK("geometry probe explicit source origin",hd_texture_pack_probe_region(pack,&q,&region)==1&&region.x==448&&region.width_words==64);
 CHECK("stale shadow cannot admit region",hd_texture_pack_match_region(pack,&q,0,&m)==0);
 CHECK("current exact source region matched",hd_texture_pack_match_region(pack,&q,1,&m)==1&&m.exact_region&&m.region_x==448&&m.upload_serial==0&&m.source_word_x==0&&m.texture_hash==hd_texture_crc32_words_le(raw.data(),raw.size()));
 auto validations=hd_texture_pack_region_validation_count(pack);auto start=std::chrono::steady_clock::now();
 for(int i=0;i<10000;++i)hd_texture_pack_match_region(pack,&q,1,&m);
 std::printf("CACHE 10000_queries_us=%lld\n",(long long)std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count());
 CHECK("stable hotpath avoids repeat source scans",hd_texture_pack_region_validation_count(pack)==validations);
 vram[300*1024+300]=0x7fff;hd_texture_pack_invalidate(pack,300,300,1,1);
 CHECK("unrelated page pixels preserve region match and cache",hd_texture_pack_match_region(pack,&q,1,&m)==1&&hd_texture_pack_region_validation_count(pack)==validations);
 vram[300*1024+450]^=1;hd_texture_pack_invalidate(pack,450,300,1,1);
 CHECK("changed source byte rejects binding",hd_texture_pack_match_region(pack,&q,1,&m)==0);
 for(int y=0;y<256;++y)for(int x=0;x<64;++x)vram[(y+256)*1024+x+448]=0x03e0;
 hd_texture_pack_invalidate(pack,448,256,64,256);
 CHECK("same geometry new exact variant selects uniquely",hd_texture_pack_match_region(pack,&q,1,&m)==1&&m.texture_hash!=hd_texture_crc32_words_le(raw.data(),raw.size()));
 q.u_first=191;CHECK("outside bound UV rejected",hd_texture_pack_probe_region(pack,&q,&region)==0);q.u_first=250;q.u_last=2;CHECK("wrapped query rejected",hd_texture_pack_probe_region(pack,&q,&region)==0);
 q.u_first=192;q.u_last=255;q.depth=1;CHECK("wrong depth rejected",hd_texture_pack_probe_region(pack,&q,&region)==0);q.depth=2;
 uint32_t upload=0;hd_texture_pack_track_upload(pack,448,256,64,256,raw.data(),raw.size(),&upload);
 CHECK("genuine runtime upload remains a separate first choice",hd_texture_pack_match_source(pack,&q,&m)==1&&m.upload_serial>0&&!m.exact_region);
 hd_texture_pack_reset_tracking(pack);CHECK("tracker reset clears upload and region cache",hd_texture_pack_tracking_upload_count(pack)==0&&hd_texture_pack_match_region(pack,&q,1,&m)==1);
 HdTextureDrawQuery indexed{};indexed.page_x=800;indexed.depth=0;indexed.u_last=63;indexed.v_last=7;indexed.clut_x=800;indexed.clut_y=500;indexed.vram=vram.data();indexed.vram_word_count=vram.size();
 for(int y=0;y<8;++y)for(int x=0;x<16;++x)vram[y*1024+x+800]=0x1111;
 for(int i=0;i<16;++i)vram[500*1024+800+i]=(uint16_t)(i*32+1);
 CHECK("indexed region exact current palette admitted",hd_texture_pack_match_region(pack,&indexed,1,&m)==1&&m.palette_hash!=0&&m.upload_width_words==16);
 indexed.clut_x=801;CHECK("different palette location rejected",hd_texture_pack_probe_region(pack,&indexed,&region)==0);indexed.clut_x=800;
 vram[500*1024+801]^=1;hd_texture_pack_invalidate(pack,801,500,1,1);
 CHECK("palette byte mutation invalidates cached source",hd_texture_pack_match_region(pack,&indexed,1,&m)==0);
 hd_texture_pack_destroy(pack);
 for(const char*bad:{"invalid","crc","duplicate","overlap","missing","depth","palette"}){
  pack=nullptr;bool refused=!hd_texture_pack_create((root/bad).string().c_str(),&pack,error,sizeof error)&&pack==nullptr;
  CHECK(bad,refused);if(pack)hd_texture_pack_destroy(pack);
 }
 std::printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
