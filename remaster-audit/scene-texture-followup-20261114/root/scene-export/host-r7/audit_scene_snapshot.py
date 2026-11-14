"""Independent CPU audit of gp0-scene-v2 snapshots; never loads a renderer.

This verifies internal packet/provenance consistency. It cannot re-establish a
live GTE ring lookup or identify world/camera transforms from combined RT/TR.
"""
import argparse
import json
from pathlib import Path

def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi

def _xform_hash(rt, tr, h, origin):
    value = 2166136261
    for word in [*(x & 0xffff for x in rt), *(x & 0xffffffff for x in tr), h,
                 *(x & 0xffffffff for x in origin)]:
        for byte in word.to_bytes(4, 'little'):
            value = ((value ^ byte) * 16777619) & 0xffffffff
    return value

def audit(bundle):
    errors, advisories, projections = [], [], []
    records = bundle.get('records', [])
    info = bundle.get('info', {})
    def check(ok, where):
        if not ok:
            errors.append(where)
        return ok
    if not check(bundle.get('schema') == 'gp0-scene-v2', 'schema'):
        return dict(passed=False, errors=errors)
    if not check(isinstance(records, list) and len(records) <= 1024, 'bounded record list'):
        return dict(passed=False, errors=errors)
    check(info.get('mode') == 4, 'sealed mode')
    check(info.get('capacity') == 1024, 'capacity')
    check(info.get('count') == len(records), 'record count')
    check(info.get('complete_interval') is True, 'complete interval')
    check(info.get('malformed') == 0 and info.get('overflow') == 0, 'overflow/malformed')
    check(info.get('textured_seen') == len(records), 'textured command coverage')
    frame = info.get('frame')
    check(_integer(frame, 0, 0xffffffff), 'frame range')
    qualified = 0
    for index, p in enumerate(records):
        start = len(errors)
        label = 'record '+str(index)
        try:
            op = p['opcode']; n = 4 if op & 8 else 3; stride = 3 if op & 16 else 2
            check(_integer(op, 0x20, 0x3f) and op & 4, label+' opcode')
            check(p['frame'] == frame and p['ordinal'] == index, label+' frame/order')
            words, sources, vertices = p['words'], p['word_sources'], p['vertices']
            count = n*3 if op & 16 else 1+n*2
            if not check(len(words) == count and len(sources) == count and len(vertices) == n, label+' lengths'):
                continue
            check(all(_integer(w, 0, 0xffffffff) for w in words+sources), label+' word ranges')
            check(words[0] >> 24 == op and p['source'] == sources[0], label+' header')
            check(p['nverts'] == n and p['indices'] == ([0,1,2,2,1,3] if n == 4 else [0,1,2]), label+' topology')
            m = p['material']; tpage = words[5 if op & 16 else 4] >> 16
            check(m['tpage'] == tpage and m['clut'] == words[2] >> 16, label+' texture identity')
            check(m['depth'] == ((tpage >> 7) & 3) and m['blend'] == ((tpage >> 5) & 3), label+' texture mode')
            check(m['raw'] == (op & 1) and m['semi'] == ((op >> 1) & 1), label+' draw mode')
            check(_integer(m['window'],0,0xfffff) and m['set_mask'] in [0,1] and m['check_mask'] in [0,1],label+' draw state')
            if m['depth'] == 3:
                advisories.append(label+': reserved depth; no material binding acceptance')
            if m['semi']:
                advisories.append(label+': PSX semitransparency fidelity requires separate qualification')
            statuses = []
            for j, v in enumerate(vertices):
                pos = 1+j*stride; here = label+' vertex '+str(j)
                check(v['address'] == sources[pos] and v['word'] == words[pos], here+' source')
                check(v['uv'] == [words[pos+1]&255, (words[pos+1]>>8)&255], here+' UV')
                check(v['rgb'] == (words[j*3 if op & 16 else 0] & 0xffffff), here+' RGB')
                statuses.append(v['reason'] == 0)
                if v['reason'] != 0:
                    continue
                check(v['address'] != 0xffffffff and v['address'] % 4 == 0, here+' tracked aligned source')
                check(v['packed'] == v['word'], here+' view word')
                lag = (frame-v['source_frame']) & 0xffffffff
                check(_integer(v['source_frame'],0,0xffffffff),here+' source frame range')
                check(lag <= 1 and v['lag'] == lag, here+' age')
                flags = v['flags']
                check(_integer(flags,0,65535),here+' flags range')
                check(flags & (1<<9) and not (flags & 0xfdfc), here+' commit/divergence flags')
                check((v['cmd'] == 1 and v['lane'] == 0) or (v['cmd'] == 0x30 and 0 <= v['lane'] <= 2), here+' projection command')
                check(isinstance(v['rtp_seq_hex'],str) and len(v['rtp_seq_hex']) == 16 and int(v['rtp_seq_hex'],16) >= 0, here+' sequence encoding')
                rt, tr, model, origin = v['combined_rt'], v['combined_tr'], v['model'], v['of']
                if not check(len(rt) == 9 and len(tr) == 3 and len(model) == 3 and len(origin) == 2, here+' transform lengths'):
                    continue
                check(all(_integer(x,-32768,32767) for x in rt+model),here+' 16-bit transform ranges')
                check(all(_integer(x,-2147483648,2147483647) for x in tr+origin),here+' 32-bit transform ranges')
                check(_integer(v['h'],1,65535),here+' projection height')
                check(v['xform_hash'] == _xform_hash(rt,tr,v['h'],origin), here+' independent transform hash')
                mac = [tr[a]*4096+sum(rt[a*3+b]*model[b] for b in range(3)) for a in range(3)]
                check(v['mac'] == mac and all(type(x) is int for x in v['mac']) and mac[2] > 0, here+' independent MAC')
                if mac[2] > 0:
                    ideal = [v['h']*mac[a]/mac[2]+origin[a]/65536 for a in range(2)]
                    error = max(abs(ideal[a]-v['screen16'][a]/65536) for a in range(2))
                    projections.append(error)
                if j and vertices[0]['reason'] == 0:
                    first = vertices[0]
                    check(all(v[k] == first[k] for k in ['combined_rt','combined_tr','h','of']),here+' common transform')
            check(p['geometry_qualified'] == all(statuses), label+' qualified result')
            if p['geometry_qualified']:
                qualified += 1
            if len(errors) != start:
                advisories.append(label+': internally inconsistent; do not stage a mesh')
        except (KeyError,TypeError,ValueError,OverflowError,IndexError) as ex:
            errors.append(label+': invalid fields '+str(ex))
    check(info.get('geometry_qualified') == qualified,'qualified count')
    return dict(passed=not errors,errors=errors,advisories=advisories,records=len(records),geometry_qualified=qualified,
                ideal_projection_error_max_px=max(projections,default=None),
                projection_error_is_diagnostic=True,live_ring_revalidated=False,world_camera_factorization=False,
                sdk_materials_or_rendering_accepted=False)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args()
    if args.snapshot.stat().st_size > 16*1024*1024:
        raise SystemExit('Snapshot exceeds bounded 16 MiB input limit')
    result=audit(json.loads(args.snapshot.read_text()))
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
