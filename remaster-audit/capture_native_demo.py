"""Observe the game's native attract/demo without gameplay input or RAM cheats."""
import argparse,json,time
from stage1_session import ROOT,command,screenshot
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=180);args=parser.parse_args()
if not 1<=args.seconds<=900:raise ValueError('Capture must be bounded to 1..900 seconds')
command('clear_input');started=time.monotonic();rows=[]
try:
 while (elapsed:=time.monotonic()-started)<args.seconds:
  rows.append({'elapsed':elapsed,'frame':command('get_registers')['frame'],
    'capture':screenshot(f'native-demo-{int(elapsed):04d}'),'pad':command('pad_status'),
    'source_count':len(list((ROOT/'stock/einhander-texture-replacements').glob('*.source.json')))})
  (ROOT/'evidence/native-demo-capture.json').write_text(json.dumps({'input_policy':'No injected gameplay input or RAM writes; native attract mode only','samples':rows},indent=2)+'\n')
  print(json.dumps({'elapsed':elapsed,'frame':rows[-1]['frame'],'sources':rows[-1]['source_count']}),flush=True)
  time.sleep(10)
finally:command('clear_input')
