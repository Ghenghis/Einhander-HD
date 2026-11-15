from pathlib import Path
import datetime,hashlib,importlib.util,json,socket,sys,time,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;sys.path.insert(0,str(r/'remaster-audit'))
import launch_ui_candidate as ui,ui_candidate_probe as probe
from native_ui_facade_route import enter_city
from run_facade_ab_probe import close
spec=importlib.util.spec_from_file_location('pacing_own_cache',n/'pacing-own-cache.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
p=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/v61-live-census-r1/hd-off_rewind-off';d=json.loads((p/'candidate.json').read_bytes());assert not (p/'launch-candidate.json').exists()
assert hashlib.sha256(Path(d['launches']['candidate']['arguments'][0]).read_bytes()).hexdigest()=='c6e573f317e5faaa624612320c5468ed8e0158092b4e53e3a0357e607e325686'
proof={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_sha256':hashlib.sha256((p/'candidate.json').read_bytes()).hexdigest(),'samples':[],'errors':[],'ram_writes':False,'state_loads':False,'foreign_cache_staged':False,'game_executed':True,'gpu_used':'RTX3090Ti intended; actual renderer identity retained in runtime logs'}
process=None
def save():(p/'census-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
try:
 process=mod.launch(d);proof['pid']=process.pid;save();print(json.dumps({'launched':True,'pid':process.pid}),flush=True)
 proof['initial_census']=probe.request(d,'pgxp_view',census=1,reset=1,recent=0)
 proof['native_route']=enter_city(d,timeout_per_state=30,poll_seconds=.5)
 proof['turbo_off']=probe.request(d,'turbo',enabled=0);proof['geometry']=probe.request(d,'geom_correction');proof['texture']=probe.request(d,'texture_correction')
 proof['fire_input']=probe.request(d,'set_input',buttons='0x7FFF');proof['city_census_reset']=probe.request(d,'pgxp_view',reset=1,recent=0)
 start=time.monotonic()
 for i in range(7):
  time.sleep(max(0,start+i*5-time.monotonic()))
  if (p/'STOP').exists():raise RuntimeError('User/root stop marker')
  row={'seconds':round(time.monotonic()-start,3),'registers':probe.request(d,'get_registers'),'census':probe.request(d,'pgxp_view',recent=4),'audio':probe.request(d,'audio_stats')}
  proof['samples'].append(row);save();print(json.dumps({'sample':i,'frame':row['registers'].get('frame'),'triangles':row['census'].get('triangles')}),flush=True)
 proof['final_phase']=probe.request(d,'frame_phase_ring',n=2048)
 proof['capture']=probe.capture(d,'v61-census-city',hires=False)
except BaseException as ex:proof['errors'].append(repr(ex));print(json.dumps({'error':repr(ex)}),flush=True)
finally:
 if process is not None:
  try:proof['disarm']=probe.request(d,'pgxp_view',census=0,recent=0)
  except Exception as ex:proof['errors'].append('Disarm '+str(ex))
  try:proof['close']=close(d)
  except Exception as ex:proof['errors'].append('Close '+str(ex))
  try:proof['owned_process_exit']=process.wait(timeout=5)
  except Exception:
   process.terminate();proof['forced_cleanup']=True;proof['owned_process_exit']=process.wait(timeout=5)
 proof['pid_gone']=process is not None and not psutil.pid_exists(process.pid)
 proof['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print(json.dumps({'done':True,'errors':proof['errors'],'pid_gone':proof['pid_gone'],'exit':proof.get('owned_process_exit')}),flush=True)
raise SystemExit(0 if not proof['errors'] and proof.get('close',{}).get('port_closed') else 1)
