"""Exact production recorder adapter/handler with native CPU fixtures; no game."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
RUNTIME=ROOT/'windows-x64/psxrecomp/runtime'
OUT=ROOT/'remaster-audit/verification/research-capture-command'
COMPILER=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 args=[str(COMPILER),'-O2','-static','-I'+str(RUNTIME/'src'),'-I'+str(RUNTIME/'include'),str(ROOT/'remaster-audit/test_research_capture_command.cpp'),'-o',str(OUT/'test_research_capture_command.exe')]
 built=subprocess.run(args,capture_output=True,text=True,timeout=60)
 (OUT/'compile.log').write_text(built.stdout+built.stderr,encoding='utf-8')
 if built.returncode:print(built.stdout+built.stderr);return built.returncode
 with tempfile.TemporaryDirectory(prefix='ein-research-command-') as directory:
  tested=subprocess.run([str(OUT/'test_research_capture_command.exe'),directory],capture_output=True,text=True,timeout=60)
 (OUT/'result.log').write_text(tested.stdout+tested.stderr,encoding='utf-8')
 if tested.stdout.strip().startswith('{'):
  report=json.loads(tested.stdout);assert report['sample_mark']['contract']=='ein-research-v1';assert report['sample_mark']['event_file']=='event-0001.bin'
  paths=[RUNTIME/'src'/('hd_research_'+n+'.h') for n in ['capture','event','filter','request','sample','renderer','debug']]+[RUNTIME/'include/gpu_gl_renderer.h',RUNTIME/'src/gpu_gl_renderer.c',RUNTIME/'src/debug_server.c',ROOT/'remaster-audit/test_research_capture_command.cpp']
  report.update(compile_exit=built.returncode,test_exit=tested.returncode,scope='Exact CPU-only native recorder adapter and wire handler; deterministic fixture RAM/VRAM, no game or GL context',sources=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in paths])
  (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['sample_mark','sample_filter','sources']},indent=2))
 else:print(tested.stdout+tested.stderr)
 return tested.returncode
if __name__=='__main__':raise SystemExit(main())
