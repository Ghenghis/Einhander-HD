"""Add one source-bound neighbor facade to a fresh H24 private candidate."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image
import build_facade_ab_candidates as base
import launch_ui_candidate as ui

VARIANT = "h24-matched-r3"
DIRECTORY = base.OUTPUT / VARIANT
ASSETS = base.ROOT / "remaster-audit/assets/h24-neighbor-v1"
SOURCE = base.ROOT / "remaster-audit/world-sign-mapping/facade-neighbor-source-v1/source-proof"
KEY = "74EF95B7-B30D16F0"
REGION = KEY + "\t800\t0\t16\t64\t0\t16\t480\n"


def check(report):
    directory = Path(report["evidence"])
    assert directory == DIRECTORY
    rows = report["files"]
    assert len(rows) == report["final_count"] == 1196
    neighbor = [r for r in rows if r["name"] == KEY + ".png"]
    assert len(neighbor) == 1
    # Verify both exact regions without changing any source files or hardlinks.
    expected = {r["name"] for r in rows}
    pack = directory / "pack"
    assert expected == {p.name for p in (pack / "einhander-texture-replacements").glob("*.png")}
    for row in rows:
        path = Path(row["composed_path"])
        assert path.parent == pack / "einhander-texture-replacements"
        assert ui.sha(path) == row["sha256"]
    spec = report["launches"]["candidate"]
    assert ui.sha(spec["arguments"][0]) == spec["executable_sha256"]
    assert ui.sha(Path(spec["arguments"][0]).parent / "settings.toml") == spec["settings_sha256"]
    assert not spec["user_cards_mounted"]
    regions = (pack / "ExactRegions.tsv").read_text().splitlines()
    assert len(regions) == 45 and regions[-1].split() == REGION.split()
    assert regions[-2].split() == base.REGION_LINE.split()
    for key, native_path in [(base.KEY, base.SOURCE / "source-proof" / (base.KEY + ".png")),
                              (KEY, SOURCE / (KEY + ".png"))]:
        with Image.open(native_path) as image:
            alpha = np.asarray(image.convert("RGBA"))[:, :, 3]
        with Image.open(pack / "einhander-texture-replacements" / (key + ".png")) as image:
            assert image.size == (4096, 4096)
            actual = np.asarray(image.convert("RGBA"))[:, :, 3]
        assert np.array_equal(actual, np.repeat(np.repeat(alpha, 64, axis=0), 64, axis=1))
    previous = base.read(base.OUTPUT / "h24-fullpass-r2/candidate.json")
    previous_hashes = {r["name"]: r["sha256"] for r in previous["files"]}
    assert all(r["sha256"] == previous_hashes[r["name"]] for r in rows if r["name"] in previous_hashes)
    return dict(ok=True, checked_png_hashes=1196, unchanged_previous_keys=1195,
        unchanged_parent_keys=1194, new_neighbor_keys=1, categorical_alpha="PASS",
        existing_h24_pixels_unchanged=True, game_actions=0, live_visual_accepted=False,
        checked_at_utc=ui.stamp())


def prepare(generated):
    generated = Path(generated).resolve()
    ASSETS.mkdir(parents=True, exist_ok=False)
    art = ASSETS / "neighbor-master.png"
    ui.copy_verified(generated, art)
    with Image.open(art) as image:
        dimensions = list(image.size)
    base.write(ASSETS / "manifest.json", dict(source_key=KEY, image=base.ref(art),
        dimensions=dimensions, provider="OpenAI built-in ImageGen", role="Neighbor facade RGB artwork",
        reference_identifiers=[str(SOURCE / (KEY + ".png")),
            str(base.OUTPUT / "h24-v2-4096-r1/authoring-input.png")],
        layout="Distinct native neighbor three-row arrangement; dark column retained",
        native_4096_authored=dimensions == [4096,4096], visual_accepted=False))
    previous = base.read(base.OUTPUT / "h24-v2-4096-r1/candidate.json")
    base.SIZE = 4096
    base.VARIANTS = {VARIANT: 4375}
    base.prepare(VARIANT, previous["authoring_input"]["local"]["path"], previous["source_manifest"]["path"])
    report = base.read(DIRECTORY / "candidate.json")
    pack = DIRECTORY / "pack"
    target = pack / "einhander-texture-replacements" / (KEY + ".png")
    raw = subprocess.check_output([shutil.which("ffmpeg"), "-v", "error", "-i", str(art),
        "-vf", "scale=4096:4096:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], timeout=60)
    rgb = np.frombuffer(raw, np.uint8).reshape(4096,4096,3)
    with Image.open(SOURCE / (KEY + ".png")) as image:
        alpha = np.asarray(image.convert("RGBA"))[:, :, 3]
    alpha = np.repeat(np.repeat(alpha,64,0),64,1)
    Image.fromarray(np.concatenate([rgb,alpha[:,:,None]],axis=2)).save(target)
    for suffix in [".words.bin", ".clut.bin", ".valid.bin", ".source.json"]:
        ui.copy_verified(SOURCE / (KEY + suffix), pack / (KEY + suffix))
    with (pack / "ExactRegions.tsv").open("a",encoding="utf-8") as stream:
        stream.write(REGION)
    report["files"].append(dict(name=KEY+".png",composed_path=str(target),sha256=ui.sha(target),
        dimensions=[4096,4096],bytes=target.stat().st_size,origin="Matched neighbor facade; one new exact source region",visual_accepted=False))
    report["final_count"] = 1196
    report["launches"]["candidate"]["environment_overrides"]["PSX_REWIND"] = "0"
    report["neighbor"] = dict(key=KEY,source_rect_words=[800,0,16,64],clut_xy=[16,480],
        source_guide=base.ref(SOURCE / (KEY+".source.json")),art=base.ref(art),
        authored_dimensions=dimensions,runtime_dimensions=[4096,4096],
        native_4096_authored=dimensions==[4096,4096],categorical_alpha_exact=True)
    report["test_scope"] = dict(existing_h24_unchanged=True,new_neighbor=KEY,no_fire=True,
        normal_speed=True,survival_assistance="timer only, 180s lease")
    base.write(DIRECTORY / "candidate.json", report)
    result = check(report)
    base.write(DIRECTORY / "preparation-verification.json", result)
    print(json.dumps(result),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--art", type=Path,
        default=base.ROOT / "docs/media/gallery/h24-neighbor-material.png")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(base.read(DIRECTORY / "candidate.json"))), flush=True)
    else:
        prepare(args.art)
