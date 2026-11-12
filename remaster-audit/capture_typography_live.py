"""Record a bounded fresh frame plus actual replacement submissions for review."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from launch_ui_candidate import load_report, sha, stamp
from ui_candidate_probe import capture, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    args = parser.parse_args()
    report = load_report(args.evidence)
    root = Path(report["evidence"])
    directory = root / ("draws-" + args.label)
    directory.mkdir(exist_ok=False)
    keys = set()
    for path in args.manifest:
        manifest = json.loads(path.read_bytes())
        keys.update(row["key"] for row in manifest.get("files", manifest.get("assets", [])))
    fields = dict(path=directory.as_posix(), max_sources=128, max_records=16000,
                  max_events=16, max_frames=600, max_seconds=15, max_bytes=67108864)
    if keys:
        fields.update(source_policy="include", source_keys=sorted(keys))
    start = request(report, "research_capture", op="start", **fields)
    try:
        time.sleep(.8)
        shot = capture(report, args.label, hires=True)
        stats = request(report, "gpu_ring_stats")
        frames = [request(report, "gpu_frame_dump", frame=stats["newest_frame"]-k, count=8192) for k in (1, 0)]
    finally:
        stop = request(report, "research_capture", op="stop")
        request(report, "clear_input")
    stream = directory / "capture.jsonl"
    rows = [json.loads(line) for line in stream.read_bytes().splitlines() if line.strip()]
    draws = Counter(row.get("key") for row in rows if row.get("event") == "replacement_gl_draw_submitted")
    result = dict(at_utc=stamp(), start=start, stop=stop, capture=shot, gp0_frames=frames,
                  submitted=dict(draws), recorder=dict(path=str(stream), sha256=sha(stream)),
                  quality_review="pending direct image inspection", ram_writes=False, assisted=False)
    output = root / (args.label + "-live.json")
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(path=str(output), submitted=dict(draws), capture=shot["path"])))


if __name__ == "__main__":
    main()
