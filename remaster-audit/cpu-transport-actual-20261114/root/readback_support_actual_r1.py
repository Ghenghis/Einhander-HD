"""Verify separate A pure controls and B inconclusive owned-loopback receipts; no rerun."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
S=R/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out=N/'support-ab-actual-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=False,tests_replayed=False,game_launched=False,gpu_used=False)
known=[]
for label,folder,run,expected in [('A','adapter-binding','controls-2243',0),('B','owned-stub','probe-2244',5)]:
    root=S/folder/'runs';a=root/run;ep=root/(run+'-envelope.json')
    m=json.loads((a/'result.json').read_bytes());e=json.loads(ep.read_bytes())
    need(e['rc']==e['wrapper_exit']==e['child_exit_code']==expected and not e['timeout_killed'],'envelope outcome '+label)
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate '+label)
    need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[14],'priority':16384},'child readback '+label)
    need(e['job_limits_readback']['affinity_mask']==16384 and e['job_limits_readback']['job_memory_limit']==268435456,'Job readback '+label)
    need(e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'cleanup receipt '+label)
    need(sha(root/(run+'-runner')/'executed-watchdog.py')=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','watchdog pin '+label)
    for p,want in m['pins'].items():need(sha(Path(p))==want,'source pin '+p)
    ids=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
    row=dict(result_sha256=sha(a/'result.json'),envelope_sha256=sha(ep),exit=expected,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
    if label=='A':
        need(m['all_ok'] is True and len(m['cases'])==41 and all(c['ok'] for c in m['cases']) and not m.get('fatal'),'A cases')
        need(sha(S/'adapter-binding/controls_binding_r1.py')==m['controls_sha256']=='5e88fb9e33a7a774210011c44e7de2a5042b2b78a85d0d4ca9873890f5431371','controls source')
        row.update(verdict='PASS',pure_controls=41,actual_sockets_tested=False)
    else:
        need(m['exit']==5 and m['errors']==[],'B outcome')
        s=m['summary']
        need(s['inconclusive_reasons']==['foreign_negative_not_exercised'] and not s['f_negative_exercised'],'B inconclusive reason')
        need(s['v_real_passed'] and s['v_real_valid'] and s['v_measure_valid'] and s['v_pre_visible'] and s['v_post_visible'],'B positive observations')
        need(s['f_listener_ambiguous_seen'] and s['f_listener_rejected_without_connect'] and s['cleanup_proven'],'B listener/cleanup')
        need(sha(S/'owned-stub/probe_peer_visibility_r2.py')==sha(a/'executed-probe.py')==m['probe_sha256']=='06f7a44a75766ee106ec39088358a7a9dcb4ae1c691b14032465ea551dd5a535','probe pin/copy')
        need(sha(a/'executed-stub.py')=='ed43bda03d4843e74e6342f17a025bc1b97b54b10d503656cfc39cf5eefcf881','stub copy')
        for name,c in m['cleanup'].items():
            need(c['cleanup_proven'] and c['absent'] and c['retained_handle_exited'],'B stub cleanup')
            ids.append((name,c['pid'],c['ctime']))
        row.update(verdict='INCONCLUSIVE',summary=s,real_game_qualified=False)
    for name,pid,created in ids:
        try:absent=psutil.Process(pid).create_time()!=created
        except psutil.NoSuchProcess:absent=True
        need(absent,'known identity remains '+label+name)
        known.append(dict(run=label,label=name,pid=pid,creation_unix=created,identity_absent=True))
    receipt[label]=row
receipt.update(metadata_readback_pass=True,known_identities=known,
    prelaunch_A_failure='Owner reports first PowerShell launcher failed before spawn because H resolved to alias h/Get-History; preserved prelaunch directory and owner receipt retained separately, not a second fixture Job.',
    canonical_collector_installed=False,foreign_peer_no_send_qualified=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(metadata_readback_pass=True,A=receipt['A'],B={k:v for k,v in receipt['B'].items() if k!='summary'},known_identities_absent=len(known))))
