"""Bounded natural Game Over capture. No RAM writes, holds, or injected damage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from launch_ui_candidate import load_report, stamp
from ui_candidate_probe import capture, request
from ui_native_journey import DisplayTransition, Journey


def teal_mask(pixels):
    a = pixels.astype(np.int16)
    return (a[:, :, 1] > 35) & (a[:, :, 2] > 35) & (a[:, :, 0] * 1.3 < a[:, :, 1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--seconds", type=int, choices=range(10, 181), default=150)
    args = parser.parse_args()
    report = load_report(args.evidence)
    root = Path(report["evidence"])
    output = root / "natural-gameover-bracket.json"
    if output.exists():
        raise ValueError("Use a fresh evidence session for a new attempt")
    reference = Path(__file__).resolve().parent / "dev-center-evidence/hud-4k-candidate-20261112-v5/captures/e2e-respawn-start-followup.png"
    reference_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    if reference_sha != "ae674c8a777df6134626a9307c038124d1e8e553fcde0ab360fd7c7030ad8464":
        raise ValueError("Visually reviewed Game Over reference changed")
    ref = np.asarray(Image.open(reference).convert("RGB").resize((320, 240)))
    ref_mask = teal_mask(ref)
    region = np.zeros((240, 320), dtype=bool)
    region[94:145, 35:285] = True
    ref_mask &= region
    if int(ref_mask.sum()) < 100:
        raise ValueError("Known visually reviewed Game Over reference is unsuitable")
    journey = Journey(report)
    request(report, "clear_input")
    started = time.monotonic()
    last_log = -10.0
    result = dict(at_utc=stamp(), reference=str(reference), reference_sha256=reference_sha, ram_writes=False,
                  assisted=False, input_injected=False, observed=False,
                  visual_confirmation_required=True, elapsed_seconds=0)
    while time.monotonic() - started < args.seconds:
        try:
            a = journey.thumbnail()
        except DisplayTransition:
            time.sleep(.15)
            continue
        mask = teal_mask(a) & region
        dice = float(2 * (mask & ref_mask).sum() / max(1, mask.sum() + ref_mask.sum()))
        outside_black = float((a.max(2)[~region] < 20).mean())
        elapsed = time.monotonic() - started
        if elapsed - last_log >= 10:
            print(json.dumps(dict(elapsed=round(elapsed, 1), dice=round(dice, 3), outside_black=round(outside_black, 3))), flush=True)
            last_log = elapsed
        if dice > .48 and outside_black > .985:
            result.update(observed=True, dice=dice, outside_black=outside_black,
                          capture=capture(report, "natural-gameover-match", hires=False))
            stats = request(report, "gpu_ring_stats")
            result["gpu_stats"] = stats
            result["gp0_frames"] = [request(report, "gpu_frame_dump", frame=stats["newest_frame"]-k, count=8192) for k in (2, 1, 0)]
            display = request(report, "display_ring_stats")
            path = root / "natural-gameover-vram.bin"
            result["display_stats"] = display
            result["vram"] = request(report, "display_ring_aux", frame=display["newest_frame"], path=path.as_posix())
            break
        time.sleep(.15)
    result["elapsed_seconds"] = round(time.monotonic()-started, 3)
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(path=str(output), observed=result["observed"], elapsed_seconds=result["elapsed_seconds"])), flush=True)
    return 0 if result["observed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
