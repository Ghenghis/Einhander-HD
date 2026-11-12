"""Measure real presents and guest frames; save raw ring evidence."""
import argparse
import json
import statistics
import time
from pathlib import Path

from stage1_session import ROOT,command


def read_stats():
    p=ROOT/'evidence/draws.jsonl.stats.json'
    return json.loads(p.read_text()) if p.exists() else {}


def percentile(values,p):
    values=sorted(values)
    return values[min(len(values)-1,int((len(values)-1)*p))] if values else None


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=10)
    parser.add_argument('--name',default='diagnostic');args=parser.parse_args()
    before_ring=command('gl_present_ring',n=1);before_frame=command('get_registers')['frame'];before_stats=read_stats()
    started=time.monotonic();time.sleep(args.seconds)
    after_frame=command('get_registers')['frame'];elapsed=time.monotonic()-started
    ring=command('gl_present_ring',n=min(4096,int(args.seconds*80+100)))
    after_stats=read_stats();perf=command('frame_perf')
    events=[r for r in ring.get('events',[]) if r[0]>=before_ring.get('total',0)]
    intervals=[events[i][3]-events[i-1][3] for i in range(1,len(events))]
    counts={key:after_stats.get(key,0)-before_stats.get(key,0) for key in ('attempts','source_matched','decoded_ready','replacement_draws')}
    summary={'seconds':elapsed,'guest_fps':(after_frame-before_frame)/elapsed,
             'present_fps':(ring['total']-before_ring['total'])/elapsed,
             'presented_frames':len(events),'interval_ms':{'median':statistics.median(intervals) if intervals else None,
                'p95':percentile(intervals,.95),'p99':percentile(intervals,.99),'max':max(intervals) if intervals else None},
             'gl_error_events':sum(r[7]!=0 for r in events),'draw_counter_delta':counts,
             'replacement_draw_ratio':counts['replacement_draws']/counts['attempts'] if counts['attempts'] else None,
             'note':'Diagnostic under current scene/load. Capture-pilot screenshots can cause stalls; final acceptance needs an undisturbed window.'}
    out=ROOT/'evidence';(out/(args.name+'-performance.json')).write_text(json.dumps({'summary':summary,'frame_perf':perf,'raw_present_ring':ring,'before_stats':before_stats,'after_stats':after_stats},indent=2)+'\n')
    print(json.dumps(summary,indent=2))
