"""Compile/run the CPU-only sink contract in a new task-owned fixture folder."""
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/'windows-x64/psxrecomp/runtime/src/hd_research_capture.h'
TEST=ROOT/'remaster-audit/test_research_capture_sink.cpp'
OUT=ROOT/'remaster-audit/verification/research-capture-sink'
COMPILER=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fixture=(OUT/'fixtures'/uuid.uuid4().hex).resolve()
    assert fixture.is_relative_to(OUT.resolve())
    fixture.mkdir(parents=True,exist_ok=False)
    command=[str(COMPILER),'-std=c++17','-O2','-static','-I'+str(HEADER.parent),str(TEST),'-o',str(OUT/'test_research_capture_sink.exe')]
    compiled=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (OUT/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
    if compiled.returncode:
        report={'pass':False,'compile_exit':compiled.returncode,'test_exit':None,'checks':0,'failures':1}
        print(compiled.stdout+compiled.stderr)
    else:
        result=subprocess.run([str(OUT/'test_research_capture_sink.exe'),str(fixture)],capture_output=True,text=True,timeout=45)
        (OUT/'test.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        print(result.stdout+result.stderr)
        report=json.loads(result.stdout.strip()) if result.stdout.strip().startswith('{') else {'pass':False,'checks':0,'failures':1}
        report.update(compile_exit=compiled.returncode,test_exit=result.returncode)
    report.update(scope='CPU-only recorder filesystem sink fixtures; no game, RAM, GL or native application launched',
        fixture_directory=fixture.as_posix(),sources=[{'path':p.as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [HEADER,TEST,Path(__file__)]])
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
