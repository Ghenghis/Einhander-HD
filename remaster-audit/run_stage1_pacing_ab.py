"""Bounded private pack/rewind A/B. No RAM writes or pixel capture during sampling.

GL timer queries are explicit and can be disabled for observer controls.
Coherency-ring samples are lower bounds when the per-query window drops
events. These diagnostic runs are not final recorder-off acceptance.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time

import build_facade_ab_candidates as base
import launch_ui_candidate as ui
from native_ui_facade_route import enter_city
from run_facade_ab_probe import identity, close
import stage_world_candidate as world
import ui_candidate_probe as probe
from gpu_capture_guard import require_quiet_gpu

ROOT = base.ROOT / "remaster-audit/dev-center-evidence/stage1-completion-20261112"
SOURCE = base.OUTPUT / "h24-matched-r3"
LEGS = {"hd-off_rewind-off": (False, False), "hd-on_rewind-off": (True, False),
        "hd-off_rewind-on": (False, True), "hd-on_rewind-on": (True, True)}


def emit(value):
    print(json.dumps(value), flush=True)


def prepare(label,args):
    hd, rewind = LEGS[label]
    directory = ROOT / args.batch / label
    directory.mkdir(parents=True, exist_ok=False)
    source_candidate=getattr(args,'candidate',None) or SOURCE / 'candidate.json'
    report = copy.deepcopy(base.read(source_candidate))
    spec = report["launches"]["candidate"]
    original = Path(spec["arguments"][0])
    assert ui.sha(original) == spec["executable_sha256"]
    selected=original
    if args.runtime:
        build=base.read(args.runtime.resolve())
        selected=Path(build["executable"])
        assert ui.sha(selected)==build["executable_sha256"]
    runtime = directory / "runtime"
    runtime.mkdir()
    executable = runtime / original.name
    ui.copy_verified(selected, executable)
    spec["executable_sha256"]=ui.sha(executable)
    shutil.copytree(original.parent / "cache", runtime / "cache")
    state = directory / "state"
    state.mkdir()
    seed, receipt = world.closed_private_seed()
    ui.copy_verified(seed, state / "card1.mcd")
    settings = (original.parent / "settings.toml").read_text(encoding="utf-8")
    settings, n = re.subn(r"(?m)^hd_textures\s*=.*$", "hd_textures = " + str(hd).lower(), settings)
    assert n == 1
    settings,n=re.subn(r'(?m)^hd_texture_root\s*=.*$',
        'hd_texture_root = '+json.dumps(Path(spec['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT']).as_posix()),settings)
    assert n==1
    for name, value in [("dir",state),("card1",state / "card1.mcd"),("card2",state / "card2.mcd")]:
        settings = re.sub(r"(?m)^" + name + r"\s*=.*$",name+" = "+json.dumps(value.as_posix()),settings)
    (runtime / "settings.toml").write_text(settings,encoding="utf-8")
    spec["arguments"][0] = str(executable)
    for flag, value in [("--debug-port","4376"),("--memcard-dir",str(state)),
                        ("--window-title","Einhander pacing - " + label)]:
        spec["arguments"][spec["arguments"].index(flag)+1] = value
    spec.update(writable_state=str(state),user_cards_mounted=False,
                settings_sha256=ui.sha(runtime / "settings.toml"))
    spec["environment_overrides"].update(EIN_DEBUG_PORT="4376",PSX_REWIND="1" if rewind else "0",
        PSXRECOMP_HD_DUMP="",PSXRECOMP_HD_SOURCE_SIDECARS="",PSXRECOMP_HD_PROOF_LOG="",
        PSXRECOMP_HD_SOURCE_CACHE_KEYS="",
        PSXRECOMP_HD_PROOF_CONTROL="",PSX_GL_PRESENT_PROBE="0",PSX_GL_PERF=str(args.gpu_queries),
        PSXRECOMP_HD_WORLD_SAMPLING=str(args.world_sampling),PSXRECOMP_HD_WORLD_ANISOTROPY="8",
        PSXRECOMP_HD_CPU_PROFILE=str(getattr(args,'cpu_profile',0)),
        PSXRECOMP_HD_FILTER_STATE_CACHE=str(getattr(args,'filter_state_cache',0)),
        PSXRECOMP_HD_OPAQUE_BATCH=str(getattr(args,'opaque_batch',0)),
        PSXRECOMP_HD_SHORT_UPLOAD_PRIORITY=str(getattr(args,'short_upload_priority',0)),
        PSXRECOMP_HD_EMISSIVE=str(getattr(args,'emissive',0)),
        PSXRECOMP_PLAYER_DRAW_TRACKING='0',PSXRECOMP_PLAYER_DRAW_ONLY='0',
        PSXRECOMP_THREAT_DRAW_TRACKING='0',
        PSX_RUNTIME_PERF_DIAG=str(getattr(args,'runtime_perf',0)),PSX_RUNTIME_PERF_DIAG_MS="1000",
        PSX_FPS_TELEMETRY="0",PSX_FRAME_INTERPOLATION="0",
        PSX_OVERLAY_CAPTURES=str(runtime / "overlay_captures.json"))
    report.update(evidence=str(directory),debug_port=4376,variant=label,
        route_reference_profile="hd" if hd else "native-stock",
        private_seed=receipt,pacing_profile=dict(hd_pack_enabled=hd,rewind_enabled=rewind,
        source_sidecars=False,recorder=False,video_capture=False,ram_writes=False,
        timer_assistance=False,gl_present_probe=False,gl_timer_queries=bool(args.gpu_queries),
        world_sampling=bool(args.world_sampling),runtime_build=base.ref(args.runtime.resolve()) if args.runtime else None,
        hd_cpu_profile=bool(getattr(args,'cpu_profile',0)),
        runtime_perf=bool(getattr(args,'runtime_perf',0)),
        filter_state_cache=bool(getattr(args,'filter_state_cache',0)),
        hd_opaque_batch=bool(getattr(args,'opaque_batch',0)),
        short_upload_priority=bool(getattr(args,'short_upload_priority',0)),
        emissive_masks=bool(getattr(args,'emissive',0)),
        guest_frame_target=args.guest_frames,
        telemetry_interval_seconds=1.0,route_poll_seconds=1.0,supersampling=9))
    if getattr(args,'native_menus',False):
        if not hd:raise ValueError('Native-menu staging requires HD-on measurement')
        control=directory/'replacement-control.txt';control.write_text('0\n')
        spec['environment_overrides']['PSXRECOMP_HD_PROOF_CONTROL']=str(control)
        report['route_reference_profile']='native-stock';report['pacing_profile']['native_menus']=True
    base.write(directory / "candidate.json",report)
    return report


def launch(report):
    directory = Path(report["evidence"])
    assert not (directory / "launch-candidate.json").exists()
    base.write(directory/'gpu-ready.json',require_quiet_gpu())
    for port in range(4373,4379):
        try:
            with socket.create_connection(("127.0.0.1",port),timeout=.2):
                raise RuntimeError("Experiment port occupied: " + str(port))
        except OSError:
            pass
    spec=report["launches"]["candidate"]
    with (directory / "stdout.log").open("xb") as out, (directory / "stderr.log").open("xb") as err:
        process=subprocess.Popen(spec["arguments"],cwd=spec["cwd"],
            env=ui.launch_environment(spec["environment_overrides"]),stdout=out,stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW)
    base.write(directory / "launch-candidate.json",dict(pid=process.pid,
        executable=spec["arguments"][0],debug_port=4376,at_utc=ui.stamp()))
    ui.PORT=4376
    try:
        ready_started=time.monotonic()
        deadline=ready_started+60
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('Owned runtime exited during startup: '+str(process.returncode))
            try:
                with socket.create_connection(("127.0.0.1",4376),timeout=.2):break
            except OSError:time.sleep(.2)
        else:raise TimeoutError('Owned runtime did not open its debug listener within60 seconds')
        base.write(directory/'launch-ready.json',dict(pid=process.pid,debug_port=4376,
            listener_ready_seconds=time.monotonic()-ready_started,at_utc=ui.stamp()))
        # CIM identity checks can take longer than the title's idle timeout.
        # Perform them before watching boot, so callers can act on the observed
        # title immediately instead of finding the native attract sequence.
        identity(report)
        import observe_native_boot as boot
        sys.argv=[boot.__file__,"--evidence",str(directory),"--label","pacing-boot"]
        assert boot.main()==0,"Native boot gate failed"
    except BaseException:
        cleanup=dict(pid=process.pid,owned_popen_handle=True,reason='Boot/identity gate failed',force_terminated=False)
        if process.poll() is None:
            process.terminate();cleanup['force_terminated']=True
        try:cleanup['exit_code']=process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();cleanup['exit_code']=process.wait(timeout=5)
        base.write(directory/'launch-failure-cleanup.json',cleanup)
        raise
    return process


def run(label,args):
    seconds=args.seconds
    report=prepare(label,args)
    directory=Path(report["evidence"])
    proof=dict(started_at_utc=ui.stamp(),profile=report["pacing_profile"],
        candidate=base.ref(directory / "candidate.json"),samples=[],errors=[],ram_writes=False,
        state_loads=False,survival_assistance=False,ordinary_fire_input=True)
    ui.copy_verified(Path(__file__),directory / "executed-pacing.py")
    process=None
    try:
        process=launch(report)
        proof["native_route"]=enter_city(report, poll_seconds=1)
        if report['pacing_profile'].get('native_menus'):
            control=directory/'replacement-control.txt';assert control.read_text().strip()=='0'
            control.write_text('1\n');proof['pack_enabled_after_native_menus']=dict(at_utc=ui.stamp(),new_menu_art_accepted=False)
        proof["turbo_off"]=probe.request(report,"turbo",enabled=0)
        proof["turbo_state"]=probe.request(report,"turbo_state")
        assert proof["turbo_state"]["enabled"]==0
        proof["fire_input"]=probe.request(report,"set_input",buttons="0x7FFF")
        emit(dict(leg=label,city=True,sampling_seconds=seconds))
        start=time.monotonic()
        next_sample=start
        for index in range(seconds+1):
            time.sleep(max(0,next_sample-time.monotonic()))
            sample=dict(index=index,started_monotonic=time.monotonic())
            for cmd, fields in [("get_registers",{}),("audio_stats",{}),
                                ("gl_present_ring",{"n":120}),("gl_coh_ring",{"n":2048}),
                                ("frame_perf",{})]:
                before=time.monotonic()
                sample[cmd]=ui.command(report,json.dumps(dict(cmd=cmd,**fields)))
                sample[cmd+"_request_ms"]=(time.monotonic()-before)*1000
            if getattr(args,'cpu_profile',0):sample['hd_cpu_profile']=probe.request(report,'hd_cpu_profile')
            sample["ended_monotonic"]=time.monotonic()
            proof["samples"].append(sample)
            if index%15==0:
                emit(dict(leg=label,index=index,frame=sample["get_registers"].get("frame"),
                    audio=sample["audio_stats"].get("out"),frame_perf=sample["frame_perf"].get("all")))
            next_sample=start+index+1
            if args.guest_frames and sample["get_registers"]["frame"]-proof["samples"][0]["get_registers"]["frame"]>=args.guest_frames:
                break
        if args.guest_frames:
            assert proof["samples"][-1]["get_registers"]["frame"]-proof["samples"][0]["get_registers"]["frame"]>=args.guest_frames,"Guest-frame target not reached within time limit"
        first,last=proof["samples"][0],proof["samples"][-1]
        dt=last["started_monotonic"]-first["started_monotonic"]
        proof["guest_fps"]=(last["get_registers"]["frame"]-first["get_registers"]["frame"])/dt
        proof["five_second_windows"]=[dict(start_index=a["index"],end_index=b["index"],
            fps=(b["get_registers"]["frame"]-a["get_registers"]["frame"])/(b["started_monotonic"]-a["started_monotonic"]))
            for a,b in zip(proof["samples"][::5],proof["samples"][5::5])]
    except Exception as error:
        proof["errors"].append(str(error))
    finally:
        if (directory/'launch-failure-cleanup.json').exists():
            proof['launch_failure_cleanup']=base.read(directory/'launch-failure-cleanup.json')
        elif (directory / "launch-candidate.json").exists():
            try:proof["close"]=close(report)
            except Exception as error:proof["errors"].append("Close: "+str(error))
        if process is not None:
            try:proof['owned_process_exit']=process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate();proof['owned_process_forced_cleanup']=True
                proof['owned_process_exit']=process.wait(timeout=5)
        commands=[json.loads(p.read_bytes()) for p in (directory / "commands").glob("*.json")]
        assert not any(p["request"]["cmd"] in ["write_ram","load_state"] for p in commands)
        proof["ended_at_utc"]=ui.stamp()
        base.write(directory / "pacing-proof.json",proof)
        emit(dict(leg=label,guest_fps=proof.get("guest_fps"),errors=proof["errors"],close=proof.get("close")))
    if proof["errors"] or not proof.get("close",{}).get("port_closed"):
        raise SystemExit(1)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leg",choices=list(LEGS)+["all"],default="all")
    parser.add_argument("--seconds",type=int,choices=[30,60,90,180],default=60)
    parser.add_argument("--batch",required=True)
    parser.add_argument("--runtime",type=Path,help="Verified private build.json; installed runtime is untouched")
    parser.add_argument("--candidate",type=Path,help="Private pinned artwork candidate.json")
    parser.add_argument("--gpu-queries",type=int,choices=[0,1],default=1)
    parser.add_argument("--world-sampling",type=int,choices=[0,1],default=0)
    parser.add_argument("--cpu-profile",type=int,choices=[0,1],default=0,
        help="Opt-in CPU attribution without GPU timer queries; requires a supporting private runtime")
    parser.add_argument("--opaque-batch",type=int,choices=[0,1],default=0,
        help="Private opt-in adjacent opaque HD triangle batching; requires a supporting runtime")
    parser.add_argument('--emissive',type=int,choices=[0,1],default=0,
        help='Optional authored window masks; same private candidate can be compared on/off')
    parser.add_argument('--native-menus',action='store_true')
    parser.add_argument("--guest-frames",type=int,choices=[900,1800],default=0)
    args=parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",args.batch):parser.error("batch must be a single directory name")
    for label in LEGS if args.leg=="all" else [args.leg]:
        run(label,args)
