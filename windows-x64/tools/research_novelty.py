"""Measure source novelty in finalized recorder bundles without contacting the game.

Keys identify original upload bytes and palettes, never actors. A complete source
must pass its validity mask, FNV checks and both key CRCs before it can satisfy a
collection target. Existing bundles are never changed. Example:

python -B tools/research_novelty.py --run RUN_A --run RUN_B --baseline RUN_A

--output creates a new report exclusively; omit it for stdout only. The target
list is an offline capture plan, not an unsupported native key-filter command.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zlib

KEY = re.compile(r"[0-9A-F]{8}-[0-9A-F]{8}\Z")
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
MAX_RUNS = 128
MAX_FILES = 5000
MAX_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            result.update(block)
    return result.hexdigest()


def fnv(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def confined(directory, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Recorded path must be relative")
    unresolved = directory / relative
    path = unresolved.resolve()
    if not path.is_relative_to(directory.resolve()) or unresolved.is_symlink():
        raise ValueError("Recorded path escapes its run or is a symlink")
    return path


def load_run(runs_root, identity):
    """Validate a finalized bundle, then return its source and draw observations."""
    if not RUN_ID.fullmatch(identity):
        raise ValueError("Invalid run ID")
    directory = confined(Path(runs_root).resolve(), identity)
    manifest_path = directory / "manifest.json"
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest exceeds bounded input size")
    manifest_sha = sha256(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("id") != identity or manifest.get("status") != "finalized":
        raise ValueError("Only matching finalized run manifests are accepted")
    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Missing or oversized manifest file list")
    tracked = set()
    byte_count = 0
    for item in files:
        relative = item["path"]
        if relative in tracked or relative == "manifest.json":
            raise ValueError("Duplicate or self-referencing manifest entry")
        path = confined(directory, relative)
        size = item["bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= MAX_BYTES:
            raise ValueError("Invalid recorded byte count")
        byte_count += size
        if byte_count > MAX_BYTES:
            raise ValueError("Run exceeds bounded input bytes")
        if not path.is_file() or path.stat().st_size != size or sha256(path) != item["sha256"]:
            raise ValueError("Recorded size/SHA256 mismatch: " + relative)
        tracked.add(relative)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual - tracked - {"manifest.json"}:
        raise ValueError("Unlisted files in finalized run")
    sources = {}
    for relative in sorted(tracked):
        if not relative.startswith("native/") or not relative.endswith(".source.json"):
            continue
        path = confined(directory, relative)
        metadata = json.loads(path.read_bytes())
        key = metadata["key"]
        if not isinstance(key, str) or not KEY.fullmatch(key) or path.name != key + ".source.json" or key in sources:
            raise ValueError("Invalid or duplicate source key")
        total = metadata["total_words"]
        if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= 1024 * 512:
            raise ValueError("Invalid source dimensions")
        if total != metadata["width_words"] * metadata["height"] or metadata["depth"] not in (0, 1, 2):
            raise ValueError("Invalid source dimensions/depth")
        payloads = []
        for suffix in ("words.bin", "valid.bin", "clut.bin"):
            sidecar = path.parent / (key + "." + suffix)
            if sidecar.relative_to(directory).as_posix() not in tracked:
                raise ValueError("Untracked source sidecar")
            payloads.append(sidecar.read_bytes())
        words, valid, clut = payloads
        clut_words = (16, 256, 0)[metadata["depth"]]
        if len(words) != total * 2 or len(valid) != total or len(clut) != clut_words * 2:
            raise ValueError("Source payload length mismatch")
        if metadata["clut_words"] != clut_words or set(valid) - {0, 1} or sum(valid) != metadata["known_words"]:
            raise ValueError("Source validity mask mismatch")
        if fnv(words) != metadata["words_fnv1a32"] or fnv(clut) != metadata["clut_fnv1a32"]:
            raise ValueError("Source FNV mismatch")
        complete = all(valid)
        crc_key = f"{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}"
        if complete and crc_key != key:
            raise ValueError("Complete source CRC mismatch: " + key)
        sources[key] = dict(key=key, complete=complete, frame=metadata.get("frame"),
                            words_sha256=hashlib.sha256(words).hexdigest(),
                            clut_sha256=hashlib.sha256(clut).hexdigest(),
                            raw_origin=metadata.get("raw_origin"), candidate_only=True)
    observations = {}
    capture = directory / "native/capture.jsonl"
    if "native/capture.jsonl" not in tracked:
        raise ValueError("Missing tracked native capture stream")
    for number, line in enumerate(capture.read_bytes().splitlines(), 1):
        if number > 20000:
            raise ValueError("Native stream exceeds bounded record count")
        row = json.loads(line)
        if row.get("event") not in ("source_draw_query_matched", "replacement_gl_draw_submitted"):
            continue
        if row.get("source_kind") != "upload":
            continue
        key = row.get("key")
        frame = row.get("frame")
        if not isinstance(key, str) or not KEY.fullmatch(key) or isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError("Invalid upload draw key/frame")
        observation = observations.setdefault(key, dict(first_frame=frame, last_frame=frame, query_rows=0, gl_rows=0))
        observation["first_frame"] = min(observation["first_frame"], frame)
        observation["last_frame"] = max(observation["last_frame"], frame)
        field = "query_rows" if row["event"] == "source_draw_query_matched" else "gl_rows"
        observation[field] += 1
    if sha256(manifest_path) != manifest_sha:
        raise ValueError("Manifest changed during analysis")
    return dict(id=identity, started_at=manifest.get("started_at", ""),
                manifest_sha256=manifest_sha, tracked_files=len(tracked), bytes=byte_count,
                sources=sources, observations=observations,
                source_cap_reached=bool(manifest.get("native_capture", {}).get("stop", {}).get("caps", {}).get("sources")))


def summarize(runs, baseline_ids=()):
    """Deduplicate complete keys and rank unfinished upload targets with provenance."""
    runs = sorted(runs, key=lambda row: (row["started_at"], row["id"]))
    identities = {run["id"] for run in runs}
    baseline_ids = set(baseline_ids)
    if not baseline_ids <= identities:
        raise ValueError("Every baseline run must be included in --run")
    archives = defaultdict(list)
    observed = defaultdict(list)
    complete = set()
    baseline_complete = set()
    yields = []
    for run in runs:
        complete_here = {key for key, source in run["sources"].items() if source["complete"]}
        yields.append(dict(id=run["id"], source_archives=len(run["sources"]),
                           complete_keys=len(complete_here), new_complete_keys=len(complete_here - complete),
                           repeated_complete_keys=len(complete_here & complete),
                           source_cap_reached=run["source_cap_reached"]))
        complete.update(complete_here)
        if run["id"] in baseline_ids:
            baseline_complete.update(complete_here)
        for key, source in run["sources"].items():
            archives[key].append(dict(run=run["id"], **source))
        for key, observation in run["observations"].items():
            observed[key].append(dict(run=run["id"], started_at=run["started_at"], **observation))
    for key, copies in archives.items():
        complete_payloads = {(row["words_sha256"], row["clut_sha256"]) for row in copies if row["complete"]}
        if len(complete_payloads) > 1:
            raise ValueError("Conflicting complete payloads for one source key: " + key)
    complete_textures = {key.split("-")[0] for key in complete}
    targets = []
    for key in sorted((set(observed) | set(archives)) - complete):
        encounters = observed.get(key, [])
        latest = max(encounters, key=lambda row: (row["started_at"], row["last_frame"]), default=None)
        targets.append(dict(key=key, reason="partial_only" if key in archives else "no_raw_archive",
                            family="palette_variant_of_complete_texture" if key.split("-")[0] in complete_textures else "texture_without_complete_capture",
                            latest_observation=latest, observations=encounters,
                            partial_copies=len(archives.get(key, [])), candidate_only=True))
    targets.sort(key=lambda row: (row["latest_observation"]["started_at"] if row["latest_observation"] else "",
                                  row["family"] == "texture_without_complete_capture",
                                  row["latest_observation"]["last_frame"] if row["latest_observation"] else -1,
                                  row["key"]), reverse=True)
    families = defaultdict(set)
    for key in archives:
        families[key.split("-")[0]].add(key)
    remaining = (set(observed) | set(archives)) - complete
    baseline_targets = set().union(*(set(run["observations"]) | set(run["sources"]) for run in runs if run["id"] in baseline_ids)) - baseline_complete
    return dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                integrity="PASS", mode="finalized_files_only", engine_commands=0,
                summary=dict(runs=len(runs), source_archives=sum(len(row) for row in archives.values()),
                             distinct_source_keys=len(archives), complete_crc_valid_keys=len(complete),
                             partial_only_keys=len(set(archives) - complete),
                             duplicate_archive_occurrences=sum(len(row) for row in archives.values())-len(archives),
                             observed_upload_keys=len(observed), observed_keys_without_archive=len(set(observed)-set(archives)),
                             unfinished_keys=len(remaining), texture_hash_families=len(families)),
                comparison=dict(baseline_runs=sorted(baseline_ids), baseline_complete_keys=len(baseline_complete),
                                added_complete_keys=sorted(complete-baseline_complete) if baseline_ids else [],
                                recovered_baseline_targets=sorted(baseline_targets & complete),
                                remaining_baseline_targets=sorted(baseline_targets - complete)),
                per_run=yields, targets=targets, known_complete_keys=sorted(complete),
                capture_plan=dict(source_filter_batches=[dict(policy="include", keys=sorted(row["key"] for row in targets[start:start+224]))
                                                         for start in range(0, len(targets), 224)],
                                  requires_capability="source_filter_supported",
                                  scope="Raw archives only; unrelated sampled draw/event channels remain active",
                                  guidance="Use a short run at the target's observed encounter. Include mode intentionally omits raw keys outside its list."),
                texture_families=[dict(texture_hash=key, palette_keys=sorted(value)) for key, value in sorted(families.items())],
                manifests=[dict(id=run["id"], sha256=run["manifest_sha256"], tracked_files=run["tracked_files"]) for run in runs],
                limitations=["Source keys and palette families do not identify actors or prove semantic ownership.",
                             "CRC-valid bytes do not establish GPU-coherent VRAM, visibility, visual quality or complete gameplay coverage.",
                             "Observed keys are sampled; this report cannot enumerate never-observed sources.",
                             "Targets and known_complete_keys are offline plans; the current native protocol has no key filter.",
                             "Integrity checks verify bundle consistency, not external authenticity of its manifest."])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path(__file__).resolve().parent / "research-runs")
    parser.add_argument("--run", action="append", required=True, dest="runs", help="Finalized run ID; repeat for each bundle")
    parser.add_argument("--baseline", action="append", default=[], help="Included baseline run ID for before/after comparison")
    parser.add_argument("--output", type=Path, help="Create a new JSON report; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        identities = list(dict.fromkeys(args.runs))
        if len(identities) > MAX_RUNS:
            raise ValueError("Too many runs")
        report = summarize([load_run(args.runs_root, identity) for identity in identities], args.baseline)
        data = json.dumps(report, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(data)
            print(json.dumps(dict(report=str(args.output.resolve()), integrity=report["integrity"], summary=report["summary"])))
        else:
            print(data, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(integrity="FAIL", error=str(error))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
