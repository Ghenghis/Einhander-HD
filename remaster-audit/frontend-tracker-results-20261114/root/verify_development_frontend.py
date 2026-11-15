"""CPU-only saved-material frontend checks; no browser, bridge or game launch."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,subprocess,sys
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
out=n/'development-frontend-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
test='windows-x64/tools/test_launch_hd.py';a=(r/test).read_text(encoding='utf-8');b=(w/test).read_text(encoding='utf-8')
begin=a.index('    def test_frontend_uses_same_saved_runtime_material_and_detail_plan')
end=a.index('    def test_changed_runtime_receipt_is_rejected',begin)
assert (a[:begin]+a[end:]).strip()==b.strip(),'Publication test has unrelated differences; do not overwrite'
(w/test).write_text(a,encoding='utf-8',newline='\n')
files=['windows-x64/tools/'+f for f in ['launch_hd.py','Start-Development.ps1','test_launch_hd.py']]
normalized=lambda p:hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
pins={rel:normalized(r/rel) for rel in files}
assert all(normalized(w/rel)==h for rel,h in pins.items())
selection=r/'windows-x64/tools/material-selection.json';before=selection.read_bytes()
rows=[];env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
def run(label,args,cwd=r):
    x=subprocess.run(args,cwd=cwd,env=env,capture_output=True,timeout=25,creationflags=0x08004000)
    (out/(label+'-stdout.log')).write_bytes(x.stdout);(out/(label+'-stderr.log')).write_bytes(x.stderr)
    rows.append(dict(label=label,args=args,exit=x.returncode));assert x.returncode==0,(label,x.stderr[-2000:],x.stdout[-2000:])
    return x.stdout.decode('utf-8-sig')
run('unit',[sys.executable,'-X','utf8','-m','unittest','-v','test_launch_hd'],r/'windows-x64/tools')
plans={}
for mode,flags in [('direct',[]),('frontend',['--frontend'])]:
    plans[mode]=json.loads(run(mode+'-check',[sys.executable,'-X','utf8',str(r/'windows-x64/tools/launch_hd.py'),'--check',*flags]))
assert all(p['ok'] and p['game_launched'] is False for p in plans.values())
assert plans['frontend']['environment_overrides']==plans['direct']['environment_overrides']
expected=list(plans['direct']['arguments']);expected[expected.index('--no-launcher')]='--launcher';assert plans['frontend']['arguments']==expected
ps='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
syntax="$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('C:/github/Einhander/windows-x64/tools/Start-Development.ps1',[ref]$tokens,[ref]$errors) | Out-Null; if($errors.Count){$errors | ConvertTo-Json -Compress; exit 1}; Write-Output 'PowerShell syntax OK'"
run('powershell-syntax',[ps,'-NoProfile','-NonInteractive','-Command',syntax])
run('development-check',[ps,'-NoProfile','-NonInteractive','-File',str(r/'windows-x64/tools/Start-Development.ps1'),'-Check'])
assert selection.read_bytes()==before
assert all(normalized(r/rel)==h and normalized(w/rel)==h for rel,h in pins.items())
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,unit_cases=9,source_normalized_sha256=pins,commands=rows,actual_saved_profile=plans['frontend']['profile'],actual_enemy_profile=plans['frontend']['enemy_profile'],actual_selection_source=plans['frontend']['selection_source'],saved_pointer_unchanged=True,frontend_flag_validated=True,below_normal=True,affinity=me.cpu_affinity(),game_run=False,gpu_run=False,browser_or_bridge_started=False,live_frontend_acceptance=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
