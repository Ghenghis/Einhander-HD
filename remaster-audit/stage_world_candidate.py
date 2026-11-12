"""Stage v6 plus exactly the 140 verified absent mixed-world source keys.

Default preparation never launches a game. This is a processing-only isolated
integration experiment; it preserves every v6 choice and does not accept
authored detail, ownership, ordered animation, or visible replacement coverage.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image

import launch_ui_candidate as ui
import verify_world_source_backlog as world


ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ROOT / "remaster-audit/dev-center-evidence"
PARENT = ALLOWED / "hud-4k-candidate-20261112-v6"
DEFAULT_EVIDENCE = ALLOWED / "hud-world-candidate-20261112-v7"
BACKLOG = ROOT / "remaster-audit/background-audit-20261112/world-source-backlog-revalidation.json"
TITLE = "Einhander - HUD and world v7 experiment"
SIDECAR_SUFFIXES = (".png", ".words.bin", ".clut.bin", ".valid.bin", ".source.json")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def file_receipt(path):
    return dict(path=str(path), sha256=ui.sha(path))


def references_unique(rows):
    references = {}
    for row in rows:
        path = str(Path(row["path"]).resolve())
        if path in references:
            require(references[path] == row["sha256"], "Conflicting evidence hash: " + path)
        references[path] = row["sha256"]
    return [dict(path=path, sha256=digest) for path, digest in sorted(references.items())]


def closed_private_seed():
    seed = load(PARENT / "private-card-seed.json")
    source = Path(seed["source"]).resolve()
    expected_root = ALLOWED / "hud-4k-candidate-20261112-v4"
    require(source == expected_root / "state/card1.mcd", "Expected the previously closed private v4 seed")
    require(seed["source_process_closed"] is True and seed["user_cards_mounted"] is False, "Private seed has no closed/user-isolation receipt")
    require(ui.sha(source) == seed["source_sha256"], "Closed private PILOT source changed")
    directory = Path(seed["source_directory_proof"])
    proof = load(directory)
    require(proof["sha256"] == seed["source_sha256"] and proof["bytes"] == 131072 and
            proof["header"] == "MC" and any(r.get("pilot") and r.get("directory_xor") for r in proof["entries"]),
            "Closed private seed lacks a valid PILOT directory proof")
    command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'Einhander_Recompiled.exe' } | "
               "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, timeout=20, check=True)
    active = json.loads(result.stdout) if result.stdout.strip() else []
    active = [active] if isinstance(active, dict) else active
    for row in active:
        executable = str(row.get("ExecutablePath") or "")
        arguments = str(row.get("CommandLine") or "")
        require(str(expected_root).lower() not in (executable + " " + arguments).lower(),
                "The private v4 card source may be in active use")
    return source, dict(source=str(source), source_sha256=seed["source_sha256"],
                        source_directory_proof=file_receipt(directory), parent_seed_receipt=file_receipt(PARENT / "private-card-seed.json"),
                        source_process_absent_now=True, profile="PILOT", user_cards_mounted=False,
                        process_check_at_utc=stamp())


def plan(evidence):
    evidence = ui.owned(evidence, ALLOWED)
    require(not evidence.exists(), "Staging requires a fresh evidence directory")
    parent = ui.load_report(PARENT)
    ui.verify_provenance(parent)
    require(parent["final_count"] == len(parent["files"]) == 1011, "Expected unchanged v6 1,011-key parent")
    backlog = load(BACKLOG)
    require(backlog["summary"]["failures"] == 0 and backlog["summary"]["absent_current_candidate"] == 140,
            "World backlog does not pass the expected 140-key contract")
    for reference in backlog["evidence_inputs"]:
        require(ui.sha(reference["path"]) == reference["sha256"], "World audit input changed: " + reference["path"])
    parent_rows = {r["name"].removesuffix(".png"): r for r in parent["files"]}
    require(len(parent_rows) == 1011, "Parent has duplicate keys")
    for row in parent_rows.values():
        require(ui.sha(row["composed_path"]) == row["sha256"] == ui.sha(row["path"]), "Parent source/composition changed: " + row["name"])
    queue = {r["key"]: r for r in load(world.STAGING / "queue.json")["assets"]}
    expanded_manifest = world.STAGING / "stage1-expanded/manifest.json"
    expanded = {r["key"]: r for r in load(expanded_manifest)["files"]}
    backlog_rows = {r["key"]: r for r in backlog["keys"]}
    missing = set(backlog["missing_keys"])
    require(len(missing) == 140 and not missing & set(parent_rows), "Addition set overlaps v6 or is not 140 keys")
    require(missing <= set(expanded), "Expanded pack lacks additions")
    conflicts = []
    for key in sorted(set(parent_rows) & set(expanded)):
        current, other = parent_rows[key], expanded[key]
        if current["sha256"] != other["sha256"]:
            conflicts.append(dict(key=key, decision="keep_v6_unresolved_region_review", selected_v6_sha256=current["sha256"],
                                  omitted_expanded_sha256=other["sha256"], expanded_processing_method=other["method"]))
    require(len(conflicts) == 320, "Expected all 320 expanded/v6 conflicts to remain unresolved")
    report = copy.deepcopy(parent)
    report.pop("launches", None)
    report.pop("prepared_at_utc", None)
    report.update(at_utc=stamp(), evidence=str(evidence), window_title=TITLE,
                  game_launched=False, production_installed=False, original_game_untouched=True)
    for row in report["files"]:
        row.pop("composed_path", None)
        row.pop("composition", None)
    references = [file_receipt(BACKLOG), file_receipt(expanded_manifest), file_receipt(world.STAGING / "queue.json"), file_receipt(Path(__file__))]
    source_rows = []
    for key in sorted(missing):
        audited = backlog_rows[key]
        require(audited["eligible_for_isolated_source_preserving_experiment"] is True,
                "Audit addition is not eligible: " + key)
        native, source_receipt = world.source_check(key, queue[key])
        prior = audited["source_checks"]
        for field in ("raw_words_sha256", "clut_sha256", "validity_sha256", "decoded_rgba_sha256", "metadata_sha256", "png_sha256"):
            require(source_receipt[field] == prior[field], "Native source evidence changed: " + key + " " + field)
        replacement = Path(audited["expanded_replacement_checks"]["path"])
        digest = ui.sha(replacement)
        require(digest == audited["expanded_replacement_checks"]["sha256"] == expanded[key]["sha256"],
                "Expanded addition changed: " + key)
        native.close()
        references.append(dict(path=str(replacement), sha256=digest))
        source = Path(queue[key]["source"])
        native_files = [file_receipt(source.with_suffix(suffix)) for suffix in SIDECAR_SUFFIXES]
        references.extend(native_files)
        addition = dict(name=key + ".png", path=str(replacement), sha256=digest,
                        bytes=replacement.stat().st_size, dimensions=expanded[key]["output_size"],
                        origin="world source-preserving addition",
                        overlay_sources=[dict(origin="world source-preserving addition", path=str(replacement), sha256=digest)],
                        processing_method=expanded[key]["method"], authored_detail_accepted=False, live_visual_accepted=False,
                        native_source_key=key, protected_native_uv_rectangles=expanded[key].get("protected_rects", []))
        report["files"].append(addition)
        source_rows.append(dict(key=key, source=source_receipt, native_files=native_files,
                                replacement=dict(path=str(replacement), sha256=digest, dimensions=expanded[key]["output_size"],
                                                 processing_method=expanded[key]["method"]),
                                semantic_state="unmapped", authored_detail_accepted=False, live_visual_accepted=False))
    report["overlay_manifests"]["parent_v6"] = dict(path=str(PARENT / "candidate.json"), sha256=ui.sha(PARENT / "candidate.json"),
                                                       asset_count=1011, contract="unchanged-parent-composition")
    report["overlay_manifests"]["world_backlog"] = dict(path=str(BACKLOG), sha256=ui.sha(BACKLOG), asset_count=140,
                                                          contract="source-preserving-missing-world-experiment-v1",
                                                          referenced_files=references_unique(references))
    report["source_counts"]["world_additions"] = 140
    report["overlay_input_count"] += 140
    report["final_count"] = len(report["files"])
    require(report["final_count"] == 1151, "Unexpected final key count")
    report["parent_composition"] = dict(path=str(PARENT / "candidate.json"), sha256=ui.sha(PARENT / "candidate.json"),
                                         selected_keys_preserved=1011, changed_keys=0)
    report["world_integration_experiment"] = dict(added_keys=sorted(missing), added_count=140,
                                                   preserved_overlap_conflicts=conflicts,
                                                   omitted_other_expanded_keys=sorted(set(expanded) - set(parent_rows) - missing),
                                                   processing_only=True, authored_completion_claimed=False,
                                                   live_verification_required=True, source_rows=source_rows)
    report["limitations"] += ["140 source-valid processing-only additions do not establish authored world detail or semantic ownership.",
                                "All 320 overlapping expanded/v6 differences retain v6 pending region review.",
                                "All stage, route, animation, lighting and final-build visual gates remain required."]
    seed_path, seed_receipt = closed_private_seed()
    return report, seed_path, seed_receipt


def decode_row(row):
    path = Path(row["composed_path"])
    require(ui.sha(path) == row["sha256"], "Composed PNG hash changed: " + row["name"])
    with Image.open(path) as image:
        image.load()
        require(image.format == "PNG" and list(image.size) == row["dimensions"], "Composed PNG decode/dimensions differ: " + row["name"])
        require(image.mode in ("RGBA", "RGB"), "Unexpected replacement PNG mode: " + row["name"])
        mode = image.mode
    return dict(name=row["name"], sha256=row["sha256"], dimensions=row["dimensions"], mode=mode, full_png_decode=True)


def revalidate(report, full_decode=True, require_unlaunched=False):
    evidence = Path(report["evidence"])
    require({"parent_v6", "world_backlog", "world_composition"} <= set(report["overlay_manifests"]),
            "World experiment provenance receipts are required")
    require(ui.sha(Path(__file__)) == report["world_launcher"]["sha256"], "World staging/launch wrapper changed")
    ui.verify_provenance(report)
    require(report["final_count"] == len(report["files"]) == 1151, "Unexpected v7 composition count")
    require(len({r["name"] for r in report["files"]}) == 1151, "Duplicate composed key")
    parent = load(PARENT / "candidate.json")
    selected = {r["name"]: r["sha256"] for r in report["files"]}
    require(all(selected.get(row["name"]) == row["sha256"] for row in parent["files"]), "v7 changed a v6 selection")
    require(set(selected) - {r["name"] for r in parent["files"]} == {key + ".png" for key in report["world_integration_experiment"]["added_keys"]},
            "v7 addition set differs from exact missing backlog")
    pngs = {p.name for p in (evidence / "pack/einhander-texture-replacements").glob("*.png")}
    require(pngs == set(selected), "Composed directory key set differs from plan")
    decoded = []
    if full_decode:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(decode_row, row) for row in report["files"]]
            for future in as_completed(futures):
                decoded.append(future.result())
                if len(decoded) % 100 == 0:
                    print(json.dumps(dict(full_png_decodes=len(decoded), total=1151)), flush=True)
    else:
        for row in report["files"]:
            require(ui.sha(ui.owned(row["composed_path"], evidence)) == row["sha256"], "Composed PNG changed: " + row["name"])
    modes = []
    for mode, spec in report["launches"].items():
        runtime = Path(spec["arguments"][0])
        require(runtime.is_relative_to(evidence) and ui.sha(runtime) == spec["executable_sha256"], "Prepared runtime changed")
        require(ui.sha(runtime.parent / "settings.toml") == spec["settings_sha256"], "Prepared settings changed")
        require(Path(spec["writable_state"]).is_relative_to(evidence), "Private writable state escaped experiment")
        overrides = spec["environment_overrides"]
        expected_pack = evidence / "pack" if mode == "candidate" else ui.BASE
        require(Path(overrides["PSXRECOMP_HD_TEXTURE_ROOT"]) == expected_pack, "Wrong pack launch root")
        require(overrides["EIN_DEBUG_PORT"] == "4371" and overrides["EIN_DEV_URL"] == "", "Wrong candidate port/bridge")
        require(all(key not in overrides for key in ui.CLEANED_ENVIRONMENT_KEYS), "Load/scheduler inherited override present")
        if require_unlaunched:
            require(not (evidence / ("launch-" + mode + ".json")).exists(), "Stale launch marker present")
        modes.append(mode)
    manifest = load(evidence / "world-additions-manifest.json")
    require(manifest["added_count"] == 140 and len(manifest["assets"]) == 140, "World sidecar manifest count differs")
    native_root = evidence / "native-sources"
    require(len(list(native_root.iterdir())) == 140 * 5, "Native source sidecar count differs")
    result = dict(at_utc=stamp(), ok=True, final_count=1151, parent_selected_keys_preserved=1011, added_source_keys=140,
                  full_png_decodes=len(decoded), all_png_hashes_checked=1151, provenance_verified=True,
                  native_source_files_checked=700, runtime_settings_modes_checked=sorted(modes),
                  unresolved_overlap_conflicts_preserved=320, game_actions=0, game_launched=False,
                  authored_completion_claimed=False, live_visual_acceptance=False,
                  candidate_receipt=file_receipt(evidence / "candidate.json"), staging_script=file_receipt(Path(__file__)))
    if decoded:
        result["pngs"] = sorted(decoded, key=lambda row: row["name"])
    return result


def rollback_plan(report):
    """Validate original base and private rollback runtime independently.

    The reversible fallback must remain usable if a world experiment PNG or
    its local native archive is damaged. It mounts the existing original base,
    and never mounts experimental assets or the candidate's private card.
    """
    evidence = Path(report["evidence"])
    require(ui.sha(Path(__file__)) == report["world_launcher"]["sha256"], "World staging/launch wrapper changed")
    manifest_path = ui.BASE / "manifest.json"
    require(ui.sha(manifest_path) == report["base_manifest_sha256"], "Original base manifest changed")
    directory, originals = ui.inventory(ui.BASE, "base")
    ui.verify_base(originals)
    require(len(originals) == 964, "Unexpected original base key count")
    spec = report["launches"]["rollback"]
    executable = ui.owned(spec["arguments"][0], evidence)
    require(ui.sha(executable) == spec["executable_sha256"] == report["runtime"]["sha256"], "Rollback executable changed")
    require(ui.sha(executable.parent / "settings.toml") == spec["settings_sha256"], "Rollback settings changed")
    require(Path(spec["environment_overrides"]["PSXRECOMP_HD_TEXTURE_ROOT"]) == ui.BASE, "Rollback does not mount original base")
    require(Path(spec["writable_state"]) == evidence / "state-rollback", "Rollback must use its separate private state")
    require(spec["environment_overrides"]["EIN_DEBUG_PORT"] == "4371" and spec["environment_overrides"]["EIN_DEV_URL"] == "", "Rollback port/bridge differs")
    require(all(key not in spec["environment_overrides"] for key in ui.CLEANED_ENVIRONMENT_KEYS), "Rollback has inherited load/scheduler override")
    rollback = copy.deepcopy(report)
    rollback["runtime_override"] = None
    rollback["overlay_manifests"] = dict(rollback_base=dict(path=str(manifest_path), sha256=report["base_manifest_sha256"],
                                                              asset_count=964, contract="original-base-independent-rollback-v1",
                                                              referenced_files=[dict(path=r["path"], sha256=r["sha256"]) for r in originals]))
    ui.verify_provenance(rollback)
    result = dict(at_utc=stamp(), ok=True, original_base_png_hashes_verified=964,
                  rollback_executable_verified=True, rollback_settings_verified=True,
                  separate_private_card_directory=True, experimental_file_dependencies=False,
                  experiment_pngs_or_sidecars_accessed=0, game_actions=0, rollback_tested_live=False,
                  launch_method="Existing receipt-checked launcher with original-base-only provenance")
    return rollback, result


def prepare(evidence):
    report, seed_path, seed_receipt = plan(evidence)
    ui.TITLE = TITLE
    ui.prepare(report)
    evidence = Path(report["evidence"])
    native_root = evidence / "native-sources"
    native_root.mkdir()
    copied_sources = []
    for row in report["world_integration_experiment"]["source_rows"]:
        native_files = []
        for reference in row["native_files"]:
            source = Path(reference["path"])
            target = native_root / source.name
            require(ui.copy_verified(source, target) == reference["sha256"], "Native archive copy changed")
            native_files.append(dict(path=str(target), sha256=reference["sha256"], source_path=str(source)))
        copied_sources.append(dict(row, copied_native_files=native_files))
    seed_targets = []
    for mode in ("candidate", "rollback"):
        target = Path(report["launches"][mode]["writable_state"]) / "card1.mcd"
        require(ui.copy_verified(seed_path, target) == seed_receipt["source_sha256"], "Private PILOT seed copy changed")
        seed_targets.append(dict(mode=mode, target=str(target), sha256=ui.sha(target)))
    seed_receipt.update(at_utc=stamp(), copies=seed_targets, target_restart_load_verified=False)
    write(evidence / "private-card-seed.json", seed_receipt)
    composition = dict(schema_version=1, at_utc=stamp(), parent=report["parent_composition"], added_count=140,
                       assets=copied_sources, conflicts=report["world_integration_experiment"]["preserved_overlap_conflicts"],
                       processing_only=True, game_launched=False, authored_completion_claimed=False, live_visual_acceptance=False)
    manifest_path = evidence / "world-additions-manifest.json"
    write(manifest_path, composition)
    report["overlay_manifests"]["world_composition"] = dict(path=str(manifest_path), sha256=ui.sha(manifest_path), asset_count=140,
                                                              contract="immutable-world-experiment-native-sidecars-v1",
                                                              referenced_files=references_unique([reference for row in copied_sources for reference in row["copied_native_files"]]))
    for mode in ("candidate", "rollback"):
        flag = " --rollback" if mode == "rollback" else ""
        launcher = '@echo off\r\n"' + sys.executable + '" "' + str(Path(__file__).resolve()) + '" --evidence "%~dp0." --launch' + flag + '\r\n'
        (evidence / ("launch-" + mode + ".cmd")).write_text(launcher, encoding="utf-8")
    report["world_launcher"] = dict(path=str(Path(__file__).resolve()), sha256=ui.sha(Path(__file__)),
                                    source_manifest=str(manifest_path), private_card_seed=str(evidence / "private-card-seed.json"))
    write(evidence / "candidate.json", report)
    validated = revalidate(report, full_decode=True, require_unlaunched=True)
    _, rollback_checked = rollback_plan(report)
    write(evidence / "rollback-isolation-check.json", rollback_checked)
    validated["private_card_seed"] = seed_receipt
    validated["rollback_tested_live"] = False
    validated["rollback_isolation_check"] = file_receipt(evidence / "rollback-isolation-check.json")
    write(evidence / "preparation-revalidation.json", validated)
    return {key: value for key, value in validated.items() if key not in ("pngs", "private_card_seed")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="Read-only full decode/provenance verification of an already staged v7")
    operation.add_argument("--launch", action="store_true", help="Validate unchanged experiment then use existing receipt-checked launcher")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    try:
        require(not args.rollback or args.launch, "--rollback requires --launch")
        if args.check or args.launch:
            report = ui.load_report(args.evidence)
            if args.rollback:
                rollback, _ = rollback_plan(report)
                result = ui.launch(rollback, True)
            else:
                result = revalidate(report, full_decode=args.check)
                if args.launch:
                    result = ui.launch(report, False)
                else:
                    result = {key: value for key, value in result.items() if key != "pngs"}
        else:
            result = prepare(args.evidence)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(ok=False, error=str(error), game_launched=False), indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
