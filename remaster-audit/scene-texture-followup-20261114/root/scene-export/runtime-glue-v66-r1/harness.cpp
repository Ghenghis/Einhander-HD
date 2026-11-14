
#include "scene_runtime.h"
#include <string>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define main inherited_fixture_main
#include "fixture_seed.cpp"
#undef main
bool transport=true,payload=true;
extern "C" int pgxp_enabled(void){return transport?1:0;}
extern "C" int pgxp_view_payload(void){return payload?1:0;}
extern "C" int pgxp_get_precise_vertex_view(uint32_t a,uint32_t w,PgxpView *v){return lookup(a,w,v);}
extern "C" int pgxp_get_precise_vertex_view_ex(uint32_t a,uint32_t w,PgxpView *v,int *why){return lookup_reason(a,w,v,why);}
extern "C" int gte_rtp_ring_get_xform(uint64_t seq,int16_t rt0[9],int32_t tr0[3],uint32_t *f,uint32_t *ra){return transform(seq,rt0,tr0,f,ra);}
uint64_t s_frame_count=100;
std::string response;
int json_get_int(const char *j,const char *key,int def) {
    std::string needle(1,char(34));needle+=key;needle+=char(34);
    const char *p=std::strstr(j,needle.c_str());if(!p)return def;p=std::strchr(p,':');return p?std::atoi(p+1):def;
}
void send_fmt(const char *fmt,...) {
    char line[16384];va_list ap;va_start(ap,fmt);int len=std::vsnprintf(line,sizeof line,fmt,ap);va_end(ap);
    if(len<0||size_t(len)>=sizeof line)std::abort();response+=line;
}
#include "exact_handler.inc"
void request(const char *j){response.clear();handle_scene_capture(42,j);std::puts(response.c_str());}
int main(int argc,char **) {
    if(argc>1){scene_runtime_tick(100);request(R"({"arm":1})");return 0;}
    request("{}"); // RPC cannot bind the owner.
    scene_runtime_tick(100);request("{}");
    transport=false;request(R"({"arm":1})");transport=true;
    payload=false;request(R"({"arm":1})");payload=true;
    request(R"({"arm":1})");
    std::thread foreign([]{if(scene_runtime_arm(100)!=SCENE_WRONG_THREAD)std::abort();});foreign.join();
    seed(0x34,100);uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=0x4000-uint32_t(j)*4;
    for(int j=0;j<3;++j)addresses[j]=sources[1+j*3];
    scene_runtime_tick(101);scene_runtime_command(101,words,count,sources,&state);scene_runtime_tick(102);
    request("{}");request(R"({"index":0})");request(R"({"index":0,"generation":0})");
    request(R"({"index":0,"generation":1})");request(R"({"index":1024,"generation":1})");request(R"({"cancel":1})");
    scene_runtime_arm(102);scene_runtime_tick(103);seed(0x34,102);for(int j=0;j<3;++j)addresses[j]=sources[1+j*3];
    scene_runtime_command(103,words,count,sources,&state);SceneCaptureInfo before{};scene_runtime_info(&before);if(before.count!=1)std::abort();
    scene_runtime_invalidate();request("{}");return 0;
}
