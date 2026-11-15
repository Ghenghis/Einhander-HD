"""Read-only recipe/lineage metadata qualification; no compiler, executable hash sweep or tests."""
from pathlib import Path
import datetime as dt, hashlib, json, os, psutil, re
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/proposals/p1-player-color/build'
V=R/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206'
B=R/'windows-x64/build-ss8c'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
def need(ok,why):
    if not ok: raise RuntimeError(why)
def raw(p,want):
    b=p.read_bytes(); need(hashlib.sha256(b).hexdigest()==want,'pin changed '+str(p)); return b
driver=raw(U/'build_p1_v69_r3.py','5f713865c62ed3cb899df775206c588a121172f64ff28dd9444da7b20267bda7')
table=raw(U/'retained-inputs.v69.tsv','d9eb77e020cc36a45b5c533869a938b2a82839826fbe2634a408579b503de757')
v69=json.loads(raw(V/'manifest.json','e6ab30e9c9c03697b3c4dcd64a253d232cd0de1d1fbc9bc73d5c7880748de8b4'))
v68=json.loads(raw(R/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1/build.json','21944d697b27b6715edcf8a4ad67c76c2527b5bf5a3aa729b981fc34702af70e'))
rsp=raw(V/'Einhander_Recompiled.v69.rsp','52342192c15c3c14f7acd556e7644b1533d1e3fedd2da32600286fffb93c8496').decode()
rows={p:h for h,p in (line.split('\t',1) for line in table.decode().splitlines() if line)}
tokens=re.findall(r'"([^"]*)"',rsp)
files=[t for t in tokens if not t.startswith('-')]
need(len(rows)==len(files)==155 and set(rows)==set(files),'table/rsp file set')
norm=lambda p:os.path.normcase(os.path.abspath(p))
old={norm(x['path']):x['sha256'] for x in v68['link_inputs']}
new={norm(V/'obj/main.cpp.obj'):'286af211733afe820d221f6bcc5fa56f4bc0f563a2c626e0de446f6e167f77c9',
     norm(V/'obj/debug_server.c.obj'):'dc75afc26f599ac93d20d877122312c0054900e85d9c3a9569a61d9c3c87a37f'}
matched_old=0; matched_new=0
for p,h in rows.items():
    q=norm(Path(p) if Path(p).is_absolute() else B/p)
    if q in new: need(h==new[q],'v69 replacement metadata mismatch'); matched_new+=1
    else: need(old.get(q)==h,'v68 retained metadata mismatch '+p); matched_old+=1
need(matched_old==153 and matched_new==2,'lineage counts')
need(len(v69['build']['main']['closure'])==1142,'v69 dependency closure count')
out=N/'p1-r3-source-qualification-r1'; out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_qualification_pass=True,
    driver_sha256=hashlib.sha256(driver).hexdigest(),retained_table_sha256=hashlib.sha256(table).hexdigest(),
    response_file_inputs=155,v68_metadata_pins_matched=153,v69_new_object_metadata_pins_matched=2,
    historical_v69_main_closure_entries=1142,
    root_review='Full r2 source read plus full r2-to-r3 narrow delta; historical main shared hash gate now represented, new keymap C-only closure separately recorded. Source-clear for one fresh qualified CPU build only.',
    historical_D_keymap_dependency_closure='UNKNOWN; no D reads, old keymap object not reproduced',
    large_retained_file_hashes_recomputed=False,compiler_run=False,game_run=False,gpu_run=False,installed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
