"""Offline, hash-bound review ledger for the final isolated v9 replay.

New capture bytes remain unreviewed until independently inspected and entered
in REVIEWS. State evidence, actual replacement submissions, bounded quality,
and whole-game acceptance remain separate. This script never contacts a game.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
V9 = ROOT / "remaster-audit/dev-center-evidence/hud-world-region-candidate-20261112-v9"

# SHA256 of inspected composed image bytes -> independent observations.
# Do not populate from a filename, an input command, another candidate, or an
# automatic similarity score. Edits to PNGs invalidate the corresponding note.
REVIEWS = {}

ADDITIONAL_EXCLUSIONS = [
    dict(path=str(ROOT/"remaster-audit/menu-restoration/description-continuity-candidate-v1"),
         reason="Stale mutable ownership-map reference; superseded without visual acceptance."),
    dict(path=str(ROOT/"remaster-audit/menu-restoration/description-continuity-candidate-v2"),
         reason="v8 settled glyph gaps and 943 erased native ink centers; rejected and superseded by v3."),
    dict(path=str(ROOT.parent/"REMASTER_STAGING/full-remaster/exact-region-build-20261112-v3"),
         reason="Independent review found P2 partial-region cache/coherence defect; resolved only in selected runtime v4."),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reference(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), sha256=sha(data), bytes=len(data))


def event_summary(row):
    return {k:row[k] for k in ("stream","line","event","key","frame","source_kind","native_words",
        "depth","semi","page_xy","clut_xy","source_word_xy","uv_bounds","xy","replacement_size",
        "not_visibility_proof") if k in row}


def main():
    candidate_path = V9 / "candidate.json"
    candidate = json.loads(candidate_path.read_text())
    files = {r["name"][:-4]:r for r in candidate["files"]}
    region_keys = set(candidate["exact_region_policy"]["copied_region_keys"])
    rows=[]
    snapshots=[]
    for path in sorted(V9.glob("native-*/capture.jsonl")):
        raw = path.read_bytes()
        lines=raw.splitlines()
        partial=0
        for number,line in enumerate(lines,1):
            try:
                row=json.loads(line)
            except json.JSONDecodeError:
                if number==len(lines) and not raw.endswith(b"\n"):
                    partial+=1
                    continue
                raise
            row.update(stream=str(path),line=number)
            rows.append(row)
        snapshots.append(dict(path=str(path),sha256=sha(raw),bytes=len(raw),partial_trailing_lines_ignored=partial))
    rows.sort(key=lambda r:(r.get("frame",0),r["stream"],r["line"]))
    draws=[r for r in rows if r.get("event")=="replacement_gl_draw_submitted"]
    integrity=[]
    checked={}
    for key in sorted({r["key"] for r in draws}):
        if key not in files:
            integrity.append(dict(kind="submitted_key_missing_candidate",key=key))
            continue
        selected=files[key]
        path=Path(selected["composed_path"])
        info=reference(path)
        with path.open("rb") as handle:
            header=handle.read(24)
        size=list(struct.unpack(">II",header[16:24]))
        if info["sha256"]!=selected["sha256"] or size!=selected["dimensions"]:
            integrity.append(dict(kind="candidate_png_changed",key=key))
        submitted={tuple(r["replacement_size"]) for r in draws if r["key"]==key}
        if submitted!={tuple(size)}:
            integrity.append(dict(kind="submitted_dimensions_differ",key=key,submitted=sorted(submitted),expected=size))
        checked[key]=dict(**info,dimensions=size,origin=selected.get("origin"),
            first_observed_submission=min(r["frame"] for r in draws if r["key"]==key),
            last_observed_submission=max(r["frame"] for r in draws if r["key"]==key))
    captures=[]
    for path in sorted((V9/"captures").glob("*.json")):
        receipt=json.loads(path.read_text())
        image=reference(receipt["path"])
        if image["sha256"]!=receipt["sha256"]:
            integrity.append(dict(kind="capture_hash_changed",path=receipt["path"]))
        lo,hi=receipt["frame_before"],receipt["frame_after"]
        exact=[r for r in draws if lo<=r["frame"]<=hi]
        before=[r for r in draws if lo-120<=r["frame"]<lo]
        visual=REVIEWS.get(image["sha256"],dict(review_status="UNREVIEWED",actual_state=None,
            functional_state_evidence="not_evaluated",bounded_art_quality="not_evaluated",
            observation="New image bytes need independent visual inspection. Filename is not state proof."))
        capture=dict(label=receipt.get("label"),image=image,receipt=reference(path),frames=[lo,hi],
            visual_review=visual,exact_submissions=[event_summary(r) for r in exact],
            sampled_prior_120_frames=[event_summary(r) for r in before],
            source_admission_scope="Sampled submissions in/near sequential composed-frame bracket; no automatic visibility or quality acceptance.")
        if receipt.get("hires"):
            internal=receipt["hires"]
            info=reference(internal["path"])
            if info["sha256"]!=internal["sha256"]:
                integrity.append(dict(kind="internal_capture_changed",path=internal["path"]))
            capture["internal_capture"]=dict(**info,dimensions=[internal["width"],internal["height"]],
                scope="Sequential internal-surface capture; not atomic with composed frame bracket. Internal pixels require their own visual inspection.")
        captures.append(capture)
    admissions={}
    for key in sorted(region_keys):
        submitted=[r for r in draws if r["key"]==key]
        admissions[key]=dict(actual_submissions=len(submitted),source_kinds=sorted({r.get("source_kind","") for r in submitted}),
            first=event_summary(submitted[0]) if submitted else None,last=event_summary(submitted[-1]) if submitted else None,
            selected_png=checked.get(key),quality_acceptance="not_inferred_from_submission")
    launch=V9/"launch-candidate.json"
    seed=V9/"private-card-seed.json"
    result=dict(schema_version=1,generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="independent_visual_review_in_progress",candidate=reference(candidate_path),
        reviewer_script=reference(Path(__file__)),recorder_snapshots=snapshots,
        integrity_status="PASS" if not integrity else "FAIL",integrity_failures=integrity,
        counts=dict(captures=len(captures),reviewed=sum(r["visual_review"]["review_status"]!="UNREVIEWED" for r in captures),
            unreviewed=sum(r["visual_review"]["review_status"]=="UNREVIEWED" for r in captures),
            gl_submissions=len(draws),submitted_candidate_keys=len(checked),
            observed_states=dict(Counter(r["visual_review"].get("actual_state") or "unreviewed" for r in captures))),
        private_profile=dict(seed_receipt=reference(seed),launch_receipt=reference(launch) if launch.exists() else None,
            scope="Separate seeded private card is preparation evidence. Native PILOT recognition/load requires an actually observed v9 state; earlier candidates confer no pass."),
        captures=captures,exact_region_admissions=admissions,submitted_png_integrity=checked,
        excluded_experiments=candidate["exact_region_policy"]["excluded_experiments"]+ADDITIONAL_EXCLUSIONS,
        whole_scope=dict(final_full_ui_coverage_accepted=False,full_game_coverage_accepted=False,
            visual_acceptance_transferred_from_v6_or_v8=False,
            remaining=["Every changed description/specification glyph, descender/counter/contour and required palette/state.",
                "Actual Game Over region admission, original hollow geometry and complete natural fade/re-entry.",
                "All five current Results regions, whole aircraft/markings, strip seams, graph modes and transitions.",
                "Native private profile load, save/discard-cancel/restart, Configuration and distinct Ranking states.",
                "Every gameplay component/location/variant/animation and final-build pacing."]),
        limitations=["Visual observations are hash-bound to independently inspected v9 image bytes.",
            "State visibility, source CRC/region admission, bounded artwork judgment and final coverage are separate gates.",
            "Sampled activation-forward recorder streams may omit individual draws. Absence of a sample alone does not prove absence of rendering.",
            "No game commands, runtime modifications or pack modifications are performed by this review."])
    output=V9/"visual-review.json"
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(output=reference(output),integrity=result["integrity_status"],counts=result["counts"])))
    return 1 if integrity else 0


if __name__=="__main__":
    raise SystemExit(main())
