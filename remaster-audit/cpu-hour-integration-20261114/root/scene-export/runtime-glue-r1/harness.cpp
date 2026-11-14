
#include "scene_runtime.h"
#include <string>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define main inherited_fixture_main
#include "fixture_seed.cpp"
#undef main
extern "C" int pgxp_get_precise_vertex_view(uint32_t a,uint32_t w,PgxpView *v){return lookup(a,w,v);}
extern "C" int gte_rtp_ring_get_xform(uint64_t seq,int16_t rt0[9],int32_t tr0[3],uint32_t *f,uint32_t *ra){return transform(seq,rt0,tr0,f,ra);}
uint64_t s_frame_count=100;
std::string response;
int json_get_int(const char *j,const char *key,int def) {
    std::string needle="\"";needle+=key;needle+="\"";
    const char *p=std::strstr(j,needle.c_str());if(!p)return def;p=std::strchr(p,':');return p?std::atoi(p+1):def;
}
void send_fmt(const char *fmt,...) {
    char line[16384];va_list ap;va_start(ap,fmt);int n=std::vsnprintf(line,sizeof line,fmt,ap);va_end(ap);
    if(n<0||size_t(n)>=sizeof line)std::abort();response+=line;
}
#include "exact_handler.inc"
void request(const char *j){response.clear();handle_scene_capture(42,j);std::puts(response.c_str());}
int main(int argc,char **argv) {
    if(argc>1){request("{\"arm\":1}");return 0;}
    request("{}");request("{\"arm\":1}");
    seed(0x24,100);scene_runtime_tick(101);scene_runtime_command(101,words,count,0x1000,&state);scene_runtime_tick(102);
    request("{}");request("{\"index\":0}");request("{\"index\":1024}");request("{\"cancel\":1}");
    return 0;
}
