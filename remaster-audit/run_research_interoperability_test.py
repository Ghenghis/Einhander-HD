"""Feed actual native-adapter fixture bytes to the production backend validator.

No game launches. Native fixture output and acknowledgement remain unchanged.
A private in-root directory alias matches the backend's required native layout.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'remaster-audit/verification/research-interoperability'
NATIVE=ROOT/'remaster-audit/verification/research-capture-command'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    native_report=json.loads((NATIVE/'result.json').read_text(encoding='utf-8'))
    assert native_report['compile_exit']==native_report['test_exit']==native_report['failures']==0
    for item in native_report['sources']:
        assert digest(item['path'])==item['sha256'], 'Rebuild native adapter fixture before interoperability test: '+item['path']
    OUT.mkdir(parents=True,exist_ok=True)
    fixture=(OUT/uuid.uuid4().hex).resolve()
    assert fixture.is_relative_to(OUT.resolve())
    fixture.mkdir(exist_ok=False)
    executable=NATIVE/'test_research_capture_command.exe'
    tested=subprocess.run([str(executable),str(fixture)],capture_output=True,text=True,timeout=60)
    assert tested.returncode==0,(tested.stdout,tested.stderr)
    producer=json.loads(tested.stdout)
    acknowledgement=producer['sample_mark']
    assert Path(acknowledgement['path']).resolve()==(fixture/'main').resolve()
    # Alias remains strictly inside this newly owned fixture directory. No
    # producer path, binary content, event field or acknowledgement is rewritten.
    os.symlink(fixture/'main',fixture/'native',target_is_directory=True)
    sys.path.insert(0,str(ROOT/'windows-x64/tools'))
    from research_service import ResearchService
    service=ResearchService(ROOT/'windows-x64',lambda *args,**kwargs:None)
    filter_ack=producer['sample_filter']
    filter_config=dict(policy='include',keys=['11223344-55667788'])
    assert service._native_filter_valid(filter_ack,filter_config)
    tampered_filter=dict(filter_ack,source_filter=dict(filter_ack['source_filter'],keys_fnv1a32=filter_ack['source_filter']['keys_fnv1a32']^1))
    assert not service._native_filter_valid(tampered_filter,filter_config)
    run={'path':fixture}
    assert service._native_valid(acknowledgement,run)
    metadata,ram=service._event_binary(run,acknowledgement)
    assert len(ram)==2*1024*1024
    assert metadata['candidate_only'] and metadata['gpu_readback'] is False and metadata['cpu_vram_may_be_stale']
    rejected={}
    for field in ['event_frame','event_host_mono_ms','event_bytes']:
        altered=dict(acknowledgement,**{field:acknowledgement[field]+1})
        try:service._event_binary(run,altered)
        except ValueError:rejected[field]=True
        else:rejected[field]=False
    assert all(rejected.values())
    paths=[ROOT/'windows-x64/tools/research_service.py',Path(__file__),executable]
    paths += [Path(item['path']) for item in native_report['sources']]
    report={'pass':True,
        'scope':'Actual exact-native-adapter headless binary parsed by production backend validator; no game or GL context.',
        'fixture_layout':'unchanged_native_ack_with_private_in_root_native_directory_alias',
        'fixture_directory':fixture.as_posix(),'native_checks':producer['checks'],
        'native_acknowledgement':acknowledgement,'backend_native_valid':True,
        'native_source_filter_acknowledgement':filter_ack,'backend_exact_source_filter_valid':True,'tampered_source_filter_fingerprint_rejected':True,
        'backend_event_binary':metadata,'tampered_exact_event_fields_rejected':rejected,
        'limitations':['This proves native/backend serialization interoperability and bounds with deterministic CPU fixture memory, not successful live gameplay recording.',
            'CPU-VRAM coherence, full ordered GP0 replay, screenshots, fast effect sequences and semantic address/model ownership remain separate capture gaps.'],
        'sources':[{'path':p.as_posix(),'sha256':digest(p)} for p in dict.fromkeys(paths)]}
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['pass','scope','native_checks','backend_native_valid','tampered_exact_event_fields_rejected']},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
