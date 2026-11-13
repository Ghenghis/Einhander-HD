"""Private normal-speed H24 pass; ordinary movement, no firing, timer aid disclosed."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

import build_facade_ab_candidates as builder
import launch_ui_candidate as ui
import ui_candidate_probe as probe
from native_ui_facade_route import enter_city
from run_facade_ab_probe import identity, close
from run_h24_facade_review import SurvivalAid

VARIANT = "h24-fullpass-r2"
DIRECTORY = builder.OUTPUT / VARIANT


def emit(data):
    print(json.dumps(data), flush=True)


def prepare():
    old = builder.read(builder.OUTPUT / "h24-v2-4096-r1/candidate.json")
    builder.SIZE = 4096
    builder.VARIANTS = {VARIANT: 4375}
    emit(builder.prepare(VARIANT, old["authoring_input"]["local"]["path"],
                         old["source_manifest"]["path"]))
    report = builder.read(DIRECTORY / "candidate.json")
    report["launches"]["candidate"]["environment_overrides"]["PSX_REWIND"] = "0"
    report["test_scope"] = dict(authored_rooms=24, no_fire=True,
        movement="ordinary down-left pulse to reduce player obstruction",
        survival_assistance="timer only, 180s lease", normal_speed=True)
    builder.write(DIRECTORY / "candidate.json", report)
    emit(builder.check(report))


def run():
    report = builder.read(DIRECTORY / "candidate.json")
    if (DIRECTORY / "fullpass-proof.json").exists() or (DIRECTORY / "launch-candidate.json").exists():
        raise ValueError("Fresh private run required")
    builder.SIZE = 4096
    builder.VARIANTS = {VARIANT: 4375}
    ui.PORT = report["debug_port"]
    proof = dict(started_at_utc=ui.stamp(), candidate=builder.ref(DIRECTORY / "candidate.json"),
                 ordinary_fire_input=False, state_loads=False, approach_fast_forward=False,
                 live_visual_accepted=False, errors=[], target_draws=[], progress=[])
    ui.copy_verified(Path(__file__), DIRECTORY / "executed-fullpass.py")
    proof["helper"] = builder.ref(DIRECTORY / "executed-fullpass.py")
    aid = None
    recorder = None
    started = False
    try:
        proof["launch"] = builder.launch(report)
        identity(report)
        if not proof["launch"]["native_title_observed"]:
            raise RuntimeError("Native title not observed")
        proof["native_route"] = enter_city(report)
        emit(dict(native_city=True))
        aid = SurvivalAid(report, identity, ui.command, ui.stamp)
        proof["turbo_off"] = probe.request(report, "turbo", enabled=0)
        proof["turbo_state"] = probe.request(report, "turbo_state")
        assert proof["turbo_state"]["enabled"] == 0
        native = DIRECTORY / "native-fullpass"
        native.mkdir()
        proof["research_start"] = probe.request(report, "research_capture", op="start", path=native.as_posix(),
            max_sources=224, max_records=20000, max_events=3, max_frames=16000,
            max_seconds=180, max_bytes=67108864, source_policy="all")
        started = True
        proof["park_input"] = probe.request(report, "set_input", buttons="0xFF3F")
        time.sleep(1.2)
        proof["park_release"] = probe.request(report, "clear_input")
        start = time.monotonic()
        cursor = 0
        tail = ""
        last_target_time = None
        exit_edge_seen = False
        next_progress = 0
        while time.monotonic() - start < 140:
            elapsed = time.monotonic() - start
            if recorder is None and elapsed >= 20:
                output = DIRECTORY / "fullpass-original.mp4"
                arguments = report["launches"]["candidate"]["arguments"]
                title = arguments[arguments.index("--window-title") + 1]
                command = [shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-n",
                    "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0", "-i", "title=" + title,
                    "-t", "115", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
                proof["video"] = dict(path=str(output), command=command, started_at_utc=ui.stamp(),
                    game_frame_before=probe.request(report, "get_registers").get("frame"),
                    scope="Actual 30Hz window recording, normal game speed, no interpolation or retiming")
                recorder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                emit(dict(recording=True, elapsed=round(elapsed)))
            journal = native / "capture.jsonl"
            if journal.exists():
                with journal.open(encoding="utf-8") as stream:
                    stream.seek(cursor)
                    data = tail + stream.read()
                    cursor = stream.tell()
                lines = data.split("\n")
                tail = lines.pop()
                for line in lines:
                    if builder.KEY not in line or '"replacement_gl_draw_submitted"' not in line:
                        continue
                    row = json.loads(line)
                    if row.get("replacement_size") != [4096, 4096]:
                        continue
                    proof["target_draws"].append(dict(row, observed_elapsed_seconds=round(elapsed, 3)))
                    last_target_time = time.monotonic()
                    if max(x[0] for x in row.get("xy", [[999, 999]])) < 5:
                        exit_edge_seen = True
            if elapsed >= next_progress:
                state = probe.request(report, "get_registers")
                status = dict(elapsed_seconds=round(elapsed), frame=state.get("frame"),
                    target_samples=len(proof["target_draws"]), exit_edge_seen=exit_edge_seen)
                proof["progress"].append(status)
                emit(status)
                next_progress += 15
            if recorder is not None and recorder.poll() is not None:
                break
            if exit_edge_seen and last_target_time is not None and time.monotonic() - last_target_time > 10:
                proof["exit_followed_by_10s_without_target_sample"] = True
                break
            time.sleep(.25)
        proof["target_draw_observed"] = bool(proof["target_draws"])
    except Exception as error:
        proof["errors"].append(str(error))
    finally:
        if recorder is not None:
            try:
                _, err = recorder.communicate(input=b"q\n" if recorder.poll() is None else None, timeout=25)
                proof["video"].update(exit=recorder.returncode, stderr=err.decode(errors="replace")[-2000:], ended_at_utc=ui.stamp())
            except Exception as error:
                proof["errors"].append("Video finalization: " + str(error))
        worker_stopped = True
        if aid is not None:
            try:
                proof["survival_assistance"] = aid.stop()
            except Exception as error:
                worker_stopped = False
                proof["errors"].append("Survival helper: " + str(error))
        if started:
            try:
                proof["final_input_release"] = probe.request(report, "clear_input")
                proof["final_turbo_state"] = probe.request(report, "turbo_state")
                proof["research_stop"] = probe.request(report, "research_capture", op="stop")
            except Exception as error:
                proof["errors"].append("Research finalization: " + str(error))
        if (DIRECTORY / "launch-candidate.json").exists() and worker_stopped:
            try:
                proof["close"] = close(report)
            except Exception as error:
                proof["errors"].append("Close: " + str(error))
        proof["ended_at_utc"] = ui.stamp()
        builder.write(DIRECTORY / "fullpass-proof.json", proof)
        emit(dict(completed=True, target_samples=len(proof["target_draws"]), errors=proof["errors"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else run()
