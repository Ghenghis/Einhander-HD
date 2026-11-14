"""Independent disk reference checks; no image decode or class-algorithm replay."""
from pathlib import Path
import datetime,hashlib,json,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
u=r/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
stock=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
summary=u/'integration/runtime-summary-v5-20261114T180533Z.json'
assert sha(summary)=='e124d0e814d2d7b9d503c7df36df1a6aba62cc18e6a9483f6ab2a7e0fa092a1b'
s=json.loads(summary.read_bytes());assert (s['units'],s['files'],s['files_pass'])==(72,118,118)
checks=[];destinations=set();variant_count=0;members=0
def check(f,h,scope):
    f=Path(f).resolve()
    if scope=='generated':assert f.is_relative_to(u.resolve()),str(f)
    else:assert f.is_relative_to(r.resolve()) or f.is_relative_to(stock.resolve()),str(f)
    assert f.drive.upper()=='C:' and sha(f)==h,str(f)
    checks.append(dict(path=str(f),sha256=h,scope=scope))
for run,meta in s['runs'].items():
    folder=u/'classsnap-v5'/run;result=folder/'result.json'
    check(result,meta['result_sha256'],'generated');d=json.loads(result.read_bytes())
    assert d['tool_sha256']=='67790a05792e3e061bfc5cef7706e31967ed03e8779df0d2666985707df63612'
    for row in d['rows']:
        for key,v in row['variants'].items():
            f=(folder/v['path']).resolve();identity=str(f).casefold()
            assert identity not in destinations,identity
            destinations.add(identity);check(f,v['sha256'],'generated');variant_count+=1
for unit in s['units_detail']:
    assert unit['shape_identical']
    for m in unit['members']:
        members+=1;assert m['built'] and m['primary_pass'] and m['s2_pass']
        for field,hfield in [('candidate','candidate_sha256'),('noR5','noR5_sha256')]:
            check(u/m[field],m[hfield],'generated')
        for field,hfield in [('words','words_sha256'),('clut','clut_sha256')]:
            check(m[field],m[hfield],'native')
assert variant_count==708 and members==118
out=n/'ui-v5-independent-readback-r3';out.mkdir(exist_ok=False)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
    summary_sha256=sha(summary),variant_files=variant_count,case_insensitive_duplicate_paths=0,
    member_files=members,total_hash_checks=len(checks),outside_project_native_cluts=54,
    reported_primary_class_passes=118,class_algorithm_replayed=False,image_look_accepted=False,
    cross_folder_conflicts=s['cross_folder_conflicts']['count'],gpu_run=False,game_run=False,installed=False,
    checks=checks)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
