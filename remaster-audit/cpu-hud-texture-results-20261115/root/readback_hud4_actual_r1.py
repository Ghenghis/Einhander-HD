"""Verify actual four-HUD measurement artifacts; no decode, compiler/DLL load or replay."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
n=Path(__file__).resolve().parent;u=Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui')
b=u/'hud4-v4-audit/runs/20261115T001900Z'
pins={u/'receipts/H4-r2-CPU13-envelope.json':'817c436cb933796ebb2a7d630e1ea6826b6fa420e7703bad9aed60c319d6649e',u/'receipts/H4-r2-CPU13-runner/executed-watchdog.py':'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',u/'hud4-v4-audit/ui_hud4_v4_region_audit_r2.py':'c5d0e375e1b69f4156a0828a8d8492e6423df5c0cd2e366a3ed1fc2fe8bf5f13',b/'result.json':'3b3c191779d60c5a07f398a388f79699e5017bc3979b38919b465926646b0314',b/'receipt.json':'e5ea35499568d1c4d9e5a73ae439cc473cd852c05b5ccda2a81fee7eb9a045c4'}
rows=[]
def check(path,want):
    raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(str(path),got)
    rows.append({'path':str(path),'sha256':got,'bytes':len(raw)});return raw
for path,want in pins.items():check(path,want)
d=json.loads((b/'result.json').read_bytes());s=json.loads((b/'receipt.json').read_bytes());e=json.loads((u/'receipts/H4-r2-CPU13-envelope.json').read_bytes())
assert len(d['controls'])==6 and all(d['controls'].values())
assert s['phase']=='done' and s['exit_code']==0 and s['error'] is None
assert e['rc']==e['child_exit_code']==e['wrapper_exit']==0 and e['job_empty'] and e['tree_absent'] and e['job']['active']==0
assert e['cpu']==13 and e['max_job_mib']==1024 and e['timeout_s']==90 and e['priority']==16384
for name,want in d['executed_artifacts'].items():check(b/name,want)
expected={'44C16454-72FBA1C5':('R1_CONNECTIVITY_FAIL',2028,2031),'8BA3BB4D-190A55AD':('R1_CONNECTIVITY_PASS',0,0),'8BA3BB4D-36D62A31':('R1_CONNECTIVITY_PASS',0,1),'8BA3BB4D-E0AE221F':('R1_CONNECTIVITY_FAIL',932,933)}
measures={}
for key,(verdict,conn,s2) in expected.items():
    v=d['rows'][key];assert (v['region_verdict'],v['conn_region'],v['s2_region'])==(verdict,conn,s2)
    assert v['metric_agree'] is True and v['r1_region']==0 and v['nonclass_region']==0
    sheet=v['review_1x'];check(b/sheet['path'],sheet['sha256'])
    clutp,cluth=v['pins']['clut'];clut=check(Path(clutp),cluth)
    measures[key]={'verdict':verdict,'r1_region':0,'conn_region':conn,'s2_region':s2,'nonclass_region':0,'metric_agree':True,'region_texels':v['region_texels'],'palette_all_zero':all(x==0 for x in clut),'review_sheet':sheet}
assert measures['8BA3BB4D-190A55AD']['palette_all_zero'] is True
identities=[]
for kind in ('wrapper','child'):
    pid,ct=e[kind+'_pid'],e[kind+'_create_time']
    try:gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess:gone=True
    assert gone,(kind,pid)
    identities.append({'kind':kind,'pid':pid,'creation_unix':ct,'identity_absent':True})
out=n/'hud4-actual-readback-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'known_identities':identities,'controls_passed':6,'measurements':measures,'whole_job_s':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes'],'job_empty':True,'tests_replayed':False,'images_decoded_by_readback':False,'compiler_dll_loaded_by_readback':False,'root_viewed_all_four_existing_review_sheets':True,'visual_observations':['44C16454whole-striproleincludesnumeral1andmixedblue/greenicons/parts; do notapplyglyph-onlyrepairacrossit.','E0flagmapappearsconcentratedtopROIedge; digitinteriorlookscoherentattheviewsheetresolution. Needcoordinate/localcontextanalysis, notblindrepair.','190A55ADisblankinbothnative/candidateandhasallzeroCLUT; astructuralpassisnotreadableHUDproof.','36D62A31white/greenoutlinegauge/digitslookscoherentasstaticsheet; NOTliveacceptance.'],'limits':['Exit0meansmeasurementcomplete, notfourpassed.','R1/connectivityisnotfullnativeclass/readability/composed/liveadmission.','Noartwasrepairedorinstalled; noGPU/gameverification.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({'out':str(out),'pins':len(rows),'known_identities':len(identities),'controls':6,'connectivity_pass':2,'connectivity_fail':2,'blank_palette_pass':1,'seconds':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes']}))
