"""Compose bounded typography repairs over an immutable, isolated game candidate."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

from PIL import Image

import launch_ui_candidate as ui
import stage_world_candidate as world


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def ref(path):
    return dict(path=str(Path(path).resolve()), sha256=ui.sha(path))


def validate(report, decode=False):
    ui.verify_provenance(report)
    keys = set()
    for row in report["files"]:
        if row["name"] in keys:
            raise ValueError("Duplicate key " + row["name"])
        keys.add(row["name"])
        if ui.sha(row["composed_path"]) != row["sha256"]:
            raise ValueError("Composed image changed " + row["name"])
        if decode:
            with Image.open(row["composed_path"]) as im:
                im.load()
                if list(im.size) != row["dimensions"]:
                    raise ValueError("Image dimensions differ " + row["name"])
    for item in report["typography_composition"]["local_region_proofs"]:
        if ui.sha(item["path"]) != item["sha256"]:
            raise ValueError("Exact region proof changed")
    for spec in report["launches"].values():
        exe = Path(spec["arguments"][0])
        if ui.sha(exe) != spec["executable_sha256"] or ui.sha(exe.parent / "settings.toml") != spec["settings_sha256"]:
            raise ValueError("Runtime/settings changed")
        if spec["user_cards_mounted"]:
            raise ValueError("Private cards are required")
    return dict(status="PASS", png_count=len(keys), decoded_all=decode,
                candidate=ref(Path(report["evidence"]) / "candidate.json"),
                live_visual_acceptance=False, production_installed=False)


def prepare(parent_dir, evidence, overlays):
    evidence = ui.owned(evidence, ui.ALLOWED)
    parent = ui.load_report(parent_dir)
    ui.verify_provenance(parent)
    report = copy.deepcopy(parent)
    for field in ("launches", "prepared_at_utc", "region_launcher"):
        report.pop(field, None)
    report.update(evidence=str(evidence), game_launched=False, production_installed=False,
                  window_title="Einhander - crisp typography review " + evidence.name)
    rows = {row["name"][:-4]: row for row in report["files"]}
    for row in rows.values():
        if ui.sha(row["composed_path"]) != row["sha256"]:
            raise ValueError("Parent composition changed " + row["name"])
        row["path"] = row.pop("composed_path")
        row.pop("composition", None)
    changes = []
    seen = set()
    for directory in overlays:
        manifest_path = Path(directory) / "manifest.json"
        manifest = read(manifest_path)
        entries = manifest.get("files", manifest.get("assets", []))
        if not entries:
            raise ValueError("Empty typography manifest")
        report["overlay_manifests"]["typography_" + Path(directory).name] = dict(**ref(manifest_path), asset_count=len(entries))
        for item in entries:
            key = item["key"]
            if key in seen:
                raise ValueError("Overlapping typography overlays: " + key)
            seen.add(key)
            output = item.get("outputs", {}).get("pack", item)
            source = Path(output["path"])
            if ui.sha(source) != output["sha256"]:
                raise ValueError("Typography output changed " + key)
            if key not in rows:
                raise ValueError("Typography overlay must replace an existing key " + key)
            row = rows[key]
            # Exact parent references prevent accidental composition over a
            # different version of a mixed artwork/glyph page.
            if item.get("parent") and item["parent"]["sha256"] != row["sha256"]:
                raise ValueError("Typography parent mismatch " + key)
            before = dict(path=row["path"], sha256=row["sha256"])
            with Image.open(source) as im:
                im.load()
                size = list(im.size)
                if size != row["dimensions"]:
                    raise ValueError("Typography canvas changed " + key)
            row.update(path=str(source), sha256=output["sha256"], bytes=source.stat().st_size,
                       origin="fresh typography " + Path(directory).name, live_visual_accepted=False)
            row.setdefault("overlay_sources", []).append(dict(path=str(source), sha256=output["sha256"], origin=row["origin"]))
            changes.append(dict(key=key, parent=before, output=ref(source), manifest=ref(manifest_path)))
    seed, seed_proof = world.closed_private_seed()
    ui.TITLE = report["window_title"]
    ui.prepare(report)
    proofs = []
    for source in sorted((Path(parent_dir) / "pack").iterdir()):
        if source.is_file() and source.suffix.lower() != ".png" and source.name != "Hashes.ini":
            target = evidence / "pack" / source.name
            ui.copy_verified(source, target)
            proofs.append(ref(target))
    for mode, spec in report["launches"].items():
        if mode == "rollback":
            original = Path(parent["launches"][mode]["arguments"][0])
            spec["executable_sha256"] = ui.copy_verified(original, Path(spec["arguments"][0]))
        ui.copy_verified(seed, Path(spec["writable_state"]) / "card1.mcd")
    report["typography_composition"] = dict(parent=ref(Path(parent_dir)/"candidate.json"),
        changes=changes, local_region_proofs=proofs, builder=ref(__file__),
        unchanged_keys=len(rows)-len(changes), changed_keys=len(changes),
        quality_status="requires_live_visual_review", private_seed=seed_proof)
    write(evidence / "candidate.json", report)
    result = validate(report, decode=True)
    write(evidence / "preparation-revalidation.json", result)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, action="append", default=[])
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.launch or args.check:
        report = ui.load_report(args.evidence)
        validate(report, decode=args.check)
        print(json.dumps(ui.launch(report, False) if args.launch else dict(status="PASS")))
    else:
        if not args.parent or not args.overlay:
            parser.error("Preparation requires --parent and --overlay")
        prepare(args.parent.resolve(), args.evidence.resolve(), [p.resolve() for p in args.overlay])


if __name__ == "__main__":
    main()
