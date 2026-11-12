"""Reconcile finalized local capture evidence without contacting the game.

Run from any directory: python remaster-audit/stage1_coverage_ledger.py
Optional independently authored reviews use observations containing task_id,
requirement_id, evidence [{path, sha256}], findings and acceptance_met.
An operator marker, file count, CRC match or GL submission never verifies an
actor, part, weapon, effect, boss phase, or the original research catalog.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import zlib

PROJECT = Path(__file__).resolve().parents[1]
EVIDENCE = PROJECT / "remaster-audit/dev-center-evidence"
RUNS = PROJECT / "windows-x64/tools/research-runs"
BASE_RUNS = {
    "research-20261112-152726-0276c11a",
    "research-20261112-153038-6a202447",
    "research-20261112-153406-11eebc24",
}
TIERS = ["missing", "observed", "source-valid", "draw-confirmed", "visually-verified"]
PLAYER = ["724E77DA-21FDE894", "7E3ADD56-21FDE894", "B16492B1-21FDE894", "E2F3477C-21FDE894"]
MECHANICAL = ["5CC44E5F-053D9A00"]
ENEMY = ["3594C110-527B28B9", "3FE0776D-527B28B9", "6BB2A2A3-527B28B9", "784BFD39-527B28B9", "DEA9D15C-527B28B9", "05C32A1E-527B28B9"]
DRACHE = {"635768EB": "camouflage/joint plate candidate", "8D0FC0AD": "livery/joint/illuminated trim candidate", "01C0DA70": "mechanical/appendage panel candidate"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def fnv(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def relative(path):
    path = path.resolve()
    return path.relative_to(PROJECT).as_posix() if path.is_relative_to(PROJECT) else str(path)


def ref(path):
    return {"path": relative(path), "sha256": file_sha(path)}


def inside(directory, name):
    path = (directory / name).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("Path escapes evidence directory")
    return path


def rows(path, errors):
    if not path.is_file():
        return []
    result = []
    for number, line in enumerate(path.read_bytes().splitlines(), 1):
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("row is not an object")
            result.append(value)
        except (ValueError, TypeError) as exc:
            errors.append({"file": relative(path), "line": number, "error": str(exc)})
    return result


def source(path):
    metadata = load(path)
    key = metadata["key"]
    words = inside(path.parent, key + ".words.bin").read_bytes()
    clut = inside(path.parent, key + ".clut.bin").read_bytes()
    valid = inside(path.parent, key + ".valid.bin").read_bytes()
    complete = (len(valid) == metadata["total_words"] == metadata["width_words"] * metadata["height"]
                and len(words) == len(valid) * 2 and all(v == 1 for v in valid)
                and metadata.get("known_words") == metadata["total_words"])
    crc_key = f"{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}"
    fnv_matches = fnv(words) == metadata["words_fnv1a32"] and fnv(clut) == metadata["clut_fnv1a32"]
    complete = complete and len(clut) == metadata["clut_words"] * 2
    return {"key": key, "metadata": ref(path), "words_sha256": sha(words),
            "clut_sha256": sha(clut), "known_words": metadata["known_words"],
            "total_words": metadata["total_words"], "width_words": metadata["width_words"],
            "height": metadata["height"], "depth": metadata["depth"],
            "frame": metadata.get("frame"), "complete": complete,
            "computed_crc_key": crc_key, "crc_matches": crc_key == key,
            "fnv_matches": fnv_matches,
            "source_valid": complete and crc_key == key and fnv_matches,
            "cpu_vram_may_be_stale": metadata.get("cpu_vram_may_be_stale", True)}


def audit_run(path):
    manifest = load(path)
    errors = []
    listed = set()
    for entry in manifest.get("files", []):
        try:
            item = inside(path.parent, entry["path"])
            if entry["path"] in listed:
                raise ValueError("duplicate manifest entry")
            listed.add(entry["path"])
            if not item.is_file() or item.is_symlink():
                raise ValueError("missing/nonregular file")
            if item.stat().st_size != entry["bytes"] or file_sha(item) != entry["sha256"]:
                raise ValueError("manifest size/hash mismatch")
        except (OSError, KeyError, ValueError) as exc:
            errors.append({"file": entry.get("path"), "error": str(exc)})
    actual = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob("*") if p.is_file()}
    unlisted = sorted(actual - listed - {"manifest.json"})
    if unlisted:
        errors.append({"error": "Unlisted files in finalized run", "files": unlisted})
    native = manifest.get("native_capture") or {}
    final = native.get("stop") or {}
    observations = rows(path.parent / "native/capture.jsonl", errors)
    events = rows(path.parent / "events.jsonl", errors)
    sources = []
    for item in sorted((path.parent / "native").glob("*.source.json")):
        try:
            sources.append(source(item))
        except (OSError, KeyError, ValueError) as exc:
            errors.append({"file": relative(item), "error": str(exc)})
    query = [r for r in observations if r.get("event") == "source_draw_query_matched"]
    gl = [r for r in observations if r.get("event") == "replacement_gl_draw_submitted"]
    archived = {s["key"] for s in sources if s["source_valid"]}
    queried_upload = {r["key"] for r in query if r.get("source_kind") == "upload"}
    source_filter = manifest.get("source_filter", {"policy": "all", "keys": []})
    policy, filter_keys = source_filter.get("policy"), source_filter.get("keys", [])
    configured_keys = set(filter_keys)
    def selected(key):
        return policy == "all" or (key in configured_keys) == (policy == "include")
    outside_policy = sorted(s["key"] for s in sources if not selected(s["key"]))
    fingerprint = fnv("".join(key + "\n" for key in sorted(filter_keys)).encode("ascii"))
    filter_checks = []
    if policy != "all":
        for operation in ["start", "stop"]:
            acknowledgement = native.get(operation) or {}
            config = acknowledgement.get("source_filter", {})
            matches = (acknowledgement.get("source_filter_supported") is True
                       and config.get("policy") == policy
                       and type(config.get("key_count")) is int and config["key_count"] == len(filter_keys)
                       and type(config.get("keys_fnv1a32")) is int and config["keys_fnv1a32"] == fingerprint
                       and config.get("scope") == "raw_source_archives_only")
            filter_checks.append({"operation": operation, "matches": matches, "acknowledgement": config})
        if not all(item["matches"] for item in filter_checks):
            errors.append({"error": "Exact source filter acknowledgement mismatch", "checks": filter_checks})
    if outside_policy:
        errors.append({"error": "Raw source keys violate recorded exact filter policy", "keys": outside_policy})
    material_fields = ["material_generation", "material_channel", "material_profile", "material_strength",
                       "material_applied", "material_diagnostic_scope", "material_preserve_accents"]
    draws = query + gl
    material_rows = [r for r in draws if any(field in r for field in material_fields)]
    malformed_material = []
    for row in material_rows:
        missing = [field for field in material_fields if field not in row]
        consistent = (not missing and type(row["material_generation"]) is int and row["material_generation"] >= 0
            and row["material_channel"] in ("stock", "player", "enemy") and isinstance(row["material_profile"], str)
            and type(row["material_strength"]) in (float, int) and math.isfinite(row["material_strength"])
            and 0 <= row["material_strength"] <= 1
            and all(type(row[field]) is bool for field in ["material_applied", "material_diagnostic_scope", "material_preserve_accents"]))
        if consistent and row["material_applied"]:
            consistent = (row["event"] == "replacement_gl_draw_submitted" and row["material_channel"] != "stock"
                          and row["material_profile"] != "stock" and row["material_strength"] > 0)
        if not consistent:
            malformed_material.append({"key": row.get("key"), "frame": row.get("frame"), "missing": missing})
    if malformed_material:
        errors.append({"error": "Malformed or inconsistent material attribution rows", "rows": malformed_material[:16]})
    material_groups = Counter((r.get("material_generation"), r.get("material_channel"), r.get("material_profile"),
                              r.get("material_applied"), r.get("material_diagnostic_scope"), r.get("material_preserve_accents")) for r in material_rows)
    return {
        "id": manifest["id"], "manifest": ref(path), "status": manifest.get("status"),
        "scenario": manifest.get("scenario"), "label": manifest.get("label"),
        "started_at": manifest.get("started_at"), "ended_at": manifest.get("ended_at"),
        "stage_context": {
            "classification": "reviewed_stage1_baseline_candidate" if manifest["id"] in BASE_RUNS else
                "post_drache_numeric_stage_unknown" if "post-drache" in (manifest.get("label") or "").lower() else "declared_scenario_awaiting_independent_stage_review",
            "numeric_stage_verified": False,
            "scenario_is_operator_annotation": True,
            "qualification": "Post-encounter scenery and a stage1 scenario label do not establish the current numeric stage or a complete Stage1 pass."},
        "stop_reason": manifest.get("stop_reason"), "backend_error": manifest.get("error"),
        "integrity": "PASS" if not errors else "FAIL", "errors": errors,
        "files_checked": len(listed), "payload_bytes": sum(x["bytes"] for x in manifest.get("files", [])),
        "ram_snapshots": len(list(path.parent.glob("snapshot-*.json"))),
        "native_event_binaries": len(list((path.parent / "native").glob("event-*.bin"))),
        "native_counts": final.get("counts", {}), "native_limits": final.get("limits", {}),
        "source_filter": source_filter,
        "source_filter_compliance": {"status": "PASS" if not outside_policy and all(c["matches"] for c in filter_checks) else "FAIL",
            "policy": policy, "key_count": len(filter_keys), "computed_keys_fnv1a32": fingerprint,
            "acknowledgements": filter_checks, "archived_keys_outside_policy": outside_policy,
            "intentionally_unselected_observed_upload_keys": sorted(k for k in queried_upload if not selected(k)),
            "selected_upload_keys_without_valid_archive": sorted(k for k in queried_upload - archived if selected(k)),
            "qualification": "Include/exclude intentionally omits unselected raw keys. Remaining capacity never establishes complete scene coverage."},
        "material_attribution": {"draw_rows": len(draws), "rows_with_fields": len(material_rows),
            "legacy_rows_without_fields": len(draws) - len(material_rows), "malformed_rows": len(malformed_material),
            "groups": [{"generation": group[0], "channel": group[1], "profile": group[2], "applied": group[3],
                        "diagnostic_scope": group[4], "preserve_accents": group[5], "rows": count}
                       for group, count in sorted(material_groups.items(), key=lambda item: str(item[0]))],
            "qualification": "Recorded selected material at submission/query time; visibility, model ownership and successful visual finish remain separate."},
        "native_caps": final.get("caps", {}), "sampling": final.get("sampling", {}),
        "source_file_budget_paused": final.get("source_file_budget_paused"),
        "source_archive_valid": len(archived), "source_archive_partial_or_invalid": sum(not s["source_valid"] for s in sources),
        "referenced_upload_keys_without_valid_archive_in_run": sorted(queried_upload - archived),
        "selection_scope": "verified_input_fixed_sampler_baseline" if manifest["id"] in BASE_RUNS else "additional_finalized_run",
        "_query": query, "_gl": gl, "_sources": sources, "_events": events,
    }


def summarize_keys(runs, installed):
    keys = defaultdict(lambda: {"sources": [], "queries": [], "submissions": [], "runs": set()})
    for run in runs:
        for item in run["_sources"]:
            keys[item["key"]]["sources"].append({**item, "run": run["id"]})
        for group, label in [(run["_query"], "queries"), (run["_gl"], "submissions")]:
            for item in group:
                keys[item["key"]][label].append(item)
                keys[item["key"]]["runs"].add(run["id"])
    result = {}
    for key, item in sorted(keys.items()):
        all_rows = item["queries"] + item["submissions"]
        valid = [s for s in item["sources"] if s["source_valid"]]
        result[key] = {"key": key, "texture_crc32": key.split("-")[0],
            "installed_manifest_member": key in installed,
            "technical_evidence_tier": "draw-confirmed" if item["submissions"] else "source-valid" if valid else "observed",
            "source_valid": bool(valid), "query_records": len(item["queries"]),
            "gl_submission_records": len(item["submissions"]), "runs": sorted(item["runs"]),
            "source_copies": item["sources"],
            "source_kinds": sorted({r.get("source_kind", "unknown") for r in all_rows}),
            "page_xy": [list(x) for x in sorted({tuple(r.get("page_xy", [])) for r in all_rows})],
            "clut_xy": [list(x) for x in sorted({tuple(r.get("clut_xy", [])) for r in all_rows})],
            "uv_rectangles_count": len({tuple(r.get("uv_bounds", [])) for r in all_rows}),
            "uv_rectangle_examples": [list(x) for x in sorted({tuple(r.get("uv_bounds", [])) for r in all_rows})[:16]],
            "query_example": item["queries"][0] if item["queries"] else None,
            "submission_example": item["submissions"][0] if item["submissions"] else None,
            "semantic_mapping_verified": False,
            "qualification": "GL submission is technical draw evidence, not visibility, actor/part ownership or successful finish acceptance."}
    return result


def overlap(a, b):
    return len(a) == len(b) == 4 and min(a[2], b[2]) >= max(a[0], b[0]) and min(a[3], b[3]) >= max(a[1], b[1])


def pattern_report(runs, keys):
    raw = defaultdict(lambda: {"keys": set(), "runs": set(), "palettes": set()})
    crc = defaultdict(list)
    for key, item in keys.items():
        crc[item["texture_crc32"]].append(key)
        for s in item["source_copies"]:
            if s["source_valid"]:
                raw[s["words_sha256"]]["keys"].add(key)
                raw[s["words_sha256"]]["runs"].add(s["run"])
                raw[s["words_sha256"]]["palettes"].add(s["clut_sha256"])
    edges = defaultdict(lambda: {"matches": 0, "runs": set(), "examples": []})
    for run in runs:
        by_context = defaultdict(list)
        for row in run["_query"] + run["_gl"]:
            if row.get("source_kind") == "upload":
                context = (row.get("frame"), tuple(row.get("page_xy", [])), row.get("depth"), tuple(row.get("clut_xy", [])))
                by_context[context].append(row)
        for row in run["_query"]:
            if row.get("source_kind") != "native_page" or row["key"].split("-")[0] not in DRACHE:
                continue
            context = (row.get("frame"), tuple(row.get("page_xy", [])), row.get("depth"), tuple(row.get("clut_xy", [])))
            for other in by_context[context]:
                if overlap(row.get("uv_bounds", []), other.get("uv_bounds", [])):
                    edge = edges[(row["key"], other["key"])]
                    edge["matches"] += 1
                    edge["runs"].add(run["id"])
                    if len(edge["examples"]) < 3:
                        edge["examples"].append({"run": run["id"], "frame": row["frame"],
                            "page_xy": row.get("page_xy"), "clut_xy": row.get("clut_xy"),
                            "full_page_uv": row.get("uv_bounds"), "upload_uv": other.get("uv_bounds"),
                            "upload_event": other["event"]})
    return {"raw_word_families": [{"words_sha256": h, "keys": sorted(d["keys"]), "runs": sorted(d["runs"]),
                    "palette_hashes": sorted(d["palettes"]), "qualification": "Identical indexed words; palette variants are not actors or animation frames."}
                for h, d in sorted(raw.items())],
            "crc_families": [{"texture_crc32": h, "keys": group,
                "query_records": sum(keys[k]["query_records"] for k in group),
                "gl_submission_records": sum(keys[k]["gl_submission_records"] for k in group),
                "raw_valid_keys": sum(keys[k]["source_valid"] for k in group),
                "old_installed_keys": [k for k in group if keys[k]["installed_manifest_member"]],
                "new_uninstalled_keys": [k for k in group if not keys[k]["installed_manifest_member"]],
                "likely_owner": DRACHE.get(h, "unassigned_by_this_ledger"), "ownership_verified": False}
                for h, group in sorted(crc.items())],
            "same_frame_page_clut_uv_overlaps": [{"full_page_key": pair[0], "upload_strip_key": pair[1],
                "overlap_observations": d["matches"], "runs": sorted(d["runs"]), "examples": d["examples"],
                "status": "candidate_shared_page_region_not_part_ownership"}
                for pair, d in sorted(edges.items(), key=lambda item: (-item[1]["matches"], item[0]))],
            "keys": list(keys.values())}


def reviewed_sources(extra_reviews):
    result = []
    for name in ["skin-mapping.json", "verified-pass-visual-review.json", "greif-finish-wasp-review.json",
                 "drache-visual-source-review.json", "effects-mapping.json", "stage1-finish-plan.json",
                 "skin-source-alias-audit.json"]:
        path = EVIDENCE / name
        if path.is_file():
            result.append(ref(path))
    for path in extra_reviews:
        result.append(ref(path))
    return result


def review_records(paths):
    records, errors = [], []
    for path in paths:
        review = load(path)
        for item in review.get("observations", []):
            refs = item.get("evidence", [])
            checked = []
            for evidence in refs:
                try:
                    target = Path(evidence["path"])
                    target = target if target.is_absolute() else PROJECT / target
                    good = target.is_file() and file_sha(target) == evidence["sha256"]
                    checked.append({**evidence, "hash_matches": good})
                except (OSError, KeyError) as exc:
                    checked.append({**evidence, "hash_matches": False, "error": str(exc)})
            acceptable = item.get("acceptance_met") is True and bool(checked) and all(x["hash_matches"] for x in checked)
            if item.get("acceptance_met") is True and not acceptable:
                errors.append({"review": relative(path), "requirement_id": item.get("requirement_id"), "error": "Review acceptance lacks intact explicit evidence references"})
            records.append({**item, "review": ref(path), "evidence": checked,
                            "evidence_integrity": bool(checked) and all(x["hash_matches"] for x in checked),
                            "explicit_review_acceptance": acceptable})
    return records, errors


def technical_state(subject_keys, keys, observed=False):
    subjects = [keys[k] for k in subject_keys if k in keys]
    if subjects and all(s["gl_submission_records"] for s in subjects) and len(subjects) == len(subject_keys):
        return "draw-confirmed"
    if subjects and all(s["source_valid"] for s in subjects) and len(subjects) == len(subject_keys):
        return "source-valid"
    return "observed" if observed or subjects else "missing"


def requirements(catalog, runs, keys, reviews):
    task_events = defaultdict(list)
    for run in runs:
        if run.get("stage_context", {}).get("semantic_evidence_eligible") is False:
            continue
        for event in run["_events"]:
            if event.get("task_id"):
                task_events[event["task_id"]].append({"run": run["id"], "id": event.get("id"),
                    "frame": event.get("frame"), "native_event_frame": (event.get("native") or {}).get("event_frame"),
                    "phase": event.get("phase"), "label": event.get("label"),
                    "scope": "operator_annotation_not_semantic_validation"})
    associations = {"skin_named_hull_binding": PLAYER + MECHANICAL,
                    "stock_gun_endymion_mk2": [], "enemy_pw104b_schabe": ENEMY,
                    "enemy_spkb03_drache": [k for k in keys if k.split("-")[0] in DRACHE],
                    "boss_drache_walking": [k for k in keys if k.split("-")[0] in DRACHE]}
    visual_observed = {"enemy_spj15_greif", "boss_greif_combat", "enemy_spkb03_drache", "boss_drache_walking", "gunpod_wasp", "stock_gun_endymion_mk2", "progression_natural_scene"}
    result = []
    for task in catalog["tasks"]:
        task_id = task["id"]
        candidates = associations.get(task_id, [])
        explicit = [r for r in reviews if r.get("task_id") == task_id]
        # Task acceptance is never automatically changed, even when a narrower
        # requirement has an explicit visual review.
        tier = technical_state(candidates, keys, bool(task_events[task_id]) or task_id in visual_observed or bool(explicit))
        result.append({"id": task_id, "label": task.get("label", task.get("title")),
            "category": task.get("category", task.get("group")),
            "catalog_verification_state": task.get("verification", {}).get("state", task.get("status", "missing")),
            "evidence_tier": tier, "required_acceptance": task.get("acceptance_criteria", task.get("confirmation_criteria", [])),
            "candidate_keys": candidates, "candidate_association_not_verified": bool(candidates),
            "events": task_events[task_id], "explicit_reviews": explicit,
            "acceptance_met": False, "remaining": task.get("blockers", task.get("missing", [])),
            "qualification": "Technical evidence tier qualifies candidate material evidence only; catalog semantics remain unpromoted."})
        prior = []
        if candidates and task_id in {"skin_named_hull_binding", "enemy_pw104b_schabe"}:
            prior.append("skin-mapping.json")
        if task_id in {"enemy_spj15_greif", "boss_greif_combat", "gunpod_wasp"}:
            prior.extend(["verified-pass-visual-review.json", "greif-finish-wasp-review.json"])
        if task_id in {"enemy_spkb03_drache", "boss_drache_walking", "boss_drache_assault", "boss_boss_destruction", "progression_natural_scene"}:
            prior.append("drache-visual-source-review.json")
        if task_id.startswith("effect_"):
            prior.append("effects-mapping.json")
        result[-1]["prior_review_evidence"] = [ref(EVIDENCE / name) for name in prior]
        if task_id == "gunpod_wasp":
            result[-1]["reviewed_negative_finding"] = "Wasp30 HUD observed earlier, but original labelled firing pair starts after Wasp has already disappeared. Actual before/after candidate ammo is2/2 unchanged; pair cannot establish Wasp firing. New postDrache Square pair is stock-only candidate, not Wasp evidence."
    extra = []
    def add(identifier, label, subject_keys=(), observed=False, remaining=(), scope="stage1_materials"):
        applicable = [r for r in reviews if r.get("requirement_id") == identifier]
        accepted = any(r["explicit_review_acceptance"] for r in applicable)
        extra.append({"id": identifier, "label": label, "acceptance_scope": scope,
            "evidence_tier": "visually-verified" if accepted else technical_state(list(subject_keys), keys, observed or bool(applicable)),
            "candidate_keys": list(subject_keys), "acceptance_met": accepted,
            "explicit_reviews": applicable, "remaining": [] if accepted else list(remaining),
            "semantic_mapping_verified": False,
            "qualification": "Acceptance, if present, applies only to this exact independently reviewed requirement, not the research catalog."})
    add("player_all_observed_body_keys", "All five observed player body source families", PLAYER + MECHANICAL, True,
        ["Matched stock/player-only/enemy-only/combined views", "Separate wing, mechanical body, attachments and gun ownership"])
    add("player_blue_wing", "Distinct blue wing source changes with requested finish", [PLAYER[0]], True,
        ["Visible stable wing acceptance in each chosen finish"])
    add("player_mechanical_body", "Mechanical panels change with requested finish", MECHANICAL, True,
        ["Visible stable mechanical panel acceptance; attached weapons remain unpartitioned"])
    add("enemy_observed_six_strip_family", "One observed enemy family, all six source strips", ENEMY, True,
        ["Match a named visible actor to exact UV regions", "Preserve markings, yellow/orange accents and effect layers"])
    add("preserve_yellow_orange_accents", "Requested yellow/orange accents remain visible", (), True,
        ["Identify exact stripe source/UV masks and show matched before/after"], "visual_preservation")
    add("preserve_hit_glow", "Hit glow remains animated and separate from hull finish", (), True,
        ["Short ordered no-hit/hit sequence with unchanged exposure", "Map effect texture or untextured primitive ownership"], "visual_preservation")
    add("actual_city_gameplay_frame", "Visible city gameplay contains the player, enemies and shots", (), False,
        ["Independently review an actual gameplay frame rather than relying on its filename"], "visual_context_only")
    add("cannon_carried_hud_identity", "Visible player carries a Gunpod while HUD identifies Cannon and ammunition", (), False,
        ["Visible solid player, attached gun and Cannon HUD in the same reviewed frame"], "weapon_visual_identity_only")
    add("player_live_palette_in_scene", "Stock, Gold and Neon visibly change the selected player with all five candidate keys submitted", (), False,
        ["Solid player screenshots and exact matching material-generation GL receipts"], "local_player_color_only")
    add("player_warm_markings_in_scene", "Yellow/orange player markings remain warm in the local palette comparison", (), False,
        ["Independent comparison of visible markings across stock, Gold and Neon"], "local_visual_preservation")
    add("cannon_two_isolated_cross_trials", "Two isolated Cannon Cross trials produce visible ammunition decrements", (), False,
        ["Repeated visible Cannon HUD decrements with paired native evidence"], "controlled_weapon_behavior_only")
    stage_families = load(EVIDENCE / "stage1-finish-plan.json")["families"]
    for family in stage_families:
        entity = family["entity_id"]
        observed = entity in {"spj15_greif", "spkb03_drache"}
        subject_keys = ENEMY if entity == "pw104b_schabe" else [k for k in keys if k.split("-")[0] in DRACHE] if entity == "spkb03_drache" else []
        add(entity + "_identity", family["name"] + " visible whole actor identity", (), observed,
            ["Review complete visible actor against original gallery; route association alone is insufficient"], "actor_identity")
        add(entity + "_part_bindings", family["name"] + " hull/armor/weapon/trim source ownership", subject_keys, observed,
            ["Resolve whole-page versus upload-strip overlap", "Map exact UV/CLUT regions and shared-atlas parts"], "part_mapping")
        add(entity + "_finish", family["name"] + " complete requested finish in gameplay", (), False,
            ["Authored UV-compatible material", "Matched bright/dark gameplay, all visible parts, preserved effects"], "visual_finish")
    for task_id, label in [("greif_transition", "Greif combat-to-transition phase"),
                           ("drache_assault", "Drache deployed assault cannon and cyan beam"),
                           ("boss_destruction", "Ordered boss final damage/destruction/debris"),
                           ("stage1_end", "Explicit Stage 1 end/transition evidence")]:
        add(task_id, label, (), task_id == "stage1_end", ["Focused phase-identifiable visible frame sequence", "Frame-aligned source/GP0/CLUT evidence and explicit review"], "stage1_completion")
    return result, extra


def technical_acceptance(runs, keys, gp0):
    def requirement(identifier, assertion, passed, evidence, remaining):
        return {"id": identifier, "assertion": assertion, "status": "PASS" if passed else "GAP",
                "evidence": evidence, "remaining": [] if passed else remaining,
                "scope": "technical_evidence_only_not_semantic_task_completion"}
    return [
        requirement("finalized_file_integrity", "All included finalized manifests resolve with matching hashes and sizes", bool(runs) and all(not r["errors"] for r in runs),
                    [r["manifest"] for r in runs], ["Resolve listed integrity errors"]),
        requirement("all_five_player_source_keys", "All five observed candidate player body keys have complete CRC/FNV-valid source evidence", all(keys.get(k, {}).get("source_valid") for k in PLAYER + MECHANICAL),
                    PLAYER + MECHANICAL, ["Recover exact missing player source/CLUT bytes"]),
        requirement("all_five_player_gl_keys", "All five observed candidate player body keys retain actual GL submissions", all(keys.get(k, {}).get("gl_submission_records", 0) for k in PLAYER + MECHANICAL),
                    PLAYER + MECHANICAL, ["Retain GL receipts for missing candidate keys"]),
        requirement("six_strip_enemy_gl_keys", "All six keys of one observed enemy family retain actual GL submissions", all(keys.get(k, {}).get("gl_submission_records", 0) for k in ENEMY),
                    ENEMY, ["Retain GL receipts without treating six strips as six enemies"]),
        requirement("gp0_bundle_integrity", "Saved GP0 bundle frame hashes match", bool(gp0) and all(not x["errors"] for x in gp0),
                    [x["manifest"] for x in gp0], ["Resolve GP0 file integrity errors"]),
        requirement("unsaturated_source_coverage", "All included runs preserve raw-source capacity until end", bool(runs) and not any(r["native_caps"].get("sources") for r in runs),
                    [r["id"] for r in runs], ["Replay missed targets with fresh/reset or targeted source quota; old omissions remain in historical runs"]),
    ]


def gp0_bundles():
    result = []
    roots = [EVIDENCE / "level1-live-d59b8e1c"] + sorted(EVIDENCE.glob("targeted-stage1-*"))
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("manifest.json")):
            data = load(path)
            if not isinstance(data.get("frames"), list):
                continue
            errors = []
            for frame in data["frames"]:
                try:
                    target = inside(path.parent, frame["file"])
                    if not target.is_file() or file_sha(target) != frame["sha256"]:
                        raise ValueError("missing frame/hash mismatch")
                except (KeyError, OSError, ValueError) as exc:
                    errors.append({"frame": frame.get("frame"), "error": str(exc)})
            result.append({"manifest": ref(path), "frames": len(data["frames"]), "errors": errors,
                "reported_truncated_frames": sum(bool(f.get("potentially_truncated")) for f in data["frames"]),
                "qualification": "Ordered command records can omit upload payloads/polyline bodies; no atomic GPU state or complete replay implied."})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=EVIDENCE / "stage1-coverage-ledger.json")
    parser.add_argument("--patterns-output", type=Path, default=EVIDENCE / "stage1-source-patterns.json")
    args = parser.parse_args()
    default_review = EVIDENCE / "stage1-targeted-visual-review.json"
    review_paths = list(dict.fromkeys(([default_review] if default_review.is_file() else []) + args.review))
    for output in [args.output, args.patterns_output]:
        if not output.resolve().is_relative_to(EVIDENCE):
            raise ValueError("Outputs must stay within this project's evidence directory")
    catalog_path = PROJECT / "windows-x64/tools/research_catalog.json"
    catalog = load(catalog_path)
    installed_path = PROJECT / "windows-x64/hd-textures/stage1-v1/manifest.json"
    installed = {f["key"] for f in load(installed_path)["files"]}
    runs, excluded = [], []
    for path in sorted(RUNS.glob("*/manifest.json")):
        manifest = load(path)
        if manifest.get("status") != "finalized":
            excluded.append({"path": relative(path), "reason": "not_finalized"})
            continue
        start = ((manifest.get("native_capture") or {}).get("start") or {})
        policy = start.get("sampling", {}).get("policy")
        if manifest["id"] not in BASE_RUNS and (manifest.get("started_at") or "") < "2026-11-12T15:43:17":
            excluded.append({"path": relative(path), "reason": "legacy_or_setup_run_excluded_from_current_coverage", "sampling_policy": policy})
            continue
        runs.append(audit_run(path))
    keys = summarize_keys(runs, installed)
    valid_by_run = defaultdict(set)
    for key, item in keys.items():
        for copy in item["source_copies"]:
            if copy["source_valid"]:
                valid_by_run[copy["run"]].add(key)
    baseline_complete = set().union(*(valid_by_run[identity] for identity in BASE_RUNS))
    seen_complete = set()
    novelty = []
    for run in sorted(runs, key=lambda r: (r.get("started_at") or "", r["id"])):
        complete = valid_by_run[run["id"]]
        new_keys = complete - seen_complete
        novelty.append({"run": run["id"], "complete_keys": len(complete),
                        "new_complete_keys": sorted(new_keys), "repeated_complete_keys": len(complete & seen_complete)})
        seen_complete.update(complete)
    patterns = pattern_report(runs, keys)
    alias_path = EVIDENCE / "skin-source-alias-audit.json"
    alias_summary = None
    if alias_path.is_file():
        aliases = load(alias_path)
        alias_summary = {"report": ref(alias_path), "summary": aliases["summary"],
            "scope": "Independent saved exact-byte rectangle comparison report; includes broader historical sources than the current-run totals. Actor ownership remains unverified.",
            "atlas_families": aliases.get("atlas_families", []),
            "aliases": aliases.get("aliases", []),
            "root_causes": aliases.get("root_causes", [])}
        patterns["independent_exact_word_alias_report"] = alias_summary
    explicit_reviews, review_errors = review_records(review_paths)
    for run in runs:
        context_reviews = [r for r in explicit_reviews if r.get("run_id") == run["id"] and r.get("context_classification") and r["evidence_integrity"]]
        if context_reviews:
            review = context_reviews[-1]
            run["stage_context"].update(classification=review["context_classification"],
                semantic_evidence_eligible=review.get("semantic_evidence_eligible", False),
                independent_review=review["review"], evidence=review["evidence"], findings=review.get("findings"),
                qualification="Exact reviewed context only. Numeric stage ID, complete pass, actor bindings and finished skins remain unverified.")
    task_rows, component_rows = requirements(catalog, runs, keys, explicit_reviews)
    gp0 = gp0_bundles()
    technical = technical_acceptance(runs, keys, gp0)
    # Gaps can be closed by future explicit requirement-level reviews, but no
    # script ever turns reviewed visual evidence into validated game control.
    accepted_components = sum(x["acceptance_met"] for x in component_rows)
    ledger = {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Finalized file integrity, technical source/draw evidence and explicit review reconciliation. No game/network/process/control calls.",
        "evidence_tiers": {"missing": "No qualifying evidence retained for this requirement.",
            "observed": "Event annotation or reviewed observation exists; meaning remains qualified.",
            "source-valid": "All associated candidate keys have complete CRC/FNV-valid source copies.",
            "draw-confirmed": "All associated candidate keys have retained GL submission receipts; ownership/visibility remain separate.",
            "visually-verified": "An explicit requirement-level independent review declares acceptance and all cited artifact hashes match."},
        "catalog": ref(catalog_path), "installed_manifest": ref(installed_path),
        "read_only_inputs": reviewed_sources(review_paths), "review_errors": review_errors,
        "summary": {"finalized_runs_all_contexts": len(runs),
            "reviewed_stage1_baseline_runs": sum(r["id"] in BASE_RUNS for r in runs),
            "additional_finalized_runs": sum(r["id"] not in BASE_RUNS for r in runs),
            "additional_runs_awaiting_independent_stage_review": sum(r["id"] not in BASE_RUNS and "independent_review" not in r["stage_context"] for r in runs),
            "files_hash_checked": sum(r["files_checked"] for r in runs),
            "integrity_errors": sum(len(r["errors"]) for r in runs),
            "source_archive_copies": sum(len(r["_sources"]) for r in runs),
            "valid_source_archive_copies": sum(s["source_valid"] for r in runs for s in r["_sources"]),
            "partial_or_invalid_source_copies": sum(not s["source_valid"] for r in runs for s in r["_sources"]),
            "unique_keys_all_technical_channels": len(keys),
            "unique_query_or_gl_keys": sum(bool(k["query_records"] or k["gl_submission_records"]) for k in keys.values()),
            "unique_query_keys": sum(bool(k["query_records"]) for k in keys.values()),
            "unique_gl_submission_keys": sum(bool(k["gl_submission_records"]) for k in keys.values()),
            "unique_archived_source_keys_including_invalid": sum(bool(k["source_copies"]) for k in keys.values()),
            "unique_valid_source_keys": sum(k["source_valid"] for k in keys.values()),
            "baseline_unique_valid_source_keys": len(baseline_complete),
            "new_unique_valid_source_keys_since_baseline": len(seen_complete - baseline_complete),
            "raw_word_families": len(patterns["raw_word_families"]),
            "historical_exact_atlas_strip_aliases": (alias_summary or {}).get("summary", {}).get("exact_atlas_upload_aliases"),
            "queries": sum(k["query_records"] for k in keys.values()),
            "gl_submissions": sum(k["gl_submission_records"] for k in keys.values()),
            "uninstalled_queried_keys": sum(k["query_records"] > 0 and not k["installed_manifest_member"] for k in keys.values()),
            "runs_source_cap_reached": sum(bool(r["native_caps"].get("sources")) for r in runs),
            "runs_intentionally_source_filtered": sum(r["source_filter"]["policy"] != "all" for r in runs),
            "source_filter_compliance_errors": sum(r["source_filter_compliance"]["status"] != "PASS" for r in runs),
            "semantic_context_excluded_runs": [r["id"] for r in runs if r["stage_context"].get("semantic_evidence_eligible") is False],
            "material_attribution_rows": sum(r["material_attribution"]["rows_with_fields"] for r in runs),
            "malformed_material_attribution_rows": sum(r["material_attribution"]["malformed_rows"] for r in runs),
            "catalog_task_states_unchanged": dict(Counter(x["catalog_verification_state"] for x in task_rows)),
            "technical_requirements_passed": sum(r["status"] == "PASS" for r in technical),
            "technical_requirements_total": len(technical),
            "component_requirements": len(component_rows), "explicitly_accepted_component_requirements": accepted_components,
            "gp0_frames_hash_checked": sum(x["frames"] for x in gp0),
            "gp0_integrity_errors": sum(len(x["errors"]) for x in gp0),
            "stage1_end_to_end_accepted": False, "full_game_coverage_percent": None},
        "runs": [{k: v for k, v in r.items() if not k.startswith("_")} for r in runs],
        "excluded_runs": excluded, "tasks": task_rows, "component_requirements": component_rows,
        "source_novelty": novelty,
        "technical_acceptance": technical,
        "gp0_bundles": gp0,
        "patterns": {"path": relative(args.patterns_output), "same_frame_uv_overlap_edges": len(patterns["same_frame_page_clut_uv_overlaps"])},
        "acceptance_gaps": ["No complete named actor/part/weapon/effect ownership map.",
            "No reviewed all-parts material acceptance preserving requested stripes and hit glow.",
            "Drache assault and boss destruction remain explicit capture/review gates.",
            "Stage1 end-to-end and alternative-route coverage require explicit evidence; later-stage/full-game completeness is not inferred."],
        "root_cause_findings": [
            {"finding": "Exact indexed-word rectangle matching in the independent alias audit bridges historical boss native pages to upload-strip source keys.",
             "evidence": {"report": ref(alias_path), "summary": alias_summary["summary"]} if alias_summary else None,
             "scope": "Saved broader-history technical source identity; not current-run source counts, actor ownership or complete visible skin acceptance.",
             "next_action": "Use the byte-valid aliases as temporary diagnostic candidates; prove visible whole-actor coverage with stock/scoped comparisons before permanent mapping."},
            {"finding": "Existing whole-boss camouflage may remain because full native-page candidates and smaller upload-strip replacement targets are distinct keys.",
             "evidence": {"candidate_crc_families": list(DRACHE),
                          "same_frame_page_clut_uv_overlap_edges": len(patterns["same_frame_page_clut_uv_overlaps"])},
             "scope": "Grounded technical explanation; exact actor/part ownership and final visible effect still require review.",
             "next_action": "Match targeted native-page and upload-strip original bytes/CLUT and UV regions; validate each requested finish on all visible parts."},
            {"finding": "A raw archive ceiling can omit later new sources while RAM and sampled draw recording continue.",
             "runs_with_source_cap": [r["id"] for r in runs if r["native_caps"].get("sources")],
             "next_action": "Reserve fresh source capacity around the named target or use validated target-key filtering; never infer completeness from a live RAM sampler."},
            {"finding": "Source archive identity, query evidence, actual GL submission, visual appearance and semantic ownership are separate gates.",
             "next_action": "Use the separate source/query/GL/visual fields and explicit narrow reviews; retain unresolved ownership states."},
            {"finding": "Wasp30 was visible earlier but the marked Wasp fire pair starts after equipment changed.",
             "next_action": "Verify pod identity in the exact before frame; isolate Square stock fire and Cross pod fire with short paired sequences. PostDrache Square evidence must stay stock-only."},
        ],
        "necessary_targeted_captures": [
            {"capture": "stable stock/player-only/enemy-only/combined finish views", "purpose": "Verify all player wing/mechanical keys and enemy body changes while preserving HUD, stripe and glow", "current_post_drache_feasibility": "only if relevant actors remain in current view; early enemies otherwise require a new natural Stage1 pass"},
            {"capture": "HUD-confirmed no-fire/stock-fire/pod-fire intervals", "purpose": "Separate hull, attachment, muzzle, projectile and impact ownership; avoid previous Wasp mislabel", "current_post_drache_feasibility": "stock possible; named pod only if equipped and visible"},
            {"capture": "fresh source-quota run before each boss", "purpose": "Capture boss part/CLUT variants before 224-source saturation", "current_post_drache_feasibility": "requires a new natural Stage1 pass for Greif/Drache"},
            {"capture": "Drache whole-body walking, deployed assault/cyan beam, final destruction", "purpose": "Close phase, boss-part and destruction gaps", "current_post_drache_feasibility": "past encounter cannot be recovered from paused postDrache state without a new natural pass or independently validated checkpoint"},
        ],
        "limitations": ["A CRC family, palette variant, file count, same-frame UV overlap or material receipt is not an enemy/model count.",
            "All source-key associations remain candidates unless an independent semantic mapping review establishes ownership.",
            "Runtime limits and sampling skips qualify completeness; missing sampled records cannot establish absence.",
            "Exact source filters intentionally omit raw keys outside the selected policy; no source-cap flag does not mean exhaustive capture.",
            "CPU VRAM can be stale; screenshots, periodic windows and GP0/source channels are not jointly atomic.",
            "Original catalog/task statuses are copied unchanged. Requirement-level acceptance does not authorize or validate RAM writes.",
            "Old setup/attract/limited-sampler runs are excluded from current coverage totals and listed explicitly."]}
    patterns.update({"schema_version": 1, "generated_at_utc": ledger["generated_at_utc"],
                     "scope": "Indexed source/palette identity and sampled same-frame page/CLUT/UV overlap; no automatic actor or part ownership promotion."})
    args.patterns_output.write_text(json.dumps(patterns, indent=2) + "\n", encoding="utf-8")
    ledger["patterns"]["sha256"] = file_sha(args.patterns_output)
    args.output.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "patterns": str(args.patterns_output), "summary": ledger["summary"]}))
    return 0 if not ledger["summary"]["integrity_errors"] and not review_errors and not ledger["summary"]["gp0_integrity_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
