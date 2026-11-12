"""Reconcile existing remaster candidates without changing packs or a game.

Run with Python 3.11+; only the JSON report is written. Actual PNG bytes are
hashed, while source/semantic/live claims remain attributed to their manifests.
The report is a merge review queue, never a visual acceptance or release gate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
STAGING = ROOT.parent / "REMASTER_STAGING/full-remaster"
KEY = re.compile(r"[0-9A-F]{8}-[0-9A-F]{8}")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def key_of(row):
    value = row.get("key", row.get("name", "")).upper().removesuffix(".PNG")
    if not KEY.fullmatch(value):
        raise ValueError("Invalid texture key: " + repr(value))
    return value


def entries(doc):
    rows = doc.get("files", doc.get("assets", []))
    return rows or ([doc] if doc.get("key") and doc.get("outputs") else [])


def output_path(value, manifest, fallback=None):
    if value:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (manifest.parent / path).resolve()
    if fallback:
        return fallback.resolve()
    raise ValueError("No output path in " + str(manifest))


def process_kind(row, authored=False):
    if row.get("neural_detail") is True:
        return "neural_upscale"
    text = str(row.get("method", "")).lower()
    if row.get("neural_detail") is False or "nearest" in text:
        return "nearest_enlargement"
    return "authored_restoration_candidate" if authored else "unclassified_candidate"


def inspect_file(path):
    try:
        before = path.stat()
        digest = sha(path)
        result = dict(path=str(path), sha256=digest, bytes=before.st_size)
        if path.suffix.lower() == ".png":
            with path.open("rb") as stream:
                header = stream.read(33)
            if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise ValueError("Invalid PNG IHDR")
            result["png_size"] = list(struct.unpack(">II", header[16:24]))
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("File changed during hash inspection")
        return result
    except (OSError, ValueError) as exc:
        return dict(path=str(path), error=str(exc))


def validate_legacy_composition(candidate, check):
    """A v6 composition snapshot cannot certify a later layered candidate."""
    if check.get("final_count") != candidate.get("final_count", len(entries(candidate))):
        raise ValueError("Composition check final_count differs from candidate; use --composition-source candidate-ledger for layered candidates")
    current = candidate.get("overlay_manifests", {})
    for group, receipt in check.get("overlay_manifests", {}).items():
        if group not in current or receipt.get("sha256") != current[group].get("sha256"):
            raise ValueError("Composition check has a stale or mismatching overlay: " + group)


def candidate_ledger_report(candidate_path, base_path, expanded_path, queue_path, workers=4):
    """Audit final chosen bytes and explicit lineage, without guessing overlays.

    Metadata references include reports, runtimes and old candidates. They are
    hash-checked references only. Per-file overlay_sources is an ordered ledger;
    only its final entry selects the output. Region geometry is not re-proved.
    """
    documents, inputs = {}, {}
    for name, path in (("ui", candidate_path), ("base", base_path), ("expanded", expanded_path), ("queue", queue_path)):
        payload = path.read_bytes()
        documents[name] = (path, json.loads(payload.decode("utf-8-sig")))
        # Bind the reported input hash to the exact JSON bytes parsed, then
        # compare the on-disk file again with the other hash requests below.
        inputs[name] = dict(path=str(path.resolve()), sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
    failures, requests, loaded, indexes = [], {}, {}, {}

    def fail(kind, **details):
        failures.append(dict(kind=kind, **details))

    def add_file(value, manifest, expected, role):
        path = output_path(value, manifest)
        request = requests.setdefault(str(path), dict(path=path, expected=set(), roles=set()))
        request["roles"].add(role)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            fail("missing_or_invalid_declared_hash", path=str(path), role=role)
        else:
            request["expected"].add(expected.lower())
        return str(path)

    def referenced_doc(receipt, manifest, role):
        path = add_file(receipt.get("path"), manifest, receipt.get("sha256"), role)
        if path not in loaded:
            try:
                loaded[path] = load(path)
            except (OSError, ValueError) as exc:
                fail("referenced_document_unreadable", path=path, error=str(exc))
                loaded[path] = {}
        return loaded[path], Path(path)

    for name, receipt in inputs.items():
        add_file(receipt["path"], documents[name][0], receipt["sha256"], "parsed_input:" + name)

    for group in ("base", "expanded", "ui"):
        manifest, doc = documents[group]
        rows = indexes[group] = {}
        for row in entries(doc):
            key = key_of(row)
            if key in rows:
                fail("duplicate_manifest_key", group=group, key=key)
            value = row.get("composed_path") if group == "ui" else None
            value = value or row.get("path", row.get("output"))
            fallback = manifest.parent / ("pack/einhander-texture-replacements" if group == "ui" else "einhander-texture-replacements") / (key + ".png")
            path = output_path(value, manifest, fallback)
            if group == "ui":
                canonical = fallback.resolve()
                if path != canonical:
                    fail("candidate_composed_path_not_canonical", key=key, declared=str(path), expected=str(canonical))
                # Always inspect the actual candidate pack, even when a stale
                # or redirected composed_path names a valid source elsewhere.
                path = canonical
            rows[key] = dict(row=row, path=add_file(str(path), manifest, row.get("sha256", row.get("output_sha256")), group))
        directory = manifest.parent / ("pack/einhander-texture-replacements" if group == "ui" else "einhander-texture-replacements")
        actual_keys = {p.stem.upper() for p in directory.glob("*.png")}
        if actual_keys != set(rows):
            fail("manifest_directory_key_mismatch", group=group, unlisted=sorted(actual_keys-set(rows)), missing=sorted(set(rows)-actual_keys))

    current = documents["ui"][1]
    if current.get("final_count", len(indexes["ui"])) != len(indexes["ui"]):
        fail("candidate_final_count_mismatch", declared=current.get("final_count"), actual=len(indexes["ui"]))
    if current.get("base_manifest_sha256") != inputs["base"]["sha256"]:
        fail("candidate_base_manifest_mismatch", path=str(base_path))

    # Audit references as references; their presence never grants precedence.
    for group, receipt in current.get("overlay_manifests", {}).items():
        add_file(receipt.get("path"), candidate_path, receipt.get("sha256"), "metadata_reference:" + group)

    provenance = {}
    for key, item in indexes["ui"].items():
        row = item["row"]
        declared = row.get("sha256")
        source = add_file(row.get("path"), candidate_path, declared, "selected_source:" + key)
        chain = row.get("overlay_sources", [])
        for receipt in chain:
            add_file(receipt.get("path"), candidate_path, receipt.get("sha256"), "overlay_lineage:" + key)
        if chain:
            if chain[-1].get("sha256") != declared:
                fail("last_overlay_does_not_select_final_bytes", key=key, selected=chain[-1].get("sha256"), final=declared)
            provenance[key] = dict(kind="ordered_overlay_selection", selected_source=source,
                overlay_count=len(chain), declared_origin=row.get("origin"), region_geometry_rechecked=False)
        elif key in indexes["base"] and indexes["base"][key]["row"].get("sha256") == declared:
            provenance[key] = dict(kind="base_bytes_preserved", selected_source=source)
        else:
            provenance[key] = dict(kind="selected_source_only_earlier_provenance_unknown", selected_source=source,
                                   declared_origin=row.get("origin"))

    # New title candidates retain typography metadata from their parent. The
    # known newer title layer takes precedence; its hash-bound parent must
    # carry the inherited typography layer unchanged. Unknown future layers
    # remain outside this audit until their schema is explicitly supported.
    layer = next((name for name in ("title_e_composition", "typography_composition") if current.get(name)), None)
    composition = current.get(layer) if layer else None
    composition_summary = dict(kind="no_supported_explicit_parent", evaluated=False)
    if composition:
        parent, parent_path = referenced_doc(composition["parent"], candidate_path, "composition_parent")
        inherited_fields = ("parent", "changes", "changed_keys", "unchanged_keys")
        if layer == "title_e_composition" and any(current.get("typography_composition", {}).get(field) != parent.get("typography_composition", {}).get(field) for field in inherited_fields):
            fail("inherited_typography_composition_differs_from_title_parent")
        parent_rows = {key_of(row): row for row in entries(parent)}
        changes, additions = {}, set()
        for change in composition.get("changes", []):
            key = key_of(change)
            if key in changes:
                fail("duplicate_composition_change", key=key)
            changes[key] = change
            parent_receipt, output = change["parent"], change["output"]
            add_file(parent_receipt.get("path"), candidate_path, parent_receipt.get("sha256"), "change_parent:" + key)
            add_file(output.get("path"), candidate_path, output.get("sha256"), "change_output:" + key)
            manifest_receipt = change.get("manifest", composition.get("manifest"))
            if not manifest_receipt:
                fail("composition_change_missing_manifest", key=key)
                manifest, manifest_path = {}, candidate_path
            else:
                manifest, manifest_path = referenced_doc(manifest_receipt, candidate_path, "change_manifest:" + key)
            authored = [r for r in entries(manifest) if key_of(r) == key]
            authored_output = authored[0].get("outputs", {}).get("pack", authored[0]) if len(authored) == 1 else {}
            if authored_output.get("sha256", authored_output.get("output_sha256")) != output.get("sha256"):
                fail("composition_output_not_bound_to_authoring_manifest", key=key, manifest=str(manifest_path))
            if key in parent_rows:
                if parent_rows[key].get("sha256") != parent_receipt.get("sha256"):
                    fail("composition_parent_key_mismatch", key=key, parent=str(parent_path))
            elif len(authored) == 1 and authored[0].get("source_verified_new_key") is True and authored[0].get("parent", {}).get("sha256") == parent_receipt.get("sha256"):
                # Explicit new-key supplements have a native source parent,
                # rather than an entry in the earlier candidate's file table.
                # This verifies the declared source bytes, not raw VRAM/CLUT.
                additions.add(key)
            else:
                fail("composition_new_key_lacks_bound_source_parent", key=key, parent=str(parent_path))
            if key not in indexes["ui"] or indexes["ui"][key]["row"].get("sha256") != output.get("sha256"):
                fail("composition_output_not_selected", key=key)
        changed = {k for k, item in indexes["ui"].items()
                   if k not in parent_rows or item["row"].get("sha256") != parent_rows[k].get("sha256")}
        if changed != set(changes) or set(parent_rows) - set(indexes["ui"]):
            fail("composition_change_set_mismatch", undeclared=sorted(changed-set(changes)),
                 unchanged_declared=sorted(set(changes)-changed), removed=sorted(set(parent_rows)-set(indexes["ui"])))
        if composition.get("changed_keys", len(changes)) != len(changes) or composition.get("unchanged_keys", len(indexes["ui"])-len(changes)) != len(indexes["ui"])-len(changes):
            fail("composition_change_counts_mismatch")
        composition_summary = dict(kind="hash_bound_parent_and_keyed_changes", evaluated=True,
                                   layer=layer, parent=str(parent_path), changed_keys=len(changes), added_keys=len(additions),
                                   replaced_keys=len(changes)-len(additions), unchanged_keys=len(indexes["ui"])-len(changes))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        actuals = {r["path"]: r for r in pool.map(inspect_file, [r["path"] for r in requests.values()])}
    for path, request in requests.items():
        actual = actuals[path]
        if actual.get("error"):
            fail("file_unreadable", **actual)
        elif request["expected"] != {actual["sha256"]}:
            fail("hash_mismatch", path=path, declared_sha256=sorted(request["expected"]), actual_sha256=actual["sha256"])
    for key, item in indexes["ui"].items():
        declared_size = item["row"].get("dimensions")
        if declared_size is not None and declared_size != actuals[item["path"]].get("png_size"):
            fail("candidate_dimensions_mismatch", key=key, declared=declared_size, actual=actuals[item["path"]].get("png_size"))

    queue_keys = set()
    for row in entries(documents["queue"][1]):
        key = key_of(row)
        if key in queue_keys:
            fail("duplicate_queue_key", key=key)
        queue_keys.add(key)
    ui_keys, expanded_keys = set(indexes["ui"]), set(indexes["expanded"])
    records, relations = [], Counter()
    for key in sorted(queue_keys | ui_keys | expanded_keys | set(indexes["base"])):
        variants = {}
        for group in indexes:
            if key in indexes[group]:
                item = indexes[group][key]
                variants[group] = dict(path=item["path"], declared_sha256=item["row"].get("sha256"),
                                       actual_sha256=actuals[item["path"]].get("sha256"), png_size=actuals[item["path"]].get("png_size"))
        if key in expanded_keys and key in ui_keys:
            # Missing files never compare as identical None/None hashes.
            same = variants["ui"]["actual_sha256"] and variants["ui"]["actual_sha256"] == variants["expanded"]["actual_sha256"]
            relation = "identical_expanded_and_ui" if same else "conflict_keep_ui_pending_region_review"
        elif key in expanded_keys:
            relation = "expanded_only_omitted_pending_source_and_visual_review"
        elif key in ui_keys:
            relation = "ui_only_preserve_current"
        else:
            relation = "absent_from_both_current_candidates"
        relations[relation] += 1
        records.append(dict(key=key, variants=variants, reconciliation=relation,
                            provenance=provenance.get(key), merge_action="none_report_only"))
    return dict(schema_version=2, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="integrity_pass_merge_review_required" if not failures else "integrity_failure_merge_blocked",
        composition_source="candidate-ledger", scope="Current candidate selected bytes, declared lineage and source-key omissions",
        invariants=dict(packs_modified=False, runtime_modified=False, game_actions=0, visual_acceptance_evaluated=False,
                        source_words_redecoded=False, png_full_decode_performed=False, report_only=True),
        inputs=inputs,
        counts=dict(base_keys=len(indexes["base"]), expanded_keys=len(expanded_keys), current_ui_keys=len(ui_keys),
            queue_keys=len(queue_keys), queue_keys_missing_current_ui=len(queue_keys-ui_keys),
            queue_keys_missing_expanded=len(queue_keys-expanded_keys), union_expanded_and_ui=len(expanded_keys | ui_keys),
            files_hashed=len(actuals), bytes_hashed=sum(r.get("bytes", 0) for r in actuals.values()),
            provenance=dict(Counter(r["kind"] for r in provenance.values())), reconciliation=dict(relations)),
        explicit_omissions=dict(queue_not_in_current_ui=sorted(queue_keys-ui_keys), queue_not_in_expanded=sorted(queue_keys-expanded_keys),
            expanded_not_in_ui=sorted(expanded_keys-ui_keys), ui_not_in_expanded=sorted(ui_keys-expanded_keys)),
        composition=composition_summary, records=records, integrity_failures=failures,
        verification_limit="SHA256, selected-source lineage and PNG IHDR checks only. Metadata references grant no overlay precedence. Earlier ownership/region provenance may remain unknown. No full PNG decode, source/UV geometry, semantic, live visibility, animation, quality, pacing or full-game acceptance is established.")


def run(args):
    base_path = args.base / "manifest.json"
    expanded_path = args.expanded / "manifest.json"
    queue_path = args.staging / "queue.json"
    batch_path = args.staging / "world-machines/manifest.json"
    candidate_path = args.candidate / "candidate.json"
    check_path = args.composition_check
    documents = {name: (path, load(path)) for name, path in (
        ("base", base_path), ("expanded", expanded_path), ("queue", queue_path),
        ("world_batch", batch_path), ("ui", candidate_path), ("composition_check", check_path))}
    validate_legacy_composition(documents["ui"][1], documents["composition_check"][1])
    records = {}
    requests = {}
    inputs = {name: ref(path) for name, (path, _) in documents.items()}
    failures = []

    def add_file(path, expected=None):
        path = Path(path).resolve()
        request = requests.setdefault(str(path), dict(path=path, expected=set()))
        if expected:
            request["expected"].add(expected.lower())
        return str(path)

    def record(key):
        return records.setdefault(key, dict(key=key, variants=[], source_queue=[], authored_alternatives=[]))

    def add_variant(group, row, manifest, authored=False, mode="pack"):
        key = key_of(row)
        output = row.get("outputs", {}).get(mode, row)
        value = output.get("composed_path") if group == "ui" else None
        value = value or output.get("path", output.get("output"))
        path = output_path(value, manifest, manifest.parent / "einhander-texture-replacements" / (key + ".png"))
        digest = output.get("sha256", output.get("output_sha256"))
        item = dict(group=group, manifest=str(manifest.resolve()), output_mode=mode,
                    path=add_file(path, digest), declared_sha256=digest,
                    process=process_kind(row, authored), declared_method=row.get("method"),
                    declared_source_verified=row.get("source_verified", row.get("source_crc_verified")),
                    declared_status=row.get("status", row.get("in_game_acceptance")),
                    semantic_acceptance="not_evaluated_by_reconciliation")
        if group == "ui":
            item["declared_composition_origin"] = row.get("origin")
            item["declared_source_path"] = row.get("path")
        for field in ("input_sha256", "source_sha256", "source_pixel_sha256", "raw_sha256", "clut_sha256",
                      "source_words_sha256", "source_clut_sha256", "protected_rects", "selected_native_regions",
                      "restored_native_regions", "region_half_open", "role", "roles", "kind"):
            if field in row:
                item[field] = row[field]
        record(key)["variants"].append(item)
        return item

    for group in ("base", "expanded", "ui"):
        path, doc = documents[group]
        seen = set()
        for row in entries(doc):
            key = key_of(row)
            if key in seen:
                failures.append(dict(kind="duplicate_manifest_key", group=group, key=key))
            seen.add(key)
            add_variant(group, row, path)
        replacement_dir = path.parent / ("pack/einhander-texture-replacements" if group == "ui" else "einhander-texture-replacements")
        actual_keys = {p.stem.upper() for p in replacement_dir.glob("*.png")}
        if actual_keys != seen:
            failures.append(dict(kind="manifest_directory_key_mismatch", group=group,
                                 unlisted=sorted(actual_keys-seen), missing=sorted(seen-actual_keys)))

    for row in documents["queue"][1]["assets"]:
        item = {k: row[k] for k in ("source", "source_size", "source_pixel_sha256", "raw_sha256", "clut_sha256",
                                   "source_verified", "kind", "first_frame", "source_metadata") if k in row}
        item["proof_status"] = "manifest_claim_not_redecoded_in_this_run"
        record(key_of(row))["source_queue"].append(item)
    for row in documents["world_batch"][1]["assets"]:
        add_variant("world_batch", row, batch_path)

    selected_manifests = documents["composition_check"][1]["overlay_manifests"]
    selected_paths = {str(Path(r["path"]).resolve()): (name, r) for name, r in selected_manifests.items()}
    authored = []
    for category in ("hud-restoration", "menu-restoration"):
        for path in sorted((AUDIT / category).glob("*/manifest.json")):
            doc = load(path)
            selected = selected_paths.get(str(path.resolve()))
            receipt = ref(path)
            if selected and receipt["sha256"] != selected[1]["sha256"]:
                failures.append(dict(kind="selected_manifest_changed", path=str(path)))
            group = "authored:" + path.parent.name
            rows = entries(doc)
            receipt.update(id=group, selected_in_ui=selected[0] if selected else None,
                           declared_contract=doc.get("contract"), declared_method=doc.get("method"),
                           main_asset_count=len(rows), strict_comparison_count=0)
            for row in rows:
                for mode in row.get("outputs", {"pack": row}):
                    # Preview images are evidence, not a texture-pack proposal.
                    if mode not in {"pack", "strict-mask-pack", "strict_pack"}:
                        continue
                    variant = add_variant(group, row, path, authored=True, mode=mode)
                    variant["selected_manifest_group"] = selected[0] if selected else None
                    if mode != "pack":
                        variant["exclusion_reason"] = "strict_native_footprint_comparison_only"
                        receipt["strict_comparison_count"] += 1
            authored.append(receipt)

    materials = []
    for path in sorted((ROOT / "windows-x64/tools/material-profiles").glob("*/material.json")):
        doc = load(path)
        item = dict(**ref(path), profile=doc.get("profile"), enemy_profile=doc.get("enemy_profile"),
                    targets=doc.get("targets", []), enemy_targets=doc.get("enemy_targets", []),
                    declared_status=doc.get("status"), declared_in_game_verified=doc.get("in_game_verified"),
                    texture_pack_entries_added=0, treatment="runtime_rgb_material_parameters", detail_files=[])
        for role, detail in doc.get("authored_detail", {}).items():
            if detail.get("path"):
                item["detail_files"].append(dict(role=role, path=add_file(detail["path"], detail.get("sha256")),
                                                declared_sha256=detail.get("sha256")))
        for source in doc.get("source_textures", []):
            add_file(source["path"], source.get("sha256"))
        materials.append(item)
    material_catalog = ROOT / "windows-x64/tools/skin_collection/materials/materials.json"
    inputs["material_catalog"] = ref(material_catalog)
    for item in load(material_catalog)["maps"]:
        add_file(material_catalog.parent / (item["id"] + ".png"), item.get("sha256"))
    selection_path = ROOT / "windows-x64/tools/material-selection.json"
    inputs["saved_material_selection"] = ref(selection_path)
    saved_selection = load(selection_path)
    descriptor = ROOT / "windows-x64" / saved_selection["descriptor_relative"]
    add_file(descriptor, saved_selection["descriptor_sha256"])

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        actuals = {r["path"]: r for r in pool.map(inspect_file, [r["path"] for r in requests.values()])}
    for path, request in requests.items():
        actual = actuals[path]
        if actual.get("error"):
            failures.append(dict(kind="file_unreadable", **actual))
        elif request["expected"] and request["expected"] != {actual["sha256"]}:
            failures.append(dict(kind="hash_mismatch", path=path, declared_sha256=sorted(request["expected"]), actual_sha256=actual["sha256"]))

    material_files = []
    for item in load(material_catalog)["maps"]:
        path = str((material_catalog.parent / (item["id"] + ".png")).resolve())
        material_files.append(dict(id=item["id"], **actuals[path], declared_sha256=item.get("sha256"),
                                   hash_verified=actuals[path].get("sha256") == item.get("sha256"),
                                   declared_in_game_verified=item.get("in_game_verified")))
    for profile in materials:
        for detail in profile["detail_files"]:
            detail.update(actuals[detail["path"]])
            detail["hash_verified"] = detail.get("sha256") == detail["declared_sha256"]

    relations = Counter()
    for key, item in sorted(records.items()):
        variants = item["variants"]
        main = {r["group"]: r for r in variants if r["group"] in {"base", "expanded", "ui"}}
        current = main.get("ui")
        current_hash = actuals[current["path"]].get("sha256") if current else None
        for variant in variants:
            actual = actuals[variant["path"]]
            variant["actual_sha256"] = actual.get("sha256")
            variant["png_size"] = actual.get("png_size")
            variant["hash_verified"] = bool(variant["declared_sha256"] and actual.get("sha256") == variant["declared_sha256"])
            variant["relation_to_current_ui"] = ("not_in_current_ui" if not current else
                "identical_bytes" if current_hash and actual.get("sha256") == current_hash else "different_bytes")
        expanded = main.get("expanded")
        if expanded and current:
            item["reconciliation"] = "identical_expanded_and_ui" if expanded["actual_sha256"] == current["actual_sha256"] else "conflict_keep_ui_pending_region_review"
        elif expanded:
            item["reconciliation"] = "expanded_only_omitted_pending_source_and_visual_review"
        elif current:
            item["reconciliation"] = "ui_only_preserve_current"
        else:
            item["reconciliation"] = "absent_from_both_current_candidates"
        item["merge_action"] = "none_report_only"
        relations[item["reconciliation"]] += 1
        if current:
            item["current_ui_origin_candidates"] = sorted({v["selected_manifest_group"] for v in variants
                if v.get("selected_manifest_group") and v["output_mode"] == "pack" and v["actual_sha256"] == current_hash}) or ["base"]
        if item["source_queue"] and not current:
            item["current_ui_omission"] = "known_source_not_present_as_an_exact_texture_key"
        if len(item["source_queue"]) > 1:
            failures.append(dict(kind="duplicate_queue_key", key=key, count=len(item["source_queue"])))

    # Independently reconstruct current UI precedence from the selected manifests.
    # Differing menu overlays have already been bounded in the composition check;
    # this gate checks that its exact chosen bytes, rather than a stale pack, exist.
    expected_ui = {}
    for key, item in records.items():
        for variant in item["variants"]:
            if variant["group"] == "base":
                expected_ui[key] = variant["actual_sha256"]
    for selected_group in selected_manifests:
        for key, item in records.items():
            for variant in item["variants"]:
                if variant.get("selected_manifest_group") == selected_group and variant["output_mode"] == "pack":
                    expected_ui[key] = variant["actual_sha256"]
    actual_ui = {key: variant["actual_sha256"] for key, item in records.items()
                 for variant in item["variants"] if variant["group"] == "ui"}
    if expected_ui != actual_ui:
        failures.append(dict(kind="reconstructed_ui_differs_from_composed_files",
                             missing=sorted(set(expected_ui)-set(actual_ui)),
                             unlisted=sorted(set(actual_ui)-set(expected_ui)),
                             differing=sorted(k for k in set(expected_ui)&set(actual_ui) if expected_ui[k] != actual_ui[k])))

    group_counts = Counter(v["group"] for r in records.values() for v in r["variants"] if v["output_mode"] == "pack")
    queue_keys = {k for k, r in records.items() if r["source_queue"]}
    ui_keys = {k for k, r in records.items() if any(v["group"] == "ui" for v in r["variants"])}
    expanded_keys = {k for k, r in records.items() if any(v["group"] == "expanded" for v in r["variants"])}
    base_keys = {k for k, r in records.items() if any(v["group"] == "base" for v in r["variants"])}
    result = dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="integrity_pass_merge_review_required" if not failures else "integrity_failure_merge_blocked",
        scope="Existing base, expanded, prepared UI, source queue, local authored alternatives and runtime material profiles",
        invariants=dict(packs_modified=False, runtime_modified=False, game_actions=0, visual_acceptance_evaluated=False,
                        source_words_redecoded=False, png_full_decode_performed=False, report_only=True),
        inputs=inputs, counts=dict(base_keys=len(base_keys), expanded_keys=len(expanded_keys), current_ui_keys=len(ui_keys),
            queue_keys=len(queue_keys), queue_rejected_observations=len(documents["queue"][1].get("rejected_observations", [])),
            world_batch_keys=group_counts["world_batch"], union_expanded_and_ui=len(expanded_keys|ui_keys),
            queue_keys_missing_current_ui=len(queue_keys-ui_keys), queue_keys_missing_expanded=len(queue_keys-expanded_keys),
            authored_manifests=len(authored), material_profiles=len(materials), files_hashed=len(actuals),
            bytes_hashed=sum(r.get("bytes", 0) for r in actuals.values()), reconciliation=dict(relations)),
        merge_policy=["Preserve prepared UI bytes when an expanded key differs; review exact native regions before any composition.",
            "Expanded-only keys remain omitted until source/CLUT/UV ownership, alpha, protection and in-game behavior are checked.",
            "Identical bytes can share provenance; they do not gain semantic or visual acceptance.",
            "Strict-mask outputs are comparison artifacts, never automatic replacements for contour-authored main outputs.",
            "Runtime material descriptors add no texture-pack keys and do not map every ship, weapon, part or phase."],
        queue_rejected_observations=documents["queue"][1].get("rejected_observations", []),
        explicit_omissions=dict(queue_not_in_current_ui=sorted(queue_keys-ui_keys), queue_not_in_expanded=sorted(queue_keys-expanded_keys),
            expanded_not_in_ui=sorted(expanded_keys-ui_keys), ui_not_in_expanded=sorted(ui_keys-expanded_keys)),
        authored_candidates=authored, material_profiles=materials, material_files=material_files,
        saved_material_selection=saved_selection,
        reconstructed_ui_provenance_matches=(expected_ui == actual_ui),
        records=[records[k] for k in sorted(records)], integrity_failures=failures,
        verification_limit="SHA256 and PNG IHDR checks establish file integrity only. Counts are keys/palette variants, not accepted objects. No source, live visibility, animation, quality, pacing or full-game acceptance was promoted.")
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), sha256=sha(args.output), status=result["status"], counts=result["counts"], integrity_failures=len(failures))))
    return 0 if not failures else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "windows-x64/hd-textures/stage1-v1")
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--expanded", type=Path, default=STAGING / "stage1-expanded")
    parser.add_argument("--candidate", type=Path, default=AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6")
    parser.add_argument("--composition-source", choices=("legacy-check", "candidate-ledger"), default="legacy-check",
                        help="Keep the legacy v6 overlay check, or audit a later candidate's selected-file ledger and explicit parent changes")
    parser.add_argument("--composition-check", type=Path, default=AUDIT / "hud-restoration/final-composition-check.json",
                        help="Hash-matching overlay snapshot for legacy-check mode")
    parser.add_argument("--output", type=Path, default=AUDIT / "pack-reconciliation.json")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.parent != AUDIT.resolve() or not args.output.name.startswith("pack-reconciliation") or args.output.suffix != ".json":
        parser.error("Report output must be a pack-reconciliation*.json file in remaster-audit")
    if args.composition_source == "candidate-ledger":
        result = candidate_ledger_report(args.candidate / "candidate.json", args.base / "manifest.json",
                                        args.expanded / "manifest.json", args.staging / "queue.json", args.workers)
        args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(dict(output=str(args.output), sha256=sha(args.output), status=result["status"],
                             counts=result["counts"], integrity_failures=len(result["integrity_failures"]))))
        return 0 if not result["integrity_failures"] else 1
    try:
        return run(args)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
