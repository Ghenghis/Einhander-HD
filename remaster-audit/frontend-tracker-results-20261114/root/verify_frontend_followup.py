from pathlib import Path
import ctypes,datetime,hashlib,json,os,psutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent;out=n/'development-frontend-cpu-r2';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
normalize=lambda f:hashlib.sha256(f.read_text(encoding='utf-8').encode()).hexdigest()
prior=json.loads((n/'development-frontend-cpu-r1/result.json').read_text());assert prior['passed']
for rel in ['windows-x64/tools/launch_hd.py','windows-x64/tools/test_launch_hd.py']:
    assert normalize(r/rel)==prior['source_normalized_sha256'][rel]
files=['windows-x64/tools/'+f for f in ['launch_hd.py','Start-Development.ps1','test_launch_hd.py']]
pins={rel:normalize(r/rel) for rel in files};assert all(normalize(w/rel)==h for rel,h in pins.items())
pointer=r/'windows-x64/tools/material-selection.json';before=pointer.read_bytes()
ps='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe';rows=[]
def run(label,args):
    x=subprocess.run(args,cwd=r,capture_output=True,timeout=25,creationflags=0x08004000)
    (out/(label+'-stdout.log')).write_bytes(x.stdout);(out/(label+'-stderr.log')).write_bytes(x.stderr)
    rows.append(dict(label=label,args=args,exit=x.returncode));assert x.returncode==0,(label,x.stderr[-2000:],x.stdout[-1000:])
    return x.stdout.decode('utf-8-sig')
script=r/windows if False else r/'windows-x64/tools/Start-Development.ps1'
command=r'''$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('C:/github/Einhander/windows-x64/tools/Start-Development.ps1',[ref]$tokens,[ref]$errors)
if($errors.Count){$errors | ConvertTo-Json -Compress; exit 1}
$fn=$ast.Find({param($item) $item -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq 'ConvertTo-DevelopmentRuntimeArguments'},$true)
if(-not $fn){throw 'Missing argument helper'}
. ([scriptblock]::Create($fn.Extent.Text))
$quoted=@(ConvertTo-DevelopmentRuntimeArguments -RuntimeArguments @('--game','C:\Project With Spaces\game.toml','--disc','C:\ROM\Disc Name.cue'))
$rejects=@()
foreach($bad in @('bad"quote','C:\tail\')){try{ConvertTo-DevelopmentRuntimeArguments -RuntimeArguments @($bad) | Out-Null; $rejects+=$false}catch{$rejects+=$true}}
@{syntax_ok=$true; quoted=$quoted; rejects=$rejects} | ConvertTo-Json -Compress
'''
quoted=json.loads(run('powershell-arguments',[ps,'-NoProfile','-NonInteractive','-Command',command]));assert quoted['syntax_ok'] and quoted['rejects']==[True,True]
shell=ctypes.WinDLL('shell32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
shell.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)];shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
count=ctypes.c_int();args=shell.CommandLineToArgvW('fixture.exe '+' '.join(quoted['quoted']),ctypes.byref(count));assert args
try:decoded=[args[i] for i in range(count.value)]
finally:kernel.LocalFree(ctypes.cast(args,ctypes.c_void_p))
assert decoded==['fixture.exe','--game',r'C:\Project With Spaces\game.toml','--disc',r'C:\ROM\Disc Name.cue'],decoded
for label,flags,expected in [('saved-port',[], 'Materials: aurora-teal / crimson-red (explicit_saved_preset)'),('stock-port',['-Stock'],'Materials: stock / stock (explicit_stock)')]:
    text=run(label,[ps,'-NoProfile','-NonInteractive','-File',str(script),'-Check','-Port','9000',*flags])
    assert expected in text and 'Launcher workspace: http://127.0.0.1:9000' in text
assert pointer.read_bytes()==before
assert all(normalize(r/rel)==h and normalize(w/rel)==h for rel,h in pins.items())
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,source_normalized_sha256=pins,commands=rows,retained_python_unit_cases=9,python_units_replayed=False,windows_argv_roundtrip=True,quote_and_trailing_slash_rejected=True,actual_custom_port_saved_and_stock=True,saved_pointer_unchanged=True,affinity=me.cpu_affinity(),below_normal=True,game_run=False,gpu_run=False,browser_or_bridge_started=False,live_frontend_acceptance=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in receipt.items() if k!='commands'}))
