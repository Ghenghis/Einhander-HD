// Exact native recorder adapter+wire handler with deterministic CPU fixtures.
// No game, GL context, GPU calls, or guest writes are used by these tests.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include "gpu_gl_renderer.h"
#include "gpu_render.h"
#include "hd_texture_pack.h"
#include "hd_research_capture.h"
#include "hd_research_event.h"
#include "hd_research_sample.h"
#include "hd_skin_material.h"
#define VRAM_W 1024
#define VRAM_H 512
static HdResearchCapture s_hd_research;
static struct {uint32_t texture,palette;} s_hd_research_seen[256];
static unsigned s_hd_research_seen_count;
static HdResearchSampler s_hd_research_sampler;
static std::vector<uint8_t> ram(HDR_RAM_BYTES);
static std::vector<uint16_t> vram(VRAM_W*VRAM_H);
static uint16_t *s_vram=vram.data();
static HdTexturePack *s_hd_pack=(HdTexturePack*)1;
static void *s_ctx=(void*)1;
static int s_raster_ok=1,s_hd_state=1,s_gpu_dirty=1,s_up_nrects=2,s_cpu_auth_dual=0;
static struct {int set;} s_pack_dirty={1};
static uint64_t s_frame_count=1000,test_ms=50000,s_hd_live_generation;
static HdSkinConfig s_hd_skin,s_hd_skin_enemy;
static const HdSkinConfig *hd_skin_for_draw(uint32_t texture,uint32_t palette){
 if(hd_skin_key_matches(&s_hd_skin,texture,palette))return &s_hd_skin;
 if(hd_skin_key_matches(&s_hd_skin_enemy,texture,palette))return &s_hd_skin_enemy;
 return nullptr;
}
static GrBackend test_backend=GR_BACKEND_OPENGL;
GrBackend gr_backend(void){return test_backend;}
static uint64_t psx_host_mono_ms(void){return test_ms;}
static const uint16_t *hd_source_upload_find(const HdTextureSourceMatch*){return nullptr;}
extern "C" int hd_texture_pack_upload_fragments(const HdTexturePack*,uint64_t,HdTextureUploadFragment *out,size_t capacity,size_t *count){
 *count=1;if(capacity){out[0]={400,256,2,2,0,0};}return HD_TEXTURE_LOOKUP_FOUND;
}
#include "hd_research_renderer.h"
static char response[8192];static int checks,failures,requests;
static void send_fmt(const char *format,...){va_list a;va_start(a,format);vsnprintf(response,sizeof response,format,a);va_end(a);}
static void send_err(int id,const char *error){send_fmt("{\"id\":%d,\"ok\":false,\"error\":\"%s\"}",id,error);}
extern "C" uint8_t *memory_get_ram_ptr(void){return ram.data();}
#include "hd_research_debug.h"
static void check(bool value,const char *label){++checks;if(!value){++failures;fprintf(stderr,"FAIL %s\n",label);}}
static void request(const std::string &s){++requests;response[0]=0;handle_research_capture(12,s.c_str());}
static uint32_t le32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static std::vector<uint8_t> read_file(const std::filesystem::path &p){std::ifstream f(p,std::ios::binary);return std::vector<uint8_t>(std::istreambuf_iterator<char>(f),{});}
int main(int argc,char **argv){
 std::string sample_filter;
 if(argc!=2)return 2;std::filesystem::path base=std::filesystem::absolute(argv[1]);std::filesystem::create_directories(base);
 for(size_t i=0;i<ram.size();++i)ram[i]=(uint8_t)(i*31u+7u);for(size_t i=0;i<vram.size();++i)vram[i]=(uint16_t)(i*17u+0x8000u);
 auto initial_ram=ram,initial_vram_bytes=std::vector<uint8_t>((uint8_t*)vram.data(),(uint8_t*)(vram.data()+vram.size()));
 request("{\"cmd\":\"research_capture\"}");check(strstr(response,"\"contract\":\"ein-research-v1\"")&&strstr(response,"\"active\":false"),"status exposes version and inactive state");
 const char *invalid[]={"{}","{\"cmd\":\"research_capture\",\"op\":\"start\"}","{\"cmd\":\"research_capture\",\"op\":\"mark\"}","{\"cmd\":\"research_capture\",\"op\":\"stop\",\"max_events\":1}","{\"cmd\":\"research_capture\",\"op\":\"status\",\"path\":\"x\"}","{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"../bad\"}","{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"valid\",\"max_bytes\":1}","{\"cmd\":\"research_capture\",\"op\":\"bogus\"}","{\"cmd\":\"research_capture\",\"cmd\":\"research_capture\"}","{\"cmd\":\"research_capture\",\"id\":1.5}","{\"cmd\":\"research_capture\",\"unknown\":{}}","{\"cmd\":\"research_capture\"} trailing"};
 for(auto s:invalid){auto before=s_hd_research;request(s);check(strstr(response,"\"ok\":false"),"strict parser rejects malformed command");check(!memcmp(&before,&s_hd_research,sizeof before),"invalid command preserves session");}
 auto start=[&](const char *name,int records=20,int sources=2,int events=2){auto p=base/name;std::filesystem::create_directories(p);return std::string("{\"cmd\":\"research_capture\",\"op\":\"start\",\"path\":\"")+p.generic_string()+"\",\"max_records\":"+std::to_string(records)+",\"max_sources\":"+std::to_string(sources)+",\"max_events\":"+std::to_string(events)+",\"max_bytes\":16777216}";};
 auto start_request=start("main");test_backend=GR_BACKEND_SOFTWARE;request(start_request);check(strstr(response,"\"ok\":false")&&!s_hd_research.active,"unsupported backend rejects start before files");test_backend=GR_BACKEND_OPENGL;
 request(start_request);check(strstr(response,"\"ok\":true")&&s_hd_research.active,"start captures ready native state");check(s_hd_research.records==1,"start writes bounded metadata");
 HdTextureSourceMatch m{};m.texture_hash=0x11223344;m.palette_hash=0x55667788;m.upload_serial=42;m.upload_width_words=2;m.upload_height=2;HdTextureDrawQuery q{};q.depth=0;q.clut_x=800;q.clut_y=500;q.u_last=7;q.v_last=1;q.vram=s_vram;q.vram_word_count=vram.size();int xs[3]={87,110,130},ys[3]={104,120,128};int us[3]={192,222,192},vs[3]={248,248,254};HdTexturePixels px{};px.width=16;px.height=4;
 hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);check(s_hd_research.sources==1&&s_hd_research.records==2&&s_hd_research.files==5,"first source emits four bounded sidecars and receipt");
 auto draw_bytes=read_file(base/"main/capture.jsonl");std::string draw_text(draw_bytes.begin(),draw_bytes.end());check(draw_text.find("\"uv_vertices\":[[192,248],[222,248],[192,254]]")!=std::string::npos,"receipt preserves oriented per-vertex UVs independently of bounds");
 auto words=read_file(base/"main/11223344-55667788.words.bin");auto valid=read_file(base/"main/11223344-55667788.valid.bin");check(words.size()==8&&valid.size()==4&&valid[0]==1,"raw source uses reconstructed fragments and explicit valid mask");check(words[0]==(uint8_t)vram[256*1024+400]&&words[1]==(uint8_t)(vram[256*1024+400]>>8),"source words are little endian");
 for(int i=0;i<2000;++i)hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);check(s_hd_research.records==2&&s_hd_research.sources==1,"repeated draw signatures do not exhaust receipt budget");
 hd_research_on_draw(&m,&q,&px,0,xs,ys,us,vs);check(s_hd_research.records==3,"actual replacement submission is distinct from source query");s_frame_count+=60;test_ms+=1000;hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);check(s_hd_research.records==4,"same draw resamples after sixty guest frames");
 s_hd_research.records=s_hd_research.limits.max_records;s_hd_research.sources=s_hd_research.limits.max_sources;
 request("{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"before_pickup\"}");check(strstr(response,"\"ok\":true")&&strstr(response,"\"event_file\":\"event-0001.bin\"")&&s_hd_research.active,"mark survives independent record/source caps");std::string sample_mark=response;
 auto event=read_file(base/"main/event-0001.bin");check(event.size()==HDR_EVENT_BYTES&&!memcmp(event.data(),"EINRC01\0",8),"fixed event magic and total size");if(event.size()==HDR_EVENT_BYTES){check(le32(event.data()+8)==1&&le32(event.data()+12)==160,"version and header size");check(le32(event.data()+32)==160&&le32(event.data()+40)==2097312,"RAM and CPU-VRAM offsets");check(le32(event.data()+48)==1&&le32(event.data()+52)==2&&le32(event.data()+56)==1&&le32(event.data()+84)==1,"coherence and no-readback flags");check(le32(event.data()+68)==hdr_fnv(ram.data(),ram.size()),"RAM checksum matches exact safe-point bytes");check(!memcmp(event.data()+160,ram.data(),ram.size()),"full RAM captured without mutation");check(le32(event.data()+72)==hdr_fnv(event.data()+2097312,HDR_VRAM_BYTES),"CPU-VRAM checksum validates");check(!memcmp(event.data()+96,"before_pickup",13),"event label association");}
 ram[0x84832]^=1;s_frame_count+=1;test_ms+=17;request("{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"after_pickup\"}");check(strstr(response,"\"event_index\":2")&&s_hd_research.events==2,"second explicit event is separately indexed");auto before=s_hd_research;request("{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"overflow\"}");check(strstr(response,"\"ok\":false")&&s_hd_research.active&&s_hd_research.events==2&&s_hd_research.bytes_written==before.bytes_written,"event cap rejects only mark with no evidence writes");
 request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");check(!s_hd_research.active&&strstr(response,"user_stop"),"explicit stop closes sink");
 request(start("reserve",20,2,2));s_hd_research.bytes_written=s_hd_research.limits.max_bytes-2*HDR_EVENT_BYTES-100;unsigned records=s_hd_research.records;hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);check(s_hd_research.active&&s_hd_research.records==records&&s_hd_research.sources==0,"source/logging pause preserves event reserve without stopping session");request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
 {
  // Simulate 246 already completed four-file sources without creating 984
  // irrelevant files. Exercise the actual final source commit and all32 real
  // full RAM/VRAM snapshots against both production reservations.
  auto directory=base/"file-reserve";std::filesystem::create_directories(directory);
  GlResearchLimits limits{256,20000,32,18000,300,112u*1024u*1024u};GlResearchState status{};char error[192];
  check(gl_renderer_research_start(directory.generic_string().c_str(),&limits,&status,error,sizeof error),"Stage-size reservation fixture starts");
  check(status.event_reserved_bytes==32ull*HDR_EVENT_BYTES&&status.event_reserved_files==32,"all32 affordable event blobs and file slots reserved without75percent byte clipping");
  s_hd_research.sources=246;s_hd_research.files=1+246*4;
  hd_research_source(&m,&q,s_frame_count,test_ms);
  check(s_hd_research.sources==247&&s_hd_research.files==989&&s_hd_research.active,"last affordable four-file source is committed");
  auto full=s_hd_research;m.texture_hash^=1;
  hd_research_source(&m,&q,s_frame_count,test_ms);
  check(s_hd_research.active&&s_hd_research.sources==247&&s_hd_research.files==989&&s_hd_research.bytes_written==full.bytes_written,"next source soft-pauses before consuming any reserved event slot");
  // Leave only64 bytes beyond the exact event binary allowance. Optional
  // mark JSON must be skipped so it cannot steal bytes from the final event.
  s_hd_research.bytes_written=limits.max_bytes-32ull*HDR_EVENT_BYTES-64;
  for(unsigned i=0;i<32;++i){
   GlResearchEvent captured{};const char *label=i==0?"before_action":i==1?"after_action":"remaining_event";
   check(gl_renderer_research_mark(label,ram.data(),(unsigned)ram.size(),&captured,&status,error,sizeof error),"reserved32-event sequence commits each complete snapshot");
   check(captured.index==i+1&&std::filesystem::file_size(directory/captured.file)==HDR_EVENT_BYTES,"reserved event index and full binary length preserved");
   check(status.active&&status.events==i+1&&status.files==990+i&&status.bytes<=limits.max_bytes,"all event captures remain within hard file and byte caps");
  }
  check(status.events==32&&status.files==1021&&status.event_reserved_files==0&&status.event_reserved_bytes==0,"all32 snapshots including After survive source exhaustion");
  check(s_hd_research.records==1,"optional mark receipt rows cannot consume future snapshot bytes");
  GlResearchEvent overflow{};auto complete=s_hd_research;
  check(!gl_renderer_research_mark("extra",ram.data(),(unsigned)ram.size(),&overflow,&status,error,sizeof error)&&s_hd_research.active&&s_hd_research.files==complete.files,"33rd snapshot rejected without bypassing event cap");
  gl_renderer_research_stop(&status);m.texture_hash^=1;
 }
 {
  // Reproduce the already exhausted legacy-run counters. A reservation cannot
  // manufacture30 missing file slots: skip every new source, allow the one
  // remaining After snapshot, then enforce the unchanged1024-file hard cap.
  auto directory=base/"legacy255";std::filesystem::create_directories(directory);
  GlResearchLimits limits{256,20000,32,18000,300,112u*1024u*1024u};GlResearchState status{};GlResearchEvent captured{};char error[192];
  check(gl_renderer_research_start(directory.generic_string().c_str(),&limits,&status,error,sizeof error),"legacy255-source boundary fixture starts");
  s_hd_research.sources=255;s_hd_research.files=1023;s_hd_research.events=2;
  auto prior=s_hd_research;hd_research_source(&m,&q,s_frame_count,test_ms);
  check(s_hd_research.active&&s_hd_research.files==1023&&s_hd_research.sources==255&&s_hd_research.bytes_written==prior.bytes_written,"255-source partial state cannot consume last event slot with sidecars");
  check(gl_renderer_research_mark("after_boundary",ram.data(),(unsigned)ram.size(),&captured,&status,error,sizeof error)&&captured.index==3,"last available legacy slot still accepts an After snapshot");
  check(status.files==1024&&!status.active&&!strcmp(status.reason,"file_limit"),"exact1024-file boundary hard-stops after final allowed snapshot");
  check(!gl_renderer_research_mark("over_limit",ram.data(),(unsigned)ram.size(),&captured,&status,error,sizeof error)&&s_hd_research.files==1024,"hard file cap cannot be bypassed by another mark");
 }
 {
  request(start("sampler-lru",20000,2,2));
  HdTextureSourceMatch source=m;source.upload_serial=0;
  for(unsigned i=0;i<512;++i){source.texture_hash=0xA0000000u+i;s_frame_count+=1;test_ms+=10;hd_research_on_draw(&source,&q,nullptr,0,xs,ys,us,vs);}
  check(s_hd_research_sampler.count==512&&s_hd_research_sampler.rows==512,"sampler fills bounded512 slots with committed source identities");
  source.texture_hash=0xB0000000u;++s_hd_live_generation;s_frame_count+=1;test_ms+=10;
  hd_research_on_draw(&source,&q,&px,0,xs,ys,us,vs);
  check(s_hd_research_sampler.count==512&&s_hd_research_sampler.evictions==1&&s_hd_research_sampler.rows==513,"novel actual GL phase after512 identities receives an LRU receipt");
  auto bytes=read_file(base/"sampler-lru/capture.jsonl");std::string text(bytes.begin(),bytes.end());
  check(text.find("replacement_gl_draw_submitted")!=std::string::npos&&text.find("B0000000-55667788")!=std::string::npos,"postcapacity GL receipt is present in committed evidence");
  unsigned previous=q.u_first;q.u_first=6;auto emitted=s_hd_research_sampler.rows;hd_research_on_draw(&source,&q,&px,0,xs,ys,us,vs);
  check(s_hd_research_sampler.rows==emitted&&s_hd_research_sampler.repeat_skips>0,"same coarse UV quadrant suppresses pertriangle repetition");
  s_frame_count+=60;test_ms+=1000;hd_research_on_draw(&source,&q,&px,0,xs,ys,us,vs);
  bytes=read_file(base/"sampler-lru/capture.jsonl");text.assign(bytes.begin(),bytes.end());
  check(s_hd_research_sampler.rows==emitted+1&&text.find("\"uv_bounds\":[6,0,7,1]")!=std::string::npos,"later coarse sample retains exact chosen UV coordinates in row");q.u_first=(uint8_t)previous;
  request("{\"cmd\":\"research_capture\",\"op\":\"status\"}");check(strstr(response,"lru_identity_phase_uv_quadrant_lease_rate")&&strstr(response,"\"evictions\":1"),"wire status discloses bounded LRU policy and eviction counts");
  request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
 }
 {
  HdResearchSampler sampler;hdr_sample_start(&sampler,20000,32,300,0);HdResearchSampleKey key{};
  for(unsigned i=0;i<1200;++i){key.words[0]=i;auto entry=hdr_sample_prepare(&sampler,&key,i,0);if(entry)hdr_sample_commit(&sampler,entry,i);}
  check(sampler.rows==32&&sampler.rate_skips==1168&&sampler.count==512&&sampler.evictions==688,"lease rate budget bounds initial novelty burst without freezing LRU discovery");
  key.words[0]=99999;auto entry=hdr_sample_prepare(&sampler,&key,1300,1000);check(entry!=nullptr,"novel late identity becomes eligible after token replenishment");if(entry)hdr_sample_commit(&sampler,entry,1300);
  check(sampler.rows==33&&sampler.rate>66&&sampler.rate<67,"Stage20000-row lease is paced across300seconds");
 }
 {
  const char *invalid_filters[]={
   "\"source_policy\":\"include\",\"source_keys\":[]",
   "\"source_policy\":\"include\"",
   "\"source_policy\":\"all\",\"source_keys\":[\"11223344-55667788\"]",
   "\"source_policy\":\"include\",\"source_keys\":[\"11223344-5566778a\"]",
   "\"source_policy\":\"exclude\",\"source_keys\":[\"11223344-55667788\",\"11223344-55667788\"]",
   "\"source_policy\":\"include\",\"source_keys\":[\"11223344-55667788\",]",
   "\"source_policy\":\"unknown\",\"source_keys\":[\"11223344-55667788\"]",
   "\"source_keys\":[\"11223344-55667788\"]"
  };
  auto filter_start=[&](const char *name,const std::string &fields){auto json=start(name,20000,1,2);json.pop_back();return json+","+fields+"}";};
  for(auto fields:invalid_filters){auto before=s_hd_research;request(filter_start("filter-invalid",fields));check(strstr(response,"\"ok\":false"),"invalid exact filter rejected");check(!memcmp(&before,&s_hd_research,sizeof before),"invalid filter leaves existing native state unchanged");}
  request("{\"cmd\":\"research_capture\",\"source_policy\":\"all\"}");check(strstr(response,"\"ok\":false"),"status cannot carry source filter configuration");
  request(filter_start("filter-include","\"source_policy\":\"include\",\"source_keys\":[\"11223344-55667788\"]"));
  sample_filter=response;
  check(strstr(response,"\"source_filter_supported\":true")&&strstr(response,"\"policy\":\"include\"")&&s_hd_research.active,"wire starts exact include filter and acknowledges capability");
  HdTextureSourceMatch candidate=m;candidate.palette_hash^=1;
  auto before=s_hd_research;hd_research_on_draw(&candidate,&q,nullptr,0,xs,ys,us,vs);
  check(s_hd_research.sources==0&&s_hd_research.files==before.files&&s_hd_research.records>before.records,"excluded palette preserves raw quota and independent query receipts");
  candidate=m;candidate.texture_hash^=1;hd_research_on_draw(&candidate,&q,nullptr,0,xs,ys,us,vs);
  check(s_hd_research.sources==0&&s_hd_research_source_filter_skips==2,"filter compares full exact texture and palette pair");
  hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);hd_research_on_draw(&m,&q,&px,0,xs,ys,us,vs);
  check(s_hd_research.sources==1&&std::filesystem::exists(base/"filter-include/11223344-55667788.source.json"),"included source survives earlier unrelated keys and consumes its quota");
  request("{\"cmd\":\"research_capture\",\"op\":\"mark\",\"label\":\"filter_context\"}");check(strstr(response,"\"ok\":true")&&s_hd_research.events==1,"full event channel remains usable under raw include filter");
  request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
  request(filter_start("filter-exclude","\"source_policy\":\"exclude\",\"source_keys\":[\"11223344-55667788\"]"));
  hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);candidate=m;candidate.palette_hash^=1;hd_research_on_draw(&candidate,&q,nullptr,0,xs,ys,us,vs);
  check(s_hd_research.sources==1&&!std::filesystem::exists(base/"filter-exclude/11223344-55667788.source.json")&&std::filesystem::exists(base/"filter-exclude/11223344-55667789.source.json"),"exclude mode skips exact known pair and retains another palette");
  request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
  std::string keys="\"source_policy\":\"include\",\"source_keys\":[";
  for(unsigned i=0;i<256;++i){char key[64];snprintf(key,sizeof key,"%s\"%08X-55667788\"",i?",":"",i);keys+=key;}keys+="]";
  auto maximum=filter_start("filter-max",keys);check(maximum.size()<8192,"256-key exact filter fits current debug receive bound");request(maximum);
  check(strstr(response,"\"ok\":true")&&strstr(response,"\"key_count\":256"),"maximum bounded filter accepted without truncation");
  request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
  keys.pop_back();keys+=",\"FFFF0000-55667788\"]";request(filter_start("filter-overflow",keys));check(strstr(response,"\"ok\":false")&&!s_hd_research.active,"257th exact key rejected rather than truncated");
  request(start("filter-default",20000,2,2));hd_research_on_draw(&m,&q,nullptr,0,xs,ys,us,vs);
  check(s_hd_research.sources==1&&s_hd_research_source_filter.source_policy==GL_RESEARCH_SOURCE_ALL&&s_hd_research_source_filter_skips==0,"legacy start clears prior filter and retains all-source behavior");
  s_hd_skin={};s_hd_skin.profile=hd_skin_find_profile("gold-obsidian");s_hd_skin.enabled=1;s_hd_skin.valid=1;s_hd_skin.strength=.65f;s_hd_skin.keys[0]={m.texture_hash,m.palette_hash};s_hd_skin.key_count=1;
  s_hd_skin.diagnostic_scope=1;s_hd_skin.diagnostic_keys[0]={m.texture_hash,m.palette_hash};s_hd_skin.diagnostic_key_count=1;s_hd_skin.preserve_accents=1;
  ++s_hd_live_generation;s_frame_count+=60;test_ms+=1000;hd_research_on_draw(&m,&q,&px,0,xs,ys,us,vs);
  auto receipts=read_file(base/"filter-default/capture.jsonl");std::string text(receipts.begin(),receipts.end());
  check(text.find("\"material_channel\":\"player\"")!=std::string::npos&&text.find("\"material_profile\":\"gold-obsidian\"")!=std::string::npos&&text.find("\"material_applied\":true")!=std::string::npos,"draw rows serialize actual selected material channel/profile and submission application");
  check(text.find("\"material_diagnostic_scope\":true")!=std::string::npos&&text.find("\"material_preserve_accents\":true")!=std::string::npos,"draw rows distinguish temporary key probes and accent preservation");
  char generation[80];snprintf(generation,sizeof generation,"\"material_generation\":%llu",(unsigned long long)s_hd_live_generation);check(text.find(generation)!=std::string::npos,"draw rows serialize live generation used by sampler");
  s_hd_skin={};request("{\"cmd\":\"research_capture\",\"op\":\"stop\"}");
 }
 request(start("deadline"));test_ms+=60000;request("{\"cmd\":\"research_capture\",\"op\":\"status\"}");check(!s_hd_research.active&&strstr(response,"time_limit"),"status enforces fixed lease after disconnect");
 std::vector<uint8_t> small(160);check(!hdr_build_event(small.data(),small.size(),ram.data(),ram.size(),vram.data(),vram.size(),"safe",1,1,0,0,0,0,0,1),"event builder rejects short output before copy");check(!hdr_label_valid("bad/path")&&!hdr_label_valid("")&&hdr_label_valid("weapon_pickup_01"),"labels are confined identifiers");
 ram[0x84832]^=1;check(ram==initial_ram&&!memcmp(vram.data(),initial_vram_bytes.data(),initial_vram_bytes.size()),"native commands leave all RAM and CPU-VRAM bytes unchanged");
 printf("{\"checks\":%d,\"requests\":%d,\"failures\":%d,\"event_bytes\":%u,\"snapshot_reservation_regression\":{\"stage_event_count\":32,\"stage_final_files\":1021,\"legacy255_last_mark_only\":true,\"hard_file_cap\":1024},\"sampler_regression\":{\"bounded_slots\":512,\"late_gl_receipt_after_full\":true,\"lease_paced\":true},\"sample_mark\":%s,\"sample_filter\":%s}\n",checks,requests,failures,HDR_EVENT_BYTES,sample_mark.c_str(),sample_filter.c_str());return failures?1:0;
}
