"""Pack Claude's approved E title art and prepare an isolated v12 derivative.

Only the two title background pages change. Existing candidates, source files,
installed packs, and user memory cards are never written. Port 4372 lets the
previous preview remain open. The 1448x1086 master is not native 4K artwork.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image

import launch_ui_candidate as ui
import stage_typography_candidate_v2 as staging
import stage_world_candidate as world

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
PARENT = AUDIT / "dev-center-evidence/remaster-4k-preview-20261112-v12"
ART = AUDIT / "menu-restoration/title-e-candidate-v1"
EVIDENCE = AUDIT / "dev-center-evidence/title-e-20261112-v13"
PRIOR = AUDIT / "menu-restoration/title-art-candidate-v2/manifest.json"
MASTER = Path("C:/github/Einhander/title-hd-mockups/title-hd-E-art-only-1448x1086-master.png")
MASTER_SHA = "28903049de7dc2c0cfa8117865351854ffc4f3c418960a6095c49f594d93a25f"
PORT = 4372
TITLE = "Einhander - approved E title preview"
KEYS = {"282438F3-00000000", "1D953D67-00000000"}


def load(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def ref(path):
    return {"path": str(Path(path).resolve()), "sha256": ui.sha(path)}


def scaled_rgb(master):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Existing FFmpeg is required")
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(master),
            "-vf", "scale=5120:3840:flags=lanczos", "-f", "rawvideo",
            "-pix_fmt", "rgb24", "pipe:1"]
    result = subprocess.run(args, capture_output=True, check=True, timeout=60)
    if len(result.stdout) != 5120 * 3840 * 3:
        raise ValueError("FFmpeg output dimensions differ")
    return np.frombuffer(result.stdout, np.uint8).reshape(3840, 5120, 3), args


def pack_title(parent):
    prior = load(PRIOR)
    if {r["key"] for r in prior["files"]} != KEYS:
        raise ValueError("Expected exactly the two established title pages")
    if ui.sha(MASTER) != MASTER_SHA:
        raise ValueError("Claude title master differs from handoff hash")
    with Image.open(MASTER) as image:
        image.load()
        if image.size != (1448, 1086):
            raise ValueError("E master registration dimensions differ")
    for info in [prior["master"], *prior["files"]]:
        if ui.sha(info["path"]) != info["sha256"]:
            raise ValueError("Original title provenance changed")
    parent_rows = {r["name"][:-4]: r for r in parent["files"]}
    # Reconstruct the established v2 pipeline before applying it to E.
    original_rgb, _ = scaled_rgb(prior["master"]["path"])
    replacement_rgb, args = scaled_rgb(MASTER)
    ART.mkdir(parents=True, exist_ok=False)
    pack = ART / "pack/einhander-texture-replacements"
    pack.mkdir(parents=True)
    local_master = ART / "full-title-master.png"
    ui.copy_verified(MASTER, local_master)
    rows = []
    for item in prior["files"]:
        key = item["key"]
        if parent_rows[key]["sha256"] != item["sha256"]:
            raise ValueError("Current parent title differs from verified v2")
        source = Path(item["source"])
        if ui.sha(source) != item["source_sha256"]:
            raise ValueError("Native title source changed")
        with Image.open(source) as image:
            native = image.convert("RGBA")
        if native.size != ((256, 256) if key.startswith("2824") else (64, 256)):
            raise ValueError("Native title page geometry differs")
        before = np.asarray(native.resize(tuple(item["size"]), Image.Resampling.NEAREST))
        offset = 0 if key.startswith("2824") else 4096
        width = before.shape[1]
        with Image.open(item["path"]) as image:
            original = np.asarray(image.convert("RGBA"))
        if (not np.array_equal(original[:3840, :, :3], original_rgb[:, offset:offset+width])
                or not np.array_equal(original[:, :, 3], before[:, :, 3])
                or not np.array_equal(original[3840:], before[3840:])):
            raise ValueError("Established title packing reconstruction failed: " + key)
        after = before.copy()
        after[:3840, :, :3] = replacement_rgb[:, offset:offset+width]
        target = pack / (key + ".png")
        Image.fromarray(after).save(target)
        with Image.open(target) as image:
            actual = np.asarray(image.convert("RGBA"))
        if not np.array_equal(actual, after):
            raise ValueError("PNG roundtrip differs")
        rows.append(dict(key=key, **ref(target), size=list(item["size"]),
                         parent=ref(parent_rows[key]["composed_path"]),
                         source=str(source), source_sha256=ui.sha(source),
                         native_alpha_stp_footprint_exact=True,
                         unused_bottom_rows_exact=True,
                         prior_pipeline_reconstruction_exact=True,
                         native_dimensions=list(native.size),
                         master_crop_half_open=[offset, 0, offset+width, 3840]))
    manifest = dict(format=1, created_at_utc=ui.stamp(), asset_count=2, files=rows,
                    master=dict(**ref(local_master), size=[1448, 1086]),
                    imported_master=ref(MASTER), parent_manifest=ref(PRIOR),
                    source_mapping=ref(prior["source_mapping"]),
                    builder=ref(__file__), ffmpeg_arguments=args,
                    method="Established FFmpeg Lanczos 5120x3840 split; native categorical alpha and unused rows retained",
                    author="claude-einhander", design="E", production_installed=False,
                    live_accepted=False, native_4k_authored=False,
                    known_limits=["Faint inpainted wrist haze reported by Claude; inspect live at 2160 lines",
                                  "Logo shadow modelled by Claude; changed title requires fresh live verification"])
    write(ART / "manifest.json", manifest)
    return manifest


def prepare():
    if ART.exists() or EVIDENCE.exists():
        raise ValueError("Immutable output already exists; use --check or --launch")
    parent = ui.load_report(PARENT)
    ui.verify_provenance(parent)
    manifest = pack_title(parent)
    report = copy.deepcopy(parent)
    for name in ("launches", "prepared_at_utc", "region_launcher"):
        report.pop(name, None)
    report.update(evidence=str(EVIDENCE), debug_port=PORT, window_title=TITLE,
                  game_launched=False, production_installed=False)
    overlays = {r["key"]: r for r in manifest["files"]}
    changes = []
    for row in report["files"]:
        if ui.sha(row["composed_path"]) != row["sha256"]:
            raise ValueError("Parent PNG changed: " + row["name"])
        row["path"] = row.pop("composed_path")
        row.pop("composition", None)
        item = overlays.get(row["name"][:-4])
        if item:
            before = ref(row["path"])
            row.update(path=item["path"], sha256=item["sha256"],
                       bytes=Path(item["path"]).stat().st_size,
                       origin="approved E title background", live_visual_accepted=False)
            row.setdefault("overlay_sources", []).append(dict(**ref(item["path"]), origin=row["origin"]))
            changes.append(dict(key=item["key"], parent=before, output=ref(item["path"])))
    if len(changes) != 2:
        raise ValueError("Expected exactly two changed title keys")
    references = [manifest["master"], manifest["imported_master"], manifest["parent_manifest"],
                  manifest["source_mapping"], manifest["builder"]]
    report["overlay_manifests"]["approved_title_e"] = dict(**ref(ART / "manifest.json"),
        asset_count=2, referenced_files=[{k:r[k] for k in ("path", "sha256")} for r in references])
    seed, seed_proof = world.closed_private_seed()
    ui.PORT, ui.TITLE = PORT, TITLE
    ui.prepare(report)
    finalize(report, parent, seed, seed_proof)


def finalize(report, parent, seed, seed_proof):
    manifest = load(ART / "manifest.json")
    parent_rows = {r["name"][:-4]: r for r in parent["files"]}
    changes = [dict(key=item["key"], parent=ref(parent_rows[item["key"]]["composed_path"]),
                    output=ref(item["path"])) for item in manifest["files"]]
    local_proofs = []
    for source in sorted((PARENT / "pack").iterdir()):
        if source.is_file() and source.suffix.lower() != ".png" and source.name != "Hashes.ini":
            target = EVIDENCE / "pack" / source.name
            ui.copy_verified(source, target)
            local_proofs.append(ref(target))
    report["typography_composition"]["local_region_proofs"] = local_proofs
    for mode, spec in report["launches"].items():
        if mode == "rollback":
            spec["executable_sha256"] = ui.copy_verified(Path(parent["launches"][mode]["arguments"][0]), Path(spec["arguments"][0]))
        ui.copy_verified(seed, Path(spec["writable_state"]) / "card1.mcd")
        flag = " --rollback" if mode == "rollback" else ""
        launcher = '@echo off\r\n"' + __import__("sys").executable + '" "' + str(Path(__file__).resolve()) + '" --evidence "%~dp0." --launch' + flag + '\r\n'
        (EVIDENCE / ("launch-" + mode + ".cmd")).write_text(launcher, encoding="utf-8")
    report["title_e_composition"] = dict(parent=ref(PARENT / "candidate.json"),
        manifest=ref(ART / "manifest.json"), builder=ref(__file__), changes=changes,
        changed_keys=2, unchanged_keys=len(report["files"])-2,
        private_seed=seed_proof, local_region_proofs=local_proofs,
        quality_status="requires live title review", production_installed=False)
    write(EVIDENCE / "candidate.json", report)
    result = staging.validate(report, decode=True)
    result.update(changed_title_keys=sorted(KEYS), unchanged_keys=len(report["files"])-2,
                  debug_port=PORT, prior_title_pipeline_reconstruction="PASS")
    write(EVIDENCE / "preparation-revalidation.json", result)
    print(json.dumps(result))


def resume_preparation():
    # Recover only this unpublished preparation after a builder error. A
    # launched or finalized candidate is immutable and cannot use this path.
    if ((EVIDENCE / "preparation-revalidation.json").exists()
            or any((EVIDENCE / ("launch-" + mode + ".json")).exists() for mode in ("candidate", "rollback"))):
        raise ValueError("Cannot resume a finalized or launched candidate")
    parent = ui.load_report(PARENT)
    ui.verify_provenance(parent)
    ui.PORT = PORT
    report = ui.load_report(EVIDENCE)
    manifest = load(ART / "manifest.json")
    if manifest["master"]["sha256"] != MASTER_SHA or {r["key"] for r in manifest["files"]} != KEYS:
        raise ValueError("Partial title preparation identity differs")
    recovery = dict(at_utc=ui.stamp(), previous_candidate=ref(EVIDENCE / "candidate.json"),
        previous_manifest=ref(ART / "manifest.json"), builder=ref(__file__),
        reason="Initial finalization passed a string to copy_verified instead of pathlib.Path",
        game_launched=False, production_installed=False)
    history_path = EVIDENCE / "preparation-recovery.json"
    history = load(history_path) if history_path.exists() else {"attempts": []}
    if "attempts" not in history:
        history = {"attempts": [history]}
    history["attempts"].append(recovery)
    write(history_path, history)
    manifest["builder"] = ref(__file__)
    write(ART / "manifest.json", manifest)
    overlay = report["overlay_manifests"]["approved_title_e"]
    overlay.update(ref(ART / "manifest.json"))
    overlay["referenced_files"] = [ref(__file__) if Path(r["path"]).resolve() == Path(__file__).resolve() else r
                                    for r in overlay["referenced_files"]]
    ui.verify_provenance(report)
    for row in report["files"]:
        if ui.sha(row["composed_path"]) != row["sha256"]:
            raise ValueError("Partial candidate image changed")
    seed, seed_proof = world.closed_private_seed()
    finalize(report, parent, seed, seed_proof)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--resume-preparation", action="store_true")
    args = parser.parse_args()
    if args.evidence.resolve() != EVIDENCE.resolve():
        raise ValueError("Only this isolated evidence directory is supported")
    if args.resume_preparation:
        resume_preparation()
    elif args.check or args.launch:
        ui.PORT = PORT
        report = ui.load_report(args.evidence)
        result = staging.validate(report, decode=args.check)
        if args.launch:
            result = ui.launch(report, args.rollback)
        print(json.dumps(result))
    else:
        prepare()


if __name__ == "__main__":
    main()
