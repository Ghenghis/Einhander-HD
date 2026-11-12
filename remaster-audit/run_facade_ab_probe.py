"""One immutable variant, finite native entry, observed exact-region proof.

Stills are 2880x2160; optional video records the actual 1280x960 window.
No injected RAM, stage jumps, state loads, asset rewrites or matched-state claim.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import build_facade_ab_candidates as builder
import launch_ui_candidate as ui
import ui_candidate_probe as probe
from native_ui_facade_route import enter_city

ROOTS = (builder.OUTPUT, builder.OUTPUT.parent / "facade-tonal-ab-20261112")


def emit(value):
    print(json.dumps(value), flush=True)


def identity(report):
    """The launch receipt and real Windows process must agree before input."""
    directory = Path(report["evidence"])
    launch = json.loads((directory / "launch-candidate.json").read_bytes())
    pid = int(launch["pid"])
    query = ("Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(pid) +
             "' | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
                            check=True, capture_output=True, text=True, timeout=15)
    row = json.loads(result.stdout)
    expected = Path(report["launches"]["candidate"]["arguments"][0]).resolve()
    assert row["ProcessId"] == pid and Path(row["ExecutablePath"]).resolve() == expected
    assert expected.is_relative_to(directory.resolve())
    return launch


def close(report):
    launch = identity(report)
    result = dict(pid=launch["pid"], clear_input=ui.command(report, json.dumps(dict(cmd="clear_input"))))
    # Runtime may acknowledge late; retain its actual reply and observe closure.
    result["quit_reply"] = ui.command(report, json.dumps(dict(cmd="quit")))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", report["debug_port"]), timeout=.2):
                pass
        except OSError:
            result["port_closed"] = True
            return result
        time.sleep(.2)
    result["port_closed"] = False
    return result


def motion(report, seconds=6, label="facade-window-motion"):
    directory = Path(report["evidence"])
    output = directory / (label + ".mp4")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or output.exists():
        return dict(ok=False, reason="Existing FFmpeg required and output must be new")
    args = report["launches"]["candidate"]["arguments"]
    title = args[args.index("--window-title") + 1]
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-f", "gdigrab",
               "-framerate", "60", "-draw_mouse", "0", "-i", "title=" + title,
               "-t", str(seconds), "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "18", "-pix_fmt", "yuv420p", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    return dict(ok=result.returncode == 0, path=str(output), exit=result.returncode,
                stderr=result.stderr[-1200:], capture_arguments=command,
                scope="Actual window capture at requested60Hz; no interpolated frames; capture load affects pacing;2160 stills separate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--close-only", action="store_true")
    parser.add_argument("--adopt-launched", action="store_true",
                        help="Explicitly continue this report's verified private process")
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--fire", action="store_true", help="Hold the ordinary fire button during this bounded visual test")
    parser.add_argument("--route-turbo", action="store_true", help="Fast-forward approach only; restore normal speed before evidence")
    parser.add_argument("--follow-seconds", type=int, choices=(0, 30, 60, 90), default=0,
                        help="Continue normal fly-past with additional2160p observations")
    args = parser.parse_args()
    directory = args.evidence.resolve()
    assert any(directory.parent == p.resolve() for p in ROOTS)
    report = builder.read(directory / "candidate.json")
    assert directory == Path(report["evidence"]).resolve()
    assert report["debug_port"] in range(4373, 4379)
    ui.PORT = report["debug_port"]
    if args.close_only:
        emit(close(report))
        return
    output = directory / "live-facade-proof.json"
    if output.exists():
        raise ValueError("This native comparison already has a result")
    # Refuse before entering cleanup: an older run is not ours to close.
    launch_marker = directory / "launch-candidate.json"
    had_launch = launch_marker.exists()
    if had_launch and not args.adopt_launched:
        raise ValueError("Fresh variant required; existing launch left untouched")
    if args.adopt_launched:
        if not had_launch:
            raise ValueError("No recorded launch to adopt")
        # Adoption is explicit and limited to this exact private process.
        identity(report)
        if report["launches"]["candidate"]["user_cards_mounted"]:
            raise ValueError("Only private test state can be adopted")
    executed = directory / "executed-probe.py"
    if executed.exists():
        raise ValueError("Executed probe snapshot already exists")
    ui.copy_verified(Path(__file__), executed)
    proof = dict(started_at_utc=ui.stamp(), candidate=builder.ref(directory / "candidate.json"),
        helper=builder.ref(executed), ram_writes=False, state_loads=False,
        approach_fast_forward=args.route_turbo,
        matched_state_comparison=False, live_visual_accepted=False, errors=[], shots=[])
    proof["ordinary_fire_input"] = args.fire
    builder.OUTPUT = directory.parent
    builder.VARIANTS = {str(p): p for p in range(4373, 4379)}
    expected_dimensions = report["registration"]["runtime_dimensions"]
    if expected_dimensions not in ([64,64], [1024,1024], [2048,2048], [4096,4096]):
        raise ValueError("Unsupported registered comparison dimensions")
    builder.SIZE = expected_dimensions[0]
    started = False
    may_close = args.adopt_launched
    try:
        if args.adopt_launched:
            builder.check(report)
            proof["launch"] = dict(adopted_existing_private_launch=builder.ref(launch_marker))
        else:
            proof["launch"] = builder.launch(report)
            may_close = True
        identity(report)
        if not args.adopt_launched and not proof["launch"]["native_title_observed"]:
            raise RuntimeError("Native title gate failed; input stopped")
        proof["native_route"] = enter_city(report)
        emit(dict(native_city_route=proof["native_route"]["evidence"], ok=True))
        native = directory / "native-facade-fly-past"
        native.mkdir(exist_ok=False)
        proof["record_start"] = probe.request(report, "research_capture", op="start", path=native.as_posix(),
            max_sources=224, max_records=20000, max_events=3, max_frames=16000,
            max_seconds=240, max_bytes=67108864, source_policy="all")
        started = True
        if args.fire:
            proof["fire_input_start"] = probe.request(report, "set_input", buttons="0x7FFF")
        if args.route_turbo:
            proof["approach_turbo_start"] = probe.request(report, "turbo", enabled=1)
        start = time.monotonic()
        cursor = 0
        tail = ""
        next_progress = 30
        while time.monotonic() - start < 230:
            capture = native / "capture.jsonl"
            if capture.exists():
                with capture.open(encoding="utf-8") as stream:
                    stream.seek(cursor)
                    text = tail + stream.read()
                    cursor = stream.tell()
                split = text.split("\n")
                tail = split.pop()
                targets = [json.loads(line) for line in split
                           if builder.KEY in line and '"replacement_gl_draw_submitted"' in line]
                targets = [row for row in targets if row.get("source_kind") == "exact_region"
                           and row.get("replacement_size") == expected_dimensions]
                if targets:
                    proof["first_target_draws"] = targets
                    proof["evidence_turbo_off"] = probe.request(report, "turbo", enabled=0)
                    proof["evidence_turbo_state"] = probe.request(report, "turbo_state")
                    if proof["evidence_turbo_state"].get("enabled") != 0:
                        raise RuntimeError("Normal-speed evidence gate failed")
                    time.sleep(1)
                    emit(dict(target_draw=targets[0]))
                    proof["shots"].append(probe.capture_static(report, "observed-facade-0"))
                    if args.video:
                        proof["motion"] = motion(report)
                        emit(proof["motion"])
                    time.sleep(.4)
                    proof["shots"].append(probe.capture_static(report, "observed-facade-1"))
                    proof["target_draw_observed"] = True
                    follow_start = time.monotonic()
                    for delay in range(30, args.follow_seconds + 1, 30):
                        time.sleep(max(0, follow_start + delay - time.monotonic()))
                        shot = probe.capture_static(report, "follow-facade-" + str(delay))
                        proof["shots"].append(shot)
                        emit(dict(normal_speed_follow_seconds=delay, capture=shot))
                    if args.video and args.follow_seconds:
                        proof["later_motion"] = motion(report, label="facade-later-window-motion")
                        emit(proof["later_motion"])
                    break
            elapsed = time.monotonic() - start
            if elapsed >= next_progress:
                emit(dict(waiting_for_exact_facade=True, elapsed_seconds=round(elapsed),
                          frame=probe.request(report, "get_registers").get("frame")))
                next_progress += 30
            time.sleep(.3)
        else:
            proof["target_draw_observed"] = False
            proof["errors"].append("Exact facade not observed during bounded native route")
    except Exception as error:
        proof["errors"].append(str(error))
    finally:
        if started:
            try:
                proof["final_input_release"] = probe.request(report, "clear_input")
                proof["final_turbo_off"] = probe.request(report, "turbo", enabled=0)
                proof["record_stop"] = probe.request(report, "research_capture", op="stop")
            except Exception as error:
                proof["errors"].append("Recorder stop: " + str(error))
        # Marker was absent before this invocation; only a new owned launch
        # can enter this path. identity() checks its exact PID and executable.
        if may_close or (not had_launch and launch_marker.exists()):
            try:
                proof["close"] = close(report)
            except Exception as error:
                proof["errors"].append("Owned-process close: " + str(error))
        proof["ended_at_utc"] = ui.stamp()
        builder.write(output, proof)
        emit(dict(path=str(output), target_draw_observed=proof.get("target_draw_observed", False),
                  shots=len(proof["shots"]), errors=proof["errors"], close=proof.get("close")))


if __name__ == "__main__":
    main()
