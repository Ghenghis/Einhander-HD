"""Record real presents and audio underruns without screenshots during sampling."""
import argparse,json,statistics,time
from stage1_session import ROOT,command
parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);parser.add_argument('--seconds',type=float,default=10);args=parser.parse_args()
before_audio=command('audio_stats');before_fmv=command('fmv_state');before=command('gl_present_ring',n=1);frame=command('get_registers')['frame']
started=time.monotonic();time.sleep(args.seconds)
elapsed=time.monotonic()-started;after_frame=command('get_registers')['frame'];ring=command('gl_present_ring',n=2000);after_audio=command('audio_stats')
events=[e for e in ring.get('events',[]) if e[0]>=before['total']]
intervals=sorted(events[i][3]-events[i-1][3] for i in range(1,len(events)))
summary={'seconds':elapsed,'guest_fps':(after_frame-frame)/elapsed,'present_fps':(ring['total']-before['total'])/elapsed,
 'interval_ms':{'median':statistics.median(intervals) if intervals else None,'p95':intervals[int((len(intervals)-1)*.95)] if intervals else None,'max':max(intervals) if intervals else None},
 'audio_underruns':after_audio.get('out',{}).get('underruns',0)-before_audio.get('out',{}).get('underruns',0),
 'audio_trace_underruns':after_audio.get('underruns',0)-before_audio.get('underruns',0),'gl_errors':sum(e[7]!=0 for e in events)}
report={'summary':summary,'before_audio':before_audio,'after_audio':after_audio,'before_fmv':before_fmv,'after_fmv':command('fmv_state'),'ring':ring,'frame_perf':command('frame_perf')}
(ROOT/'evidence'/f'{args.name}-av.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))
