"""Map sampled live v6 description glyph UVs to authored and inherited paths.

No game calls or pack writes. Sampling does not census every printed glyph.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
LIVE = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6"
PARENT = "BDAE4156-B88C038E"
LABELS = {
    "resume-v6-fighter-mkii-settled": "Endymion MkII description and set weapons",
    "resume-v6-fighter-next-1": "Endymion MkIII description and set weapons",
    "resume-v6-fighter-next-2": "Astraea description and set weapons",
    "resume-v6-arm-selection-settled": "ARM specification plus Manipulator description",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_ref(path):
    return {"path": str(path), "sha256": sha(path.read_bytes())}


def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def main():
    font_path = AUDIT / "menu-restoration/font-strip-candidate-v6/manifest.json"
    candidate_path = LIVE / "candidate.json"
    hud_path = AUDIT / "hud-restoration/candidate-20261112-coherent-v4/manifest.json"
    font = json.loads(font_path.read_bytes())
    assets = {x["key"]: x for x in font["files"]}
    composed = {Path(x["name"]).stem: x for x in json.loads(candidate_path.read_bytes())["files"]}
    hud = {x["key"]: x for x in json.loads(hud_path.read_bytes())["files"]}
    parent_raw_path = Path(hud[PARENT]["source"]).with_suffix(".words.bin")
    parent_clut_path = Path(hud[PARENT]["source"]).with_suffix(".clut.bin")
    parent_raw, parent_clut = parent_raw_path.read_bytes(), parent_clut_path.read_bytes()
    assert sha(parent_raw) == hud[PARENT]["raw_sha256"]
    assert sha(parent_clut) == hud[PARENT]["clut_sha256"]
    aliases = {}
    for key, asset in assets.items():
        if not key.endswith("B88C038E"):
            continue
        row = asset.get("raw_parent", {}).get("native_row")
        if row is None:
            matches = [x for x in asset.get("all_raw_matches", []) if x["key"] == PARENT]
            row = matches[0]["native_row"] if matches else None
        if row is None:
            continue
        archive = asset.get("source_archives", {})
        raw_path = Path(archive["words"]["path"]) if "words" in archive else Path(asset["source"]).with_suffix(".words.bin")
        clut_path = Path(archive["clut"]["path"]) if "clut" in archive else Path(asset["source"]).with_suffix(".clut.bin")
        words, palette = raw_path.read_bytes(), clut_path.read_bytes()
        assert words == parent_raw[row * 128:(row + 8) * 128], key
        assert palette == parent_clut, key
        aliases[key] = {"parent": PARENT, "native_row": row, "raw_words_exact": True,
                        "clut_exact": True, "kind": asset["kind"],
                        "selected_native_regions": asset.get("selected_native_regions", []),
                        "raw_evidence": file_ref(raw_path), "clut_evidence": file_ref(clut_path)}
    log_path = LIVE / "native-v6-fighter-replay/capture.jsonl"
    log_bytes = log_path.read_bytes()
    records = [(n, json.loads(line)) for n, line in enumerate(log_bytes.splitlines(), 1)]
    glyphs, contexts = {}, []
    for label, observation in LABELS.items():
        receipt_path = LIVE / "captures" / (label + ".json")
        receipt = json.loads(receipt_path.read_bytes())
        image_path = Path(receipt["path"])
        assert sha(image_path.read_bytes()) == receipt["sha256"]
        lo, hi = receipt["frame_before"] - 60, receipt["frame_after"]
        context_ids = []
        for line, row in records:
            key = row.get("key", "")
            if not lo <= row.get("frame", -1) <= hi or row.get("event") != "replacement_gl_draw_submitted":
                continue
            if not (key.endswith("B88C038E") or key.endswith("678CA3BD")):
                continue
            # Native drawing buffers alternate by 240 lines. This is enough to
            # classify the observed text ROI, not an atomic screen registration.
            x, y = row["xy"][0]
            y %= 240
            arm = label.endswith("arm-selection-settled")
            role = ("arm_specification" if arm and 65 <= y < 100 and x < 140 else
                    "arm_manipulator_description" if arm and 190 <= y < 225 else
                    "fighter_description_or_equipment" if not arm and 85 <= y < 225 and x < 145 else None)
            if role is None:
                continue
            uv = row["uv_bounds"]
            uv_half = [uv[0], uv[1], uv[2] + 1, uv[3] + 1]
            item = assets.get(key)
            alias = aliases.get(key)
            source_local = [uv_half[0], uv_half[1], uv_half[2], uv_half[3]]
            parent_uv = uv_half.copy()
            if alias:
                source_local[1] -= alias["native_row"]
                source_local[3] -= alias["native_row"]
            elif key != PARENT and item and item.get("raw_parent"):
                source_local[1] -= item["raw_parent"]["native_row"]
                source_local[3] -= item["raw_parent"]["native_row"]
            selected = item.get("selected_native_regions", []) if item else []
            covered = any(contains(box, source_local) for box in selected)
            path_type = ("reconstructed_solid_glyph_field" if covered else
                         "inherited_full_page_hud" if key == PARENT else
                         "inherited_row88_hud_alias" if key == "913FE978-B88C038E" else
                         "outside_bounded_glyph_field")
            gid = key + ":" + ",".join(map(str, uv_half))
            context_ids.append(gid)
            if gid not in glyphs:
                glyphs[gid] = {"id": gid, "key": key, "native_uv_half_open": uv_half,
                    "source_local_uv_half_open": source_local, "observed_role": role,
                    "source_kind": row["source_kind"], "page_xy_words": row["page_xy"],
                    "clut_xy_words": row["clut_xy"], "depth": row["depth"],
                    "path_type": path_type, "fully_inside_authored_solid_field": covered,
                    "source_alias": alias,
                    "old_full_page_crosses_eight_row_boundary": key == PARENT and uv[1] // 8 != uv[3] // 8,
                    "candidate_asset": {k: composed[key][k] for k in ("origin", "sha256", "dimensions", "composed_path")},
                    "witnesses": []}
            glyphs[gid]["witnesses"].append({"capture_line": line, "frame": row["frame"],
                "context": label, "xy": row["xy"], "source_word_xy": row["source_word_xy"],
                "cpu_vram_may_be_stale": row.get("cpu_vram_may_be_stale"),
                "not_visibility_proof": row.get("not_visibility_proof")})
        contexts.append({"id": label, "visual_observation": observation,
                         "receipt": file_ref(receipt_path), "screenshot": file_ref(image_path),
                         "screenshot_bracket": [receipt["frame_before"], receipt["frame_after"]],
                         "sample_window": [lo, hi], "sampled_glyph_ids": sorted(set(context_ids))})
    result = {"schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "mixed_glyph_paths_source_mapped_repair_pending", "game_actions": 0,
              "inputs": [file_ref(font_path), file_ref(candidate_path), file_ref(hud_path),
                         {"path": str(log_path), "sha256_of_read_snapshot": sha(log_bytes), "bytes": len(log_bytes)}],
              "contexts": contexts, "source_row_aliases": aliases,
              "glyphs": sorted(glyphs.values(), key=lambda x: x["id"]),
              "findings": [
                  "Reconstructed 8-row descriptions cover x[0,64) and[192,256), preserving central logos.",
                  "Descender rectangles can cross8-row boundaries and resolve through inherited BDAE full-page HUD output instead of reconstructed strip aliases.",
                  "913FE978-B88C038E is the exact BDAE row88 alias; it remains an old HUD-style output and was excluded from the nine body repairs.",
                  "ARM specification rows use their bounded reconstructed fields; the lower Manipulator paragraph reuses the mixed description books.",
              ],
              "canonical_parent_repair_bounds": {
                  "key": PARENT, "coordinate_convention": "native source pixel half-open rectangles",
                  "continuous_rectangles": [[0, 32, 64, 104], [192, 32, 256, 104],
                                            [0, 112, 64, 120], [192, 112, 256, 120]],
                  "derivation": "Union of the nine previously authored description-row side columns plus exact source-row88 alias; adjacent rows share one continuous canonical field",
                  "explicitly_protected": ["Central x[64,192) logos/icons in every row",
                                           "Entire row band y[104,112) without a description-alias proof",
                                           "All pixels outside the four canonical rectangles"],
                  "minimum_exact_live_fallback_repairs": [[0, 48, 6, 57], [224, 88, 226, 98]],
                  "qualification": "Source-exact row identity and prior bounded authoring support the canonical field; this sampled capture alone does not enumerate every character"},
              "repair_recommendation": [
                  "Use one canonical source-faithful solid glyph field per actual source glyph UV, including its full descender height.",
                  "Patch only source-proven description glyph rectangles into BDAE4156-B88C038E, retaining all logos/icons/unrelated regions exactly.",
                  "Regenerate exact row aliases including913FE978-B88C038E from that same canonical authored glyph field and actual palette; preserve source-local UVs.",
                  "Keep ARM diagrams/right halves protected and validate specification glyph style separately.",
                  "Recompose a new isolated candidate and replay all three fighter descriptions plus ARM specs and lower paragraph; require actual draw and visual acceptance."],
              "limits": ["Sampled activation-forward capture is not every character draw; exact UV IDs are not independently decoded ASCII character names.",
                         "Screen ROI classification uses reviewed settled scenes and drawing-buffer normalization; source receipts are not atomic visible screenshots.",
                         "Repairing observed UVs alone is not proof of all fighter/weapon/menu glyph coverage."],
              "summary": {"sampled_unique_glyph_rectangles": len(glyphs),
                          "inherited_or_uncovered_rectangles": [x["id"] for x in glyphs.values() if not x["fully_inside_authored_solid_field"]],
                          "row_aliases_exact_raw_clut_verified": len(aliases)}}
    output = AUDIT / "hud-restoration/description-glyph-coverage.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(output), "status": result["status"], "summary": result["summary"]}))


if __name__ == "__main__":
    main()
