"""Read-only launch material checks; no sockets, process launch or GPU."""
from pathlib import Path
import datetime,hashlib,json,psutil,tomllib
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/v68-unassisted-r1/hd-on_rewind-off'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
c=json.loads((e/'candidate.json').read_bytes());s=c['launches']['candidate'];env=s['environment_overrides']
exe=Path(s['arguments'][0]);settings=exe.parent/'settings.toml'
assert sha(exe)==s['executable_sha256']=='5c1436ff778701d981410da61046aca60c0da60215a5f724523197b58199dfaa'
assert exe.resolve().is_relative_to((e/'runtime').resolve()) and sha(settings)==s['settings_sha256']
tomllib.loads(settings.read_text(encoding='utf-8'))
for flag in ['--game','--disc','--bios','--memcard-dir']:
    p=Path(s['arguments'][s['arguments'].index(flag)+1]);assert p.is_absolute() and p.drive.upper()=='C:' and p.exists(),flag
assert s['user_cards_mounted'] is False and Path(s['writable_state']).resolve()==(e/'state').resolve()
assert (e/'state/card1.mcd').is_file()
expected={'PSX_FRAME_PHASE_RING':'1','PSXRECOMP_NATIVE_UPLOAD_LEDGER':'1','PSX_DISPLAY_RING':'0',
    'PSX_FRAME_INTERPOLATION':'0','PSX_GL_PERF':'0','PSX_REWIND':'0'}
for k,v in expected.items():assert env[k]==v,(k,env.get(k))
assert c['visual_profile']['telemetry_only'] and c['visual_profile']['timer_only_assistance'] is False
assert c['pacing_profile']['ram_writes'] is False and c['production_installed'] is False
assert c['debug_port']==4376 and len(c['files'])==1699
assert (e/'replacement-control.txt').read_text()=='0\n'
assert not (e/'launch-candidate.json').exists() and not (e/'world-flypast-proof.json').exists()
for row in c['files']:assert Path(row['composed_path']).drive.upper()=='C:'
out=n/'v68-staged-material-readback-r1';out.mkdir(exist_ok=False)
d=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
    candidate_sha256=sha(e/'candidate.json'),executable_sha256=sha(exe),settings_sha256=sha(settings),
    private_state=str(e/'state'),card1_sha256=sha(e/'state/card1.mcd'),source_entries=1699,
    all_active_paths_on_c=True,prepared_debug_port=4376,observer_environment=expected,
    full_png_hash_replay=False,private_prepare_verified_all_pngs=True,
    skin_and_experimental_environment={k:v for k,v in env.items() if any(word in k for word in ['SKIN','CLASS_MIP','DECODE_WORKER'])},
    game_run=False,gpu_run=False,installed=False,live_qualified=False)
(out/'result.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(d))
