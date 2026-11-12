"""Bounded captures and finite native pad input for the isolated UI candidate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

from launch_ui_candidate import command, load_report

BUTTONS = dict(start=0xFFF7, confirm=0xBFFF, cancel=0xEFFF,
               up=0xFFEF, right=0xFFDF, down=0xFFBF, left=0xFF7F,
               fire=0x7FFF, swap=0xEFFF)


def request(report, cmd, **fields):
    reply = command(report, json.dumps(dict(cmd=cmd, **fields)))
    if reply.get("ok") is not True:
        raise RuntimeError(cmd + ": " + str(reply))
    return reply


def capture(report, label, hires=True):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,55}", label):
        raise ValueError("Use a short lowercase capture label")
    directory = Path(report["evidence"]) / "captures"
    directory.mkdir(exist_ok=True)
    target = directory / (label + ".png")
    internal = directory / (label + "-internal.png")
    if target.exists() or internal.exists() or target.with_suffix(".json").exists():
        raise ValueError("Capture already exists")
    if len(list(directory.glob("*.png"))) >= 180:
        raise ValueError("Capture count budget reached")
    if sum(p.stat().st_size for p in directory.glob("*.png")) > 384*1024*1024:
        raise ValueError("Capture byte budget reached")
    before = request(report, "get_registers").get("frame")
    seq = request(report, "present_shot_seq").get("seq", 0)
    request(report, "present_shot", path=target.as_posix())
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        status = request(report, "present_shot_seq")
        if status.get("seq", 0) > seq:
            if not status.get("wrote") or not target.is_file():
                raise RuntimeError("Composed capture failed")
            break
        time.sleep(.06)
    else:
        raise RuntimeError("Composed capture completion timeout")
    data = target.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Composed capture is not PNG")
    width, height = struct.unpack(">II", data[16:24])
    result = dict(at_utc=datetime.now(timezone.utc).isoformat(), label=label,
                  path=str(target), width=width, height=height,
                  sha256=hashlib.sha256(data).hexdigest(), frame_before=before,
                  frame_after=request(report, "get_registers").get("frame"),
                  scope="Sequential next-present composed frame; not atomic with hires/telemetry")
    if hires:
        result["hires"] = request(report, "screenshot_hires", path=internal.as_posix())
        payload = internal.read_bytes()
        if payload[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Internal capture is not PNG")
        actual = struct.unpack(">II", payload[16:24])
        if actual != (result["hires"]["width"], result["hires"]["height"]):
            raise RuntimeError("Internal PNG dimensions disagree with runtime reply")
        result["hires"]["sha256"] = hashlib.sha256(payload).hexdigest()
    target.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def pulse(report, button, seconds=.12):
    if button not in BUTTONS or not .05 <= seconds <= 2:
        raise ValueError("Use a known button and a 0.05 to 2 second pulse")
    try:
        pressed = request(report, "set_input", buttons=f"0x{BUTTONS[button]:04X}")
        time.sleep(seconds)
    finally:
        released = request(report, "clear_input")
    return dict(button=button, seconds=seconds, pressed=pressed, released=released)


def capture_static(report, label):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,55}", label):
        raise ValueError("Use a short lowercase capture label")
    directory = Path(report["evidence"]) / "captures"
    directory.mkdir(exist_ok=True)
    target = directory / (label + ".png")
    if target.exists() or target.with_suffix(".json").exists():
        raise ValueError("Static capture already exists")
    before = request(report, "get_registers").get("frame")
    result = request(report, "screenshot_hires", path=target.as_posix())
    payload = target.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Static capture is not PNG")
    if struct.unpack(">II", payload[16:24]) != (result["width"], result["height"]):
        raise RuntimeError("Static capture dimensions disagree with runtime")
    result.update(path=str(target), sha256=hashlib.sha256(payload).hexdigest(),
                  at_utc=datetime.now(timezone.utc).isoformat(), frame_before=before,
                  frame_after=request(report, "get_registers").get("frame"),
                  scope="Synchronous GL display-surface readback; no next-present dependency")
    target.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def motion(report, label, seconds):
    if not 2 <= seconds <= 10:
        raise ValueError("Motion evidence must be 2 to 10 seconds")
    output = Path(report["evidence"]) / (label + ".mp4")
    if output.exists():
        raise ValueError("Motion evidence already exists")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Existing FFmpeg is required")
    started = time.monotonic()
    frames = []
    while time.monotonic() - started < seconds:
        captured = capture(report, f"{label}-{len(frames):03d}", hires=False)
        frames.append(dict(path=captured["path"], offset=time.monotonic()-started,
                           sha256=captured["sha256"]))
        time.sleep(.12)
    concat = Path(report["evidence"]) / (label + "-frames.txt")
    lines = []
    for index, frame in enumerate(frames):
        safe_path = Path(frame["path"]).as_posix()
        if "'" in safe_path:
            raise ValueError("Unexpected quote in owned evidence path")
        duration = frames[index+1]["offset"]-frame["offset"] if index+1 < len(frames) else .15
        lines += ["file '"+safe_path+"'", "duration "+str(duration)]
    concat.write_text("\n".join(lines)+"\n", encoding="utf-8")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-safe", "0",
                    "-f", "concat", "-i", str(concat), "-fps_mode", "vfr", "-c:v", "libx264",
                    "-crf", "18", "-pix_fmt", "yuv420p", str(output)], check=True, timeout=45)
    result = dict(path=str(output), duration_seconds=frames[-1]["offset"], frames=frames,
                  scope="Actual composed renderer frames at measured intervals; video has no synthetic/interpolated frames")
    output.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "frames"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--capture")
    parser.add_argument("--static-capture")
    parser.add_argument("--pulse", choices=BUTTONS)
    parser.add_argument("--seconds", type=float, default=.12)
    parser.add_argument("--delay", type=float, default=.3)
    parser.add_argument("--motion", type=float, help="Capture 2 to 10 seconds of actual renderer motion")
    args = parser.parse_args()
    if not 0 <= args.delay <= 4:
        raise ValueError("Delay must be 0 to 4 seconds")
    report = load_report(args.evidence)
    result = {}
    if args.pulse:
        result["input"] = pulse(report, args.pulse, args.seconds)
        time.sleep(args.delay)
    if args.capture:
        result["capture"] = capture(report, args.capture)
    if args.static_capture:
        result["capture"] = capture_static(report, args.static_capture)
    if args.motion:
        result["motion"] = motion(report, "gameplay-motion", args.motion)
    if not result:
        result["gpu"] = request(report, "gpu_state")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
