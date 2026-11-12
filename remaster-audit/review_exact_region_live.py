"""Review finalized v9 draw admission without controlling or polling a game.

Pass explicit native STOP receipts after the root recorder has stopped. Source
queries, PNG presence, GL submissions, screenshot context, and human visual
acceptance remain separate evidence levels. This never grants release approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zlib

from PIL import Image

import launch_ui_candidate as ui


ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "remaster-audit/dev-center-evidence/hud-world-region-candidate-20261112-v9"
SUBMITTED = "replacement_gl_draw_submitted"
QUERIED = "source_draw_query_matched"
VISUAL_CHECKS = {
    "results": ("contours", "seams", "transparency", "modulation", "composition", "markings"),
    "gameover": ("contours", "counters", "tone", "glow", "rotation", "transparency"),
    "font": ("contours", "stroke_continuity", "counters", "readability", "no_clipping"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            value.update(chunk)
    return value.hexdigest()


def ref(path):
    return dict(path=str(Path(path).resolve()), sha256=digest(path))


def resolve(path, evidence):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (evidence / path).resolve()


def stop_body(document):
    if isinstance(document.get("reply"), dict):
        document = document["reply"]
    require(document.get("ok") is True and document.get("op") == "stop" and document.get("active") is False,
            "A successful explicit native STOP receipt with active=false is required; active captures are never read")
    require(isinstance(document.get("path"), str) and isinstance(document.get("start_frame"), int) and isinstance(document.get("frame"), int),
            "STOP receipt lacks capture path or native frame bounds")
    require(document["start_frame"] <= document["frame"], "STOP receipt frame bounds are reversed")
    return document


def finalized_stream(stop_path, evidence):
    document = stop_body(load(stop_path))
    directory = Path(document["path"]).resolve()
    require(directory.is_relative_to(evidence) and directory != evidence, "Finalized capture must belong to this candidate evidence directory")
    path = directory / "capture.jsonl"
    before = path.stat()
    require(before.st_size <= 256*1024*1024, "Capture JSONL exceeds this review's 256MiB bound")
    payload = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and len(payload) == before.st_size,
            "Finalized capture changed during its one-shot read; stop the writer before reviewing")
    lines = [line for line in payload.splitlines() if line.strip()]
    rows = [json.loads(line) for line in lines]
    require(rows and rows[0].get("event") == "capture_start" and rows[0].get("contract") == "ein-research-v1",
            "Native capture start record is missing or unsupported")
    require(rows[0].get("frame") == document["start_frame"], "STOP receipt belongs to another capture activation")
    for row in rows:
        if isinstance(row.get("frame"), int):
            require(document["start_frame"] <= row["frame"] <= document["frame"], "Capture row lies outside its finalized STOP frame bounds")
    for row in rows:
        row["_capture"] = str(directory)
    return rows, dict(stop_receipt=ref(stop_path), capture=dict(path=str(path), sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)),
                      start_frame=document["start_frame"], stop_frame=document["frame"],
                      jsonl_records=len(rows), stop_record_count=document.get("counts", {}).get("records"),
                      counters=document.get("counts"), caps=document.get("caps"), sampling=document.get("sampling"),
                      coverage=document.get("coverage"), full_replay=document.get("full_replay", False),
                      stopped=True, actively_polled=False)


def local_source_rect(event):
    """Convert a logged upload query to logical source pixels, without guessing ownership."""
    try:
        depth = int(event["depth"])
        ppw = 4 >> depth
        u0, v0, u1, v1 = event["uv_bounds"]
        sx, sy = event["source_word_xy"]
        if depth not in (0, 1, 2) or u0 > u1 or v0 > v1:
            return None
        x = sx*ppw + u0 % ppw
        return [x, sy, x+u1-u0+1, sy+v1-v0+1]
    except (KeyError, TypeError, ValueError):
        return None


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def qualify_submission(event, target):
    if event.get("event") != SUBMITTED or event.get("key") != target["key"]:
        return False, "not_actual_submission"
    if event.get("replacement_size") != target["dimensions"]:
        return False, "replacement_dimensions_differ"
    if target["kind"] in ("results", "gameover"):
        x, y, w, h = target["source_rect"]
        if event.get("source_kind") != "exact_region" or event.get("native_words") != [w, h] or event.get("depth") != target["depth"]:
            return False, "not_expected_exact_region_source"
        try:
            u0, v0, u1, v1 = event["uv_bounds"]
            px, py = event["page_xy"]
            sx, sy = event["source_word_xy"]
            ppw = 4 >> target["depth"]
            inferred = [px+u0//ppw-sx, py+v0-sy]
            if u0 > u1 or v0 > v1 or inferred != [x, y]:
                return False, "source_origin_or_wrapping_differs"
            if not (x <= px+u0//ppw <= px+u1//ppw < x+w and y <= py+v0 <= py+v1 < y+h):
                return False, "query_outside_manifested_source"
        except (KeyError, TypeError, ValueError):
            return False, "incomplete_source_geometry"
    elif target["kind"] == "font":
        if event.get("native_words") != target["native_words"] or event.get("depth") != target["depth"]:
            return False, "font_native_source_layout_differs"
        rect = local_source_rect(event)
        if rect is None or not any(overlaps(rect, selected) for selected in target["authored_regions"]):
            return False, "draw_does_not_touch_authored_font_region"
    return True, "actual_gl_submission_with_expected_artifact_and_source_geometry"


def targets_from_candidate(report, evidence):
    composition = load(evidence / "exact-region-composition.json")
    selected = {row["name"].removesuffix(".png"): row for row in report["files"]}
    targets = []
    for plan in composition["regions"]:
        key = plan["key"]
        row = selected[key]
        require(row["sha256"] == plan["sha256"] and row["dimensions"] == plan["dimensions"], "Region selection differs from pinned composition")
        x, y, w, h = plan["source_rect"]
        raw = (evidence / "pack" / (key+".words.bin")).read_bytes()
        valid = (evidence / "pack" / (key+".valid.bin")).read_bytes()
        clut = (evidence / "pack" / (key+".clut.bin")).read_bytes()
        require(len(raw) == w*h*2 and valid == bytes([1])*(w*h) and not clut and f"{zlib.crc32(raw):08X}-00000000" == key,
                "Prepared direct-color region source proof differs")
        targets.append(dict(kind=plan["kind"], key=key, source_rect=plan["source_rect"], depth=plan["depth"],
                            dimensions=row["dimensions"], png=dict(path=row["composed_path"], sha256=row["sha256"]),
                            origin=row["origin"], source_proof_crc_verified=True))
    font_dir = Path(report["exact_region_policy"]["font_directory"])
    font = load(font_dir / "manifest.json")
    require(len(font["files"]) == 11, "Expected eleven corrected font outputs")
    for source in font["files"]:
        key = source["key"]
        row = selected[key]
        require(row["sha256"] == source["sha256"] and Path(row["path"]).resolve() == Path(source["path"]).resolve(), "Final font selection is not the corrected v3 output")
        metadata = next(ref for ref in source["source_proof"] if ref["path"].endswith(".source.json"))
        native = load(metadata["path"])
        targets.append(dict(kind="font", key=key, depth=native["depth"], native_words=[native["width_words"], native["height"]],
                            authored_regions=source["selected_native_regions"], dimensions=row["dimensions"],
                            png=dict(path=row["composed_path"], sha256=row["sha256"]), origin=row["origin"],
                            parent_native_row=source.get("parent_native_row")))
    world_keys = set(report["world_integration_experiment"]["added_keys"])
    require(len(world_keys) == 140, "Expected the separately tracked 140 processing-only world additions")
    for key in sorted(world_keys):
        row = selected[key]
        targets.append(dict(kind="world_processing", key=key, dimensions=row["dimensions"],
                            png=dict(path=row["composed_path"], sha256=row["sha256"]), origin=row["origin"],
                            semantic_ownership_verified=False, authored_detail_accepted=False))
    require(len({target["key"] for target in targets}) == len(targets) == 157, "Region/font/world target keys overlap or counts differ")
    for target in targets:
        info = target["png"]
        require(digest(info["path"]) == info["sha256"], "Final target PNG hash changed: " + target["key"])
        with Image.open(info["path"]) as image:
            image.load()
            require(image.format == "PNG" and list(image.size) == target["dimensions"], "Final target PNG decode/dimensions differ")
    return targets


def capture_receipt(path, evidence):
    path = resolve(path, evidence)
    row = load(path)
    image_path = resolve(row["path"], evidence)
    require(digest(image_path) == row["sha256"], "Composed screenshot hash differs")
    with Image.open(image_path) as image:
        image.load()
        require(image.format == "PNG" and image.size == (row["width"], row["height"]), "Composed screenshot dimensions differ")
    before, after = row.get("frame_before"), row.get("frame_after")
    require(isinstance(before, int) and isinstance(after, int) and before <= after, "Screenshot requires native before/after frame bounds")
    return dict(receipt=ref(path), image=ref(image_path), frame_before=before, frame_after=after,
                dimensions=[row["width"], row["height"]], label=row.get("label"), scope=row.get("scope"),
                atomic_with_draw_events=False)


def context_for_capture(capture, events, gap=120):
    eligible = [row for row in events if row["frame"] <= capture["frame_after"]]
    prior = [row for row in eligible if row["frame"] <= capture["frame_before"]]
    nearest = max(eligible, key=lambda row: row["frame"]) if eligible else None
    return dict(submission_observed_before_or_during_capture=bool(eligible),
                actual_submission_before_capture_readiness=bool(prior),
                first_submission_precedes_fresh_capture=bool(prior),
                nearest_submission_frame=nearest["frame"] if nearest else None,
                nearest_gap_frames=capture["frame_after"]-nearest["frame"] if nearest else None,
                recent_submission_context=bool(nearest and capture["frame_after"]-nearest["frame"] <= gap),
                exact_event_within_capture_bracket=any(capture["frame_before"] <= row["frame"] <= capture["frame_after"] for row in eligible),
                visibility_proven_by_event=False)


def self_test():
    target = dict(key="ABCDEF12-00000000", kind="results", dimensions=[1024, 3584], source_rect=[448, 256, 64, 224], depth=2)
    event = dict(event=SUBMITTED, key=target["key"], replacement_size=target["dimensions"], source_kind="exact_region", native_words=[64, 224],
                 depth=2, uv_bounds=[192, 0, 255, 223], page_xy=[256, 256], source_word_xy=[0, 0], frame=100)
    require(qualify_submission(event, target)[0], "Self-test rejected explicit region UV origin")
    require(not qualify_submission(dict(event, event=QUERIED), target)[0], "A source query was counted as a GL submission")
    require(not qualify_submission(dict(event, source_kind="native_page"), target)[0], "A native page was counted as exact-region admission")
    require(not qualify_submission(dict(event, replacement_size=[4096, 4096]), target)[0], "Wrong PNG dimensions were accepted")
    require(not qualify_submission(dict(event, source_word_xy=[1, 0]), target)[0], "Wrong source origin was accepted")
    context = context_for_capture(dict(frame_before=90, frame_after=92), [event])
    require(not context["actual_submission_before_capture_readiness"], "A later submission accepted a premature capture")
    try:
        stop_body(dict(ok=True, op="status", active=True, path="unused", start_frame=1, frame=2))
    except ValueError:
        pass
    else:
        raise ValueError("Active capture gate was bypassed")
    return dict(checks=7, failures=0, game_actions=0, native_stream_reads=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT)
    parser.add_argument("--stop-receipt", action="append", type=Path, default=[], help="Final explicit native stop reply; repeat for multiple completed streams")
    parser.add_argument("--capture-receipt", action="append", type=Path, default=[], help="Composed screenshot JSON receipt; repeat as needed")
    parser.add_argument("--visual-review", type=Path, help="Optional reviewer-authored screenshot/sequence observations; no acceptance is inferred from filenames")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return 0
    require(args.stop_receipt, "Supply explicit STOP receipts after recording is finalized; no live stream will be read")
    evidence = args.evidence.resolve()
    output = args.output.resolve() if args.output else evidence / "exact-region-live-review-v1.json"
    require(output.is_relative_to(ROOT / "remaster-audit") and not output.exists(), "Use a new review output inside remaster-audit")
    report = ui.load_report(evidence)
    launch_path = evidence / "launch-candidate.json"
    launch = load(launch_path)
    require(launch["mode"] == "candidate" and launch["executable_sha256"] == report["runtime_override"]["sha256"] and
            Path(launch["arguments"][0]).resolve() == Path(report["launches"]["candidate"]["arguments"][0]).resolve() and
            Path(launch["environment_overrides"]["PSXRECOMP_HD_TEXTURE_ROOT"]).resolve() == evidence / "pack",
            "Launch receipt does not identify this final candidate executable and pack")
    require(digest(launch["arguments"][0]) == launch["executable_sha256"], "Launched candidate executable changed")
    require(launch["settings_sha256"] == report["launches"]["candidate"]["settings_sha256"] ==
            digest(Path(launch["arguments"][0]).parent / "settings.toml"), "Launched candidate settings changed")
    ui.verify_provenance(report)
    # STOP gates are checked before reading any stream content. No sleeps or polls.
    stops = [resolve(path, evidence) for path in args.stop_receipt]
    for path in stops:
        stop_body(load(path))
    events, streams = [], []
    for path in stops:
        rows, info = finalized_stream(path, evidence)
        events.extend(rows)
        streams.append(info)
    targets = targets_from_candidate(report, evidence)
    by_key = {target["key"]: target for target in targets}
    visual_path = resolve(args.visual_review, evidence) if args.visual_review else None
    ledger = load(visual_path) if visual_path else {}
    review_entries = ledger.get("screenshots", [])
    capture_paths = {str(resolve(path, evidence)) for path in args.capture_receipt}
    capture_paths.update(str(resolve(entry["receipt"], evidence)) for entry in review_entries)
    for sequence in ledger.get("sequences", []):
        capture_paths.update(str(resolve(phase["receipt"], evidence)) for phase in sequence.get("phases", []))
    captures = {path: capture_receipt(path, evidence) for path in sorted(capture_paths)}
    qualified = {}
    target_rows = []
    for target in targets:
        key = target["key"]
        related = [row for row in events if row.get("key") == key]
        valid, invalid = [], []
        for row in related:
            if row.get("event") != SUBMITTED:
                continue
            ok, reason = qualify_submission(row, target)
            (valid if ok else invalid).append(row if ok else dict(frame=row.get("frame"), reason=reason, event=row))
        qualified[key] = valid
        contexts = {path: context_for_capture(capture, valid) for path, capture in captures.items()}
        manual = []
        for entry in review_entries:
            if key not in entry.get("keys", []):
                continue
            path = str(resolve(entry["receipt"], evidence))
            checks = entry.get("checks", {})
            required = VISUAL_CHECKS.get(target["kind"], ())
            complete = bool(required) and all(checks.get(name) is True for name in required)
            explicit = bool(entry.get("reviewer") and entry.get("observed_state") and entry.get("observation"))
            manual.append(dict(reviewer=entry.get("reviewer"), observed_state=entry.get("observed_state"), observation=entry.get("observation"),
                               screenshot_receipt=path, checks=checks, required_checks=list(required),
                               declared_visual_acceptance=entry.get("visual_accepted") is True,
                               explicit_observation_complete=explicit, required_checks_complete=complete,
                               recent_submission_context=contexts[path]["recent_submission_context"],
                               accepted_scene_observation=bool(entry.get("visual_accepted") is True and explicit and complete and contexts[path]["recent_submission_context"]),
                               remaining=entry.get("remaining", [])))
        target_rows.append(dict(target, sampled_source_queries=sum(row.get("event") == QUERIED for row in related),
                               sampled_gl_submissions=len(valid), rejected_submission_evidence=invalid,
                               first_submission_frame=min((row["frame"] for row in valid), default=None),
                               last_submission_frame=max((row["frame"] for row in valid), default=None),
                               submission_example=valid[0] if valid else None,
                               screenshot_contexts=contexts, manual_scene_observations=manual,
                               technical_admission_observed=bool(valid),
                               scene_visually_accepted=any(row["accepted_scene_observation"] for row in manual),
                               semantic_component_count=None, component_live_verified=False))
    sequences = []
    for sequence in ledger.get("sequences", []):
        phases = []
        for phase in sequence.get("phases", []):
            path = str(resolve(phase["receipt"], evidence))
            capture = captures[path]
            keys = sequence.get("keys", [])
            phases.append(dict(phase=phase["phase"], receipt=path, frame=capture["frame_before"], image_sha256=capture["image"]["sha256"],
                               all_keys_have_recent_submissions=bool(keys) and all(key in qualified and context_for_capture(capture, qualified[key])["recent_submission_context"] for key in keys)))
        expected = sequence.get("required_phases", ["fade_in", "hold", "fade_out"] if sequence.get("kind") == "gameover" else [])
        names = [phase["phase"] for phase in phases]
        ordered = bool(phases) and all(a["frame"] < b["frame"] for a, b in zip(phases, phases[1:]))
        coverage = bool(expected) and all(name in names for name in expected)
        motion = sequence.get("motion_evidence")
        motion_verified = False
        if motion:
            path = resolve(motion["path"], evidence)
            require(digest(path) == motion["sha256"], "Motion evidence hash changed")
            motion_verified = path.stat().st_size > 0
        explicit = bool(sequence.get("reviewer") and sequence.get("observation"))
        accepted = bool(sequence.get("visual_accepted") is True and sequence.get("complete_sequence_observed") is True and explicit and
                        ordered and coverage and len({phase["image_sha256"] for phase in phases}) > 1 and
                        all(phase["all_keys_have_recent_submissions"] for phase in phases) and motion_verified)
        sequences.append(dict(name=sequence.get("name"), kind=sequence.get("kind"), keys=sequence.get("keys", []), phases=phases,
                              required_phases=expected, required_phase_coverage=coverage, frames_strictly_ordered=ordered,
                              reviewer=sequence.get("reviewer"), observation=sequence.get("observation"),
                              complete_sequence_declared=sequence.get("complete_sequence_observed") is True,
                              motion_file_hash_verified=motion_verified, complete_motion_visual_acceptance=accepted,
                              qualification="Ordered stills alone do not establish every fade/animation frame"))
    regions = [row for row in target_rows if row["kind"] in ("results", "gameover")]
    font = [row for row in target_rows if row["kind"] == "font"]
    world = [row for row in target_rows if row["kind"] == "world_processing"]
    summary = dict(exact_region_keys=6, exact_region_keys_with_actual_gl_submissions=sum(row["technical_admission_observed"] for row in regions),
                   results_strips_submitted=sum(row["technical_admission_observed"] for row in regions if row["kind"] == "results"),
                   gameover_region_submitted=any(row["technical_admission_observed"] for row in regions if row["kind"] == "gameover"),
                   corrected_font_keys=11, corrected_font_keys_with_authored_region_submissions=sum(row["technical_admission_observed"] for row in font),
                   processing_only_world_keys=140, processing_only_world_keys_submitted=sum(row["technical_admission_observed"] for row in world),
                   world_semantic_components_verified=0, finalized_native_streams=len(streams), screenshots_checked=len(captures),
                   accepted_scene_observations=sum(row["scene_visually_accepted"] for row in regions+font),
                   complete_gameover_fade_accepted=any(row["kind"] == "gameover" and row["complete_motion_visual_acceptance"] for row in sequences),
                   source_queries_are_visibility_proof=False, gl_submissions_are_visibility_proof=False,
                   final_build_accepted=False, release_ready=False)
    result = dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  report_kind="finalized_run_admission_review", summary=summary, candidate_receipt=ref(evidence/"candidate.json"),
                  launch_receipt=ref(launch_path), streams=streams, screenshot_evidence=list(captures.values()),
                  exact_regions=regions, corrected_font_paths=font, world_processing_submissions=world, sequence_reviews=sequences,
                  visual_review_input=ref(visual_path) if visual_path else None, helper=ref(Path(__file__)),
                  limitations=["Native evidence is sampled activation-forward; absent rows do not prove absence of rendering.",
                               "A source query, PNG presence, decode readiness or GL submission does not establish visibility, wording fidelity or semantic ownership.",
                               "Screenshot/draw frame brackets are sequential, not atomic; human visual observations remain explicit and separately gated.",
                               "The 140 world entries are technical processing additions, never counts of accepted buildings, ships, signs or animation states.",
                               "Full-game routes, variants, complete animation loops and representative pacing remain separate release gates."],
                  active_stream_reads=0, game_actions=0, production_accepted=False)
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), **summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
