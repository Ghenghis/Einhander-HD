"""Verify a closed private Robin source run without changing captured files."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image

import build_stage1_frozen_candidate as candidate
from verify_world_source_backlog import source_check,sha_file,sha_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    args=parser.parse_args();root=args.run.resolve()
    if not root.is_relative_to(candidate.EVIDENCE.resolve()):raise ValueError('Private completion evidence required')
    output=root/'native-source-verification.json'
    if output.exists():raise ValueError('Source verification is already frozen')
    proof=json.loads((root/'robin-proof.json').read_bytes())
    if proof['errors'] or proof['ram_writes'] or proof['state_loads'] or not proof.get('close',{}).get('port_closed') or proof.get('owned_process_exit')!=0:
        raise ValueError('Require a clean, closed source run')
    rows=[];rejected=[]
    for meta in sorted((root/'source-pages').glob('*.source.json')):
        key=meta.name.removesuffix('.source.json');path=meta.with_name(key+'.png')
        try:
            metadata=json.loads(meta.read_bytes());raw=meta.with_name(key+'.words.bin');clut=meta.with_name(key+'.clut.bin')
            with Image.open(path) as image:
                native=image.convert('RGBA');size=list(native.size);pixels=sha_bytes(native.tobytes())
            _,receipt=source_check(key,dict(source=str(path),source_metadata=metadata,source_verified=True,
                raw_sha256=sha_file(raw),clut_sha256=sha_file(clut),source_size=size,source_pixel_sha256=pixels))
            rows.append(dict(key=key,**receipt))
        except Exception as error:rejected.append(dict(key=key,error=str(error)))
    result=dict(verified_at_utc=datetime.now(timezone.utc).isoformat(),
        run=candidate.sha(root/'robin-proof.json'),requested_craft=proof['route']['requested_craft'],
        source_pairs=len(rows),rejected=rejected,entries=rows,ram_writes=False,state_loads=False,
        stage_clear_verified=False,scope='Native CRC, complete validity, pinned bytes and independent PSX1555 PNG comparison; ownership and live appearance still require draw/capture review')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(receipt=str(output),verified=len(rows),rejected=len(rejected))))
    if rejected or not rows:raise SystemExit(1)


if __name__=='__main__':main()
