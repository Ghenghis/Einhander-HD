"""Prove the focused GL fixture detects the prior pending-destination bug.

Compiles a private renderer copy with only the new re-arm removed. Never edits
the runtime source or starts a game. Pass --build to a completed staged build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True)
    args=parser.parse_args();root=args.build.resolve();report=json.loads((root/'build.json').read_text())
    out=root/'negative-control';out.mkdir(exist_ok=False)
    source=next(Path(p) for p in report['source_hashes'] if p.endswith('gpu_gl_renderer.c'))
    original=source.read_text();needle='            hd_rearm_pending_destination(x0,y0,x1,y1);'
    assert original.count(needle)==1
    negative=out/'gpu_gl_renderer.c'
    negative.write_text(original.replace(needle,'            if(x0<=x1&&y0<=y1)hd_page_mark_gpu_dirty(&s_hd_pages,x0,y0,x1-x0+1,y1-y0+1);'))
    harness=source.parents[4]/'remaster-audit/test_exact_regions_gl.c'
    assert harness.is_file()
    wrapper=out/'negative-renderer.c';wrapper.write_text('#define HD_RENDERER_SOURCE "'+negative.as_posix()+'"\n#include "'+harness.as_posix()+'"\n')
    commands={x['label']:x['arguments'] for x in report['commands']};results=[]
    def run(command,label,expected=0):
        result=subprocess.run(command,cwd=source.parents[3]/'build-ss8c',capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(label+'.log')).write_text(result.stdout+result.stderr);results.append({'label':label,'arguments':command,'exit':result.returncode})
        assert result.returncode==expected,(label,result.returncode,result.stdout+result.stderr)
        return result
    obj=out/'negative-renderer.obj';compile_cmd=commands['compile-gl-renderer'].copy()
    compile_cmd[compile_cmd.index('-o')+1]=str(obj);compile_cmd[compile_cmd.index('-MF')+1]=str(obj)+'.d';compile_cmd[-1]=str(wrapper)
    run(compile_cmd,'compile-negative')
    rsp=out/'negative-link.rsp';rsp.write_text((root/'region-gl-link.rsp').read_text().replace((root/'region-test-renderer.obj').as_posix(),obj.as_posix()))
    exe=out/'negative-control.exe';link=commands['link-gl'].copy();link[next(i for i,x in enumerate(link) if x.startswith('@'))]='@'+str(rsp);link[link.index('-o')+1]=str(exe)
    run(link,'link-negative')
    env=os.environ.copy();env.update(PSXRECOMP_HD_PAGE_FALLBACK='1',PSXRECOMP_HD_CPU_AUTHORITY='0')
    result=subprocess.run([str(exe),str(root/'fixtures/valid')],cwd=source.parents[3]/'build-ss8c',env=env,capture_output=True,text=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'negative-test.log').write_text(result.stdout+result.stderr)
    expected='CHECK next full query rejects overwritten complete proof FAIL'
    success=result.returncode==1 and expected in result.stdout
    outcome={'negative_control_detected':success,'exit':result.returncode,'expected_failure':expected,'output':result.stdout,
             'runtime_source_untouched':source.read_text()==original,'renderer_copy_sha256':hashlib.sha256(negative.read_bytes()).hexdigest(),'commands':results}
    (out/'result.json').write_text(json.dumps(outcome,indent=2)+'\n');print(json.dumps(outcome))
    return 0 if success and outcome['runtime_source_untouched'] else 1

if __name__=='__main__':raise SystemExit(main())
