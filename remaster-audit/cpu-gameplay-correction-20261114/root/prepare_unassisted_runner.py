"""Create a separately reviewable runner; preserve the historical assisted runner."""
from pathlib import Path
import hashlib

root = Path('C:/github/Einhander')
old = root / 'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v58-frame-phases/run_frame_phases.py'
target = root / 'remaster-audit/run_stage1_unassisted_review.py'
source = old.read_text(encoding='utf-8')

def replace(before, after):
    global source
    if source.count(before) != 1:
        raise ValueError('Historical source changed: ' + before[:70])
    source = source.replace(before, after)

replace('the disclosed 180-second timer-only aid.', 'optional, explicitly selected timer assistance (off by default).')
replace("kind='assisted assembled-world fly-past'", "kind='bounded stock/OpenGL gameplay review'")
replace('timer_only_assistance=True,lease_seconds=180', 'timer_only_assistance=bool(args.timer_assist),lease_seconds=180 if args.timer_assist else 0')
replace("    # The generic pacing preparation starts with unassisted metadata. This\n    # runner always starts SurvivalAid; disclose its timer writes in both profiles.\n    report['pacing_profile'].update(ram_writes=True,timer_assistance=True)",
        "    report['pacing_profile'].update(ram_writes=bool(args.timer_assist),timer_assistance=bool(args.timer_assist))")
replace("Path(__file__).parent/'audio-evidence/process-loopback/build/process_loopback_capture.exe'", "Path(__file__).parent/'dev-center-evidence/stage1-completion-20261112/sampling-build-v58-frame-phases/audio-evidence/process-loopback/build/process_loopback_capture.exe'")
replace('        process=pacing.launch(report)', '        process=fenced_launch(report)')
replace('        aid=SurvivalAid(report,owned_identity,ui.command,ui.stamp)', "        if report['visual_profile']['timer_only_assistance']:\n            aid=SurvivalAid(report,owned_identity,ui.command,ui.stamp)")
replace("composed_stills=report['visual_profile'].get('composed_stills',True),timer_assistance=True)", "composed_stills=report['visual_profile'].get('composed_stills',True),\n            timer_assistance=report['visual_profile']['timer_only_assistance'])")
replace("if request.get('addr')!='0x80085718' or request.get('val')!='0xA5':forbidden.append(request)", "if (not report['visual_profile']['timer_only_assistance'] or\n                    request.get('addr')!='0x80085718' or request.get('val')!='0xA5'):forbidden.append(request)")
replace("    p.add_argument('--batch',required=True)", "    p.add_argument('--batch',required=True)\n    p.add_argument('--timer-assist',action='store_true',help='Explicit diagnostic timer RAM writes; default is unassisted')")
replace("default=9,help='Private render preference; normal user setting is2, visual baseline9'", "default=2,help='Private render preference; default2 limits resource use'")
replace("p.add_argument('--telemetry-only',action='store_true',help='Same disclosed timer-assisted route without video, source collection or measurement screenshots')", "p.add_argument('--telemetry-only',action='store_true',default=True,help='Default light measurement: no video/source capture/screenshots')\n    p.add_argument('--record-evidence',dest='telemetry_only',action='store_false',help='Separate explicitly requested source/image recording; not recorder-off timing')")
replace("choices=[120,150,170],default=170", "choices=[30,60,120,150,170],default=60")
replace("def run(args):", '''def validate_review_policy(report, hold, permission, now):
    """Reject before GPU launch. Tokens and broker state never enter receipts."""
    import datetime
    if not isinstance(hold, dict) or hold.get('schema') != 'einhander-user-gpu-hold-v1':
        raise ValueError('A current user resource instruction is required')
    deadline = datetime.datetime.fromisoformat(hold['reserved_until_utc'].replace('Z', '+00:00'))
    if deadline.tzinfo is None or now.tzinfo is None or now < deadline:
        raise ValueError('User GPU reservation is still active or has an invalid time')
    if permission.get('allowed') is not True:
        raise ValueError('A fresh shared GPU grant is required')
    visual = report['visual_profile']
    assisted = visual.get('timer_only_assistance')
    if type(assisted) is not bool:
        raise ValueError('Assistance must be explicitly declared')
    for key in ('ram_writes', 'timer_assistance'):
        if report['pacing_profile'].get(key) is not assisted:
            raise ValueError('Assistance metadata disagrees')
    seconds = visual.get('capture_seconds')
    if type(seconds) is not int or seconds not in (30, 60, 120, 150, 170):
        raise ValueError('Unbounded measurement rejected')
    if report.get('production_installed') is not False:
        raise ValueError('Private runtime required')
    return dict(allowed=True, assistance=assisted, measurement_seconds=seconds)


def fenced_launch(report):
    import datetime, os
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/coordination'))
    import shared_gpu_guard as guard
    import psutil
    directory = Path(report['evidence'])
    hold_path = Path(__file__).resolve().parent / 'runtime-review/gpu-texture-remix-20261114/user-cpu-only-hold-20261114T173705Z.json'
    hold = json.loads(hold_path.read_bytes())
    token = os.environ.get('EINHANDER_SHARED_GPU_TOKEN', '')
    decision = validate_review_policy(report, hold, guard.current_permission(token),
        datetime.datetime.now(datetime.timezone.utc))
    spec = report['launches']['candidate']
    executable = Path(spec['arguments'][0]).resolve()
    if not executable.is_relative_to(directory.resolve() / 'runtime'):
        raise ValueError('Executable is outside the private runtime')
    if ui.sha(executable) != spec['executable_sha256']:
        raise ValueError('Prepared executable changed')
    if ui.sha(executable.parent / 'settings.toml') != spec['settings_sha256']:
        raise ValueError('Prepared settings changed')
    for row in report['files']:
        if ui.sha(row['composed_path']) != row['sha256']:
            raise ValueError('Prepared texture changed: ' + row['name'])
    load = psutil.cpu_percent(interval=1)
    free = psutil.virtual_memory().available / 2**30
    if load >= 60 or free < 16:
        raise RuntimeError('Resource gate refused the launch')
    decision.update(cpu_percent=load, free_gib=free,
        shared_check=guard.broker_action('check', token, directory))
    me = psutil.Process()
    decision['registration'] = guard.broker_action('start', token, directory,
        pid=me.pid, command=' '.join(me.cmdline()),
        created_utc=datetime.datetime.fromtimestamp(me.create_time(), datetime.timezone.utc).isoformat())
    pacing.base.write(directory / 'shared-gameplay-permission.json', decision)
    # This grant is never implicitly released. The coordinator must verify the
    # registered runner and its child are absent before explicit release.
    return pacing.launch(report)


def run(args):''')
with target.open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(source)
print({'old_sha256': hashlib.sha256(old.read_bytes()).hexdigest(),
       'new_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
       'game_launched': False})
