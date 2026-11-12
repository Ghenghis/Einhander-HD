"""Revalidate the known mixed-world backlog without modifying packs or the game.

Source validity and output preservation can make an asset eligible for an
isolated experiment. They do not establish object ownership, authored detail,
visible replacement admission, or animation acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STAGING = Path("C:/github/REMASTER_STAGING/full-remaster")
AUDIT = ROOT / "remaster-audit/background-audit-20261112/stage1-background-gap-inventory.json"
DEFAULT_CANDIDATE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v6/candidate.json"
DEFAULT_OUTPUT = AUDIT.with_name("world-source-backlog-revalidation.json")


def sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_check(key, queued):
    path = Path(queued["source"])
    metadata_path = path.with_suffix(".source.json")
    metadata = load(metadata_path)
    raw = path.with_suffix(".words.bin").read_bytes()
    clut = path.with_suffix(".clut.bin").read_bytes()
    valid = path.with_suffix(".valid.bin").read_bytes()
    width_words, height, depth = (metadata[name] for name in ("width_words", "height", "depth"))
    require(depth in (0, 1, 2), "Unsupported source depth")
    total_words = width_words * height
    require(total_words > 0 and len(raw) == total_words * 2, "Raw word length differs from dimensions")
    require(len(valid) == total_words and all(v == 1 for v in valid), "Incomplete validity map")
    require(metadata["known_words"] == metadata["total_words"] == total_words, "Metadata validity differs")
    require(metadata["key"] == key, "Metadata key differs")
    require(metadata == queued["source_metadata"], "Queue metadata differs")
    require(queued["source_verified"] is True, "Queue source is not verified")
    require(len(clut) == metadata["clut_words"] * 2, "CLUT byte length differs from metadata")
    require(depth == 2 or len(clut) == (32 if depth == 0 else 512), "Indexed CLUT length differs")
    require(f"{zlib.crc32(raw):08X}" == key.split("-")[0], "Raw CRC differs from texture key")
    require(f"{zlib.crc32(clut):08X}" == key.split("-")[1], "CLUT CRC differs from palette key")
    require(sha_bytes(raw) == queued["raw_sha256"], "Raw SHA256 differs from queue")
    require(sha_bytes(clut) == queued["clut_sha256"], "CLUT SHA256 differs from queue")
    words = np.frombuffer(raw, dtype="<u2")
    if depth == 0:
        indices = ((words[:, None] >> np.array([0, 4, 8, 12], dtype=np.uint16)) & 15).reshape(-1)
        pixels = np.frombuffer(clut, dtype="<u2")[indices]
    elif depth == 1:
        indices = ((words[:, None] >> np.array([0, 8], dtype=np.uint16)) & 255).reshape(-1)
        pixels = np.frombuffer(clut, dtype="<u2")[indices]
    else:
        pixels = words
    rgba = np.empty((pixels.size, 4), dtype=np.uint8)
    rgba[:, 0] = (pixels & 31) << 3
    rgba[:, 1] = ((pixels >> 5) & 31) << 3
    rgba[:, 2] = ((pixels >> 10) & 31) << 3
    rgba[:, 3] = np.where(pixels == 0, 0, np.where((pixels & 0x8000) != 0, 255, 127))
    decoded = rgba.tobytes()
    size = (width_words * (4 if depth == 0 else 2 if depth == 1 else 1), height)
    with Image.open(path) as image:
        image.load()
        native = image.convert("RGBA")
    require(native.size == size == tuple(queued["source_size"]), "PNG dimensions differ from source layout")
    require(native.tobytes() == decoded, "Independent PSX1555 decode differs from native PNG")
    require(sha_bytes(decoded) == queued["source_pixel_sha256"], "Decoded pixel hash differs from queue")
    receipt = dict(
        status="pass", path=str(path), metadata_path=str(metadata_path),
        metadata_sha256=sha_file(metadata_path), png_sha256=sha_file(path),
        raw_words_sha256=sha_bytes(raw), clut_sha256=sha_bytes(clut), validity_sha256=sha_bytes(valid),
        decoded_rgba_sha256=sha_bytes(decoded), dimensions=list(size), depth=depth,
        clut_xy=metadata.get("clut_xy"), native_source_fragments=metadata.get("fragments"),
        frame=metadata.get("frame"), upload_serial=metadata.get("upload_serial"),
        total_words=total_words, alpha_classes=dict(Counter(decoded[3::4])),
        checks=["raw_and_clut_crc", "raw_and_clut_sha256", "complete_word_validity",
                "metadata_dimensions", "independent_psx1555_decode", "native_png_pixels"],
    )
    return native, receipt


def replacement_check(key, row, path, native):
    require(path.is_file(), "Replacement file missing")
    digest = sha_file(path)
    require(digest == row["sha256"], "Replacement SHA256 differs from manifest")
    with Image.open(path) as image:
        image.load()
        restored = image.convert("RGBA")
    require(restored.size == tuple(row["output_size"]), "Replacement dimensions differ from manifest")
    scale = restored.width // native.width
    require(scale >= 1 and restored.size == (native.width * scale, native.height * scale), "Nonuniform integer scale")
    require(restored.getchannel("A").tobytes() == native.getchannel("A").resize(restored.size, Image.Resampling.NEAREST).tobytes(),
            "Native categorical coverage/STP map differs")
    protected = []
    for rect in row.get("protected_rects", []):
        require(len(rect) == 4 and 0 <= rect[0] < rect[2] <= native.width and 0 <= rect[1] < rect[3] <= native.height,
                "Protected rectangle outside source bounds")
        target = tuple(value * scale for value in rect)
        expected = native.crop(rect).resize((target[2] - target[0], target[3] - target[1]), Image.Resampling.NEAREST)
        require(restored.crop(target).tobytes() == expected.tobytes(), "Protected region differs from nearest native source")
        protected.append(dict(native_uv_half_open=rect, output_uv_half_open=list(target), exact_native_rgb_and_classes=True))
    if row.get("neural_detail") is False:
        require(restored.resize(native.size, Image.Resampling.NEAREST).tobytes() == native.tobytes(), "Native fallback roundtrip differs")
    return dict(status="pass", path=str(path), sha256=digest, bytes=path.stat().st_size,
                dimensions=list(restored.size), scale=scale, processing_method=row["method"],
                processing_class="neural_upscale" if row.get("neural_detail") else "nearest_enlargement",
                native_categorical_alpha_exact=True, protected_regions=protected,
                authored_detail_accepted=False, live_visual_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    require(args.output.resolve().is_relative_to(ROOT / "remaster-audit"), "Output must remain within remaster-audit")
    audit, candidate, queue, expanded = (load(p) for p in (AUDIT, args.candidate, STAGING / "queue.json", STAGING / "stage1-expanded/manifest.json"))
    queued = {r["key"]: r for r in queue["assets"]}
    expanded_rows = {r["key"]: r for r in expanded["files"]}
    current = {r["name"].removesuffix(".png"): r for r in candidate["files"]}
    families = {r["texture_crc32"]: r for r in audit["family_inventory"]}
    keys = sorted({key for family in families.values() for key in family["known_queue_palette_keys"]})
    missing = sorted(set(keys) - set(current))
    prior_missing = sorted({key for family in families.values() for key in family["known_queue_keys_absent_current_candidate"]})
    rows, failures = [], []
    for index, key in enumerate(keys):
        family = families[key.split("-")[0]]
        row = dict(key=key, texture_crc32=key.split("-")[0], palette_crc32=key.split("-")[1],
                   absent_current_candidate=key not in current,
                   semantic_ownership_verified=False, ordered_animation_coverage_verified=False,
                   family_candidate_description=family["source_content_review"],
                   component_state="unmapped", source_checks={}, expanded_replacement_checks={},
                   remaining_gates=["semantic_owner_and_placement", "stage_route_visibility", "source_uv_draw_witness",
                                    "authored_detail", "ordered_animation_or_lighting_states", "final_candidate_visual_and_motion_acceptance"])
        try:
            native, row["source_checks"] = source_check(key, queued[key])
            path = STAGING / "stage1-expanded/einhander-texture-replacements" / (key + ".png")
            row["expanded_replacement_checks"] = replacement_check(key, expanded_rows[key], path, native)
            declared_protected = family["protected_native_uv_rectangles_half_open"]
            require(expanded_rows[key].get("protected_rects", []) == declared_protected, "Protected bounds differ from world audit")
            if key in current:
                entry = current[key]
                composed = Path(entry["composed_path"])
                require(sha_file(composed) == entry["sha256"], "Current composition SHA256 differs")
                row["current_candidate"] = dict(path=str(composed), sha256=entry["sha256"],
                                                dimensions=entry["dimensions"], origin=entry["origin"])
            row["eligible_for_isolated_source_preserving_experiment"] = True
            row["production_admission_approved"] = False
        except Exception as error:
            row["error"] = str(error)
            row["eligible_for_isolated_source_preserving_experiment"] = False
            row["production_admission_approved"] = False
            failures.append(dict(key=key, error=str(error)))
        rows.append(row)
        if (index + 1) % 40 == 0:
            print(json.dumps(dict(checked=index + 1, total=len(keys), failures=len(failures))), flush=True)
    sources = [AUDIT, args.candidate, STAGING / "queue.json", STAGING / "stage1-expanded/manifest.json", Path(__file__)]
    report = dict(
        schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="Fresh read-only file/source revalidation of ten historically grouped mixed page families; no game or API calls",
        asset_mutations=0, game_calls=0,
        summary=dict(known_palette_keys=len(keys), mixed_page_families=len(families),
                     source_and_expanded_checks_passed=len(rows)-len(failures), failures=len(failures),
                     current_candidate_total_keys=len(current), present_current_candidate=len(set(keys) & set(current)),
                     absent_current_candidate=len(missing), previous_missing_set_matches=missing == prior_missing,
                     missing_source_valid_eligible_for_isolated_experiment=sum(r["absent_current_candidate"] and r["eligible_for_isolated_source_preserving_experiment"] for r in rows),
                     authored_world_completions_accepted=0, semantic_object_count=None,
                     ordered_animation_sequences_accepted=0, production_admissions_approved=0),
        missing_keys=missing, keys=rows, failures=failures,
        evidence_inputs=[dict(path=str(p), sha256=sha_file(p)) for p in sources],
        staging_recommendation="Only passing exact-key outputs are eligible for a separate reversible source-preserving integration experiment. Preserve UI overlay precedence. Capture actual replacement admission and matching route/CLUT/UV observations before accepting any visible component.",
        reconstruction_required=["Protected nearest-source sign/glyph regions still need source-faithful authored restoration",
                                 "Ownership and placement on mixed pages remain unverified",
                                 "Neural dimensions do not establish authored building, signage, window or skyline detail",
                                 "Complete ordered lighting, palette-cycle, streamed-upload and parallax sequences remain unverified"],
        limitations=["A missing texture/palette key is not a count of missing visible objects",
                     "This audit does not modify, install, launch or visually accept any pack",
                     "Native exact alpha preservation is tested for these existing source-preserving candidates; it is not a universal constraint on later authored contour restoration"],
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), **report["summary"]), indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
