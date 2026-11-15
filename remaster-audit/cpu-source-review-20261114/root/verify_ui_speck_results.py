"""Verify small measure-only receipts and previously viewed sheets, without decoding source atlases."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
pins=[]
def require(ok,why):
    if not ok:raise RuntimeError(why)
def pin(path,want=None):
    raw=Path(path).read_bytes();got=hashlib.sha256(raw).hexdigest()
    require(want is None or want==got,'pin changed '+str(path))
    pins.append(dict(path=str(path),sha256=got,bytes=len(raw)));return raw
pin(U/'tools/ui_speck_measure_r3.py','f00af9d6f59735ff6440deea95e2dbddfc89dac14e6ef8a76e78107ffb509114')
receipt=json.loads(pin(U/'receipts/J-S1r3-20261114T192817Z.json','e0028441c8dcc26b29123c5431ef43dcd03646e9aa96e7a16f0c7c83e5fdf6e9'))
base=U/'speck-measure/20261114T192819Z'
result=json.loads(pin(base/'result.json','0514702e3a484b092273e2df3a9d395fb5f3ec48814c6cd625659b183e3aed33'))
require(receipt['outer_exit']==0 and not receipt['killed'] and receipt['python_processes_left']==0,'execution/cleanup')
require(receipt['affinity_mask']=='2000' and receipt['preflight']['cpu_pct']<60 and receipt['preflight']['free_gib']>=16,'CPU gate')
require(len(result['rows'])==3 and len(result['selftest'])==7 and all(result['selftest'].values()),'case counts')
want={'1AD90FC9-02491337.png':(27448,12622,2924,14),
    '1AD90FC9-79902A90.png':(27448,10671,2844,14),
    '1AD90FC9-4315989E.png':(8249,8672,2220,28)}
rows=[]
for row in result['rows']:
    m=row['snap_native'];expected=want[row['key']]
    require(tuple(m[k] for k in ('rgba_hole_px','dark_visible_px','dark_components','enclosed_hole_components'))==expected,'metric differs')
    pin(base/row['review']['path'],row['review']['sha256'])
    rows.append(dict(key=row['key'],bright_native_cell_scope_texels=row['scope_texels'],
        authored=row['authored'],snap_native=m,crop_texels=row['review']['crop_texels'],
        sheet_actually_viewed_by_root=True,body_text_scope_accepted=False))
# The original launcher reports absence; this check only verifies its two PIDs are currently absent,
# without a root recheck of their exact creation times (the receipt's creation field is locale-formatted).
present=[pid for pid in (receipt['cmd_pid'],receipt['python_pid']) if psutil.pid_exists(pid)]
out=N/'ui-speck-independent-readback-r1';out.mkdir(exist_ok=False)
data=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=True,sources=pins,rows=rows,
    root_viewed_review_images=3,source_atlases_decoded_by_root=0,
    old_rgb_only_inference='withdrawn; counts alone do not establish visible text-dot cause',
    alpha_cause_claim='unproven: two crops are an eye emblem and one is a coarse logo; native edges/counters included',
    quality_decision='unresolved; no color-only fill or alpha repair accepted',
    resource_enforcement='polled working-set cap; NOT a Windows Job commit cap',
    whole_job_memory_qualification=False,measured_peak_working_set_mib=receipt['peak_ws_mib'],
    actual_elapsed_s=receipt['wall_s'],reported_processes_left=0,
    root_current_pid_presence=present,root_creation_identity_replayed=False,
    native_class_replay_repeated=False,repair_executed=False,gpu_run=False,game_run=False,installed=False,
    next='fixed manually reviewed body-text ROI plus protected contour/counter semantics; new source/CPU grant needed')
(out/'result.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in data.items() if k not in ('sources','rows')}))
