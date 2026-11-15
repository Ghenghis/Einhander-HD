"""Small artifact/hash/identity readback only; no targets, images decoded, tests or GPU."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;l=r/'remaster-audit/parallel-stages-20261114'
out=n/'transport-refusals-hud-readback-r1';out.mkdir(exist_ok=False)
pins={l/'s67/proposals/raw37c-diagnostic/raw37c_driver_r11.py':'8f753ce74ad3ab4728a0b5b485bab5764cf34294ad1de17d394e44001e4dd17d',l/'s67/proposals/raw37c-diagnostic/test_raw37c_driver_r8.py':'fe9f5467a480cb6c56ffa73f95ab4a92ea8e787933afc2b73915360df7677869',l/'s67/proposals/raw37c-diagnostic/test_raw37c_driver_r9.py':'f2634fd68a486fc31e421f9507d8333cdddc8f588a481ed8b67b176298ffb6b9',l/'s67/runs/raw37c-controls-r8-2349-envelope.json':'a497a5e5adbb0682a2de4036052e08f5cd561e8c47269755fcc48f2e2564c368',l/'s67/runs/raw37c-controls-r8-2349.log':'b8022ef9071648050e257a842789c19a054a5ff3f6157b11e179e304e2b0106f',l/'s67/runs/raw37c-controls-r9-2352-envelope.json':'d7ac6ac5005ab8d5a9697d6502f1005a2e2d50f893dbf8629ceda73b02af825f'}
rows=[]
for path,want in pins.items():
    raw=path.read_bytes(); got=hashlib.sha256(raw).hexdigest();assert got==want,(str(path),got)
    rows.append({'path':str(path),'sha256':got,'bytes':len(raw),'matched_reported_pin':True})
env=json.loads((l/'s67/runs/raw37c-controls-r8-2349-envelope.json').read_bytes())
assert env['child_exit_code']==1 and env['job_empty'] and env['tree_absent'] and env['job']['active']==0
assert "KeyError: 'cleanup_holder'" in (l/'s67/runs/raw37c-controls-r8-2349.log').read_text()
identities=[]
for kind in ('wrapper','child'):
    pid,ct=env[kind+'_pid'],env[kind+'_create_time'];absent=False
    try: absent=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess:absent=True
    assert absent,(kind,pid,'sameidentitystillpresent')
    identities.append({'kind':kind,'pid':pid,'creation_unix':ct,'identity_absent':True})
declines=[]
for path in [l/'s67/runs/raw37c-controls-r9-2352-envelope.json',l/'s67/runs/raw37c-controls-r9-2353-coordinator-envelope.json',l/'s45/runs/diagbands-r5-fixtures-envelope.json']:
    raw=path.read_bytes();e=json.loads(raw)
    assert e['declined'] is True and e['child_pid'] is None and e['wrapper_exit']==3 and e['rc'] is None
    assert e['precheck']['system_cpu_pct']>=e['precheck']['max_cpu']
    declines.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'cpu':e['precheck']['system_cpu_pct'],'child_started':False,'at_utc':e['precheck']['at_utc']})
stage=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/raw37c-r6-20261114T2331Z/hd-on_rewind-off/raw37c-staging.json'
raw=stage.read_bytes();assert hashlib.sha256(raw).hexdigest()=='2710782ef5627a16f9c1528ac1f662d80bd03a1cb5985365c5ef1db04f809c79'
st=json.loads(raw);pack=Path(st['pack']['root']);assert pack.resolve().is_relative_to(stage.parent.resolve())
old=r/'remaster-audit/hud-restoration/candidate-20261112-coherent-v4/pack/einhander-texture-replacements'
hud=[]
for key in ['44C16454-72FBA1C5','8BA3BB4D-190A55AD','8BA3BB4D-36D62A31','8BA3BB4D-E0AE221F']:
    oldp=old/(key+'.png');oldsha=hashlib.sha256(oldp.read_bytes()).hexdigest()
    matches=[(rel,h) for rel,h in st['pack']['png_pins'].items() if Path(rel).name==key+'.png']
    actual=[]
    for rel,want in matches:
        path=pack/rel;assert path.resolve().is_relative_to(pack.resolve())
        got=hashlib.sha256(path.read_bytes()).hexdigest();assert got==want
        actual.append({'relative':rel,'sha256':got,'equals_coherent_v4':got==oldsha})
    hud.append({'key':key,'coherent_v4_path':str(oldp),'coherent_v4_sha256':oldsha,'staged':actual,'decoded':False})
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'identities':identities,'raw_controls_r8':'FAIL no final checkcounts; source fixture closure omission, not game failure','declines':declines,'hud':hud,'staging_receipt_sha256':hashlib.sha256(raw).hexdigest(),'tests_replayed':False,'gpu_game_used':False,'limits':['Known wrapper/child identities only; sampled descendant withoutctime not an independentidentityproof.','Three resource declines are nochild refusals, not controls executed/failing.','Four currentstaged PNG hashes only; no decode/class/readability/visual/live or installedrelease proof.','Historical v4 test/visual records not replayed.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'pins':len(rows),'identities':len(identities),'resource_declines':len(declines),'hud':[{k:v for k,v in x.items() if k in ('key','staged')} for x in hud]}))
