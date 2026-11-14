"""Execute exact private v64 RPC handler and Windows adapter on CPU fixtures."""
from pathlib import Path
import datetime, hashlib, json, os, psutil, shutil, subprocess
n=Path(__file__).resolve().parent;r=n.parents[3]
b=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v64-scene-capture-r2'
out=n/'runtime-glue-r1';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(b/'Einhander_Recompiled.exe')=='2bfb715fca71fff81f70d2e4d1acd61f1e83ddd1f803663467a528b5800972c5'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
text=(b/'src/debug_server.c').read_text();start=text.index('/* PRIVATE default-OFF scene observer control.')
end=text.index('/* pgxp_view —',start);handler=text[start:end]
(out/'exact_handler.inc').write_text(handler)
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
'''
# This is a Python raw string: C's escaped quote is ONE backslash.
harness=harness.replace('\\\\"','\\"')
(out/'harness.cpp').write_text(harness)
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
exe=out/'runtime_glue.exe';commands=[]
def run(label,args,env=None):
    x=subprocess.run(args,cwd=out,capture_output=True,text=True,timeout=45,creationflags=0x4000,env=env)
    (out/(label+'.log')).write_text(x.stdout+x.stderr)
    commands.append(dict(label=label,args=args,exit=x.returncode))
    assert x.returncode==0,label
    return x.stdout
run('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra','-Wno-comment','-Wno-unused-parameter','-I'+str(b/'include'),str(out/'harness.cpp'),str(out/'scene_capture.cpp'),str(out/'scene_json.cpp'),str(out/'scene_runtime.cpp'),'-o',str(exe)])
env={k:v for k,v in os.environ.items() if not k.startswith('PSXRECOMP_SCENE_CAPTURE')}
lines=[json.loads(l) for l in run('enabled',[str(exe)],dict(env,PSXRECOMP_SCENE_CAPTURE='1')).splitlines()]
assert len(lines)==6 and lines[0]['mode']==1 and lines[1]['mode']==2
assert lines[2]['mode']==4 and lines[2]['count']==1 and lines[2]['complete_interval'] and lines[2]['geometry_qualified']==1
assert lines[3]['record']['geometry_qualified'] and lines[3]['record']['vertices'][0]['lag']==1
assert not lines[4]['ok'] and lines[5]['mode']==1 and lines[5]['count']==0
for label,value in [('disabled','0'),('badenv','true')]:
    x=json.loads(run(label,[str(exe),'off'],dict(env,PSXRECOMP_SCENE_CAPTURE=value)))
    assert not x['ok'] and x['error']==2
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,commands=commands,rpc_responses=lines,
             actual_windows_adapter=True,exact_handler_sha256=sha(out/'exact_handler.inc'),gpu_executed=False,guest_executed=False,
             fixtures_only=True,user_gpu_hold_unchanged=True,cpu_affinity=me.cpu_affinity(),below_normal=True,
             sources={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.h','.cpp','.inc']})
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py')
print(json.dumps(dict(passed=True,rpc_cases=8,gpu=False)))
