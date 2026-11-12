"""Read-only fleet/weapon/skin inventory audit; writes its two audit reports."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "remaster-audit/hud-restoration/fleet-weapon-skin-gap-audit-20261112.json"
EVIDENCE = ROOT / "remaster-audit/dev-center-evidence"


def read(relative):
    return json.loads((ROOT / relative).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item_file(item):
    if item.get("saved_path"):
        return Path(item["saved_path"])
    return ROOT / "windows-x64" / item["image"].removeprefix("/files/")


def main():
    enemy = read("windows-x64/tools/enemy_catalog.json")
    loadout = read("windows-x64/tools/loadout_catalog.json")
    if len(enemy["families"]) != 40 or len(loadout["ships"]) != 5 or len(loadout["gunpods"]) != 12:
        raise ValueError("Catalog inventory counts changed; review before publishing")
    mapping = read("remaster-audit/dev-center-evidence/skin-mapping.json")
    base = read("windows-x64/hd-textures/stage1-v1/manifest.json")
    ledger = read("remaster-audit/dev-center-evidence/stage1-coverage-ledger.json")
    aliases = read("remaster-audit/dev-center-evidence/skin-source-alias-audit.json")
    collection = read("windows-x64/tools/skin_collection/collection.json")
    equipment = read("windows-x64/tools/skin_collection/equipment-art.json")
    materials = read("windows-x64/tools/skin_collection/materials/materials.json")
    bosses = read("windows-x64/tools/skin_collection/bosses/boss-art.json")
    effects = read("windows-x64/tools/effects_catalog.json")
    cannon = read("remaster-audit/dev-center-evidence/cannon-isolated-fire-review.json")
    drache = read("remaster-audit/dev-center-evidence/drache-visual-source-review.json")
    greif = read("remaster-audit/dev-center-evidence/greif-material-isolation-review.json")
    player_review = read("remaster-audit/dev-center-evidence/targeted-stage1-filtered-20261112-1602/player-material-natural-expiry/visual-review.json")
    live_candidate = read("remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5/candidate.json")
    composition = read("remaster-audit/hud-restoration/final-composition-check.json")
    header = ROOT / "windows-x64/psxrecomp/runtime/src/hd_skin_material.h"
    profiles = re.findall(r'\{"([a-z0-9-]+)",\s+0x[0-9A-F]+u,\s+0x[0-9A-F]+u\}', header.read_text())
    if len(profiles) != 14:
        raise ValueError("Material profile contract changed; review it before claiming counts")
    errors, source_rows = [], []
    spec = importlib.util.spec_from_file_location("fleet_hud", ROOT / "windows-x64/tools/build_hud_ui_candidate.py")
    hud = importlib.util.module_from_spec(spec); spec.loader.exec_module(hud)
    installed = {a["key"]: a for a in base["files"]}
    env = live_candidate["launches"]["candidate"]["environment_overrides"]
    current_player = env["PSXRECOMP_SKIN_KEYS"].split(",")
    current_enemy = env["PSXRECOMP_SKIN_ENEMY_KEYS"].split(",")
    live_log = EVIDENCE / "hud-4k-candidate-20261112-v5/native-live-gameplay/capture.jsonl"
    live_rows = [json.loads(line) for line in live_log.read_text().splitlines()]
    for asset in mapping["assets"]:
        key = asset["key"]
        metadata, raw, clut = hud.verify_stock(Path(asset["source"]).parent, key)
        if hashlib.sha256(raw).hexdigest() != asset["raw_sha256"] or hashlib.sha256(clut).hexdigest() != asset["clut_sha256"] or sha(asset["source"]) != asset["source_sha256"]:
            errors.append("source identity changed: "+key)
        output = ROOT / "windows-x64/hd-textures/stage1-v1/einhander-texture-replacements" / (key+".png")
        if sha(output) != installed[key]["sha256"]:
            errors.append("installed output changed: "+key)
        receipts = [r for r in live_rows if r.get("key") == key]
        counts = Counter(r["event"] for r in receipts)
        first = asset["observed_draw_receipts"][0]
        source_rows.append({"key": key, "observed_owner": asset["observed_owner"],
            "source_crc32": key[:8], "clut_crc32": key[9:], "source_size": asset["source_size"],
            "source_fragments": metadata["fragments"], "clut_xy": metadata["clut_xy"],
            "source_path": asset["source"], "raw_sha256": asset["raw_sha256"], "clut_sha256": asset["clut_sha256"],
            "source_crc_clut_decode_verified_now": True,
            "output_path": str(output), "output_sha256": installed[key]["sha256"], "output_size": list(Image.open(output).size),
            "output_hash_verified_now": True, "output_method": installed[key]["method"],
            "configured_material_channel": "player" if key in mapping["player_keys"] else "enemy",
            "included_in_v5_explicit_material_keys": key in current_player+current_enemy,
            "sample_page_space_uv_bounds": first["uv_bounds"],
            "sample_receipt": {"path": first["path"], "line": first["line"], "frame": first["frame"], "event": first["event"]},
            "v5_retained_query_count": counts["source_draw_query_matched"], "v5_retained_gl_submission_count": counts["replacement_gl_draw_submitted"],
            "v5_observed_profiles": sorted({r.get("material_profile", "missing") for r in receipts}),
            "named_model_id_verified": False, "part_or_weapon_exclusivity_verified": False, "cross_stage_exclusivity_verified": False})
    sizes = Counter()
    for file in base["files"]:
        path = ROOT / "windows-x64/hd-textures/stage1-v1/einhander-texture-replacements" / (file["key"]+".png")
        if not path.exists():
            errors.append("missing baseline file: "+file["key"])
        else:
            sizes[Image.open(path).size] += 1
    art_checks = []
    for category, rows in (("signature_finish_concepts", collection["skins"]), ("equipment_concepts", equipment["items"]),
                           ("reusable_rgb_detail_maps", materials["maps"]), ("boss_concepts", bosses["items"])):
        for item in rows:
            path = item_file(item)
            if not path.exists() or sha(path) != item["sha256"]:
                errors.append("art hash/file mismatch: "+str(path))
                continue
            dimensions = list(Image.open(path).size)
            if dimensions != [item["width"], item["height"]]:
                errors.append("art dimensions mismatch: "+str(path))
            art_checks.append({"category": category, "id": item.get("id", item.get("entity_id")), "path": str(path),
                               "sha256": item["sha256"], "dimensions": dimensions})
    review_hash_checks = []
    for sample in player_review["screenshots"]:
        matches = sha(sample["path"]) == sample["sha256"]
        review_hash_checks.append({"path": sample["path"], "sha256_matches": matches})
        if not matches:
            errors.append("player review screenshot changed: "+sample["path"])
    enemy_roster = [{"id": r["id"], "name": r["name"], "kind": r["kind"],
                     "mapping_status": r["mapping"]["status"], "named_runtime_model_verified": False,
                     "complete_4k_uv_skin_verified": False} for r in enemy["families"]]
    player_roster = []
    for ship in loadout["ships"]:
        player_roster.append({"id": ship["id"], "name": ship["name"], "availability": ship["availability"],
                             "mapping": ship["mapping"], "named_runtime_model_verified": False,
                             "observed_material_candidate": "five blue/yellow player keys; Endymion Mk.II visually selected/observed, part identity unpartitioned" if ship["id"] == "endymion_mk2" else None,
                             "concept_art_available": ship["id"] in {i["entity_id"] for i in equipment["items"]},
                             "complete_4k_uv_skin_verified": False, "builtin_weapon": ship["built_in_weapon"]})
    gunpods = []
    for pod in loadout["gunpods"]:
        task = next(r for r in ledger["tasks"] if r["id"] == "gunpod_"+pod["id"])
        gunpods.append({"id": pod["id"], "name": pod["name"], "availability": pod["availability"],
                       "concept_art_available": True, "ledger_evidence_tier": task["evidence_tier"],
                       "independent_uv_material_binding_verified": False, "runtime_type_or_slot_address_verified": False,
                       "complete_authored_4k_weapon_skin_verified": False,
                       "narrow_runtime_evidence": "two Cross-only shots and HUD15→14→13 observed; projectile and source ownership unresolved" if pod["id"] == "cannon" else "HUD identity observed; isolated Wasp fire attempt not accepted" if pod["id"] == "wasp" else None})
    inputs = ["windows-x64/tools/enemy_catalog.json", "windows-x64/tools/loadout_catalog.json",
              "windows-x64/tools/effects_catalog.json", "windows-x64/tools/research_catalog.json",
              "windows-x64/hd-textures/stage1-v1/manifest.json", "windows-x64/psxrecomp/runtime/src/hd_skin_material.h",
              "windows-x64/tools/skin_collection/collection.json", "windows-x64/tools/skin_collection/equipment-art.json",
              "windows-x64/tools/skin_collection/materials/materials.json", "windows-x64/tools/skin_collection/bosses/boss-art.json",
              "remaster-audit/dev-center-evidence/skin-mapping.json", "remaster-audit/dev-center-evidence/skin-source-alias-audit.json",
              "remaster-audit/dev-center-evidence/stage1-coverage-ledger.json", "remaster-audit/dev-center-evidence/cannon-isolated-fire-review.json",
              "remaster-audit/dev-center-evidence/greif-material-isolation-review.json", "remaster-audit/dev-center-evidence/drache-visual-source-review.json",
              "remaster-audit/dev-center-evidence/targeted-stage1-filtered-20261112-1602/player-material-natural-expiry/visual-review.json",
              "remaster-audit/hud-restoration/final-composition-check.json", "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5/candidate.json"]
    report = {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "game_actions": 0,
        "scope": "Read-only audit of saved catalogs, original-source identities, installed atlas files, material code, retained runtime draws and explicit reviews; report is the only output.",
        "summary": {"playable_hull_inventory": 5, "primary_starter_hulls": 3, "reported_secret_hulls": 2,
                    "named_gunpod_inventory": 12, "common_manual_gunpods": 8, "reported_secret_gunpods": 4,
                    "gallery_named_enemy_model_groups": 40, "boss_or_midboss_groups": 12, "other_enemy_groups": 28,
                    "exact_total_runtime_enemy_types": None, "exact_aircraft_only_count": None,
                    "authoritative_named_model_uv_bindings": 0, "complete_authored_per_model_4k_skins_verified": 0,
                    "observed_atlas_material_groups": 2, "source_verified_player_keys": 5, "source_verified_enemy_strip_keys": 6,
                    "current_v5_explicit_player_material_keys": len(current_player), "current_v5_explicit_enemy_material_keys": len(current_enemy),
                    "locally_reviewed_player_palette_switch_scene": 1, "fully_skinned_bosses_accepted": 0,
                    "independent_gunpod_texture_or_shot_bindings_verified": 0, "full_stage1_accepted": False,
                    "later_stage_or_cross_stage_skin_acceptance": False, "all_ships_complete": False},
        "inventory": {"players": player_roster, "gunpods": gunpods, "enemy_groups": enemy_roster,
                      "enemy_count_definition": enemy["summary"]["definition"], "enemy_kind_counts": enemy["summary"]["kind_counts"],
                      "uncensused": ["Unnamed and spawn-only variants", "Background actors and hazards", "Large Stage6 objective spacecraft", "Detachable boss weapons/armor/engine and damage states", "Enemy projectiles and procedural/untextured effects", "Alternate routes and later-stage population"]},
        "source_and_runtime_bindings": source_rows,
        "baseline_pack": {"path": str(ROOT / "windows-x64/hd-textures/stage1-v1/manifest.json"), "files": len(base["files"]),
                          "neural_rgb_processed_entries": sum(bool(f.get("neural_detail")) for f in base["files"]),
                          "pixel_preserving_entries": sum(not bool(f.get("neural_detail")) for f in base["files"]),
                          "dimensions_header_verified": {f"{w}x{h}": n for (w, h), n in sorted(sizes.items())},
                          "all_manifest_files_present": sum(sizes.values()) == len(base["files"]),
                          "full_4096_square_entries": sizes[(4096, 4096)],
                          "interpretation": "File counts are texture/palette entries across UI, scenery, actors and effects. Neural upscaling and long4096px strips are not complete hand-authored 4K craft or named model counts. Full 964 output hashes were not rechecked here; all 11 scoped actor outputs were."},
        "skin_assets": {"runtime_palette_profiles": profiles, "runtime_palette_profile_count": len(profiles),
                        "signature_finish_concepts": len(collection["skins"]), "equipment_concepts": len(equipment["items"]),
                        "equipment_composition": {"starter_hulls": 3, "gunpods": 12, "enemy_schabe": 1},
                        "boss_concepts": len(bosses["items"]), "reusable_rgb_detail_maps": len(materials["maps"]),
                        "concept_dimensions": [1672, 941], "detail_map_dimensions": [1254, 1254],
                        "art_hash_dimension_checks": art_checks,
                        "limitations": ["Concept artwork is not a UV-compatible installed model skin.", "Fourteen runtime RGB transforms do not constitute14 fully mapped skins per ship.", "Six detail maps are optional RGB shader microdetail; no PBR channels, true emission or new mesh/physics are established.", "Actual concept and detail dimensions are below native4K; no resolution enlargement is misreported as generation detail."]},
        "reviewed_acceptance": {"player_local": player_review["acceptance"], "player_review_screenshot_hashes": review_hash_checks,
                                "greif": greif["acceptance"], "drache": {"phase_review": drache["phase_review"],
                                    "source_candidates": drache["prospective_source_bindings"]["strong_candidates"],
                                    "full_finish_accepted": False, "source_binding_status": "candidate_only_not_apply_allowlist"},
                                "cannon": cannon["controlled_fire_acceptance"], "effect_catalog": effects["summary"]},
        "boss_source_candidates": {"alias_summary": aliases["summary"],
                                   "candidate_native_atlases": aliases["atlas_families"],
                                   "important_limits": ["111 exact native-page/upload-strip matches are layout evidence, not 111 bosses or actor ownership.", "Greif eight-key Gold/Lime probe affected small trim; large blue torso/head/base remained blue. Full skin NOT_ACCEPTED.", "Drache candidate families635768EB/8D0FC0AD/01C0DA70 remain unpartitioned and palette variants incomplete.", "No permanent named boss allowlist exists in the material header."]},
        "known_address_evidence": {"cannon_ammo_candidates": cannon["repeated_ram_candidates"], "interpretation": cannon["candidate_interpretation"],
                                   "verified_model_entity_ids": [], "verified_ship_selector_addresses": [], "verified_gunpod_type_or_slot_addresses": [],
                                   "note": "0x80084832 and 0x80084834 tracked 15→14→13 locally; width, mirroring, ownership and write/freeze safety remain unvalidated. VRAM fragment addresses above are capture placements, not stable actor structures."},
        "coverage_ledger_snapshot": {"summary": ledger["summary"], "acceptance_gaps": ledger["acceptance_gaps"],
                                    "note": "Historical finalized Stage1 ledger counts are bounded source/draw evidence, not a census of later stages or new UI recorders."},
        "fresh_v5_actor_draws": {"log": str(live_log), "sha256": sha(live_log), "records": len(live_rows),
                                "event_counts": dict(Counter(r["event"] for r in live_rows)),
                                "note": "Sampled query/GL receipts identify source keys and selected shader channels, not actors. Zero rows for a key means not retained in this segment, not proof it never renders."},
        "ui_candidate_separation": {"composition_check": str(ROOT / "remaster-audit/hud-restoration/final-composition-check.json"),
                                    "composition_ok": composition["ok"], "candidate_key_count": composition["final_count"],
                                    "preparation_performed": composition["preparation_performed"], "live_accepted": False,
                                    "recorded_v5_key_count": live_candidate["final_count"],
                                    "overlay_source_counts": composition["source_counts"],
                                    "meaning": "The 1011-key composition check is HUD/menu/illustration work, not fleet material coverage; at this snapshot preparation_performed isfalse and v6 candidate manifest is absent. No new named actor allowlist is introduced."},
        "remaining_action_plan": [
            {"order": 1, "action": "Finish actual actor census across every route/stage, starter/secret craft and equipment state", "deliverable": "Named model/spawn/part table, including unnamed/small craft, large craft, bosses and damage variants; mark unknown identities", "gate": "Do not treat40 gallery groups as the exhaustive runtime total"},
            {"order": 2, "action": "Map each actor and weapon independently to complete sourceCRC+CLUT+UV bindings", "deliverable": "Source words/palette integrity, page/upload aliases, exact UV regions, model-part ownership and shared-key exclusions", "gate": "Capture one subject/state with bracketing screenshot+GP0+VRAM and clean weapon-only/no-fire controls"},
            {"order": 3, "action": "Author source-faithful high-resolution hull, built-in gun, Gunpod and boss-part textures", "deliverable": "UV-compatible artwork with deliberate surface detail, preserved livery and categorical alpha, per-model finish variants", "gate": "A concept sheet, uniform recolor or large pixel dimensions alone is insufficient"},
            {"order": 4, "action": "Integrate exact verified bindings into a separate reversible gameplay candidate", "deliverable": "Per-model/channel selector, palette/animation coverage, alpha and material test receipts, unchanged unrelated actors/UI", "gate": "Resolve shared atlas contamination and missing native-page/animated palette variants before broad allowlists"},
            {"order": 5, "action": "Complete actual gameplay acceptance for every mapped model/weapon/finish", "deliverable": "Bright/dark, rear/underside/pose, equip/drop/swap, fire/hit/destruction, boss phases, stage/route transitions and rollback evidence", "gate": "Only explicit per-item accepted rows count complete; keep remaining rows open"}],
        "input_provenance": [{"path": str(ROOT / p), "sha256": sha(ROOT / p)} for p in inputs],
        "verification": {"source_crc_clut_decode_and_installed_hash_checks": len(source_rows), "art_hash_and_dimension_checks": len(art_checks),
                         "player_review_screenshot_hash_checks": len(review_hash_checks), "errors": errors, "pass": not errors},
        "claim_limits": ["CRC/source key, CLUT variant, atlas strip, image file and model identity are different counts.",
                         "Local palette-change acceptance does not verify full model ownership, surface artwork, all player ships, enemies, weapons or stages.",
                         "Small/large aircraft count, exhaustive spawn census and later-stage4K coverage remain unknown; no global percentage is inferred.",
                         "No game/process/UI/network operation or asset/material mutation was performed by this audit."]}
    detailed = OUT.with_name("fleet-weapon-skin-gap-evidence-20261112.json")
    detailed.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    concise = {
        "schema_version": 1, "generated_at_utc": report["generated_at_utc"], "game_actions": 0,
        "scope": report["scope"], "summary": report["summary"],
        "root_facts": [
            "Five playable identities are cataloged: Endymion Mk.II/Mk.III, Astraea Mk.I and two reported secret hulls. None has an authoritative complete named model/part UV binding.",
            "Twelve named Gunpods have original-reference identities and concept studies; independent weapon texture, type/slot, muzzle/projectile/impact bindings remain unverified. Cannon has two narrowly accepted isolated Cross trials only.",
            "Forty gallery-derived enemy groups include 12 bosses/midbosses and 28 other combat models, including walkers, trains and emplacements. This is not an aircraft-only count or an exhaustive spawn census.",
            "The actual material mapping is five aggregate player texture keys plus six strips of one observed green/orange enemy family, probably Schabe. Named actor IDs, per-part ownership and cross-stage exclusivity remain unresolved.",
            "The explicit v5 launch selects four player keys and six enemy keys. The fifth mechanical-player key is stock in this launch; header support for five keys does not mean five are active.",
            "Player atlas outputs are 1024x1024; the six enemy strips are 4096x128. These are neural RGB upscales, not proof of complete newly authored 4K ships.",
            "The baseline 964 entries include 311 neural RGB entries and 653 pixel-preserving entries; there are zero 4096-square baseline PNGs. File/palette counts do not equal craft counts.",
            "Fourteen finish concepts, 16 equipment concepts, 2 boss concepts and 6 reusable 1254-square detail maps exist. They are not per-model UV skins. All 38 artwork hashes/dimensions were checked.",
            "A visible local player stock/Gold/Neon color test passed, but complete poses/parts/lighting/cross-stage quality remains pending. Greif full skin was explicitly NOT_ACCEPTED; Drache and later bosses have candidate sources only.",
            "The 1011-key composition check is separate HUD/menu/illustration work. Its recorded preparation_performed flag is false and live acceptance is false; it does not add fleet material ownership."],
        "verified_atlas_sources": [{k: row[k] for k in ["key", "observed_owner", "source_size", "source_fragments", "clut_xy", "output_size",
            "included_in_v5_explicit_material_keys", "sample_page_space_uv_bounds", "sample_receipt", "v5_retained_gl_submission_count"]} for row in source_rows],
        "known_addresses": report["known_address_evidence"],
        "boss_candidates": {"native_families": [a["family"] for a in aliases["atlas_families"]],
                            "exact_upload_aliases": aliases["summary"]["exact_atlas_upload_aliases"],
                            "aliases_with_GL_receipts": aliases["summary"]["aliases_with_replacement_submission"],
                            "ownership_verified": False, "complete_boss_skins_accepted": 0},
        "uncensused": report["inventory"]["uncensused"],
        "remaining_action_plan": report["remaining_action_plan"],
        "verification": report["verification"],
        "detailed_evidence": {"path": str(detailed), "sha256": sha(detailed),
                              "contents": "Full 40-enemy/5-player/12-Gunpod roster, eleven CRC/CLUT/PNG/hash bindings, 38 art checks, explicit reviews, current UI composition and hashed input provenance"},
        "claim_limits": report["claim_limits"]}
    OUT.write_text(json.dumps(concise, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "sha256": sha(OUT), "summary": report["summary"], "verification": report["verification"]}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
