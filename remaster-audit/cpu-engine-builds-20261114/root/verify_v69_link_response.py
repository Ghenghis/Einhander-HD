"""Compare actual link response and argv to the pinned parent; metadata only."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
E=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
B=E/'sampling-build-v68-recorder-reserve-r1';A=R/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
base_raw=(B/'Einhander_Recompiled.rsp').read_bytes()
need(sha(base_raw)=='c2b737c691b83aac0b0ab6bf6fecb853eba52f51f04827b8009ef2c9d3952130','parent response changed')
m=json.loads((A/'manifest.json').read_bytes());base=json.loads((B/'build.json').read_bytes())
text=base_raw.decode('utf-8');changes=[]
for label,old in [('main',E/'sampling-build-v58-frame-phases/main.cpp.obj'),('debug',E/'sampling-build-v67-decode-identity-r3/debug_server.c.obj')]:
    before=str(old).replace('\\','/');after=m['build'][label]['obj'].replace('\\','/')
    need(text.count(before)==1,'parent object not unique');text=text.replace(before,after)
    changes.append(dict(label=label,before=before,after=after))
new_rsp=A/'Einhander_Recompiled.v69.rsp';actual=new_rsp.read_bytes();need(actual==text.encode('utf-8'),'unexpected response change')
link=[c for c in base['commands'] if c['label']=='link'];need(len(link)==1,'parent link ambiguous')
expected=list(link[0]['args']);ri=[i for i,x in enumerate(expected) if x.startswith('@')];oi=[i for i,x in enumerate(expected) if x=='-o']
need(len(ri)==len(oi)==1,'parent link shape');expected[ri[0]]='@'+str(new_rsp);expected[oi[0]+1]=str(A/'Einhander_Recompiled.exe')
child=m['children'][-1];need(child['step']=='build:link' and child['argv']==expected and child['cwd']==link[0]['cwd'],'actual link argv/cwd changed')
out=N/'v69-link-response-readback-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=True,parent_rsp_sha256=sha(base_raw),
    actual_rsp_sha256=sha(actual),exactly_two_object_paths_replaced=True,changes=changes,
    actual_link_argv_and_cwd_match=True,compiler_or_game_executed=False,gpu_run=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
