"""Prepare an isolated v6/scene-v3 game integration and a bounded diagnostic adapter."""
from pathlib import Path
import datetime,hashlib,json,re,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v66-reviewed-scene-r3'
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v6'
rd=f/'host-run/20261114T142204Z';pk=rd/'pack-v6'
out=e/'sampling-build-v67-decode-identity-r1';out.mkdir(exist_ok=False)
src=out/'src';src.mkdir();shutil.copytree(base/'include',out/'include')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(base/'Einhander_Recompiled.exe')=='51ec32e3fdf4fc7567e807bce7106576a51e0c39ae73e65cb0599c33bd6a5a98'
assert sha(f/'READY.json')=='33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0'
assert json.loads((n/'v6-cpu-verification-r1/result.json').read_text())['passed']
assert sha(out/'include/hd_texture_pack.h')==sha(n/'v6-pack-base-from-v48/include/hd_texture_pack.h')
for name in ['gpu_gl_renderer.c','hd_class_mips.inc']:
    shutil.copy2(rd/'patched'/name,src/name)
for name in ['hd_texture_pack.cpp','hd_texture_identity.h','hdcm_x4.h']:
    shutil.copy2(pk/name,src/name)
shutil.copy2(n/'v6-pack-base-from-v48/src/hd_decode_queue.h',src/'hd_decode_queue.h')
(out/'third_party').mkdir();shutil.copy2(n/'v6-pack-base-from-v48/third_party/stb_image.h',out/'third_party/stb_image.h')
inc=(src/'hd_class_mips.inc').read_text(encoding='utf-8')
enum=inc.split('enum {',1)[1].split('};',1)[0]
enum=re.sub(r'/\*.*?\*/','',enum,flags=re.S)
reasons=[x.strip().split('=')[0].strip() for x in enum.split(',') if x.strip()]
assert reasons[-1]=='HDCM_REASONS' and reasons[-2]=='HDCM_E_IDENTITY'
reasons=reasons[:-1];assert len(reasons)==21
names=['preload_ok','preload_bytes','preload_ticks','attempted','admitted','levels_uploaded','bytes','ticks','rgb_edge_slots','rgb_opaque_skipped','rgbonly_preload_ok','rgbonly_admitted','rgbonly_opaque_bypass','rgbonly_identity_attempts']
handler='''/* PRIVATE v6 read-only diagnostics. Full four reason tables; reject contract drift. */
extern int gl_renderer_class_mips_counters(uint64_t *out, int cap);
static void handle_hd_class_mips(int id,const char *json) {
    enum { HEAD=14, REASONS=21, TOTAL=HEAD+4*REASONS };
    (void)json; uint64_t v[TOTAL]={0}; char values[TOTAL*21+1]; size_t pos=0;
    int count=gl_renderer_class_mips_counters(v,TOTAL);
    if(count!=TOTAL){send_fmt("{\\"id\\":%d,\\"ok\\":false,\\"error\\":\\"hdcm-counter-contract\\"}",id);return;}
    for(int i=0;i<count;i++) {
        int wrote=snprintf(values+pos,sizeof(values)-pos,"%s%llu",i?",":"",(unsigned long long)v[i]);
        if(wrote<0 || (size_t)wrote>=sizeof(values)-pos) { send_fmt("{\\"id\\":%d,\\"ok\\":false}",id); return; }
        pos+=(size_t)wrote;
    }
    values[pos]=0;
    send_fmt("{\\"id\\":%d,\\"ok\\":true,\\"schema\\":\\"hdcm-v6-counters\\",\\"head_count\\":14,\\"reason_count\\":21,\\"table_count\\":4,\\"values\\":[%s]}",id,values);
}

'''
debug=(base/'src/debug_server.c').read_text(encoding='utf-8')
a=debug.index('/* PRIVATE read-only scoped class-mip/RGB admission counters.')
b=debug.index('/* PRIVATE default-OFF scene observer control.',a)
old=debug[a:b];assert 'uint64_t v[64]' in old and 'hdcm-v4-counters' in old
debug=debug[:a]+handler+debug[b:]
(src/'debug_server.c').write_text(debug,encoding='utf-8',newline='\n')
(out/'counter-handler.inc').write_text(handler,encoding='utf-8',newline='\n')
contract=dict(schema='hdcm-v6-counters',head_count=14,reason_count=21,table_count=4,value_count=98,head_names=names,reason_names=reasons,table_names=['class_preload_rejected','class_rejected','rgb_preload_rejected','rgb_rejected'],identity_attempts_note='Head13 increments before identity accessor result; it counts attempts, not accepted entries.')
(out/'counter-contract.json').write_text(json.dumps(contract,indent=2)+'\n',encoding='utf-8')
harness=r'''#define main frozen_glue_main
#define gl_renderer_class_mips_counters actual_class_mips_counters
#include "glue_harness.c"
#undef main
#undef gl_renderer_class_mips_counters
#include <stdarg.h>
static int forced_count=-999;
int gl_renderer_class_mips_counters(uint64_t *out,int cap){
    int n=actual_class_mips_counters(out,cap);
    return forced_count==-999?n:forced_count;
}
static void send_fmt(const char *format,...){
    va_list ap;va_start(ap,format);vprintf(format,ap);va_end(ap);putchar('\n');
}
#include "counter-handler.inc"
int main(void){
    memset(&s_hdcm_diag,0,sizeof s_hdcm_diag);
    handle_hd_class_mips(10,"{}");
    s_hdcm_diag.rgbonly_identity_used=UINT64_MAX;
    s_hdcm_diag.rgbonly_rejected[HDCM_E_IDENTITY]=UINT64_MAX;
    handle_hd_class_mips(11,"{}");
    memset(&s_hdcm_diag,0xff,sizeof s_hdcm_diag);
    handle_hd_class_mips(12,"{}");
    for(int i=0;i<4;i++){forced_count=(int[]){-1,0,97,99}[i];handle_hd_class_mips(20+i,"{}");}
    return 0;
}
'''
(out/'counter-handler-test.c').write_text(harness,encoding='utf-8',newline='\n')
receipt=dict(prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),parent=str(base),frozen=str(f),parent_executable_sha256=sha(base/'Einhander_Recompiled.exe'),sources={p.relative_to(out).as_posix():sha(p) for p in src.iterdir()},headers={p.relative_to(out).as_posix():sha(p) for p in (out/'include').rglob('*') if p.is_file()},counter_contract=contract,counter_handler_sha256=sha(out/'counter-handler.inc'),counter_test_sha256=sha(out/'counter-handler-test.c'),build_complete=False,game_launched=False,gpu_run=False,scope='Prepare three rebuilt TUs: renderer v6, actual worker pack, diagnostic adapter. Retain v66 GP0 scene-v3 and pinned other core/guest/platform objects. Not a clean full-source build or installed release.')
(out/'prepared.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
shutil.copy2(__file__,out/'executed-prepare.py');print(json.dumps(dict(out=str(out),source_hashes=receipt['sources'],contract=contract)))
