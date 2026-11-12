"""Observe native boot; skip only an actually decoding movie, never blind Start."""
import argparse
import json
from pathlib import Path
import re
import time

from launch_ui_candidate import load_report, stamp
from ui_candidate_probe import request, pulse
from ui_native_journey import DisplayTransition, Journey, title_scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--label", default="native-boot")
    args = parser.parse_args()
    report = load_report(args.evidence)
    journey = Journey(report)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,35}", args.label):
        raise ValueError("Use a short lowercase boot label")
    output = Path(report["evidence"]) / (args.label+"-observation.json")
    if output.exists():
        raise ValueError("This boot attempt already has evidence")
    result = dict(started_at_utc=stamp(), ram_writes=False, observed_title=False,
                  movie_skip=None, observations=[], errors=[])
    deadline = time.monotonic()+60
    previous_count = None
    try:
        while time.monotonic() < deadline:
            try:
                a = journey.thumbnail()
            except DisplayTransition:
                time.sleep(.2)
                continue
            cyan, white = title_scores(a)
            movie = request(report, "fmv_state")
            count = movie.get("mdec_decode_count", 0)
            result["observations"].append(dict(frame=request(report, "get_registers")["frame"],
                                                cyan=cyan, white=white, mdec_decode_count=count))
            if cyan > 400 and white > 130:
                result["observed_title"] = True
                result["title_capture"] = journey.shot(args.label+"-title-observed")
                break
            if result["movie_skip"] is None and previous_count is not None and count > previous_count:
                result["movie_skip"] = dict(reason="Observed active MDEC decode count increase", before=previous_count,
                                              after=count, input=pulse(report, "start", .15))
            previous_count = count
            time.sleep(.2)
    except Exception as error:
        result["errors"].append(str(error))
    finally:
        request(report, "clear_input")
        result["ended_at_utc"] = stamp()
        output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(dict(path=str(output), title_observed=result["observed_title"], errors=result["errors"])))
    return 0 if result["observed_title"] and not result["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
