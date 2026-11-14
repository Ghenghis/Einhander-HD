"""CPU-only admission/integrity checks; no installation or visual acceptance."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess
import psutil

psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
root=Path('C:/github/Einhander')
n=Path(__file__).resolve().parent
out=root/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v3'
candidate=out/'candidate.json'
sha=lambda p: hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
c=json.loads(candidate.read_text())
plan=json.loads((n/'world-final-bindings-plan-v1.json').read_text())
parent_path=Path(plan['parent']['path'])
assert sha(parent_path)==plan['parent']['sha256']
parent=json.loads(parent_path.read_text())
assert c['final_count']==len(c['files'])==1699
assert not c['production_installed'] and not c['live_visual_accepted']
assert c['authored_entries']==len(plan['entries'])==53
assert c['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT']==str(out/'pack')
bad=[]
for kind, rows in [('candidate',c['files']+c.get('emissive_files',[])),('parent',parent['files']+parent.get('emissive_files',[]))]:
    for row in rows:
        if sha(row['composed_path'])!=row['sha256']: bad.append([kind,row['name']])
assert not bad,bad
by={r['name']:r for r in c['files']}
old={r['name']:r for r in parent['files']}
protected={name:by[name]['sha256'] for name in parent['sign_crisp_v2']['replaced']}
assert all(digest==old[name]['sha256'] for name,digest in protected.items())
patches={e['key']+'.png' for e in plan['entries']}
assert not patches.intersection(protected)
new=sorted(set(by)-set(old))
changed=sorted(k for k in patches if k in old and by[k]['sha256']!=old[k]['sha256'])
classes=json.loads((n/'world-final-class-check.json').read_text())
assert not classes['failures'] and classes['keys_checked']==53
assert classes['plan_sha256']==sha(n/'world-final-bindings-plan-v1.json')
exe=root/'remaster-audit/claude-backlog/sign-washout-audit/verifier-build/verify_native.exe'
assert sha(exe)=='859fc54e92a8397170f3fb4c6f959c8d49e5d205b8b3fe6bda7c9fed997bfd7b'
assert sha(root/'remaster-audit/verify_stage1_candidate_native.cpp')=='89b9be62002933bf7d8d8464bf216c7f70a06a863307f4579d3d3e8c315d876d'
native=[]
for label,pack,count in [('new',out/'pack',1699),('parent',parent_path.parent/'pack',1698)]:
    args=[str(exe),str(pack),str(count)]
    p=subprocess.run(args,capture_output=True,text=True,timeout=120,creationflags=0x4000)
    native.append({'label':label,'args':args,'exit':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()})
    assert p.returncode==0,native[-1]
    assert json.loads(p.stdout)['failures']==0
manifest_rows=[]
for f in sorted((out/'pack').rglob('*')):
    if f.is_file():manifest_rows.append({'path':f.relative_to(out/'pack').as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)})
canonical=''.join(f"{r['path']} {r['sha256']}\n" for r in manifest_rows)
manifest={'format':1,'pack':str(out/'pack'),'files':len(manifest_rows),'root_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'rows':manifest_rows}
(out/'pack-sha256-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_sha256':sha(candidate),
    'parent_candidate_sha256':sha(parent_path),'final_key_count':c['final_count'],'patch_count':len(patches),
    'added_keys':new,'changed_existing_keys':changed,'protected_crisp_signs':protected,'pinned_mismatches':bad,
    'native':native,'class_check':{'keys':classes['keys_checked'],'native_centres_checked':classes['native_centres_checked'],'failures':0},
    'manifest_files':manifest['files'],'pack_root_sha256':manifest['root_sha256'],
    'all_checks_pass':True,'scope':'Admission, native class preservation, hash/source/parent integrity only. Live appearance, gameplay, timing and complete scene coverage NOT accepted.'}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'READY.json').write_text(json.dumps({'candidate_sha256':sha(candidate),'verification_sha256':sha(out/'verification.json'),
    'pack_manifest_sha256':sha(out/'pack-sha256-manifest.json'),'ready_for':'bounded private live review',
    'production_installed':False,'visual_accepted':False},indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['all_checks_pass','final_key_count','patch_count','manifest_files','native','class_check']},indent=2))
print(json.dumps({'added_keys':len(new),'changed_existing_keys':len(changed),'protected_signs':len(protected)}))
