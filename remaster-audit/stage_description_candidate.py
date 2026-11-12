"""Stage v7 world composition plus eleven bounded description outputs as v8.

Default preparation and --check never contact the game. Launching is explicit,
checks immutable source/protected-pixel/crop contracts again, and uses private
candidate/stock rollback runtimes and independently seeded private PILOT cards.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image

from build_three_asset_proof import verify_stock
import launch_ui_candidate as ui
import stage_world_candidate as world

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
PARENT = world.DEFAULT_EVIDENCE
FONT = AUDIT / "menu-restoration/description-continuity-candidate-v2"
DEFAULT_EVIDENCE = world.ALLOWED / "hud-world-font-candidate-20261112-v8"
TITLE = "Einhander - HUD world and font v8 experiment"
BASE_KEY = "BDAE4156-B88C038E"
REGIONS = [[0, 32, 64, 104], [192, 32, 256, 104], [0, 112, 64, 120], [192, 112, 256, 120]]
ALIAS_ROWS = {"E1F18F98-B88C038E": 32, "786B98BF-B88C038E": 40, "2C781811-B88C038E": 48,
              "921FC559-B88C038E": 56, "D050AD1B-B88C038E": 64, "5C02D3C1-B88C038E": 72,
              "913A6603-B88C038E": 80, "913FE978-B88C038E": 88, "5F101F62-B88C038E": 96,
              "AAA5C104-B88C038E": 112}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")


def receipt(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=ui.sha(path))


def pixels(path):
    with Image.open(path) as image:
        image.load()
        return np.asarray(image.convert("RGBA")).copy()


def verify_font(directory=FONT):
    """Independent raw/source, baseline, authored-region and alias verifier."""
    directory = Path(directory).resolve()
    manifest_path = directory / "manifest.json"
    manifest = load(manifest_path)
    require(manifest["contract"] == "verified-description-continuity-v1", "Unexpected font contract")
    rows = {r["key"]: r for r in manifest["files"]}
    require(len(rows) == len(manifest["files"]) == manifest["asset_count"] == 11 and
            set(rows) == {BASE_KEY} | set(ALIAS_ROWS), "Exact full-page plus ten-row key set required")
    references = [receipt(manifest_path), receipt(directory / "build-source.py"), receipt(Path(__file__))]
    # Include the builder's imported algorithms as explicit reproducibility inputs.
    references += [receipt(AUDIT / "build_coherent_font_candidate.py"), receipt(AUDIT / "build_three_asset_proof.py"),
                   receipt(AUDIT / "menu-restoration/font-strip-candidate-v6/palette-contour-library.py")]
    for item in manifest["references"]:
        require(ui.sha(item["path"]) == item["sha256"], "Font referenced evidence changed: " + item["path"])
        references.append(item)
    proof_root = directory / "source-proof"
    map_path = proof_root / "description-glyph-coverage.json"
    mapped = load(map_path)
    bounds = mapped["canonical_parent_repair_bounds"]
    require(bounds["key"] == BASE_KEY and bounds["coordinate_convention"] == "native source pixel half-open rectangles" and
            bounds["continuous_rectangles"] == REGIONS and mapped["summary"]["row_aliases_exact_raw_clut_verified"] == 10,
            "Captured canonical repair bounds or ten-row proof changed")
    references.append(receipt(map_path))
    v6_path = world.PARENT / "candidate.json"
    v6 = {r["name"][:-4]: r for r in load(v6_path)["files"]}
    references.append(receipt(v6_path))
    full_source, full_raw, full_clut = verify_stock(proof_root, BASE_KEY)
    require([full_source["width_words"], full_source["height"], full_source["depth"]] == [64, 256, 0] and
            len(full_raw) == 32768 and len(full_clut) == 32 and
            len((proof_root / (BASE_KEY+".valid.bin")).read_bytes()) == 16384,
            "Full-page source dimensions differ")
    full = pixels(rows[BASE_KEY]["path"])
    require(full.shape == (4096, 4096, 4), "Full-page authoring size differs")
    selected = np.zeros((4096, 4096), bool)
    for x0, y0, x1, y1 in REGIONS:
        selected[y0*16:y1*16, x0*16:x1*16] = True
    checked = []
    for key, row in rows.items():
        require(ui.owned(row["path"], directory) == directory / "pack/einhander-texture-replacements" / (key+".png"),
                "Font output escaped its isolated pack")
        require(ui.sha(row["path"]) == row["sha256"], "Font output changed: " + key)
        references.append(dict(path=row["path"], sha256=row["sha256"]))
        baseline = row["baseline"]
        require(baseline == dict(path=v6[key]["composed_path"], sha256=v6[key]["sha256"]),
                "Font baseline does not name exact v6 composition: " + key)
        require(ui.sha(baseline["path"]) == baseline["sha256"], "Font baseline bytes changed: " + key)
        references.append(baseline)
        for proof in row["source_proof"]:
            require(Path(proof["path"]).parent.resolve() == proof_root and ui.sha(proof["path"]) == proof["sha256"],
                    "Font local source proof changed: " + key)
            references.append(proof)
        expected_proofs = {key+suffix for suffix in world.SIDECAR_SUFFIXES}
        require({Path(p["path"]).name for p in row["source_proof"]} == expected_proofs,
                "Font source archive is incomplete: " + key)
        metadata, raw, clut = verify_stock(proof_root, key)
        actual = full if key == BASE_KEY else pixels(row["path"])
        prior = pixels(baseline["path"])
        if key == BASE_KEY:
            mask = selected
            require(row["selected_native_regions"] == REGIONS and row["parent_native_row"] is None,
                    "Full-page selected bounds differ")
        else:
            start = ALIAS_ROWS[key]
            require(row["parent_native_row"] == start and row["selected_native_regions"] == [[0,0,64,8],[192,0,256,8]],
                    "Alias selected bounds/row differ: " + key)
            require([metadata["width_words"], metadata["height"], metadata["depth"]] == [64,8,0] and len(raw) == 1024 and
                    len((proof_root / (key+".valid.bin")).read_bytes()) == 512 and raw == full_raw[start*128:(start+8)*128] and clut == full_clut,
                    "Alias is not byte-exact raw/CLUT parent row: " + key)
            mask = selected[start*16:(start+8)*16]
            require(actual.shape == (128,4096,4) and np.array_equal(actual[mask], full[start*16:(start+8)*16][mask]),
                    "Alias selected RGBA does not equal full-page crop: " + key)
        require(actual.shape == prior.shape and np.array_equal(actual[~mask], prior[~mask]), "Protected pixels changed: " + key)
        require(set(map(int,np.unique(actual[:,:,3]))) <= {0,127,255}, "Noncategorical font alpha: " + key)
        changed = int(np.any(actual != prior, axis=2).sum())
        require(changed == row["changed_pixels"], "Declared changed-pixel count differs: " + key)
        checked.append(dict(key=key, selected_regions=row["selected_native_regions"], changed_pixels=changed,
                            protected_pixels_exact=True, source_crc_clut_decode_verified=True,
                            selected_alias_crop_exact=(key != BASE_KEY), sha256=row["sha256"]))
    require(len(list(proof_root.iterdir())) == 56, "Expected 55 raw-source files and one immutable map snapshot")
    return manifest, world.references_unique(references), checked


def verify_world_local(report):
    evidence = Path(report["evidence"])
    parent = load(PARENT / "candidate.json")
    additions = set(parent["world_integration_experiment"]["added_keys"])
    require(len(additions) == 140 and report["world_integration_experiment"]["added_keys"] == parent["world_integration_experiment"]["added_keys"],
            "v7 world addition set changed")
    current = {r["name"][:-4]:r for r in report["files"]}
    previous = {r["name"][:-4]:r for r in parent["files"]}
    require(set(current) == set(previous) and len(current) == 1151, "v8 key set differs from v7")
    require(all(current[key]["sha256"] == row["sha256"] for key,row in previous.items() if key not in {BASE_KEY}|set(ALIAS_ROWS)),
            "v8 changed a key outside the eleven-font overlay")
    require(all(current[key]["sha256"] == previous[key]["sha256"] for key in additions), "World addition PNG changed")
    manifest = load(evidence / "world-additions-manifest.json")
    require(manifest["added_count"] == len(manifest["assets"]) == 140, "Local world manifest count differs")
    count = 0
    for item in manifest["assets"]:
        key = item["key"]
        require(key in additions and len(item["copied_native_files"]) == 5, "Local world archive key/count differs")
        for proof in item["copied_native_files"]:
            require(Path(proof["path"]).resolve().parent == evidence / "native-sources" and ui.sha(proof["path"]) == proof["sha256"],
                    "Local world source changed: " + key)
            count += 1
    require(count == len(list((evidence / "native-sources").iterdir())) == 700, "Expected 700 world sidecars")
    return dict(world_additions_preserved=140, copied_world_source_files_checked=count, original_nonfont_choices_preserved=True)


def revalidate(report, full_decode=False, require_unlaunched=False):
    evidence = Path(report["evidence"]).resolve()
    require(ui.sha(Path(__file__)) == report["description_launcher"]["sha256"], "Description wrapper changed")
    require({"description_continuity", "description_composition", "parent_v7", "world_composition"} <= set(report["overlay_manifests"]),
            "Required font/world provenance missing")
    ui.verify_provenance(report)
    _, _, font_checks = verify_font()
    world_checks = verify_world_local(report)
    require(report["final_count"] == len(report["files"]) == 1151, "Unexpected final count")
    require({p.name for p in (evidence / "pack/einhander-texture-replacements").glob("*.png")} == {r["name"] for r in report["files"]},
            "Composed PNG key set differs")
    if full_decode:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(world.decode_row, row) for row in report["files"]]
            for n, future in enumerate(as_completed(futures),1):
                future.result()
                if n % 200 == 0:
                    print(json.dumps(dict(full_png_decodes=n,total=1151)),flush=True)
    else:
        for row in report["files"]:
            require(ui.sha(ui.owned(row["composed_path"],evidence)) == row["sha256"], "Composed PNG changed")
    font_manifest = load(FONT / "manifest.json")
    composed = {r["name"][:-4]: r for r in report["files"]}
    require(all(composed[r["key"]]["sha256"] == r["sha256"] for r in font_manifest["files"]), "Composed font outputs differ")
    for mode, spec in report["launches"].items():
        exe = ui.owned(spec["arguments"][0],evidence)
        require(ui.sha(exe) == spec["executable_sha256"] == report["runtime"]["sha256"] and
                ui.sha(exe.parent / "settings.toml") == spec["settings_sha256"], "Runtime/settings changed")
        require(Path(spec["writable_state"]) == evidence / ("state" if mode=="candidate" else "state-rollback"), "Private state escaped")
        overrides = spec["environment_overrides"]
        require(Path(overrides["PSXRECOMP_HD_TEXTURE_ROOT"]) == (evidence/"pack" if mode=="candidate" else ui.BASE) and
                overrides["EIN_DEBUG_PORT"] == "4371" and overrides["EIN_DEV_URL"] == "", "Launch pack/port/bridge differs")
        require(all(key not in overrides for key in ui.CLEANED_ENVIRONMENT_KEYS), "Inherited scheduler/load override")
        if require_unlaunched:
            require(not (evidence / ("launch-"+mode+".json")).exists(), "Candidate already launched")
    return dict(ok=True, at_utc=stamp(), final_count=1151, font_outputs_overwritten=11,
                font_outputs_with_changed_pixels=sum(r["changed_pixels"]>0 for r in font_checks), font_checks=font_checks,
                **world_checks, all_png_hashes_verified=1151, full_png_decodes=1151 if full_decode else 0,
                protected_center_logos_and_unproven_row104_exact=True, selected_fullpage_alias_crops_exact=True,
                provenance_verified=True, game_actions=0, game_launched=False, live_visual_acceptance=False,
                candidate_receipt=receipt(evidence / "candidate.json"))


def rollback_plan(report):
    # Deliberately do not read font manifests, experiment PNGs or sidecars here.
    require(ui.sha(Path(__file__)) == report["description_launcher"]["sha256"], "Description wrapper changed")
    return world.rollback_plan(report)


def prepare(evidence):
    evidence = ui.owned(evidence,world.ALLOWED)
    require(not evidence.exists(), "Preparation requires a fresh v8 directory")
    parent = ui.load_report(PARENT)
    world.revalidate(parent, full_decode=False)
    font, references, font_checks = verify_font()
    seed_path, seed = world.closed_private_seed()
    report = copy.deepcopy(parent)
    report.pop("launches",None)
    report.pop("prepared_at_utc",None)
    report.update(at_utc=stamp(),evidence=str(evidence),window_title=TITLE,game_launched=False,production_installed=False)
    font_rows = {r["key"]:r for r in font["files"]}
    for row in report["files"]:
        row.pop("composed_path",None)
        row.pop("composition",None)
        key = row["name"][:-4]
        if key in font_rows:
            addition = font_rows[key]
            row["description_override_parent"] = dict(path=row["path"],sha256=row["sha256"],origin=row["origin"])
            row.update(path=addition["path"],sha256=addition["sha256"],dimensions=addition["size"],
                       bytes=Path(addition["path"]).stat().st_size,origin="description continuity v2")
            row.setdefault("overlay_sources",[]).append(dict(origin="description continuity v2",path=addition["path"],sha256=addition["sha256"]))
    report["overlay_manifests"]["parent_v7"] = dict(**receipt(PARENT / "candidate.json"),asset_count=1151,contract="parent-world-composition-v7")
    report["overlay_manifests"]["description_continuity"] = dict(**receipt(FONT / "manifest.json"),asset_count=11,
        contract="verified-description-continuity-v1",referenced_files=references)
    report["source_counts"]["description_continuity"] = 11
    report["overlay_input_count"] += 11
    report["upstream_v6_composition"] = report["parent_composition"]
    report["parent_composition"] = dict(**receipt(PARENT / "candidate.json"),font_overwrite_count=11,
                                       world_additions_preserved=140,all_other_selected_keys_preserved=1140)
    report["limitations"] += ["v8 overwrites exactly eleven v7 font outputs; one unchanged row remains deliberately identical.",
        "Technical source/crop/protected-pixel checks do not accept visible glyph quality; Fighter/ARM replay is required."]
    ui.TITLE = TITLE
    ui.prepare(report)
    native_root = evidence / "native-sources"
    native_root.mkdir()
    parent_world = load(PARENT / "world-additions-manifest.json")
    local_world = copy.deepcopy(parent_world)
    copied_world_refs = []
    for asset in local_world["assets"]:
        for item in asset["copied_native_files"]:
            source = Path(item["path"])
            target = native_root / source.name
            require(ui.copy_verified(source,target) == item["sha256"], "World archive copy changed")
            item.update(path=str(target),source_path=str(source))
            copied_world_refs.append(dict(path=str(target),sha256=item["sha256"]))
    world_manifest = evidence / "world-additions-manifest.json"
    write(world_manifest,local_world)
    report["overlay_manifests"]["world_composition"] = dict(**receipt(world_manifest),asset_count=140,
        contract="immutable-world-experiment-native-sidecars-v1",referenced_files=world.references_unique(copied_world_refs))
    font_sources = evidence / "font-native-sources"
    shutil.copytree(FONT / "source-proof",font_sources)
    shutil.copyfile(FONT / "build-source.py",evidence / "font-build-source.py")
    local_font_refs = [receipt(p) for p in sorted(font_sources.iterdir())] + [receipt(evidence / "font-build-source.py")]
    font_composition = evidence / "font-composition-manifest.json"
    write(font_composition,dict(schema_version=1,at_utc=stamp(),source_manifest=receipt(FONT / "manifest.json"),
        parent=receipt(PARENT / "candidate.json"),overwritten_keys=sorted(font_rows),technical_checks=font_checks,
        copied_source_evidence=local_font_refs,game_actions=0,live_visual_acceptance=False))
    report["overlay_manifests"]["description_composition"] = dict(**receipt(font_composition),asset_count=11,
        contract="immutable-description-continuity-composition-v1",referenced_files=local_font_refs)
    targets = []
    for mode in ("candidate","rollback"):
        target = Path(report["launches"][mode]["writable_state"]) / "card1.mcd"
        require(ui.copy_verified(seed_path,target) == seed["source_sha256"], "Private seed copy changed")
        targets.append(dict(mode=mode,target=str(target),sha256=ui.sha(target)))
        flag = " --rollback" if mode=="rollback" else ""
        command = '@echo off\r\n"'+sys.executable+'" "'+str(Path(__file__).resolve())+'" --evidence "%~dp0." --launch'+flag+'\r\n'
        (evidence / ("launch-"+mode+".cmd")).write_text(command,encoding="utf-8")
    seed.update(at_utc=stamp(),copies=targets,target_restart_load_verified=False)
    write(evidence / "private-card-seed.json",seed)
    report["description_launcher"] = receipt(Path(__file__))
    write(evidence / "candidate.json",report)
    validation = revalidate(report,full_decode=True,require_unlaunched=True)
    _, rollback = rollback_plan(report)
    write(evidence / "rollback-isolation-check.json",rollback)
    validation.update(private_card_seed=receipt(evidence / "private-card-seed.json"),
                      rollback_isolation=receipt(evidence / "rollback-isolation-check.json"))
    write(evidence / "preparation-revalidation.json",validation)
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",type=Path,default=DEFAULT_EVIDENCE)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check",action="store_true")
    operation.add_argument("--launch",action="store_true")
    parser.add_argument("--rollback",action="store_true")
    args = parser.parse_args()
    require(not args.rollback or args.launch,"--rollback requires --launch")
    if args.check or args.launch:
        report = ui.load_report(args.evidence)
        if args.rollback:
            rollback,_ = rollback_plan(report)
            result = ui.launch(rollback,True)
        else:
            result = revalidate(report,full_decode=args.check)
            if args.launch:
                result = ui.launch(report,False)
    else:
        result = prepare(args.evidence)
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
