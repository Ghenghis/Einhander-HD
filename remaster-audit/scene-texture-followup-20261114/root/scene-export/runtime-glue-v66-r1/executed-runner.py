from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
n=Path(__file__).resolve().parent;r=n.parents[3]
b=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r2'
out=n/'runtime-glue-v66-r1';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(b/'Einhander_Recompiled.exe')=='6193f454c0d8b37552a6c6930b9921a24715c98d46d25ac05a944c5f0af8b7e6'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
text=(b/'src/debug_server.c').read_text();start=text.index('/* PRIVATE default-OFF scene observer control.');end=text.index('/* pgxp_view —',start)
(out/'exact_handler.inc').write_text(text[start:end])
for p in (b/'src').iterdir():
    if p.name.startswith('scene_'):shutil.copy2(p,out/p.name)
shutil.copy2(n/'test_scene_capture.cpp',out/'fixture_seed.cpp')
harness=r'''
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
'''
(out/'harness.cpp').write_text(harness)
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe';exe=out/'runtime_glue.exe';commands=[]
def run(label,args,env=None):
    x=subprocess.run(args,cwd=out,capture_output=True,text=True,timeout=45,creationflags=0x4000,env=env)
    (out/(label+'.log')).write_text(x.stdout+x.stderr);commands.append(dict(label=label,args=args,exit=x.returncode))
    assert x.returncode==0,label
    return x.stdout
run('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra','-Wno-comment','-Wno-unused-parameter','-I'+str(b/'include'),str(out/'harness.cpp'),str(out/'scene_capture.cpp'),str(out/'scene_json.cpp'),str(out/'scene_runtime.cpp'),'-o',str(exe)])
env={k:v for k,v in os.environ.items() if not k.startswith('PSXRECOMP_SCENE_CAPTURE')}
lines=[json.loads(l) for l in run('enabled',[str(exe)],dict(env,PSXRECOMP_SCENE_CAPTURE='1')).splitlines()]
assert len(lines)==12,lines
assert lines[0]['error']==2 and lines[1]['mode']==1 and lines[1]['generation']==0
assert lines[2]['error']==4 and lines[3]['error']==4
assert lines[4]['mode']==2 and lines[4]['generation']==1
assert lines[5]['mode']==4 and lines[5]['complete_interval'] and lines[5]['geometry_qualified']==1 and lines[5]['owner_errors']==1
assert lines[6]['error']==3 and lines[7]['error']==2
assert lines[8]['record']['generation']==1 and lines[8]['record']['complete_interval'] and lines[8]['record']['eligible_triangle_mask']==1
assert lines[8]['record']['word_sources']==[0x4000-j*4 for j in range(9)]
assert lines[9]['error']==2 and lines[10]['mode']==1 and lines[10]['count']==0
assert lines[11]['mode']==1 and lines[11]['count']==0 and lines[11]['generation']==2
for label,value in [('disabled','0'),('badenv','true')]:
    x=json.loads(run(label,[str(exe),'off'],dict(env,PSXRECOMP_SCENE_CAPTURE=value)));assert x['error']==2
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,commands=commands,rpc_responses=lines,
             actual_windows_adapter=True,exact_handler_sha256=sha(out/'exact_handler.inc'),gpu_executed=False,guest_executed=False,
             fixtures_only=True,user_gpu_hold_unchanged=True,cpu_affinity=me.cpu_affinity(),below_normal=True,wrong_thread_test=True,
             sources={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.h','.cpp','.inc']})
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py')
print(json.dumps(dict(passed=True,rpc_cases=14,gpu=False)))
