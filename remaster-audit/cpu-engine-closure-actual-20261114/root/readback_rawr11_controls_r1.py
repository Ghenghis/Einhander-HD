"""Read actual CPU control artifacts; no repeated execution or socket/GPU use."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
b=r/'coordination/pizza-review-20261114/controls-r9-window-20261114T235819Z'
pins={b/'receipt.json':'c2def76ce24e0cfc896931666aab93a02ff730ec13ca24151bc871a6965adb2d',b/'eligibility-1.json':'8cb4ff0d186c4bcd0299fe3c12e0bc4e13ce124415aac7b971952af95320eee9',b/'controls.log':'9cf03e9e237843dc6a24cd3c2e8dd5b06b7afa24f837792611f0e7db1c6066f9'}
rows=[]
for path,want in pins.items():
    raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(str(path),got)
    rows.append({'path':str(path),'sha256':got,'bytes':len(raw)})
outer=json.loads((b/'receipt.json').read_bytes());e=json.loads((b/'eligibility-1.json').read_bytes())
assert len(outer['attempts'])==1 and outer['actual_child_started'] is True and outer['outcome']=='CHILD_FINISHED'
assert outer['test_exit']==0 and outer['wrapper_exit']==0 and outer['cleanup_proven'] is True
assert e['child_exit_code']==0 and e['rc']==0 and e['wrapper_exit']==0 and e['job_empty'] and e['tree_absent'] and e['job']['active']==0
assert e['cpu']==14 and e['priority']==16384 and e['max_job_mib']==1024 and e['timeout_s']==60
summary=json.loads((b/'controls.log').read_text().splitlines()[-1]);assert summary=={'checks':79,'failures':[],'result':'PASS'}
identities=[]
for kind in ('wrapper','child'):
    pid,ct=e[kind+'_pid'],e[kind+'_create_time']
    try:absent=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess:absent=True
    assert absent,(pid,ct)
    identities.append({'kind':kind,'pid':pid,'creation_unix':ct,'identity_absent':True})
out=n/'rawr11-controls-actual-readback-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'known_identities':identities,'actual_summary':summary,'elapsed_s':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes'],'cpu':14,'wrapper_job_empty':True,'tests_replayed':False,'socket_game_gpu_used':False,'scope':'79 pure test-double controls; expected argparse error is a negative control. Earlier failedfixture and CPU refusals retained. No real peer/network/GUI/audio/RT/DLSS acceptance.'}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'checks':79,'failures':0,'pins':len(rows),'known_identities':len(identities),'seconds':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes']}))
