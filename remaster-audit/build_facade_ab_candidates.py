"""Immutable, one-key facade experiments derived from the reviewed title E pack.

Resampling/packing only: this does not create artistic detail or claim 4K art.
Each variant owns its pack, executable, settings, cards, port and evidence.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import zlib

import numpy as np
from PIL import Image

import launch_ui_candidate as ui
import stage_world_candidate as world

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "remaster-audit/dev-center-evidence/title-e-20261112-v13"
OUTPUT = ROOT / "remaster-audit/dev-center-evidence/facade-ab-20261112"
SOURCE = ROOT / "remaster-audit/world-sign-mapping/facade-pilot-source-v2"
KEY = "52F33418-5E9B9AC3"
VARIANTS = {"architecture": 4373, "lighting": 4374, "structure": 4375, "material": 4376}
SIZE = 2048
REGION_LINE = KEY + "\t768\t0\t16\t64\t0\t0\t480\n"


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ref(path):
    return dict(path=str(Path(path).resolve()), sha256=ui.sha(path))


def native_source():
    manifest = read(SOURCE / "manifest.json")
    assert manifest["cropped_exact_source_key"] == KEY
    assert manifest["physical_source_rect_words"] == [768, 0, 16, 64]
    assert manifest["depth"] == 0 and manifest["clut_xy"] == [0, 480]
    for item in manifest["source_proof"]:
        if ui.sha(item["path"]) != item["sha256"]:
            raise ValueError("Native source evidence changed")
    prefix = SOURCE / "source-proof" / KEY
    raw = prefix.with_suffix(".words.bin").read_bytes()
    palette = prefix.with_suffix(".clut.bin").read_bytes()
    valid = prefix.with_suffix(".valid.bin").read_bytes()
    assert len(raw) == 2048 and len(palette) == 32 and valid == bytes([1]) * 1024
    assert KEY == f"{zlib.crc32(raw):08X}-{zlib.crc32(palette):08X}"
    with Image.open(manifest["native_crop"]["path"]) as image:
        native = np.asarray(image.convert("RGBA"))
    assert native.shape == (64, 64, 4) and set(np.unique(native[:, :, 3])) == {127, 255}
    return native


def prepare(variant, image_path, manifest_path=None):
    directory = OUTPUT / variant
    if directory.exists():
        raise ValueError("Immutable variant already exists")
    image_path = Path(image_path).resolve()
    source_receipt = ref(image_path)
    native = native_source()
    parent = read(PARENT / "candidate.json")
    rows = parent["files"]
    assert len(rows) == 1194 and KEY + ".png" not in {r["name"] for r in rows}
    # Verify before making any outputs. Parent art is never opened for writing.
    for row in rows:
        if ui.sha(row["composed_path"]) != row["sha256"]:
            raise ValueError("Parent PNG changed: " + row["name"])
    spec = copy.deepcopy(parent["launches"]["candidate"])
    executable = Path(spec["arguments"][0])
    if ui.sha(executable) != spec["executable_sha256"]:
        raise ValueError("Parent executable changed")
    seed, seed_proof = world.closed_private_seed()
    with Image.open(image_path) as image:
        image.load()
        source_size = list(image.size)
    directory.mkdir(parents=True)
    pack = directory / "pack"
    replacements = pack / "einhander-texture-replacements"
    replacements.mkdir(parents=True)
    local_source = directory / "authoring-input.png"
    ui.copy_verified(image_path, local_source)
    if ui.sha(local_source) != source_receipt["sha256"]:
        raise ValueError("Authoring input changed while copying")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Existing FFmpeg required for deterministic registration")
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(local_source),
            "-vf", f"scale={SIZE}:{SIZE}:flags=lanczos", "-f", "rawvideo",
            "-pix_fmt", "rgb24", "pipe:1"]
    result = subprocess.run(args, check=True, capture_output=True, timeout=60)
    assert len(result.stdout) == SIZE * SIZE * 3
    rgb = np.frombuffer(result.stdout, np.uint8).reshape(SIZE, SIZE, 3)
    classes = np.repeat(np.repeat(native[:, :, 3], SIZE // 64, 0), SIZE // 64, 1)
    rgba = np.concatenate((rgb, classes[:, :, None]), axis=2)
    target = replacements / (KEY + ".png")
    Image.fromarray(rgba).save(target)
    with Image.open(target) as image:
        assert np.array_equal(np.asarray(image.convert("RGBA")), rgba)
    files = []
    for row in rows:
        source = Path(row["composed_path"])
        dest = replacements / row["name"]
        # Both packs are immutable. No game or builder writes numeric PNGs.
        os.link(source, dest)
        if not os.path.samefile(source, dest):
            raise ValueError("Expected immutable parent hardlink")
        files.append(dict(name=row["name"], composed_path=str(dest), sha256=row["sha256"],
                          dimensions=row["dimensions"], bytes=dest.stat().st_size,
                          origin="unchanged immutable parent", parent=ref(source)))
    for source in (PARENT / "pack").iterdir():
        if source.is_file():
            ui.copy_verified(source, pack / source.name)
    regions = (pack / "ExactRegions.tsv").read_text(encoding="utf-8")
    assert regions.splitlines()[0] == "EIN_EXACT_REGIONS_V1"
    assert KEY not in regions and len(regions.splitlines()) == 43
    (pack / "ExactRegions.tsv").write_text(regions.rstrip() + "\n" + REGION_LINE, encoding="utf-8")
    for suffix in (".words.bin", ".clut.bin", ".valid.bin", ".source.json"):
        ui.copy_verified(SOURCE / "source-proof" / (KEY + suffix), pack / (KEY + suffix))
    files.append(dict(name=KEY + ".png", composed_path=str(target), sha256=ui.sha(target),
                      dimensions=[SIZE, SIZE], bytes=target.stat().st_size,
                      origin="facade A/B candidate", visual_accepted=False))
    runtime = directory / "runtime"
    runtime.mkdir()
    new_exe = runtime / executable.name
    ui.copy_verified(executable, new_exe)
    if (executable.parent / "cache").exists():
        shutil.copytree(executable.parent / "cache", runtime / "cache")
    state = directory / "state"
    state.mkdir()
    ui.copy_verified(seed, state / "card1.mcd")
    settings = ui.settings_override((executable.parent / "settings.toml").read_text(encoding="utf-8"), pack)
    # Explicit private card paths supplement the verified --memcard-dir override.
    import re
    for name, value in (("dir", state), ("card1", state / "card1.mcd"), ("card2", state / "card2.mcd")):
        settings = re.sub(r"(?m)^" + name + r"\s*=.*$", name + " = " + json.dumps(str(value).replace("\\", "/")), settings)
    (runtime / "settings.toml").write_text(settings, encoding="utf-8")
    port = VARIANTS[variant]
    spec["arguments"][0] = str(new_exe)
    for flag, value in (("--debug-port", str(port)), ("--memcard-dir", str(state)),
                        ("--window-title", "Einhander facade A/B - " + variant)):
        spec["arguments"][spec["arguments"].index(flag) + 1] = value
    spec.update(writable_state=str(state), settings_sha256=ui.sha(runtime / "settings.toml"))
    spec["environment_overrides"].update(EIN_DEBUG_PORT=str(port), PSXRECOMP_HD_TEXTURE_ROOT=str(pack),
        PSX_OVERLAY_CAPTURES=str(runtime / "overlay_captures.json"), PSXRECOMP_HD_FACADE_MOTION="0")
    report = dict(format=1, evidence=str(directory), debug_port=port, variant=variant,
        files=files, final_count=len(files), launches={"candidate": spec},
        parent=ref(PARENT / "candidate.json"), builder=ref(__file__), prepared_at_utc=ui.stamp(),
        authoring_input=dict(**source_receipt, local=ref(local_source), dimensions=source_size),
        source_manifest=ref(manifest_path) if manifest_path else None,
        registration=dict(key=KEY, source_rect_words=[768, 0, 16, 64], depth=0, clut_xy=[0, 480],
            runtime_dimensions=[SIZE, SIZE], resize_arguments=args,
            categorical_alpha_exact=True, black_rgb_mask_applied=False,
            geometric_registration="Full-square correspondence; authored contours still require actual in-game review"),
        private_seed=seed_proof, unchanged_parent_keys=len(rows), added_exact_regions=1,
        production_installed=False, live_visual_accepted=False, native_4k_authored=source_size == [4096,4096],
        known_limits=["1254 references do not acquire native detail when resampled",
                      "Structural control images do not establish realistic materials",
                      "No PBR/HDR engine claim; lighting is baked RGB",
                      "Actual exact-region draw readiness and motion review pending"])
    write(directory / "candidate.json", report)
    write(directory / "preparation-verification.json", check(report))
    return dict(ok=True, evidence=str(directory), unchanged=1194, added=KEY, runtime_size=SIZE,
                authoring_dimensions=source_size)


def check(report):
    directory = Path(report["evidence"])
    assert directory.resolve().is_relative_to(OUTPUT.resolve())
    expected = {row["name"] for row in report["files"]}
    assert expected == {p.name for p in (directory / "pack/einhander-texture-replacements").glob("*.png")}
    assert len(expected) == report["final_count"] == 1195
    for row in report["files"]:
        path = Path(row["composed_path"])
        assert path.parent == directory / "pack/einhander-texture-replacements"
        assert ui.sha(path) == row["sha256"]
    spec = report["launches"]["candidate"]
    assert ui.sha(spec["arguments"][0]) == spec["executable_sha256"]
    assert ui.sha(Path(spec["arguments"][0]).parent / "settings.toml") == spec["settings_sha256"]
    assert not spec["user_cards_mounted"]
    assert (directory / "pack/ExactRegions.tsv").read_text().splitlines()[-1].split() == REGION_LINE.split()
    assert len((directory / "pack/ExactRegions.tsv").read_text().splitlines()) == 44
    native = native_source()
    with Image.open(directory / "pack/einhander-texture-replacements" / (KEY + ".png")) as image:
        actual = np.asarray(image.convert("RGBA"))
        assert image.size == (SIZE, SIZE)
    assert np.array_equal(actual[:, :, 3], np.repeat(np.repeat(native[:, :, 3], SIZE // 64, 0), SIZE // 64, 1))
    return dict(ok=True, checked_png_hashes=1195, unchanged_parent_keys=1194,
                exact_region_count=43, categorical_alpha="PASS", game_actions=0,
                live_visual_accepted=False, checked_at_utc=ui.stamp())


def launch(report):
    directory = Path(report["evidence"])
    if (directory / "launch-candidate.json").exists():
        raise ValueError("Fresh variant launch only")
    check(report)
    # Compare one process at a time; no competing experiment may own a port.
    for port in VARIANTS.values():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.2):
                raise ValueError(f"Comparison port {port} is occupied")
        except OSError:
            pass
    spec = report["launches"]["candidate"]
    with (directory / "stdout.log").open("xb") as out, (directory / "stderr.log").open("xb") as err:
        process = subprocess.Popen(spec["arguments"], cwd=spec["cwd"], env=ui.launch_environment(spec["environment_overrides"]),
            stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    receipt = dict(at_utc=ui.stamp(), pid=process.pid, debug_port=report["debug_port"],
                   executable=spec["arguments"][0], private_state=spec["writable_state"], user_cards_mounted=False)
    write(directory / "launch-candidate.json", receipt)
    ui.PORT = report["debug_port"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", ui.PORT), timeout=.2):
                break
        except OSError:
            time.sleep(.1)
    import observe_native_boot as boot
    sys.argv = [str(Path(boot.__file__)), "--evidence", str(directory), "--label", "ab-boot"]
    result = boot.main()
    return dict(**receipt, native_title_observed=result == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=VARIANTS)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.image:
        result = prepare(args.variant, args.image, args.source_manifest)
    else:
        report = read(OUTPUT / args.variant / "candidate.json")
        result = launch(report) if args.launch else check(report)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
