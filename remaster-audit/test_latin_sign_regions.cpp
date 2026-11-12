// Exercise the unchanged production loader, source matcher, and PNG cache on
// the actual authored Latin-region candidate. No renderer or game is started.
#define STB_IMAGE_IMPLEMENTATION
#include "../windows-x64/psxrecomp/runtime/third_party/stb_image.h"
#include "hd_texture_pack.h"
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
namespace fs=std::filesystem;
static int checks=0,failures=0;
#define CHECK(name,x) do { bool ok=!!(x);++checks;failures+=!ok;if(!ok)std::printf("FAIL %s key=%s\n",name,r.key.c_str()); } while(0)
struct Row { std::string key; unsigned x,y,w,h,d,cx,cy; uint32_t th,ph; };
static std::vector<unsigned char> bytes(const fs::path&p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static std::vector<uint16_t> words(const fs::path&p){auto b=bytes(p);std::vector<uint16_t>v(b.size()/2);for(size_t i=0;i<v.size();++i)v[i]=b[i*2]|unsigned(b[i*2+1])<<8;return v;}
int main(int argc,char**argv){
 if(argc!=3)return 2;fs::path root=argv[1];unsigned expected=std::stoul(argv[2]);std::ifstream tsv(root/"ExactRegions.tsv");std::string line;std::getline(tsv,line);if(line!="EIN_EXACT_REGIONS_V1")return 2;
 std::vector<Row>rows;while(std::getline(tsv,line)){if(line.empty())continue;Row r{};std::istringstream s(line);if(!(s>>r.key>>r.x>>r.y>>r.w>>r.h>>r.d>>r.cx>>r.cy))return 2;r.th=std::stoul(r.key.substr(0,8),nullptr,16);r.ph=std::stoul(r.key.substr(9,8),nullptr,16);rows.push_back(r);}
 Row r{};r.key="PACK";HdTexturePack*p=nullptr;char error[1024]{};
 CHECK("actual manifest accepted",hd_texture_pack_create(root.string().c_str(),&p,error,sizeof error));if(!p){std::puts(error);return 1;}
 CHECK("exact region count",hd_texture_pack_region_count(p)==expected&&rows.size()==expected);
 std::vector<uint16_t>vram(1024*512);size_t total_bytes=0;unsigned indexed=0;
 for(const auto& row:rows){r=row;if(r.d!=0)continue;++indexed;auto raw=words(root/(r.key+".words.bin"));auto clut=words(root/(r.key+".clut.bin"));
  CHECK("raw and palette proof lengths",raw.size()==r.w*r.h&&clut.size()==16);if(raw.size()!=r.w*r.h||clut.size()!=16)continue;
  for(unsigned y=0;y<r.h;++y)for(unsigned x=0;x<r.w;++x)vram[(r.y+y)*1024+r.x+x]=raw[y*r.w+x];
  for(unsigned i=0;i<16;++i)vram[r.cy*1024+r.cx+i]=clut[i];
  hd_texture_pack_invalidate(p,r.x,r.y,r.w,r.h);hd_texture_pack_invalidate(p,r.cx,r.cy,16,1);
  HdTextureDrawQuery q{};q.page_x=(r.x/64)*64;q.page_y=(r.y/256)*256;q.depth=0;q.u_first=(r.x-q.page_x)*4;q.u_last=q.u_first+r.w*4-1;q.v_first=r.y-q.page_y;q.v_last=q.v_first+r.h-1;q.clut_x=r.cx;q.clut_y=r.cy;q.vram=vram.data();q.vram_word_count=vram.size();
  HdTextureSourceMatch m{};HdTextureRegionCandidate g{};
  CHECK("region separate from tracked uploads",hd_texture_pack_match_source(p,&q,&m)==HD_TEXTURE_LOOKUP_NONE&&hd_texture_pack_tracking_upload_count(p)==0);
  CHECK("actual full draw geometry covered",hd_texture_pack_probe_region(p,&q,&g)==HD_TEXTURE_LOOKUP_FOUND&&g.x==r.x&&g.y==r.y&&g.width_words==r.w&&g.height==r.h&&g.clut_x==r.cx&&g.clut_y==r.cy);
  CHECK("stale CPU shadow rejected",hd_texture_pack_match_region(p,&q,0,&m)==HD_TEXTURE_LOOKUP_NONE);
  CHECK("exact current palette selects intended phase",hd_texture_pack_match_region(p,&q,1,&m)==HD_TEXTURE_LOOKUP_FOUND&&m.exact_region&&m.upload_serial==0&&m.texture_hash==r.th&&m.palette_hash==r.ph&&m.region_x==r.x&&m.region_y==r.y&&m.source_word_x==0&&m.source_y==0);
  auto validations=hd_texture_pack_region_validation_count(p);for(unsigned i=0;i<200;++i)hd_texture_pack_match_region(p,&q,1,&m);
  CHECK("hot source phase uses cached proof",hd_texture_pack_region_validation_count(p)==validations);
  q.clut_x=(q.clut_x+16)%1024;CHECK("wrong CLUT location rejected",hd_texture_pack_probe_region(p,&q,&g)==HD_TEXTURE_LOOKUP_NONE);q.clut_x=r.cx;
  --q.u_first;CHECK("outside source quad rejected",hd_texture_pack_probe_region(p,&q,&g)==HD_TEXTURE_LOOKUP_NONE);++q.u_first;
  auto pos=r.y*1024+r.x;vram[pos]^=0x8000;hd_texture_pack_invalidate(p,r.x,r.y,1,1);CHECK("mutated full proof rejected",hd_texture_pack_match_region(p,&q,1,&m)==HD_TEXTURE_LOOKUP_NONE);vram[pos]^=0x8000;hd_texture_pack_invalidate(p,r.x,r.y,1,1);
  pos=r.cy*1024+r.cx;vram[pos]^=0x8000;hd_texture_pack_invalidate(p,r.cx,r.cy,1,1);CHECK("mutated palette rejected",hd_texture_pack_match_region(p,&q,1,&m)==HD_TEXTURE_LOOKUP_NONE);vram[pos]^=0x8000;hd_texture_pack_invalidate(p,r.cx,r.cy,1,1);
  CHECK("restored exact phase admitted",hd_texture_pack_match_region(p,&q,1,&m)==HD_TEXTURE_LOOKUP_FOUND&&m.texture_hash==r.th&&m.palette_hash==r.ph);
 }
 // Decode sequentially using the production worker, then revisit every phase.
 // The main renderer uses a 256 MiB budget. The 36 sign ROIs total 71 MiB.
 hd_texture_pack_set_decode_budget(p,256u*1024*1024);
 for(const auto&row:rows){r=row;if(r.d!=0)continue;int status=hd_texture_pack_request_decode(p,r.th,r.ph);CHECK("PNG request accepted",status>=HD_TEXTURE_LOOKUP_NONE);HdTexturePixels px{};
  auto until=std::chrono::steady_clock::now()+std::chrono::seconds(15);int ready=0;
  while(std::chrono::steady_clock::now()<until){ready=hd_texture_pack_acquire_decoded(p,r.th,r.ph,&px);if(ready==HD_TEXTURE_LOOKUP_FOUND)break;if(hd_texture_pack_request_decode(p,r.th,r.ph)==HD_TEXTURE_LOOKUP_ERROR)break;std::this_thread::sleep_for(std::chrono::milliseconds(5));}
  CHECK("production PNG decoder returns authored 16x ROI",ready==HD_TEXTURE_LOOKUP_FOUND&&px.rgba&&px.width==r.w*4*16&&px.height==r.h*16&&px.stride==px.width*4);
  if(ready==HD_TEXTURE_LOOKUP_FOUND){total_bytes+=size_t(px.width)*px.height*4;bool alpha=true;for(size_t i=3;i<size_t(px.stride)*px.height;i+=4)if(px.rgba[i]!=0&&px.rgba[i]!=127&&px.rgba[i]!=255){alpha=false;break;}CHECK("decoded PSX alpha categorical",alpha);hd_texture_pixels_release(&px);}
 }
 for(const auto&row:rows){r=row;if(r.d!=0)continue;CHECK("all palettes remain resident on revisit",hd_texture_pack_request_decode(p,r.th,r.ph)==HD_TEXTURE_LOOKUP_FOUND);HdTexturePixels px{};CHECK("all palette pixels acquire immediately",hd_texture_pack_acquire_decoded(p,r.th,r.ph,&px)==HD_TEXTURE_LOOKUP_FOUND);hd_texture_pixels_release(&px);}
 hd_texture_pack_destroy(p);std::printf("RESULT checks=%d failures=%d regions=%u indexed=%u decoded_bytes=%zu decoded_MiB=%.1f game_actions=0\n",checks,failures,expected,indexed,total_bytes,double(total_bytes)/(1024*1024));return failures?1:0;
}
