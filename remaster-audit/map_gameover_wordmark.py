"""Reject the mislabeled v5 Game Over bracket and decode its actual sprites.

Writes metadata only. No game, pack or runtime actions. The visual review is
pinned to the screenshot SHA256 so reruns cannot silently reuse a changed image.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zlib

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
EVIDENCE = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v5"
REVIEWED_SCREENSHOT_SHA = "ed5b5040ac30313000aec306e049094c561b09c48a46c3cfbf88bf8267362a7f"
TRUE_WORDMARK_SHA = "ae674c8a777df6134626a9307c038124d1e8e553fcde0ab360fd7c7030ad8464"
NATURAL_V6_WORDMARK_SHA = "c774df90cb37631afddd1886a1713dd68493dfb7a6953cb84dab35a1a803fd30"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_ref(path):
    return {"path": str(path), "sha256": sha(path.read_bytes())}


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def vram_rectangle(vram, x, y, width_words, height):
    assert 0 <= x < 1024 and 0 <= y < 512
    assert x + width_words <= 1024 and y + height <= 512
    return b"".join(vram[((y + row) * 1024 + x) * 2:
                         ((y + row) * 1024 + x + width_words) * 2]
                    for row in range(height))


def decode4(raw, clut):
    palette = struct.unpack("<16H", clut)
    rgba = bytearray()
    for packed in struct.unpack("<%dH" % (len(raw) // 2), raw):
        for shift in (0, 4, 8, 12):
            word = palette[(packed >> shift) & 15]
            rgba.extend(((word & 31) << 3, ((word >> 5) & 31) << 3,
                         ((word >> 10) & 31) << 3,
                         0 if word == 0 else 255 if word & 0x8000 else 127))
    return bytes(rgba)


def map_natural_v6():
    root = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6"
    bracket_path = root / "natural-gameover-bracket.json"
    if not bracket_path.is_file():
        return None
    bracket = json.loads(bracket_path.read_bytes())
    shot_path = Path(bracket["capture"]["path"])
    assert sha(shot_path.read_bytes()) == NATURAL_V6_WORDMARK_SHA == bracket["capture"]["sha256"]
    assert bracket["ram_writes"] is False and bracket["assisted"] is False and bracket["input_injected"] is False
    vram_path = Path(bracket["vram"]["path"])
    vram = vram_path.read_bytes()
    primitives = []
    for frame in bracket["gp0_frames"]:
        offset = [0, 0]
        for entry in frame["entries"]:
            words = [int(x, 16) for x in entry["w"]]
            if entry["op"] == "0xE5":
                offset = [signed(words[0], 11), signed(words[0] >> 11, 11)]
            if entry["op"] != "0x2D":
                continue
            assert len(words) == 9
            tpage = words[4] >> 16
            depth = (tpage >> 7) & 3
            page = [(tpage & 15) * 64, ((tpage >> 4) & 1) * 256]
            uv = [[words[n] & 255, (words[n] >> 8) & 255] for n in (2, 4, 6, 8)]
            xy = [[signed(words[n], 16) + offset[0], signed(words[n] >> 16, 16) + offset[1]]
                  for n in (1, 3, 5, 7)]
            assert depth == 2 and page == [256, 256]
            assert uv == [[192, 0], [255, 0], [192, 255], [255, 255]]
            primitives.append({"frame": frame["frame"], "op": entry["op"], "raw_texture": True,
                "primitive_semi_enabled": False, "depth": depth, "texture_format": "direct_16bit_1555",
                "texpage": "0x%04X" % tpage, "page_xy_words": page, "uv_vertices": uv,
                "uv_bounds_inclusive": [192, 0, 255, 255],
                "uv_bounds_half_open": [192, 0, 256, 256], "xy_after_draw_offset": xy,
                "display_normalized_xy": [[x, y % 240] for x, y in xy],
                "guest_packet_address": entry["src"], "submission_pc": entry["pc"],
                "return_address": entry["ra"], "producer_pc_verified": False,
                "clut_used": False, "texture_orientation": "64x256 source strip rotated90degrees clockwise onto255x64 quad"})
    assert len(primitives) == 3
    page_raw = vram_rectangle(vram, 256, 256, 256, 256)
    strip_raw = vram_rectangle(vram, 448, 256, 64, 256)
    page_key = "%08X-00000000" % zlib.crc32(page_raw)
    strip_key = "%08X-00000000" % zlib.crc32(strip_raw)
    assert page_key == "F044D8BE-00000000" and strip_key == "5125FF82-00000000"
    rgba = bytearray()
    decoded = struct.unpack("<16384H", strip_raw)
    rotated_mask = bytearray(256 * 64)
    for index, word in enumerate(decoded):
        color = [(word & 31) << 3, ((word >> 5) & 31) << 3, ((word >> 10) & 31) << 3]
        rgba.extend(color + [0 if word == 0 else 255 if word & 0x8000 else 127])
        y, x = divmod(index, 64)
        rotated_mask[x * 256 + 255 - y] = 255 if max(color) > 24 else 0
    mask_image = Image.frombytes("L", (256, 64), bytes(rotated_mask)).resize((1024, 256), Image.Resampling.NEAREST)
    expected_mask = Image.new("L", (1280, 960))
    expected_mask.paste(mask_image, (128, 352))
    with Image.open(shot_path) as image:
        pixels = image.convert("RGB").tobytes()
    actual_mask = bytes(255 if max(pixels[i:i+3]) > 24 else 0 for i in range(0, len(pixels), 3))
    predicted = expected_mask.tobytes()
    intersection = sum(bool(a and b) for a, b in zip(actual_mask, predicted))
    dice = 2 * intersection / (sum(bool(x) for x in actual_mask) + sum(bool(x) for x in predicted))
    candidate_path = root / "candidate.json"
    candidate = json.loads(candidate_path.read_bytes())
    keys = {Path(x["name"]).stem for x in candidate["files"]}
    log_path = root / "native-v6-fighter-replay/capture.jsonl"
    log_bytes = log_path.read_bytes()
    lo, hi = bracket["capture"]["frame_before"], bracket["capture"]["frame_after"]
    matches = []
    for n, line in enumerate(log_bytes.splitlines(), 1):
        row = json.loads(line)
        if lo <= row.get("frame", -1) <= hi:
            matches.append({"line": n, "row": row})
    return {"status": "mapped_draw_source_region_rebuild_and_runtime_admission_pending",
        "visual_confirmation": {"capture": source_ref(shot_path), "observed": "Actual GAME OVER, teal outlined serif wordmark on black",
                                "same_shape_as_v5_reference": True,
                                "ram_writes": False, "assisted": False, "input_injected": False},
        "bracket": source_ref(bracket_path), "vram": source_ref(vram_path),
        "timing": {"screenshot": [lo, hi], "gp0": [x["frame"] for x in primitives],
                   "vram_frame": bracket["vram"]["frame"], "atomic": False,
                   "qualification": "GP0 overlaps screenshot bracket; later CPU VRAM source region independently decodes same wordmark, but GPU source/readiness admission is not established"},
        "primitives": primitives,
        "source": {"page_word_rect": [256, 256, 256, 256], "page_crc32": page_key[:8],
                   "page_key_candidate": page_key, "page_raw_sha256": sha(page_raw),
                   "sampled_strip_word_rect": [448, 256, 64, 256], "strip_crc32": strip_key[:8],
                   "strip_key_candidate": strip_key, "strip_raw_sha256": sha(strip_raw),
                   "direct_1555_decoded_rgba_sha256": sha(rgba), "clut": None,
                   "alpha_classes": dict(Counter(rgba[3::4])),
                   "palette_hash": "00000000", "palette_fades": "No indexed CLUT; inspect following subtractive untextured quad rather than invent palette variants",
                   "runtime_key_admission_verified": False,
                   "exact_source_alias_verification": "Strip is an exact crop of this snapshot; tracked upload identity and accepted alias mapping are not proven"},
        "geometric_cross_check": {"method": "Rotate decoded64x256 source mask clockwise, nearest4x, place at quad origin128,352; compare RGBmax>24 screenshot mask",
                                   "mask_dice": dice, "qualification": "Shape/location corroboration only; no appearance acceptance inferred from this metric"},
        "candidate_coverage": {"candidate": source_ref(candidate_path), "page_key_present": page_key in keys,
                               "strip_key_present": strip_key in keys,
                               "draw_records_in_visible_bracket": matches,
                               "source_log_snapshot": {"path": str(log_path), "bytes": len(log_bytes), "sha256": sha(log_bytes)},
                               "authored_wordmark_present_verified": False},
        "remediation": ["Archive GPU-authoritative exact used source words and runtime source query/upload identity",
                        "Author source-faithful wordmark contours in its exact64x256 rotated source region",
                        "Verify a stable strip upload alias and preserve unrelated native-page pixels",
                        "Test both alternating draw buffers; broad native-page self-reference rejection may affect the lower buffer even though actual sampled strip does not overlap destination",
                        "Preserve the following native subtractive fade quad and verify complete fade/results transition",
                        "Require actual final-candidate replacement admission plus fresh visible and motion review"],
        "live_verified": False}


def main():
    gp_path = EVIDENCE / "gameover-word-source-gp0.json"
    vr_path = EVIDENCE / "gameover-word-source-vram.json"
    gp = json.loads(gp_path.read_bytes())
    vr = json.loads(vr_path.read_bytes())
    shot_path = Path(gp["screenshot"]["path"])
    assert sha(shot_path.read_bytes()) == REVIEWED_SCREENSHOT_SHA == gp["screenshot"]["sha256"], "visual review screenshot changed"
    vram_path = Path(vr["dump"]["path"])
    vram = vram_path.read_bytes()
    assert len(vram) == 1024 * 512 * 2
    hud_path = AUDIT / "hud-restoration/candidate-20261112-coherent-v4/manifest.json"
    hud_assets = {x["key"]: x for x in json.loads(hud_path.read_bytes())["files"]}
    snapshots = []
    page_checks = {}
    op_counts = Counter()
    for frame in gp["frames"]:
        tpage, offset, texture_window = 0, [0, 0], None
        frame_sprites = []
        for command in frame["entries"]:
            op = int(command["op"], 16)
            op_counts[command["op"]] += 1
            words = [int(x, 16) for x in command["w"]]
            if op == 0xE1:
                tpage = words[0] & 0x1FF
            elif op == 0xE2:
                texture_window = words[0] & 0xFFFFF
            elif op == 0xE5:
                offset = [signed(words[0], 11), signed(words[0] >> 11, 11)]
            elif op == 0x67:
                depth = (tpage >> 7) & 3
                assert depth == 0 and texture_window == 0
                page_xy = [(tpage & 15) * 64, ((tpage >> 4) & 1) * 256]
                clut_word = words[2] >> 16
                clut_xy = [(clut_word & 63) * 16, clut_word >> 6]
                u, v = words[2] & 255, (words[2] >> 8) & 255
                width, height = words[3] & 0xFFFF, words[3] >> 16
                raw = vram_rectangle(vram, *page_xy, 64, 256)
                clut = vram_rectangle(vram, *clut_xy, 16, 1)
                key = "%08X-%08X" % (zlib.crc32(raw), zlib.crc32(clut))
                if key not in page_checks:
                    authored = hud_assets[key]
                    native_path = Path(authored["source"])
                    rgba = decode4(raw, clut)
                    with Image.open(native_path) as image:
                        native_equal = image.convert("RGBA").tobytes() == rgba
                    assert sha(raw) == authored["raw_sha256"]
                    assert sha(clut) == authored["clut_sha256"]
                    assert sha(native_path.read_bytes()) == authored["source_sha256"] and native_equal
                    page_checks[key] = {
                        "key": key, "page_xy_words": page_xy, "depth": depth,
                        "source_word_dimensions": [64, 256], "source_pixel_dimensions": [256, 256],
                        "clut_xy_words": clut_xy, "clut_words_le": ["%04X" % x for x in struct.unpack("<16H", clut)],
                        "raw_sha256": sha(raw), "clut_sha256": sha(clut),
                        "decoded_rgba_sha256": sha(rgba), "native_source": source_ref(native_path),
                        "raw_matches_verified_archived_source": True,
                        "clut_matches_verified_archived_source": True,
                        "independent_4bpp_decode_equals_native_png": native_equal,
                        "alpha_classes": dict(Counter(rgba[3::4])),
                        "alias_conclusion": "Exact canonical page/CLUT match; no alias required",
                    }
                screen_xy = [signed(words[1], 16) + offset[0], signed(words[1] >> 16, 16) + offset[1]]
                frame_sprites.append({
                    "sequence": command["seq"], "op": command["op"],
                    "guest_packet_address": command["src"],
                    "submission_pc": command["pc"], "return_address": command["ra"],
                    "producer_pc_verified": False,
                    "key_from_later_vram_snapshot": key, "page_xy_words": page_xy,
                    "depth": depth, "clut_xy_words": clut_xy,
                    "uv_half_open": [u, v, u + width, v + height],
                    "xy_after_draw_offset": screen_xy, "native_size": [width, height],
                    "coordinate_note": "VRAM drawing coordinates before active display-buffer origin normalization",
                    "draw_offset": offset, "semi_enabled": True,
                    "semi_mode": (tpage >> 5) & 3, "raw_texture": True,
                    "command_rgb": [words[0] & 255, (words[0] >> 8) & 255, (words[0] >> 16) & 255],
                })
        snapshots.append({"frame": frame["frame"], "sprites": frame_sprites})
    coverage = []
    for version in ("v5", "v6"):
        path = AUDIT / ("dev-center-evidence/hud-4k-candidate-20261112-" + version + "/candidate.json")
        candidate = json.loads(path.read_bytes())
        assets = {Path(x["name"]).stem: x for x in candidate["files"]}
        rows = []
        for key in page_checks:
            asset = assets.get(key)
            actual = sha(Path(asset["composed_path"]).read_bytes()) if asset else None
            rows.append({"key": key, "present": asset is not None,
                         "composed_sha256_matches": bool(asset and actual == asset["sha256"]),
                         "dimensions": asset["dimensions"] if asset else None,
                         "origin": asset["origin"] if asset else None})
        coverage.append({"version": version, "candidate": source_ref(path), "assets": rows,
                         "actual_replacement_submission_in_this_bracket_verified": False})
    reviewed_names = {
        "e2e-respawn-start-followup": "Actual GAME OVER wordmark, large teal serif outline on black",
        "e2e-post-gameover-current": "Total Evaluation screen, not the wordmark",
        "gameover-black-text-0": "Darkened Stage1 gameplay, not the wordmark",
        "gameover-black-text-1": "Darkened Stage1 gameplay, not the wordmark",
        "gameover-black-text-2": "Darkened Stage1 gameplay, not the wordmark",
        "gameover-map-fixture-game-entry": "ARM SELECTION, not gameplay or the wordmark",
        "gameover-word-source-actual": "START / overlapping 2 4FIGHTERS LEFT, not GAME OVER",
        "handoff-after-continue": "Stage1 gameplay after Continue, not the wordmark",
    }
    capture_review = []
    for name, observation in reviewed_names.items():
        receipt_path = EVIDENCE / "captures" / (name + ".json")
        receipt = json.loads(receipt_path.read_bytes())
        image_path = Path(receipt["path"])
        assert sha(image_path.read_bytes()) == receipt["sha256"]
        capture_review.append({"capture": source_ref(image_path), "receipt": source_ref(receipt_path),
                               "frame_bracket": [receipt["frame_before"], receipt["frame_after"]],
                               "visual_observation": observation,
                               "is_game_over_wordmark": name == "e2e-respawn-start-followup"})
    true_ref = next(x for x in capture_review if x["is_game_over_wordmark"])
    assert true_ref["capture"]["sha256"] == TRUE_WORDMARK_SHA
    low, high = true_ref["frame_bracket"]
    log_path = EVIDENCE / "native-live-gameplay/capture.jsonl"
    before, inside, after = [], [], []
    for line_number, line in enumerate(log_path.read_text().splitlines(), 1):
        entry = json.loads(line)
        frame = entry.get("frame", -1)
        witness = {"line": line_number, "frame": frame, "event": entry.get("event"), "key": entry.get("key")}
        if frame < low:
            before.append(witness)
        elif frame <= high:
            inside.append(witness)
        else:
            after.append(witness)
    assert not inside, "New wordmark-period draw evidence requires a fresh ownership review"
    true_ref.update({"pixel_bounds_rgb_max_gt_24_half_open": [158, 383, 1129, 569],
                     "normalized_bounds": [158 / 1280, 383 / 960, 1129 / 1280, 569 / 960],
                     "scene_matching_guidance": "Centered teal outlined serif GAME OVER on otherwise black; not START/life-count or Evaluation art",
                     "same_frame_source_map_available": False,
                     "source_capture_gap": {"capture_log": source_ref(log_path), "records_in_screenshot_bracket": 0,
                                            "nearest_previous_record": before[-1], "nearest_following_record": after[0]},
                     "later_vram_not_corresponding": {"receipt": source_ref(EVIDENCE / "post-gameover-vram.json"),
                                                       "frame": 46968,
                                                       "reason": "2786 frames after screenshot upper bracket; no wordmark ownership transfer is justified"}})
    result = {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "insufficient_evidence_for_game_over_wordmark",
        "game_actions": 0, "asset_mutations": 0,
        "visual_review": {"screenshot": source_ref(shot_path),
            "observed": "Black screen with START and overlapping 2 4FIGHTERS LEFT lettering",
            "is_game_over_wordmark": False,
            "finding": "Filename was assigned before visible state confirmation; it cannot establish GAME OVER ownership"},
        "bounded_v5_capture_review": capture_review,
        "confirmed_game_over_visual_reference": true_ref,
        "rejected_claims": ["The BDAE4156 sprites below are not proof of the GAME OVER wordmark",
                            "Animated 8E1A509D footer queries are not wordmark ownership evidence",
                            "Later CPU VRAM bytes plus earlier GP0 do not establish atomic renderer source authority"],
        "inputs": [source_ref(gp_path), source_ref(vr_path), source_ref(vram_path), source_ref(hud_path)],
        "capture_timing": {"screenshot_frame_bracket": [gp["screenshot"]["frame_before"], gp["screenshot"]["frame_after"]],
                           "gp0_frames": [x["frame"] for x in snapshots], "vram_frame": vr["dump"]["frame"],
                           "atomic": False, "qualification": gp["screenshot"]["scope"]},
        "actual_bracket": {"text_rendering": "Five raw semitransparent variable-size textured sprites per frame, GP0 0x67",
                           "other_geometry": "One black untextured semitransparent quad, GP0 0x2A; not letter geometry",
                           "op_counts": dict(op_counts), "frames": snapshots,
                           "native_page_palette_checks": list(page_checks.values()),
                           "coverage": coverage,
                           "semantic_mapping": [
                               {"uv_half_open": [136, 149, 215, 168], "observed_role": "START"},
                               {"uv_half_open": [0, 152, 99, 167], "observed_role": "FIGHTERS"},
                               {"uv_half_open": [200, 192, 248, 207], "observed_role": "LEFT"},
                               {"uv_half_open": [32, 192, 47, 207], "observed_role": "remaining-fighters digit 2"},
                               {"uv_half_open": [64, 192, 79, 207], "observed_role": "overlapping digit 4"}]},
        "game_over_mapping": {"rendering_type": None, "page": None, "depth": None,
                              "clut": None, "uv": None, "keys": [], "live_verified": False},
        "required_next_capture": [
            "Reach and visually confirm the actual GAME OVER wordmark in the isolated candidate",
            "Capture its complete visible fade/continue transition with same-frame draw/upload/source words and palette bracket",
            "Record screen coordinates, UV/CLUT and submission producer before assigning text ownership",
            "Compare exact native decode and aliases, then check replacement readiness and fresh final-candidate visible frames"],
        "verification": {"screenshot_hash_pinned": True, "native_page_and_palette_checks": len(page_checks),
                         "canonical_exact_source_keys": sorted(page_checks),
                         "game_over_mapping_accepted": False,
                         "true_game_over_visual_reference_found": True,
                         "true_wordmark_source_bracket_found": False,
                         "classification": "Successful evidence rejection; actual wordmark remains unmapped"},
    }
    natural_v6 = map_natural_v6()
    if natural_v6 is not None:
        result["status"] = "wordmark_source_region_mapped_runtime_key_admission_unverified"
        result["natural_v6_wordmark_mapping"] = natural_v6
        result["game_over_mapping"] = {
            "rendering_type": "raw_opaque_textured_quad_GP0_0x2D",
            "page": [256, 256], "depth": 2, "clut": None,
            "uv_half_open": [192, 0, 256, 256],
            "source_key_candidates": [natural_v6["source"]["page_key_candidate"],
                                      natural_v6["source"]["strip_key_candidate"]],
            "runtime_admitted_keys": [], "live_verified": False,
        }
        result["verification"].update(true_wordmark_source_bracket_found=True,
            true_wordmark_source_region_mapped=True,
            classification="Fresh unassisted v6 wordmark has mapped direct-color quad/region; runtime matching and rebuilt appearance remain unverified")
    output = AUDIT / "hud-restoration/gameover-wordmark-map.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(output), "status": result["status"], "verification": result["verification"]}))


if __name__ == "__main__":
    main()
