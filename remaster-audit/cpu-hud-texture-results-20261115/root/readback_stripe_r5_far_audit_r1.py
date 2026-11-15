"""Read existing failed stripe evidence and far-background audit; no image decode/test replay."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;l=r/'remaster-audit/parallel-stages-20261114'
files=[l/'s45/tools/s45_diag_bands_r5.py',l/'s45/runs/diagbands-r5-fixtures-attempt2-envelope.json',l/'s45/repairs/20261115T001350Z-diagbands-r5-fixtures/receipt.json',l/'s45/repairs/20261115T001350Z-diagbands-r5-fixtures/fixtures-receipt.json',l/'s67/reports/S67-STAGE1-FAR-NEON-BUILDING-AUDIT-20261115.md',l/'s67/reports/S67-STAGE1-FAR-NEON-BUILDING-AUDIT-20261115-ERRATUM-r1.md']
rows=[]
for f in files:raw=f.read_bytes();rows.append({'path':str(f),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
assert rows[0]['sha256']=='4df3b6a612244969df99564144a73813a7370ed2b1525ebc02978ec7bc09ae10'
assert rows[4]['sha256']=='4f39c1c33d70c711a2ad65d5d0b5f4048bb2f66d5cd3bf150e83c84b3c47243e'
assert rows[5]['sha256']=='ecf1fb3bdfe208a84882f79d3c996148b0df9dbbf5805c0da96aa9ff23311125'
e=json.loads(files[1].read_bytes());d=json.loads(files[3].read_bytes());cases=d['cases'];assert len(cases)==24 and sum(x['ok'] for x in cases)==21 and d['all_ok'] is False
neg=[x for x in cases if x['expect_fail']];bad=[{'name':x['name'],'reason':x['msg']} for x in cases if not x['ok']]
assert len(neg)==16 and all(x['ok'] for x in neg) and len(bad)==3
assert e['child_exit_code']==3 and e['rc']==3 and e['wrapper_exit']==3 and e['job_empty'] and e['tree_absent'] and e['job']['active']==0
identities=[]
for kind in ('wrapper','child'):
    pid,ct=e[kind+'_pid'],e[kind+'_create_time']
    try:gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess:gone=True
    assert gone,(pid,ct)
    identities.append({'kind':kind,'pid':pid,'creation_unix':ct,'identity_absent':True})
stage=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/raw37c-r6-20261114T2331Z/hd-on_rewind-off/raw37c-staging.json';raw=stage.read_bytes();assert hashlib.sha256(raw).hexdigest()=='2710782ef5627a16f9c1528ac1f662d80bd03a1cb5985365c5ef1db04f809c79'
st=json.loads(raw);mapping=st['pack']['png_pins'];missing_key='95A3BCF8-7589E98F.png';assert not any(Path(rel).name==missing_key for rel in mapping)
subset={}
for key in ['95A3BCF8-60245B3A.png','95A3BCF8-07A9568D.png','95A3BCF8-723E222C.png']:
    matches=[(rel,want) for rel,want in mapping.items() if Path(rel).name==key];assert len(matches)==1
    rel,want=matches[0];f=Path(st['pack']['root'])/rel;got=hashlib.sha256(f.read_bytes()).hexdigest();assert got==want
    subset[key]={'relative':rel,'sha256':got,'current_staged_bytes_match':True}
out=n/'stripe-r5-far-audit-readback-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'known_identities':identities,'stripe_actual':{'cases':24,'ok':21,'negative_cases_ok':16,'failed':True,'failures':bad,'whole_job_s':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes'],'job_empty':True},'far_background':{'missing_staged_key':missing_key,'staged_subset':subset,'original_audit_and_erratum_read':True,'full_visual_acceptance':False},'tests_replayed':False,'images_decoded':False,'gpu_game_used':False,'limits':['Far-audit drawcount/role/source assertions are owner/subagentmetadata; root independentlychecks only threecurrentstagedhashes and missing-mapmembership, not allcitedsources.','Page-level failure is unattributed to particularROI; no dominanceoutsideK/failedinsideC claim.','MissingCLUTblocks offlineauthoring/audit, not nativegamerendering.','No accepted-look appliesonlyauditedsubset and recordedqualifiedliveproof.','R6 metrics relaxations do not change candidateRGBalgorithm; not repaireddefects/acceptedart.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({'out':str(out),'pins':len(rows),'identities':len(identities),'stripe':'FAILED21of24','staged_hashes':3,'missing_key':missing_key}))
