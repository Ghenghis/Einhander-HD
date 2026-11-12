"""Recover missing source byte pairs from CRC-validated saved evidence only.

This joins captured original upload words with a captured CLUT or an exact-CRC
CLUT at a draw-observed location in a validated marked CPU-VRAM snapshot. It
does not invent pixels, contact the game, edit native archives or assert that
the two byte payloads were captured together. Derived results stay separate.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zlib

from research_novelty import KEY, fnv, load_run, sha256
from research_service import EVENT_RAM_BYTES, EVENT_VRAM_BYTES, ResearchService


def crc(data):
    return f"{zlib.crc32(data):08X}"


def add_candidate(index, identity, data, provenance):
    digest = hashlib.sha256(data).hexdigest()
    entry = index[identity].setdefault(digest, dict(data=data, sha256=digest, provenance=[]))
    if provenance not in entry["provenance"]:
        entry["provenance"].append(provenance)


def merge_partial_words(expected_crc, dimensions, fragments, expected_full_fnv=None):
    """Union only known words; reject conflicting overlaps and incomplete unions.

    Each fragment's FNV is over its actual saved payload, including unknown
    slots. A genuinely missing full source has no independently known full FNV;
    the returned full FNV is explicitly computed, not an invented expectation.
    """
    width, height, depth = dimensions
    if any(isinstance(value, bool) or not isinstance(value, int) for value in dimensions) or not 1 <= width <= 1024 or not 1 <= height <= 512 or depth not in (0, 1, 2):
        raise ValueError("Invalid partial-source dimensions/depth")
    total = width * height
    merged, known = bytearray(total*2), bytearray(total)
    conflicts = []
    for fragment in fragments:
        data, valid = fragment["data"], fragment["valid"]
        if len(data) != total*2 or len(valid) != total or set(valid) - {0, 1}:
            return dict(status="invalid_fragment_layout", total_words=total)
        if fnv(data) != fragment["words_fnv1a32"]:
            return dict(status="source_checksum_mismatch", total_words=total)
        for index, is_known in enumerate(valid):
            if not is_known:
                continue
            word = data[index*2:index*2+2]
            if known[index] and merged[index*2:index*2+2] != word:
                if len(conflicts) < 32:
                    conflicts.append(index)
            else:
                merged[index*2:index*2+2] = word
                known[index] = 1
    coverage = sum(known)
    if conflicts:
        return dict(status="conflicting_overlap", known_words=coverage, total_words=total, conflicting_word_offsets=conflicts)
    if coverage != total:
        return dict(status="insufficient_coverage", known_words=coverage, total_words=total)
    data = bytes(merged)
    if crc(data) != expected_crc:
        return dict(status="merged_crc_mismatch", computed_crc=crc(data), expected_crc=expected_crc, known_words=coverage, total_words=total)
    full_fnv = fnv(data)
    if expected_full_fnv is not None and full_fnv != expected_full_fnv:
        return dict(status="merged_fnv_mismatch", known_words=coverage, total_words=total)
    return dict(status="merged", data=data, known_words=coverage, total_words=total, words_fnv1a32=full_fnv,
                independent_full_fnv_available=expected_full_fnv is not None,
                independent_full_fnv_verified=expected_full_fnv is not None)


def read_clut(vram, x, y, depth):
    if len(vram) != EVENT_VRAM_BYTES or depth not in (0, 1, 2):
        raise ValueError("Invalid bounded CPU-VRAM/CLUT layout")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (x, y)) or not 0 <= x < 1024 or not 0 <= y < 512:
        raise ValueError("Observed CLUT position outside native VRAM")
    words = (16, 256, 0)[depth]
    return b"".join(vram[2*(y*1024+((x+i) & 1023)):2*(y*1024+((x+i) & 1023))+2] for i in range(words))


def recover(runs_root, novelty):
    runs_root = Path(runs_root).resolve()
    if novelty.get("integrity") != "PASS" or not isinstance(novelty.get("manifests"), list):
        raise ValueError("A passing novelty report with finalized manifests is required")
    if not 1 <= len(novelty["manifests"]) <= 128:
        raise ValueError("Recovery requires at most128 finalized runs")
    targets = {item["key"] for item in novelty["targets"]}
    if any(not isinstance(key, str) or not KEY.fullmatch(key) for key in targets):
        raise ValueError("Invalid target key")
    runs, manifests = [], []
    for receipt in novelty["manifests"]:
        run = load_run(runs_root, receipt["id"])
        if run["manifest_sha256"] != receipt["sha256"]:
            raise ValueError("Novelty manifest receipt changed")
        runs.append(run)
        manifests.append(dict(id=run["id"], sha256=run["manifest_sha256"]))
    words, palettes, partials = defaultdict(dict), defaultdict(dict), defaultdict(list)
    layouts = defaultdict(set)
    draws = defaultdict(list)
    events = []
    live_calls = []
    def forbidden(*args, **kwargs):
        live_calls.append(args)
        raise AssertionError("Offline recovery must not contact the game")
    validator = ResearchService(runs_root.parent.parent, forbidden)
    for run in runs:
        directory = runs_root/run["id"]
        manifest = json.loads((directory/"manifest.json").read_bytes())
        for key, source in run["sources"].items():
            path = directory/"native"/(key+".source.json")
            metadata = json.loads(path.read_bytes())
            raw = (path.parent/(key+".words.bin")).read_bytes()
            clut = (path.parent/(key+".clut.bin")).read_bytes()
            dimensions = (metadata["width_words"], metadata["height"], metadata["depth"])
            if source["complete"]:
                add_candidate(words, (key[:8], dimensions), raw, dict(run=run["id"], file="native/"+key+".words.bin", source_key=key,
                                                                    metadata_file="native/"+key+".source.json", raw_origin=metadata.get("raw_origin")))
            else:
                partials[(key[:8], dimensions)].append(dict(data=raw, valid=(path.parent/(key+".valid.bin")).read_bytes(),
                                                           words_fnv1a32=metadata["words_fnv1a32"],
                                                           provenance=dict(run=run["id"], source_key=key, file="native/"+key+".words.bin",
                                                                           validity_file="native/"+key+".valid.bin", metadata_file="native/"+key+".source.json",
                                                                           words_sha256=source["words_sha256"], words_fnv1a32=metadata["words_fnv1a32"],
                                                                           known_words=metadata["known_words"], total_words=metadata["total_words"])))
            # CLUT remains independently useful even if its associated words
            # were partial. Its own expected CRC must match exactly.
            if crc(clut) == key[9:]:
                add_candidate(palettes, (key[9:], metadata["depth"]), clut, dict(kind="source_clut", run=run["id"], file="native/"+key+".clut.bin", source_key=key))
        for number, line in enumerate((directory/"native/capture.jsonl").read_bytes().splitlines(), 1):
            row = json.loads(line)
            key = row.get("key")
            if key not in targets or row.get("source_kind") != "upload":
                continue
            width, height = row["native_words"]
            depth = row["depth"]
            if any(isinstance(value, bool) or not isinstance(value, int) for value in (width, height, depth)) or not 1 <= width <= 1024 or not 1 <= height <= 512 or depth not in (0, 1, 2):
                raise ValueError("Invalid draw-observed source layout")
            x, y = row["clut_xy"]
            layouts[key].add((width, height, depth, x, y))
            draws[key].append(dict(run=run["id"], file="native/capture.jsonl", line=number, frame=row["frame"],
                                   dimensions=[width, height], depth=depth, clut_xy=[x, y]))
        acknowledgements = [manifest.get("native_capture", {}).get("baseline")]
        event_log = directory/"events.jsonl"
        if event_log.is_file():
            acknowledgements += [json.loads(line).get("native") for line in event_log.read_bytes().splitlines()]
        associated = set()
        for acknowledgement in acknowledgements:
            if not acknowledgement or not acknowledgement.get("ok") or not acknowledgement.get("event_file"):
                continue
            metadata, _ = validator._event_binary(dict(path=directory), acknowledgement)
            if metadata["file"] in associated:
                continue
            associated.add(metadata["file"])
            payload = (directory/metadata["file"]).read_bytes()
            offset, length = struct.unpack_from("<II", payload, 40)
            if (offset, length) != (160+EVENT_RAM_BYTES, EVENT_VRAM_BYTES):
                raise ValueError("Unexpected CPU-VRAM event layout")
            events.append(dict(run=run["id"], file=metadata["file"], sha256=metadata["sha256"], frame=metadata["frame"], vram=payload[offset:offset+length]))
        actual = {path.relative_to(directory).as_posix() for path in (directory/"native").glob("event-*.bin")}
        if actual != associated:
            raise ValueError("Unassociated event binary in finalized bundle")
    partial_merges = []
    for identity, fragments in sorted(partials.items()):
        texture_crc, dimensions = identity
        existing = words.get(identity, {})
        independent_fnv = fnv(next(iter(existing.values()))["data"]) if len(existing) == 1 else None
        result = merge_partial_words(texture_crc, dimensions, fragments, independent_fnv)
        diagnostic = dict(texture_crc=texture_crc, dimensions=list(dimensions), input_fragments=len(fragments),
                          **{key:value for key,value in result.items() if key != "data"})
        partial_merges.append(diagnostic)
        if result["status"] == "merged":
            add_candidate(words, identity, result["data"],
                          dict(kind="merged_complementary_partial_words", source_fragments=[row["provenance"] for row in fragments],
                               all_known_overlaps_agree=True, full_validity_union=True,
                               expected_texture_crc=texture_crc, computed_full_words_fnv1a32=result["words_fnv1a32"],
                               independent_full_fnv_available=result["independent_full_fnv_available"],
                               independent_full_fnv_verified=result["independent_full_fnv_verified"]))
    if targets - set(draws):
        raise ValueError("Every recovery target must have an actual upload draw observation")
    for key, observed_layouts in layouts.items():
        for _, _, depth, x, y in observed_layouts:
            for event in events:
                clut = read_clut(event["vram"], x, y, depth)
                if crc(clut) == key[9:]:
                    add_candidate(palettes, (key[9:], depth), clut,
                                  dict(kind="marked_cpu_vram_clut", run=event["run"], file=event["file"], event_sha256=event["sha256"],
                                       event_frame=event["frame"], clut_xy=[x, y],
                                       cpu_vram_may_be_stale=True, gpu_readback=False))
    recovered, unresolved, payloads = [], [], {}
    for key in sorted(targets):
        dimensions = {(width, height, depth) for width, height, depth, _, _ in layouts[key]}
        if len(dimensions) != 1:
            unresolved.append(dict(key=key, reason="ambiguous_draw_dimensions_or_depth"))
            continue
        dimensions = next(iter(dimensions))
        word_candidates = words.get((key[:8], dimensions), {})
        clut_candidates = palettes.get((key[9:], dimensions[2]), {})
        if len(word_candidates) != 1 or len(clut_candidates) != 1:
            unresolved.append(dict(key=key, reason="missing_or_ambiguous_exact_bytes", word_candidates=len(word_candidates), clut_candidates=len(clut_candidates)))
            continue
        word = next(iter(word_candidates.values()))
        clut = next(iter(clut_candidates.values()))
        assert f"{crc(word['data'])}-{crc(clut['data'])}" == key
        recovered.append(dict(key=key, width_words=dimensions[0], height=dimensions[1], depth=dimensions[2],
                              words_sha256=word["sha256"], clut_sha256=clut["sha256"],
                              words_fnv1a32=fnv(word["data"]), clut_fnv1a32=fnv(clut["data"]),
                              words_bytes=len(word["data"]), clut_bytes=len(clut["data"]),
                              words_provenance=word["provenance"], clut_provenance=clut["provenance"],
                              draw_observations=draws[key], derivation="independently_crc_validated_byte_join",
                              atomic_pair_capture=False, actor_ownership_verified=False, candidate_only=True))
        payloads[key] = (word["data"], clut["data"])
    if live_calls or validator.worker is not None or validator.watcher is not None:
        raise AssertionError("Recovery unexpectedly activated a service")
    report = dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(), integrity="PASS", mode="offline_derived_candidates", engine_commands=0,
                  tool_sha256=sha256(Path(__file__)),
                  summary=dict(finalized_runs=len(runs), targets=len(targets), recovered_candidate_pairs=len(recovered),
                               unresolved_targets=len(unresolved), validated_marked_vram_events=len(events),
                               partial_word_families_checked=len(partial_merges),
                               partial_word_families_merged=sum(row["status"] == "merged" for row in partial_merges)),
                  partial_word_merges=partial_merges,
                  native_archive_counts_unchanged=True, manifests=manifests, recovered=recovered, unresolved=unresolved,
                  remaining_include_batches=[dict(policy="include", keys=[row["key"] for row in unresolved[start:start+224]]) for start in range(0, len(unresolved), 224)],
                  limitations=["Derived byte pairs remain separate from original native source archives and do not increase native capture counts.",
                               "Words and palettes can come from different frames/runs; this does not establish an atomic source-palette observation.",
                               "Exact CRC matches and SHA256 provenance validate saved candidate bytes, not actor identity or GPU-coherent visible rendering.",
                               "Marked CPU-VRAM can be stale; only a CLUT matching its expected observed key CRC is accepted.",
                               "Partial-input FNV hashes validate saved zero-filled inputs. A merged full FNV is computed and only independently verified when a complete reference already exists.",
                               "Unknown source words and ambiguous payloads are never reconstructed by interpolation or guessed pixels."])
    return report, payloads


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--novelty", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=Path(__file__).resolve().parent/"research-runs")
    parser.add_argument("--output-dir", type=Path, help="Create a new derived-evidence directory; existing directories are never overwritten")
    args = parser.parse_args(argv)
    try:
        report, payloads = recover(args.runs_root, json.loads(args.novelty.read_bytes()))
        report["novelty_input"] = dict(path=str(args.novelty.resolve()), sha256=sha256(args.novelty))
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=False)
            for row in report["recovered"]:
                key = row["key"]
                words, clut = payloads[key]
                for suffix, data in (("words.bin", words), ("clut.bin", clut), ("recovered.json", (json.dumps(row, indent=2)+"\n").encode("utf-8"))):
                    with (args.output_dir/(key+"."+suffix)).open("xb") as stream:
                        stream.write(data)
            (args.output_dir/"recovery.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
            print(json.dumps(dict(report=str((args.output_dir/"recovery.json").resolve()), integrity=report["integrity"], summary=report["summary"])))
        else:
            print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(integrity="FAIL", error=str(error))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
