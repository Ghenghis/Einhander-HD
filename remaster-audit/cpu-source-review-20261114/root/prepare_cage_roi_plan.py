"""Prepare a pinned one-region plan using JSON/native identity bytes only; no image decode or composition."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import psutil
import zlib

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
E=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
C=R/'remaster-audit/claude-backlog/95a3-cage/frozen/95A3BCF8-C-cage-v2'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(ok,why):
    if not ok:raise RuntimeError(why)
def pinned(path,expected):
    raw=Path(path).read_bytes();require(sha(raw)==expected,'pin changed: '+str(path));return raw
parent_path=E/'world-integrated-mijpq-roi-r1/candidate.json'
parent_sha='903bd84a6be19fdef2b6d19293121515035b68c61b7d0ff67f4ff7cf38b30b20'
parent=json.loads(pinned(parent_path,parent_sha))
manifest_path=C/'manifest.json';manifest_sha='9c7cf244ca55ef259a825bc1e8f71d04ed01e9e9f8362f66be40c825e0b02c4f'
manifest=json.loads(pinned(manifest_path,manifest_sha))
key='95A3BCF8-857DB48E';k=manifest['keys'][key]
require(k['bbox']==[64,0,112,64] and k['parent']['shape']==[2048,2048,4],'cage geometry')
require(manifest['validation_passed'] is True,'cage not validated')
row=[r for r in parent['files'] if r['name']==key+'.png']
require(len(row)==1 and row[0]['sha256']==k['parent']['sha256']==
    '59e799b40a9c6beb37284a8597847f5110ea2e26310f47672804c2520462ed63','new parent cage page differs: review required')
require(len(parent['files'])==1699,'unexpected parent inventory')
require(not any(r['name']==key+'-emissive.png' for r in parent.get('emissive_files',[])),
    'changed page has a companion mask: explicit mask policy required')
files=k['native']['files']
words=pinned(files['words.bin']['path'],files['words.bin']['sha256'])
clut=pinned(files['clut.bin']['path'],files['clut.bin']['sha256'])
metadata=json.loads(pinned(files['source.json']['path'],files['source.json']['sha256']))
require((metadata['width_words'],metadata['height'],metadata['depth'])==(64,256,0),'native geometry')
require(len(words)==64*256*2 and len(clut)==32,'native lengths')
require(f'{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}'==key,'native identity')
image_sha='7668b54d510726698219a235681b7038942fe3a3d9492901124b4d190b02bad4'
require(image_sha+'  page2048/'+key+'.png' in (C/'SHA256SUMS.txt').read_text(),'missing image ledger entry')
old_plan=json.loads((N/'mijpq-roi-plan-r1.json').read_bytes())
handoff=old_plan['entries'][0]['source_handoff']
pinned(handoff['path'],handoff['sha256'])
plan=dict(parent=dict(path=str(parent_path),sha256=parent_sha),
    entries=[dict(key=key,manifest=dict(path=str(manifest_path),sha256=manifest_sha),
        image=dict(path=str(C/'page2048'/f'{key}.png'),sha256=image_sha),source_handoff=handoff,
        native_source=dict(source_words=dict(path=files['words.bin']['path'],sha256=files['words.bin']['sha256']),
            source_clut=dict(path=files['clut.bin']['path'],sha256=files['clut.bin']['sha256']),
            source_shape_words=[64,256],depth=0),roi_overlay=dict(native_size=[256,256],uv=[64,0,112,64]))],
    purpose='Pending host-clearance CPU-only cage correctness composition onto latest O/M/I/J/P/Q parent. Not executed, not installed, not final HD art or live acceptance.')
out=N/'cage-roi-plan-r1';out.mkdir(exist_ok=False)
with (out/'plan.json').open('x',encoding='utf-8') as stream:
    json.dump(plan,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),plan_sha256=sha((out/'plan.json').read_bytes()),
    parent_sha256=parent_sha,manifest_sha256=manifest_sha,native_crc_key=key,
    parent_entry_count=1699,planned_changed_pages=1,planned_unchanged_pages=1698,
    image_hash_source='Previously verified frozen ledger; not replayed during host hold',
    images_decoded=0,composition_executed=False,admission_executed=False,installed=False,
    required_next=['host diagnostics clearance and fresh CPU grant',
        'recheck composer/guard/full-input pins before one new output',
        'independently compare all1699pages:1698byte-identical; previous10O/M/I/J/P/Qpages retained',
        'changed page outsideROI RGBA equal latestparent; ROI equal frozen artifact; categorical native alpha',
        'bounded CPU native admission then separately granted live visual/motion review'])
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
