"""Replay preserved F3 source in a fresh workspace, without touching the current engine.

--prepare-only verifies source closure and regenerates six exact tested headers.
--run additionally compiles/runs the six variants; requires a separate CPU grant.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only',action='store_true')
    mode.add_argument('--run',action='store_true')
    parser.add_argument('--cpu',type=int,choices=[11,13,15],default=15)
    args=parser.parse_args()
    args.workspace.mkdir(exist_ok=False)
    source=args.workspace/'source';shutil.copytree(args.bundle,source)
    sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    expected=json.loads((source/'EXPECTED.json').read_bytes())
    assert sha(source/'build_and_run.py')==expected['script_sha256']
    assert sha(source/'harness.c')==expected['harness_sha256']
    for name,h in expected['pins'].items():assert sha(source/'inputs'/name)==h,name
    spec=importlib.util.spec_from_file_location('preserved_f3',source/'build_and_run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.SRC=source/'inputs'
    # Source-root override is explicit configuration. The original script and
    # failed current renderer remain byte-identical; HERE is already isolated.
    prepared=module.prepare()
    assert prepared['variant_headers']==expected['variant_headers']
    result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_root_override=str(module.SRC),original_script_sha256=sha(source/'build_and_run.py'),
        exact_tested_variant_headers=True,source_pins=prepared['pins'],compiler_run=False,gpu_run=False,game_run=False)
    (args.workspace/'prepare-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if args.run:return module.run(args.workspace/'run',100,1<<args.cpu)
    print(json.dumps(result));return 0

if __name__=='__main__':raise SystemExit(main())
