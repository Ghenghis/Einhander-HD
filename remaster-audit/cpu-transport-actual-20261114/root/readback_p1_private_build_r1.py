"""Verify actual P1 private build artifacts/lineage; no compiler/game/test or large input sweep."""
from pathlib import Path
import datetime as dt, hashlib, json, os, psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
A=U/'builds/p1-v69-2240'; E=U/'receipts/P1-build-2240-envelope.json'
V=R/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
need(sha(E)=='890e84e08534a5ae6b1af384f9a4d597f46bf7d361916b66626ff7a61663b4f8','envelope changed')
need(sha(A/'manifest.json')=='e34ca075064dfa594652a8361fa0842c75569b7c2375b853e4ff05eda39882fa','manifest changed')
e=json.loads(E.read_bytes());m=json.loads((A/'manifest.json').read_bytes());v=json.loads((V/'manifest.json').read_bytes())
need(m['verdict']=='PASS' and m['reasons']==m['missing_or_failed_steps']==[],'build failed')
need(len(m['steps'])==12 and all(s['ok'] for s in m['steps'].values()),'missing step')
need(m['driver_sha256']=='5f713865c62ed3cb899df775206c588a121172f64ff28dd9444da7b20267bda7','builder pin')
for source,copy,name in [('p1_main',A/'src/main.cpp','copy:main'),('p1_keymap_c',A/'src/host_keymap.c','copy:keymap_c'),('p1_keymap_h',A/'include/host_keymap.h','copy:keymap_h')]:
    row=m['inputs'][source];want=row['expected']
    need(sha(Path(row['path']))==sha(copy)==want==m['steps'][name]['read_sha256']==m['steps'][name]['copy_sha256'],'source/copy mismatch '+source)
for name,want in m['steps']['outputs']['hashes'].items():
    need(sha(A/('Einhander_Recompiled.exe' if name=='exe' else 'obj/'+name))==want,'output hash '+name)
need(m['steps']['outputs']['hashes']['exe']=='37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc','new exe pin')
need(sha(V/'Einhander_Recompiled.exe')=='f1ccb34dc0d06ba945fd822c9e807fe14b452b0d61584b731dcd4163f27759e5','v69 changed')
norm=lambda p:os.path.normcase(os.path.normpath(str(p)))
old={norm(p):h for p,h in v['build']['main']['closure'].items()}
new={norm(d['path']):d['sha256'] for d in m['steps']['deps:main']['deps']}
old_src=norm(V/'src/main.cpp');old_h=norm(R.parent/'Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime/include/host_keymap.h')
new_src=norm(A/'src/main.cpp');new_h=norm(A/'include/host_keymap.h')
need(len(old)==len(new)==1142 and set(new)==(set(old)-{old_src,old_h})|{new_src,new_h},'main closure paths')
need(all(new[p]==old[p] for p in set(old)-{old_src,old_h}),'main shared dependency hash changed')
need(new[norm(V/'include/recomp_audio_drc.h')]=='c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c','audio header binding')
k={norm(d['path']):d['sha256'] for d in m['steps']['deps:keymap']['deps']}
need(len(k)==118 and all(h and p.startswith('c:\\') for p,h in k.items()),'keymap closure')
need(k[new_h]=='ba28065153423cc39640832ef169143794a14f9babe69adc3616923da8dcbf0f','keymap new header')
oldrsp=(V/'Einhander_Recompiled.v69.rsp').read_bytes();newrsp=(A/'Einhander_Recompiled.p1.rsp').read_bytes()
replacements=m['steps']['rsp']['replaced'];need(len(replacements)==2,'wrong replacement count')
expected=oldrsp
for before,after in replacements:
    a=('"'+before+'"').encode();b=('"'+after+'"').encode();need(expected.count(a)==1,'nonunique response path');expected=expected.replace(a,b)
need(newrsp==expected,'response bytes differ beyond two object paths')
need(m['steps']['retained_inputs']['file_inputs']==155 and not m['steps']['retained_inputs']['mismatched'],'retained file receipt')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'envelope outcome')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384},'child readback')
need(e['job_limits_readback']['affinity_mask']==32768 and e['job_limits_readback']['job_memory_limit']==1073741824,'Job readback')
need(e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'cleanup receipt')
need(sha(U/'receipts/P1-build-2240-runner/executed-watchdog.py')=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','copied watchdog')
ids=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
for c in m['children']:
    need(c['rc']==0 and not c['timed_out'],'child compile/link failed')
    ids.append((c['step'],c['pid'],c['creation_unix']))
known=[]
for label,pid,created in ids:
    need(created is not None,'missing creation time')
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known identity remains '+label)
    known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'p1-build-actual-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,
    manifest_sha256=sha(A/'manifest.json'),envelope_sha256=sha(E),new_executable_sha256=sha(A/'Einhander_Recompiled.exe'),
    new_executable_bytes=(A/'Einhander_Recompiled.exe').stat().st_size,
    changed_translation_units=2,retained_link_inputs=153,main_closure_entries=1142,keymap_closure_entries=118,
    source_and_output_hashes_checked=True,recorded_main_closure_compared=True,all_current_dependencies_rehashed_by_root=False,
    response_file_bytes_compared=True,known_identities=known,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],
    original_v69_executable_unchanged=True,historical_D_keymap_closure='UNKNOWN',old_keymap_reproduced=False,
    large_toolchain_and_retained_inputs_rehashed_by_root=False,
    inherited_warning='main includes unchanged pgxp.h nested-comment warning; compile still exit0',
    compiler_replayed=False,game_launched=False,gpu_used=False,installed=False,
    scope='Private CPU incremental menu build on v69 audio lineage, not in-game color/input/art or release acceptance')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='known_identities'}))
