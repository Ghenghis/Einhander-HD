"""Build an evidence-gated seed register; never infer object coverage from PNG counts.

Run from any directory: python -B remaster-audit/build_component_register.py
This reads retained evidence and writes component-register.json only. It does not
drive the game, modify packs, or promote historical live observations to v6.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
STATES = ["unmapped", "mapped", "rebuilt", "integrated", "live-verified"]
KEY = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{8}$")
INPUTS = {
    "loadout": ROOT / "windows-x64/tools/loadout_catalog.json",
    "enemy": ROOT / "windows-x64/tools/enemy_catalog.json",
    "effects": ROOT / "windows-x64/tools/effects_catalog.json",
    "fleet_audit": AUDIT / "hud-restoration/fleet-weapon-skin-gap-audit-20261112.json",
    "world_audit": AUDIT / "background-audit-20261112/stage1-background-gap-inventory.json",
    "ui_audit": AUDIT / "hud-restoration/e2e-coverage.json",
    "hud_map": AUDIT / "hud-restoration/hud-semantic-map.json",
    "menu_map": AUDIT / "menu-restoration/menu-semantic-map.json",
    "candidate": AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6/candidate.json",
    "composition": AUDIT / "hud-restoration/final-composition-check.json",
}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ref(path: Path, selector: str | None = None) -> dict:
    value = {"path": str(path.resolve()), "sha256": sha(path)}
    if selector is not None:
        value["selector"] = selector
    return value


def load_inputs():
    return {key: json.loads(path.read_text(encoding="utf-8-sig")) for key, path in INPUTS.items()}


def record(component_id, name, category, source_ref, required_states, **extra):
    result = {
        "id": component_id, "name": name, "category": category,
        "record_kind": "semantic_component", "status": "unmapped",
        "model_part": None, "stage": None, "placements": [],
        "identity_evidence": [source_ref],
        "ownership": {"confidence": "unverified", "runtime_actor_id": None,
                      "verified_complete_source_binding": False,
                      "shared_source_exclusions_verified": False},
        "source": {"disc_archive_location": None, "guest_upload_address": None,
                   "producer_pc": None, "vram_page_xy_words": None,
                   "word_rect": None, "depth": None, "texture_keys": [],
                   "clut_xy_words": None, "uv_bounds": None,
                   "uv_convention": None, "blend_mode": None,
                   "transparency_classes": None, "technical_source_refs": [],
                   "binding_evidence": []},
        "animation": {"ordered_sequence": [], "complete_loop_verified": False,
                      "palette_variants_are_not_frame_count": True},
        "authoring": {"asset_version": None, "hashes": [], "dimensions": [],
                      "protected_bounds": [], "changed_coverage": None,
                      "composition_lineage": []},
        "gates": {"mapping": False, "rebuild": False,
                  "integration": False, "live_verification": False},
        "states": [{"id": component_id + "/" + s, "status": "unmapped",
                    "evidence": [], "defects": [], "required": True}
                   for s in required_states],
        "live_evidence": [], "historical_observations": [],
        "remaining": ["Verify complete source/UV/CLUT ownership with native draw and visible brackets"],
        "defects": ["complete_ownership_unverified"],
    }
    result.update(extra)
    return result


def status_for(gates):
    result = "unmapped"
    for gate, status in zip(["mapping", "rebuild", "integration", "live_verification"], STATES[1:]):
        if not gates[gate]:
            break
        result = status
    return result


def build():
    data = load_inputs()
    components = []
    for ship in data["loadout"]["ships"]:
        sr = ref(INPUTS["loadout"], "ships[id=" + ship["id"] + "]")
        hull = record("player/" + ship["id"] + "/hull", ship["name"], "player_hull", sr,
                      ["all_parts_and_poses", "damage_and_destruction", "lighting_and_stage_contexts"],
                      availability=ship["availability"], identity_reference=ship.get("art_reference"))
        hull["remaining"] += ["Partition hull, armor, engines, trim, glow and shared weapon atlas regions",
                              "Observe upper/lower/rear poses and stage/route reuse"]
        components.append(hull)
        gun = record("player/" + ship["id"] + "/built-in-weapon",
                     ship["name"] + ": " + ship["built_in_weapon"]["name"], "built_in_weapon", sr,
                     ["model_and_mounts", "idle_no_fire", "firing", "muzzle_projectile_impact"],
                     parent_component=hull["id"], specification=ship["built_in_weapon"])
        components.append(gun)
    for pod in data["loadout"]["gunpods"]:
        components.append(record("gunpod/" + pod["id"], pod["name"], "gunpod",
            ref(INPUTS["loadout"], "gunpods[id=" + pod["id"] + "]"),
            ["model", "upper_mount", "lower_mount", "reserve", "swap_drop_pickup",
             "firing", "ammo_empty_and_rollover", "damage_and_destruction"],
            availability=pod["availability"], identity_reference=pod.get("art_reference")))
    for enemy in data["enemy"]["families"]:
        components.append(record("enemy/" + enemy["id"], enemy["name"], "enemy_model",
            ref(INPUTS["enemy"], "families[id=" + enemy["id"] + "]"),
            ["spawn_and_all_parts", "poses_and_attack", "damage_and_destruction", "stage_route_variants"],
            enemy_kind=enemy["kind"], identity_reference=enemy.get("art_reference"),
            gallery_variants=enemy.get("variants", []),
            catalog_mapping_observation=enemy.get("mapping"),
            boss_phases={"required": enemy["kind"] == "boss_or_midboss",
                         "enumeration_complete": False, "known_phase_records": []}))

    # The technical index has independent units and cannot enter semantic totals.
    technical = []
    world = data["world_audit"]
    for family in world["family_inventory"]:
        crc = family["texture_crc32"]
        technical.append({
            "id": "source/world/" + crc, "record_kind": "technical_source_family",
            "texture_crc32": crc, "semantic_owner": None,
            "semantic_ownership_verified": False,
            "content_review": family["source_content_review"],
            "source_keys": family["known_queue_palette_keys"],
            "missing_from_v6_keys_at_audit": family["known_queue_keys_absent_current_candidate"],
            "sample_source": family["sample_source"],
            "raw_clut_decode_checks": {"result": family["source_check"],
                "checked_variant_count": family["independently_checked_original_sources"],
                "evidence_scope": "prior_saved_audit_not_reexecuted_source_decode"},
            "draw_witnesses": family["exact_draw_witness_examples"],
            "protected_regions": family["protected_native_uv_rectangles_half_open"],
            "protected_coordinate_convention": world["protected_regions"]["coordinate_convention"],
            "evidence": ref(INPUTS["world_audit"], "family_inventory[texture_crc32=" + crc + "]"),
            "does_not_count_as": ["sign", "building", "layer", "animation_loop", "complete_actor"],
        })
    for observed in data["fleet_audit"]["verified_atlas_sources"]:
        technical.append({"id": "source/fleet/" + observed["key"],
                          "record_kind": "technical_source_binding",
                          "semantic_owner": None, "named_model_ownership_verified": False,
                          "observation": observed,
                          "evidence": ref(INPUTS["fleet_audit"],
                                          "verified_atlas_sources[key=" + observed["key"] + "]")})
    for effect in data["effects"]["families"]:
        technical.append({"id": "source/effect/" + effect["texture_hash"],
            "record_kind": "technical_source_family", "semantic_owner": None,
            "source_keys": effect["variant_keys"], "source_dimensions": effect["source_dimensions"],
            "confidence": effect["confidence"], "alpha_contract": effect["alpha_contract"],
            "draw_witnesses": effect["representative_receipt_examples"],
            "ordered_animation_verified": False,
            "evidence": ref(INPUTS["effects"], "families[id=" + effect["id"] + "]")})

    # Exact-key + reviewed UV UI components may advance to integration in the
    # isolated prepared pack. Actual v6 replay remains a separate false gate.
    exact_ui = {"title_illustration_wordmark", "copyright_square_footer",
                "fighter_blueprint_hull_engine", "results_aircraft_poster"}
    composed = {Path(x["name"]).stem: x for x in data["candidate"]["files"]}
    for previous in data["ui_audit"]["components"]:
        cid = previous["id"]
        row = record("ui/" + cid, cid.replace("_", " "), "ui_component",
                     ref(INPUTS["ui_audit"], "components[id=" + cid + "]"),
                     ["all_registered_display_states", "palette_and_motion", "final_v6_replay"])
        row["historical_observations"] = [previous]
        row["source"]["binding_evidence"] = previous["observed_evidence"]
        row["source"]["uv_bounds"] = previous["known_native_uv"]
        row["remaining"] = previous["remaining_acceptance"] + ["Close comprehensive state-level gates for this component"]
        if cid in exact_ui:
            keys = previous["source_identity"]
            assert all(KEY.fullmatch(key) for key in keys), cid
            row["source"]["texture_keys"] = keys
            row["source"]["uv_convention"] = "as recorded in linked UI audit; do not conflate inclusive and half-open"
            row["ownership"].update(confidence="documented_bounded_ui_regions",
                                    verified_complete_source_binding=True)
            row["gates"].update(mapping=True, rebuild=True)
            checks = []
            for key in keys:
                asset = composed.get(key)
                path = Path(asset["composed_path"]) if asset else None
                checks.append({"key": key, "path": str(path) if path else None,
                               "expected_sha256": asset["sha256"] if asset else None,
                               "actual_sha256": sha(path) if path and path.is_file() else None,
                               "dimensions": asset["dimensions"] if asset else None})
            row["gates"]["integration"] = all(x["actual_sha256"] == x["expected_sha256"]
                                                       and x["actual_sha256"] for x in checks)
            row["authoring"].update(asset_version="prepared_ui_v6",
                                   hashes=checks,
                                   composition_lineage=[ref(INPUTS["candidate"]), ref(INPUTS["composition"])])
            row["defects"] = ["final_v6_live_replay_and_complete_states_pending"]
        elif cid == "gp_green_plates":
            row["gates"]["mapping"] = True
            row["source"].update(producer_pc=None, texture_keys=[], uv_bounds=None,
                                  binding_kind="documented_untextured_GP0_0x3A_Gouraud_quad")
            row["ownership"].update(confidence="documented_procedural_component",
                                    verified_complete_source_binding=True)
            row["defects"] = ["art_direction_and_remaining_color_slot_states_unaccepted"]
        row["status"] = status_for(row["gates"])
        # Parent status describes bounded assets; these states remain pending and
        # are mandatory for live verification, including unchanged title assets.
        components.append(row)

    # Unknown component totals are work queues, never fictional census records.
    queues = []
    def queue(qid, name, scope, source_refs, required):
        queues.append({"id": "sweep/" + qid, "record_kind": "discovery_queue", "name": name,
                       "status": "open", "scope": scope, "component_total": None,
                       "enumeration_complete": False, "source_refs": source_refs,
                       "required_evidence": required, "accepted_passes": []})
    for qid, title in [
        ("sign-designs-and-placements", "Every sign design, wording and placement"),
        ("building-designs-and-surfaces", "Building facades, surface types and occlusion"),
        ("sky-parallax-background-layers", "Sky, distant/middle/foreground layers and parallax"),
        ("windows-rooftop-lighting", "Window patterns, beacons, reflections and procedural lights"),
        ("environment-animation", "Complete sign/light/palette/upload/scroll sequences"),
    ]:
        queue(qid, title, "Every stage and route; Stage1 mixed technical families are starting evidence only",
              ["source/world/" + x["texture_crc32"] for x in world["family_inventory"]],
              ["Visible native route/camera bracket", "Exact source+CLUT+UV or procedural draw ownership",
               "Separate unique design and placement IDs", "Complete timed loop and transition evidence"])
    for qid, title in [
        ("stages-and-routes", "Enumerate every stage, alternative route and transition"),
        ("unnamed-and-small-actors", "Unnamed/spawn-only/small/distant/occluded actors and hazards"),
        ("large-objectives-and-shared-parts", "Large objectives, shared parts and detachable geometry"),
        ("weapon-effects", "Muzzle flashes, projectiles, beams, trails, hits and explosions"),
        ("pickups-and-equipment-states", "Pickups, arm switching, ammo and durability extremes"),
        ("unlock-gallery-end-states", "Legitimate unlocks, Gallery, endings and credits"),
        ("intro-and-video", "Boot, story and video source classification and treatment"),
        ("independent-omissions", "Compare complete raw draw/upload census with registered components"),
    ]:
        queue(qid, title, "Full game; no full-game completed sweep exists in checked evidence", [],
              ["Named semantic/state inventory with source and visible brackets",
               "Two complete repeated post-repair sweeps with no newly unclassified component"])
    for enemy in data["enemy"]["families"]:
        if enemy["kind"] == "boss_or_midboss":
            queue("boss-phases/" + enemy["id"], enemy["name"] + ": enumerate all phases and parts",
                  "Boss spawn, attacks, transformations, damage and destruction",
                  ["enemy/" + enemy["id"]],
                  ["Phase IDs and transition conditions from observed runtime",
                   "Per-part source/UV/CLUT ownership and complete phase motion"])
    journeys = [{"id": "journey/" + x["id"], "record_kind": "acceptance_journey",
                 "status": "pending_final_candidate", "historical_status": x["status"],
                 "expected": x["expected"], "historical_evidence": x.get("screenshot_evidence", []),
                 "remaining": x.get("remaining_acceptance", []), "final_candidate_verified": False,
                 "evidence": ref(INPUTS["ui_audit"], "screen_states[id=" + x["id"] + "]")}
                for x in data["ui_audit"]["screen_states"]]
    result = {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress_seed_inventory_not_exhaustive", "game_actions": 0,
        "candidate_scope": "isolated prepared hud-4k-candidate-20261112-v6",
        "provenance": {key: ref(path) for key, path in INPUTS.items()},
        "state_order": STATES,
        "gate_contract": {
            "mapped": "Complete bounded semantic ownership with source+CLUT+UV or documented procedural draw; named art identity alone fails",
            "rebuilt": "Mapped regions with source-faithful authored detail and protected/alpha checks; size/upscale/recolor alone fails",
            "integrated": "Rebuilt exact assets included in scoped composed candidate with verified file hashes",
            "live-verified": "All required states, variants, motion, actual final-candidate submissions and fresh visible brackets accepted; no open defect",
        },
        "count_rules": ["Semantic components, technical sources, states and journeys have different units",
                        "Mixed atlas pages and palette variants never count as signs/buildings/animation loops",
                        "Unknown totals remain null; this seed inventory cannot supply a completion percentage",
                        "Historical partial acceptance is preserved but cannot pass final-candidate/state gates"],
        "components": components, "technical_source_index": technical,
        "discovery_queues": queues, "acceptance_journeys": journeys,
        "summary": {"semantic_component_records": len(components),
                    "by_category": dict(Counter(x["category"] for x in components)),
                    "by_status": dict(Counter(x["status"] for x in components)),
                    "technical_source_records": len(technical),
                    "world_source_families": len(world["family_inventory"]),
                    "known_world_palette_variants": sum(len(x["known_queue_palette_keys"]) for x in world["family_inventory"]),
                    "known_world_variants_missing_v6_at_audit": sum(len(x["known_queue_keys_absent_current_candidate"]) for x in world["family_inventory"]),
                    "protected_regions": sum(len(v) for v in world["protected_regions"]["rectangles_by_crc"].values()),
                    "boss_phase_discovery_queues": sum(x["id"].startswith("sweep/boss-phases/") for x in queues),
                    "open_discovery_queues": len(queues), "acceptance_journeys": len(journeys),
                    "full_game_semantic_total": None, "completion_percentage": None,
                    "release_ready": False},
    }
    validate(result, data)
    result["validation"] = {"pass": True, "assertions": [
        "Every catalog hull/Gunpod/enemy identity is included exactly once in its category",
        "Every reported boss has an unresolved phase-discovery queue",
        "Every audited mixed family, known variant, omitted variant and protected region is retained",
        "No source page or palette variant is counted as a semantic component",
        "No final-candidate live verification is inferred from historical partial evidence",
        "All integrated component assets have freshly checked exact composed-file hashes",
        "Unknown full-game totals and completion percentage remain null"]}
    return result


def validate(result, data):
    components = result["components"]
    assert len({x["id"] for x in components}) == len(components), "duplicate semantic ID"
    expected_ids = {
        "player_hull": {"player/" + x["id"] + "/hull" for x in data["loadout"]["ships"]},
        "built_in_weapon": {"player/" + x["id"] + "/built-in-weapon" for x in data["loadout"]["ships"]},
        "gunpod": {"gunpod/" + x["id"] for x in data["loadout"]["gunpods"]},
        "enemy_model": {"enemy/" + x["id"] for x in data["enemy"]["families"]},
        "ui_component": {"ui/" + x["id"] for x in data["ui_audit"]["components"]},
    }
    assert set(x["category"] for x in components) == set(expected_ids), "unknown semantic category"
    for category, expected in expected_ids.items():
        assert {x["id"] for x in components if x["category"] == category} == expected, category
    for row in components:
        assert row["status"] == status_for(row["gates"]), row["id"]
        assert row["record_kind"] == "semantic_component"
        assert row["gates"]["live_verification"] is False, "historical acceptance leakage"
        if row["gates"]["integration"]:
            assert row["gates"]["rebuild"] and row["gates"]["mapping"], row["id"]
            assert row["authoring"]["hashes"], "integration lacks asset evidence"
            assert all(x["expected_sha256"] and x["expected_sha256"] == x["actual_sha256"]
                       for x in row["authoring"]["hashes"])
    world_sources = [x for x in result["technical_source_index"] if x["id"].startswith("source/world/")]
    expected_keys = {key for x in data["world_audit"]["family_inventory"] for key in x["known_queue_palette_keys"]}
    assert {key for x in world_sources for key in x["source_keys"]} == expected_keys
    expected_missing = {key for x in data["world_audit"]["family_inventory"] for key in x["known_queue_keys_absent_current_candidate"]}
    assert {key for x in world_sources for key in x["missing_from_v6_keys_at_audit"]} == expected_missing
    for x in world_sources:
        assert x["semantic_owner"] is None and x["semantic_ownership_verified"] is False
        assert set(x["missing_from_v6_keys_at_audit"]) <= set(x["source_keys"])
    assert sum(len(x["protected_regions"]) for x in world_sources) == data["world_audit"]["summary"]["protected_uv_rectangles"]
    boss_ids = {"sweep/boss-phases/" + e["id"] for e in data["enemy"]["families"] if e["kind"] == "boss_or_midboss"}
    assert boss_ids <= {x["id"] for x in result["discovery_queues"]}
    assert all(q["enumeration_complete"] is False for q in result["discovery_queues"])
    assert result["summary"]["completion_percentage"] is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate saved register against current evidence without rewriting it")
    args = parser.parse_args()
    output = AUDIT / "component-register.json"
    generated = build()
    if args.check:
        saved = json.loads(output.read_text(encoding="utf-8"))
        validate(saved, load_inputs())
        for key in ("components", "technical_source_index", "discovery_queues", "acceptance_journeys", "provenance", "summary"):
            assert saved[key] == generated[key], "saved register differs from current evidence: " + key
        print(json.dumps({"check": "PASS", "path": str(output), "summary": saved["summary"]}))
    else:
        output.write_text(json.dumps(generated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"written": str(output), "validation": generated["validation"], "summary": generated["summary"]}))


if __name__ == "__main__":
    main()
