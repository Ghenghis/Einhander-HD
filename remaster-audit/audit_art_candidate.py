"""Audit source registration and expose motion sampling limits for art candidates.

The generated previews are synthetic screening aids. They never certify a game
draw, actual motion, HDR, native-4K authoring, or visual quality by themselves.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def motion_sampling(speed, fps, refresh_hz):
    """Nyquist period for a translating periodic screen-space pattern.

    The strict bound is period > 2*speed/fps. The sample-and-hold estimate
    assumes an eye tracking the object and a full refresh display hold.
    """
    if not all(math.isfinite(x) for x in (speed, fps, refresh_hz)) or min(fps, refresh_hz) <= 0 or speed < 0:
        raise ValueError("Use finite speed >= 0 and finite positive frame/refresh rates")
    return {"screen_speed_px_per_second": speed, "game_frames_per_second": fps,
        "display_refresh_hz": refresh_hz, "displacement_px_per_game_frame": speed / fps,
        "period_must_exceed_px_for_temporal_nyquist": 2 * speed / fps,
        "tracking_hold_blur_estimate_px": speed / refresh_hz,
        "assumptions": "Constant translation, periodic screen pattern, sampled once per game frame; full-refresh hold and perfect eye tracking for blur estimate."}


def inspect_pixels(source, candidate):
    source = source.convert("RGBA")
    candidate = candidate.convert("RGBA")
    sw, sh = source.size
    cw, ch = candidate.size
    if cw * sh != ch * sw:
        raise ValueError("Candidate aspect ratio differs from native source")
    if cw % sw or ch % sh or cw < sw or cw // sw != ch // sh:
        raise ValueError("Candidate must have a matching integer native UV scale")
    original_alpha = source.getchannel("A")
    classes = set(original_alpha.getdata())
    if not classes <= {0, 127, 255}:
        raise ValueError("Native source contains unsupported PSX alpha classes")
    expected = original_alpha.resize(candidate.size, Image.Resampling.NEAREST)
    if expected.tobytes() != candidate.getchannel("A").tobytes():
        raise ValueError("Candidate changed categorical PSX transparency/STP footprint")
    rgb = np.asarray(candidate.convert("RGB"), dtype=np.float32) / 255.0
    active = np.asarray(candidate.getchannel("A")) > 0
    values = rgb[active]
    if not values.size:
        raise ValueError("Candidate has no visible source texels")
    luma = values @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    return {"native_dimensions": [sw, sh], "candidate_dimensions": [cw, ch],
        "native_scale": cw // sw, "aspect_registration": "PASS",
        "categorical_class_map_exact": "PASS", "source_alpha_classes": sorted(classes),
        "visible_pixel_luma_percentiles_0_to_1": {str(p): float(np.percentile(luma, p)) for p in (1, 10, 50, 90, 99)},
        "visible_pixel_mean_rgb_0_to_1": values.mean(axis=0).tolist(),
        "qualification": "Pixel statistics describe the candidate; no automatic visual-quality pass threshold is implied."}


def previews(source, candidate, out):
    # Deliberately show RGB, since 127/255 are PSX rendering classes rather than
    # conventional opacity and compositing them would misrepresent the game.
    source = source.convert("RGB")
    candidate = candidate.convert("RGB")
    compare = Image.new("RGB", (1536, 800), (16, 19, 24))
    draw = ImageDraw.Draw(compare)
    for x, image, label in ((0, source, "NATIVE SOURCE / nearest reference"), (768, candidate, "AUTHORED CANDIDATE / RGB only")):
        image.thumbnail((752, 752), Image.Resampling.NEAREST if x == 0 else Image.Resampling.LANCZOS)
        compare.paste(image, (x + 8, 40))
        draw.text((x + 8, 10), label, fill=(235, 235, 235))
    compare.save(out / "source-candidate-review.png")
    # Levels reveal whether details survive minification. They are not actual
    # GPU-generated mipmaps, anisotropic samples, or a native game replay.
    candidate = Image.open(out / "candidate-rgb.png").convert("RGB")
    sheet = Image.new("RGB", (1536, 600), (16, 19, 24))
    draw = ImageDraw.Draw(sheet)
    for i, width in enumerate((512, 256, 128, 64, 32, 16)):
        height = max(1, round(width * candidate.height / candidate.width))
        image = candidate.resize((width, height), Image.Resampling.LANCZOS)
        image.thumbnail((504, 248), Image.Resampling.LANCZOS)
        x = (i % 3) * 512
        y = (i // 3) * 300
        sheet.paste(image, (x + 8, y + 35))
        draw.text((x + 8, y + 10), f"SIMULATED projected width {width} px", fill=(235, 235, 235))
    sheet.save(out / "minification-review.png")
    repeat = candidate.resize((256, 256), Image.Resampling.LANCZOS)
    sheet = Image.new("RGB", (768, 768))
    for y in range(3):
        for x in range(3):
            sheet.paste(repeat, (x * 256, y * 256))
    sheet.save(out / "synthetic-repeat-review.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=60)
    parser.add_argument("--refresh-hz", type=float, default=60)
    parser.add_argument("--screen-speed-px-per-second", type=float, nargs="+", default=[60, 180, 480])
    parser.add_argument("--speed-origin", choices=("assumed-screening", "measured-from-native-replay"), default="assumed-screening")
    parser.add_argument("--motion-evidence", type=Path)
    args = parser.parse_args()
    if args.speed_origin == "measured-from-native-replay" and (not args.motion_evidence or not args.motion_evidence.is_file()):
        raise ValueError("Measured speed requires a persisted native-replay evidence file")
    if args.output.exists():
        raise ValueError("Use a fresh review output directory")
    with Image.open(args.source) as source, Image.open(args.candidate) as candidate:
        report = inspect_pixels(source, candidate)
        cases = [motion_sampling(v, args.fps, args.refresh_hz) for v in args.screen_speed_px_per_second]
        args.output.mkdir(parents=True)
        candidate.convert("RGB").save(args.output / "candidate-rgb.png")
        previews(source.copy(), candidate.copy(), args.output)
    report.update({"at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(args.source.resolve()), "sha256": digest(args.source)},
        "candidate": {"path": str(args.candidate.resolve()), "sha256": digest(args.candidate)},
        "motion_speed_origin": args.speed_origin, "motion_cases": cases,
        "motion_evidence": {"path": str(args.motion_evidence.resolve()), "sha256": digest(args.motion_evidence)} if args.motion_evidence else None,
        "review_required": ["Window/floor registration and partial UV strips", "Palette and sign lettering", "Visible seams at repeated placements", "Actual 3840x2160 native game replay with near/far draws", "Cold/warm frame-time p50/p95/p99 and stutter counts with generation idle", "Controller-driven menu and gameplay regression"],
        "live_game_motion": "NOT RUN", "visual_quality": "REVIEW REQUIRED",
        "native_4k_authored_detail": "NOT ESTABLISHED", "production_installed": False})
    (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit": str(args.output / "audit.json"), "class_map": "PASS", "live_game_motion": "NOT RUN"}))


if __name__ == "__main__":
    main()
