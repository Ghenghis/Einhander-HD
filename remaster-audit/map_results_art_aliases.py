"""Test Results art region aliases against fresh GPU-truth VRAM and GP0.

The report can optionally export current native source pages and a whole edit
target. No existing image is changed and no game command is issued. Matching
layout, page location, or dimensions cannot substitute for exact native
used-region word equality.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zlib

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v6"
ART = ROOT / "remaster-audit/menu-restoration/results-art-candidate-v2/manifest.json"
DEFAULT_OUT = ROOT / "remaster-audit/menu-restoration/results-art-alias-map.json"
DEFAULT_SOURCE_OUT = ROOT / "remaster-audit/menu-restoration/results-native-v6-variant-source-v1"
POSITIONS = [(320, 0), (384, 0), (448, 0), (320, 256), (384, 256)]
EXPECTED_CURRENT = ["118DB76A", "986250B4", "F6796FFD", "D5602570", "8942621A"]
REGION = [0, 0, 64, 224]


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ref(path):
    return dict(path=str(path), sha256=sha(Path(path).read_bytes()))


def raw(words):
    return words.astype("<u2").tobytes()


def alpha(words):
    return np.where(words == 0, 0, np.where(words & 32768, 255, 127)).astype(np.uint8)


def decode(words):
    return np.stack(((words & 31) << 3, ((words >> 5) & 31) << 3, ((words >> 10) & 31) << 3, alpha(words)), axis=-1).astype(np.uint8)


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def equal_used_region(old, current):
    require(old.shape == current.shape == (256, 256), "Alias comparison requires complete 256x256 native word pages")
    return bool(np.array_equal(old[:224, :64], current[:224, :64]))


def bounds(mask):
    locations = np.argwhere(mask)
    if not len(locations):
        return None
    ymin, xmin = locations.min(axis=0)
    ymax, xmax = locations.max(axis=0) + 1
    return [int(xmin), int(ymin), int(xmax), int(ymax)]


def poster_draws(frame):
    tpage, offset = None, None
    draws = []
    for entry in frame["entries"]:
        words = [int(w, 16) for w in entry["w"]]
        opcode = words[0] >> 24
        if opcode == 0xE1:
            tpage = words[0] & 0x7FF
        elif opcode == 0xE5:
            offset = (signed(words[0], 11), signed(words[0] >> 11, 11))
        elif (opcode & 0xFC) == 0x64 and len(words) == 4 and tpage is not None and offset is not None:
            page = ((tpage & 15) * 64, ((tpage >> 4) & 1) * 256)
            uv = [words[2] & 255, (words[2] >> 8) & 255]
            size = [words[3] & 65535, words[3] >> 16]
            depth = (tpage >> 7) & 3
            if page not in POSITIONS or uv != [0, 0] or size != [64, 224] or depth != 2:
                continue
            screen = [signed(words[1], 16) + offset[0], signed(words[1] >> 16, 16) + offset[1]]
            require(screen[0] == POSITIONS.index(page) * 64 and screen[1] in (8, 248), "Unexpected poster draw placement")
            draws.append(dict(frame=frame["frame"], seq=entry["seq"], page_xy=list(page), depth=2,
                              source_uv=uv, size=size, uv_half_open=REGION, screen_xy=screen,
                              vertex_rgb=[words[0] & 255, (words[0] >> 8) & 255, (words[0] >> 16) & 255],
                              command_source=entry.get("src"), command_pc=entry.get("pc"),
                              opcode=f"{opcode:02X}", gp0=entry))
    return draws


def guardrails():
    source = np.zeros((256, 256), dtype=np.uint16)
    changed_used = source.copy()
    changed_used[223, 63] = 1
    require(not equal_used_region(source, changed_used), "One-word used-region mismatch was accepted")
    changed_outside = source.copy()
    changed_outside[224, 63] = 1
    require(equal_used_region(source, changed_outside), "Outside-only changes incorrectly disprove region equality")
    try:
        equal_used_region(source[:, :64], source)
    except ValueError:
        pass
    else:
        raise ValueError("Truncated source page was accepted")
    return dict(single_used_word_mismatch_rejected=True, outside_only_change_scoped_correctly=True, incomplete_page_rejected=True)


def extract_current_source(output, report, vram, bracket_path, vram_path, capture_path, alias_path):
    output = output.resolve()
    require(output.is_relative_to(ROOT / "remaster-audit/menu-restoration"), "Native proof output must stay inside menu-restoration")
    require(not output.exists(), "Native source proof requires a new immutable directory")
    output.mkdir()
    strips, pages = [], []
    frame = report["capture_bracket"]["gpu_truth_display_ring_frame"]
    for row in report["pages"]:
        x, y = row["page_xy_vram_words"]
        key = row["observed_current_key"]
        words = vram[y:y+256, x:x+256].copy()
        payload = raw(words)
        require(f"{zlib.crc32(payload):08X}-00000000" == key, "Native proof full-page identity differs")
        (output / (key + ".words.bin")).write_bytes(payload)
        (output / (key + ".clut.bin")).write_bytes(b"")
        (output / (key + ".valid.bin")).write_bytes(bytes([1]) * 65536)
        rgba = decode(words)
        Image.fromarray(rgba).save(output / (key + ".png"))
        with Image.open(output / (key + ".png")) as image:
            require(image.convert("RGBA").tobytes() == rgba.tobytes(), "Native proof PNG decode roundtrip differs")
        metadata = dict(key=key, frame=frame, upload_serial=0, width_words=256, height=256, depth=2,
                        clut_xy=[0, 0], clut_words=0, known_words=65536, total_words=65536,
                        reconstructed_crc32=key.split("-")[0], page_xy=[x, y],
                        raw_origin="GPU-truth display-ring full-VRAM readback; independently corroborated full-page native query identity",
                        fragments=[[x, y, 256, 256, 0, 0]])
        (output / (key + ".source.json")).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        strips.append(rgba[:224, :64])
        pages.append(dict(key=key, native_size=[256, 256], page_xy=[x, y],
                          replacement_region_half_open=REGION, master_crop_half_open=[row["column"]*64, 0, (row["column"]+1)*64, 224],
                          expected_display_relative_screen_xy=[row["column"]*64, 8],
                          native_words_sha256=sha(payload), native_used_words_sha256=sha(raw(words[:224, :64])),
                          native_rgba_sha256=sha(rgba.tobytes()), used_region_rgba_sha256=sha(rgba[:224, :64].tobytes()),
                          native_alpha_classes={str(value): int(count) for value, count in zip(*np.unique(rgba[:, :, 3], return_counts=True))},
                          source_files=[ref(output / (key + suffix)) for suffix in (".png", ".words.bin", ".clut.bin", ".valid.bin", ".source.json")],
                          source_crc_verified=True, source_decode_verified=True, source_validity_complete=True,
                          exact_historical_alias_eligible=False, gp0_witnesses=row["gp0_witnesses"], query_example=row["query_example"]))
    master = np.concatenate(strips, axis=1)
    require(master.shape == (224, 320, 4) and sha(master.tobytes()) == report["native_current_master"]["decoded_rgba_sha256"],
            "Native master assembly differs from used-region proof")
    native_master = output / "results-native-320x224.png"
    Image.fromarray(master).save(native_master)
    display = master.copy()
    display[:, :, 3] = np.where(display[:, :, 3] == 0, 0, 255)
    generation_target = output / "results-native-display-320x224.png"
    Image.fromarray(display).save(generation_target)
    manifest = dict(
        schema_version=1, contract="verified-results-current-variant-source-v1",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_variant="distinct_v6_results_aircraft_composition_hull_binding_pending",
        source_master=dict(**ref(native_master), dimensions=[320, 224], rgba_sha256=sha(master.tobytes()), alpha_policy="Native PSX categorical coverage/STP values"),
        display_reference=dict(**ref(generation_target), dimensions=[320, 224], rgba_sha256=sha(display.tobytes()),
                               alpha_policy="Both nonzero PSX classes displayed opaque; source categories retained in native master and raw pages"),
        generation_target=dict(**ref(generation_target), dimensions=[320, 224], exact_aspect_ratio="10:7",
                               instruction="This current aircraft composition is the exact edit target. Restore its existing pose, silhouette, proportions, markings and colors; do not use or merge the historical v2 aircraft composition."),
        pages=pages, source_bracket=ref(bracket_path), source_vram=dict(**ref(vram_path), frame=frame),
        immutable_native_query_log=ref(capture_path), alias_report=ref(alias_path),
        extraction_script=ref(Path(__file__)),
        restore_contract="Author one coherent current320x224 aircraft master. Split into five64x224 strips in screen-x order. Bind each only toUV[0,0,64,224] of its matching256x256 current native16bpp page. Preserve current categorical alpha/STP and outside RGBA; retain existing draw modulation and geometry.",
        historical_master_reuse_approved=False, semantic_hull_binding_verified=False,
        production_installed=False, game_actions=0, creative_edits=0, live_visual_accepted=False,
        limitations=["This is a native source export, not a remastered image.",
                     "The fresh GPU-truth display-ring capture and GP0 frames are sequential; exact full-page CRCs are separately corroborated by immutable native-query evidence.",
                     "Fighter-specific ownership remains an inference until tied to an observed selection fixture."],
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dict(directory=str(output), manifest=ref(output / "manifest.json"), generation_target=str(generation_target),
                source_pages=5, native_master_size=[320, 224], creative_edits=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v6", type=Path, default=V6)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--extract", action="store_true", help="Export native current-variant raw pages and whole edit target into a fresh proof directory")
    parser.add_argument("--source-output", type=Path, default=DEFAULT_SOURCE_OUT)
    args = parser.parse_args()
    require(args.output.resolve().is_relative_to(ROOT / "remaster-audit"), "Report must stay inside remaster-audit")
    bracket_path = args.v6 / "results-v6-current-bracket.json"
    vram_path = args.v6 / "results-v6-current-vram.bin"
    capture_path = args.v6 / "native-v6-fighter-replay/capture.jsonl"
    bracket = load(bracket_path)
    art = load(ART)
    mapping_path = Path(art["source_mapping"]["path"])
    require(sha(mapping_path.read_bytes()) == art["source_mapping"]["sha256"], "Historical Results mapping changed")
    mapping = load(mapping_path)
    for info in mapping["pages"]:
        require(info["replacement_region_half_open"] == REGION, "Historical source region changed")
    require(bracket["vram"]["ok"] and bracket["vram"]["vram_words"] == 524288, "Fresh VRAM receipt is incomplete")
    require(Path(bracket["vram"]["path"]).resolve() == vram_path.resolve(), "Fresh VRAM receipt names another file")
    payload = vram_path.read_bytes()
    require(len(payload) == 1048576, "Fresh VRAM must be complete 1024x512 words")
    vram = np.frombuffer(payload, dtype="<u2").reshape(512, 1024)
    draws = [draw for frame in bracket["frames"] for draw in poster_draws(frame)]
    require({tuple(draw["page_xy"]) for draw in draws} == set(POSITIONS), "Fresh GP0 does not establish all five poster pages")
    queries = [json.loads(line) for line in capture_path.read_text().splitlines()]
    rows, used_total, alpha_total = [], 0, 0
    current_master, old_master = [], []
    source_refs = [ref(bracket_path), ref(vram_path), ref(capture_path), ref(ART), ref(mapping_path), ref(Path(__file__))]
    mapped = {tuple(row["page_xy"]): row for row in mapping["pages"]}
    authored = {row["key"]: row for row in art["files"]}
    for index, (x, y) in enumerate(POSITIONS):
        old_page = mapped[(x, y)]
        old_key = old_page["key"]
        old_raw_path = Path(authored[old_key]["source"]).with_suffix(".words.bin")
        old_payload = old_raw_path.read_bytes()
        require(sha(old_payload) == old_page["source_words_sha256"] == authored[old_key]["source_words_sha256"], "Historical Results raw source changed")
        require(f"{zlib.crc32(old_payload):08X}-00000000" == old_key, "Historical source CRC differs")
        old = np.frombuffer(old_payload, dtype="<u2").reshape(256, 256)
        with Image.open(authored[old_key]["source"]) as image:
            require(image.size == (256, 256) and image.convert("RGBA").tobytes() == decode(old).tobytes(), "Historical source independent decode differs")
        require(sha(Path(authored[old_key]["path"]).read_bytes()) == authored[old_key]["sha256"], "Existing authored output changed")
        current = vram[y:y+256, x:x+256].copy()
        current_raw = raw(current)
        current_key = f"{zlib.crc32(current_raw):08X}-00000000"
        require(current_key == EXPECTED_CURRENT[index] + "-00000000", "Fresh GPU-truth page identity differs from observed Results variant")
        matched = [r for r in queries if r.get("event") == "source_draw_query_matched" and r.get("key") == current_key
                   and r.get("page_xy") == [x, y] and r.get("uv_bounds") == [0, 0, 63, 223]
                   and r.get("depth") == 2 and r.get("native_words") == [256, 256]]
        require(matched, "Fresh Results identity lacks matching native-page query witnesses")
        submitted = [r for r in queries if r.get("event") == "replacement_gl_draw_submitted" and r.get("key") == current_key]
        selected = [r for r in draws if r["page_xy"] == [x, y]]
        different = old != current
        outside = np.ones((256, 256), dtype=bool)
        outside[:224, :64] = False
        used_different = int(different[:224, :64].sum())
        alpha_different = int((alpha(old[:224, :64]) != alpha(current[:224, :64])).sum())
        used_total += used_different
        alpha_total += alpha_different
        old_master.append(old[:224, :64])
        current_master.append(current[:224, :64])
        source_refs += [ref(old_raw_path), ref(Path(authored[old_key]["source"])), ref(Path(authored[old_key]["path"]))]
        rows.append(dict(column=index, page_xy_vram_words=[x, y], historical_key=old_key, observed_current_key=current_key,
                         native_words=[256, 256], depth=2, palette_crc32="00000000", clut_used=False,
                         used_uv_inclusive=[0, 0, 63, 223], used_uv_half_open=REGION,
                         current_full_page_words_sha256=sha(current_raw), historical_full_page_words_sha256=sha(old_payload),
                         current_used_region_words_sha256=sha(raw(current[:224, :64])),
                         historical_used_region_words_sha256=sha(raw(old[:224, :64])),
                         used_word_samples=64*224, used_word_differences=used_different,
                         used_alpha_stp_class_differences=alpha_different,
                         unrelated_outside_word_differences=int(different[outside].sum()),
                         used_difference_bbox_half_open=bounds(different[:224, :64]),
                         exact_used_region_alias_eligible=equal_used_region(old, current),
                         existing_authored_master_reuse_approved=False,
                         source_variant_status="distinct_source_requires_own_art_restoration" if used_different else "region_equal_requires_current_outside_repack",
                         native_query_witnesses=len(matched), replacement_submissions=len(submitted),
                         query_example=matched[0], gp0_witnesses=selected,
                         current_source_archive_required=True, semantic_hull_binding_verified=False,
                         live_visual_accepted=False))
    old_master = np.concatenate(old_master, axis=1)
    current_master = np.concatenate(current_master, axis=1)
    eligible = sum(row["exact_used_region_alias_eligible"] for row in rows)
    report = dict(
        schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="Read-only exact native-word Results art alias test; no game commands, image changes, pack changes or v7 changes",
        summary=dict(pages_checked=5, exact_used_region_aliases_eligible=eligible,
                     distinct_current_source_pages=5-eligible, used_word_samples=71680,
                     used_word_differences=used_total, used_alpha_stp_class_differences=alpha_total,
                     existing_art_master_reuse_approved=False, replacement_submissions_observed=sum(r["replacement_submissions"] for r in rows),
                     new_restoration_required=eligible != 5, associated_player_hull_identity_verified=False),
        native_current_master=dict(dimensions=[320, 224], decoded_rgba_sha256=sha(decode(current_master).tobytes()),
                                   words_sha256=sha(raw(current_master)), construction="Five observed64x224 strips joined in screen-x order"),
        native_historical_master=dict(dimensions=[320, 224], decoded_rgba_sha256=sha(decode(old_master).tobytes()),
                                      words_sha256=sha(raw(old_master))),
        capture_bracket=dict(gpu_truth_display_ring_frame=bracket["vram"]["frame"],
                             sequential_gp0_frames=[frame["frame"] for frame in bracket["frames"]],
                             not_atomic=True, corroboration="Fresh full-page CRCs equal immutable native-page query keys for all five observed source regions"),
        pages=rows, evidence_inputs=source_refs, guardrail_checks=guardrails(),
        bounded_fix=dict(strategy="Separate source-variant restoration; do not re-key the historical aircraft art",
                         new_native_proof="Archive each fresh256x25616bpp page and its exact key/validity plus GP0/query witnesses. Assemble the current320x224 native aircraft master from the five64x224 used regions.",
                         authoring="Restore this current aircraft composition with its own faithful whole-master edit; retain observed pose, geometry, markings, colors and black backdrop. Record generated dimensions separately from deterministic resampling.",
                         packing="Split one coherent new master into five strips. Start each full output from its matching current native page, change onlyUV[0,0,64,224], preserve current unrelated outside RGBA and categorical alpha/STP, and name by the observed current whole-page key.",
                         integration="Create a new immutable candidate/manifest and use a dedicated verified source-variant contract; do not modify existing v6/v7 packs or silently bypass the launcher's historical five-key contract.",
                         acceptance="Require actual five-key replacement submissions, fresh visible Results captures after decode readiness, strip seams/modulation/alpha review, graph modes and re-entry. Bind each additional Results aircraft variant separately to its verified player selection."),
        limitations=["A full-page CRC difference alone does not establish used-region inequality; the report compares the actual sampled64x224 native words.",
                     "Here all five used regions differ, so changed unrelated pixels do not explain the identity mismatch.",
                     "The current artwork is visually distinct; a fighter-specific cause remains an inference until tied to an observed selection fixture.",
                     "Source-query matching proves technical identity, not final on-screen remaster acceptance."],
        game_actions=0, asset_mutations=0, prepared_v7_modified=False,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    extracted = extract_current_source(args.source_output, report, vram, bracket_path, vram_path, capture_path, args.output) if args.extract else None
    print(json.dumps(dict(output=str(args.output), **report["summary"], guardrail_checks=report["guardrail_checks"], native_source_export=extracted), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
