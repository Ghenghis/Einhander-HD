"""Deterministically encode the separately generated current Results artwork.

Creative restoration is already performed by built-in ImageGen. This builder
copies that master into the project, records its actual generation dimensions,
then uses FFmpeg for deterministic scale/split and exact native source binding.
It never operates a game or modifies an existing candidate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zlib

import numpy as np
from PIL import Image, ImageDraw

from map_results_art_aliases import decode


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "remaster-audit/menu-restoration/results-native-v6-variant-source-v1"
OUT = ROOT / "remaster-audit/menu-restoration/results-current-art-candidate-v1"
GENERATED = Path("C:/Users/Admin/.codex/generated_images/01a1d12b-64a7-7e80-8604-0efeba0fffa8/exec-5ed8e4d8-6162-4695-aa52-cf84eda46eea.png")
SCALE = 16


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def sha_file(path):
    return sha(Path(path).read_bytes())


def ref(path):
    return dict(path=str(path), sha256=sha_file(path))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, document):
    Path(path).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def verify_source():
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["contract"] == "verified-results-current-variant-source-v1" and len(manifest["pages"]) == 5,
            "Expected the separately proved current Results variant")
    pages = []
    for page in manifest["pages"]:
        key = page["key"]
        for receipt in page["source_files"]:
            require(sha_file(receipt["path"]) == receipt["sha256"], "Native source proof changed")
        raw = (SOURCE / (key + ".words.bin")).read_bytes()
        valid = (SOURCE / (key + ".valid.bin")).read_bytes()
        clut = (SOURCE / (key + ".clut.bin")).read_bytes()
        metadata = json.loads((SOURCE / (key + ".source.json")).read_text())
        require(len(raw) == 131072 and valid == bytes([1])*65536 and clut == b"", "Incomplete current native source")
        require(f"{zlib.crc32(raw):08X}-00000000" == key, "Native full-page CRC differs")
        require([metadata[k] for k in ("key", "width_words", "height", "depth", "known_words", "total_words")] ==
                [key, 256, 256, 2, 65536, 65536], "Native source layout differs")
        words = np.frombuffer(raw, dtype="<u2").reshape(256, 256)
        rgba = decode(words)
        with Image.open(SOURCE / (key + ".png")) as image:
            require(image.size == (256, 256) and image.convert("RGBA").tobytes() == rgba.tobytes(), "Independent native source decode differs")
        used = rgba[:224, :64]
        require(not np.any(used[:, :, 3] == 0), "This candidate requires the proved opaque Results used region; do not impose a pixel-shaped cutout mask on a different source")
        pages.append((page, words, rgba))
    whole = np.concatenate([rgba[:224, :64] for _, _, rgba in pages], axis=1)
    with Image.open(manifest["source_master"]["path"]) as image:
        require(image.convert("RGBA").tobytes() == whole.tobytes(), "Current native whole-master assembly differs")
    return manifest, pages, whole


def shape_metrics(native, authored):
    """Descriptive threshold comparisons, never semantic acceptance gates."""
    with Image.fromarray(authored[:, :, :3]) as image:
        small = np.asarray(image.resize((320, 224), Image.Resampling.LANCZOS))
    rows = []
    for threshold in (24, 48, 80):
        a = native[:, :, :3].max(axis=2) > threshold
        b = small.max(axis=2) > threshold
        union = int(np.logical_or(a, b).sum())
        intersection = int(np.logical_and(a, b).sum())
        rows.append(dict(rgb_max_threshold=threshold, source_pixels=int(a.sum()), authored_pixels=int(b.sum()),
                         intersection_over_union=intersection/union if union else 1.0,
                         qualification="Brightness/glow/material-sensitive comparison; not exact silhouette or semantic shape proof"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, default=GENERATED)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--prompt-file", required=True, type=Path, help="Exact prompt text or saved ImageGen session JSON containing this generated asset")
    parser.add_argument("--marking-proof", type=Path, help="Optional separately reviewed JSON with native_master_rects and evidence, applied as protected native rectangles")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT / "remaster-audit/menu-restoration") and not output.exists(), "Choose a new isolated candidate directory")
    require(args.generated.is_file() and args.prompt_file.is_file(), "Generated master and exact prompt receipt are required")
    prompt = args.prompt_file.read_text(encoding="utf-8")
    prompt_asset_index = None
    if args.prompt_file.suffix.lower() == ".json":
        execution = json.loads(prompt)
        matches = [(index, row) for index, row in enumerate(execution["assets"])
                   if Path(row["generated"]).resolve() == args.generated.resolve()]
        require(len(matches) == 1 and execution["tool"] in ("built-in ImageGen", "built-in image_gen.imagegen"), "Saved prompt session does not identify this one built-in generated asset")
        prompt_asset_index, asset = matches[0]
        require(Path(asset["input"]).resolve() == SOURCE / "results-native-display-320x224.png", "Saved prompt names another edit target")
        prompt = asset["prompt"]
    require(bool(prompt.strip()), "Exact execution prompt cannot be empty")
    source_manifest, pages, native_whole = verify_source()
    with Image.open(args.generated) as image:
        generated_size = list(image.size)
        require(image.mode in ("RGB", "RGBA") and abs((image.width/image.height)/(10/7)-1) < .001,
                "Generated whole master must retain the current native 10:7 aspect within one-pixel rounding")
    marking_rects = []
    marking_proof = None
    if args.marking_proof:
        marking_proof = json.loads(args.marking_proof.read_text(encoding="utf-8"))
        require(marking_proof.get("reviewed") is True and marking_proof.get("source_master_sha256") == source_manifest["source_master"]["sha256"] and
                bool(marking_proof.get("evidence")), "Marking protection requires a reviewed exact-source rectangle proof")
        for rect in marking_proof["native_master_rects"]:
            require(len(rect) == 4 and 0 <= rect[0] < rect[2] <= 320 and 0 <= rect[1] < rect[3] <= 224,
                    "Marking rectangle is outside the native whole master")
            marking_rects.append(rect)
    ffmpeg = shutil.which("ffmpeg")
    require(ffmpeg is not None, "Existing FFmpeg is required for deterministic encoding")
    for folder in ("pack/einhander-texture-replacements", "pack-fullpage/einhander-texture-replacements",
                   "strict-source-footprint/pack/einhander-texture-replacements",
                   "strict-source-footprint/pack-fullpage/einhander-texture-replacements",
                   "encoded-strips", "source-proof", "previews"):
        (output / folder).mkdir(parents=True, exist_ok=False)
    for folder in ("pack", "pack-fullpage", "strict-source-footprint/pack", "strict-source-footprint/pack-fullpage"):
        (output / folder / "Hashes.ini").write_text("", encoding="utf-8")
    master = output / "results-current-aircraft-master.png"
    shutil.copyfile(args.generated, master)
    require(sha_file(master) == sha_file(args.generated), "Project master copy changed")
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    if args.marking_proof:
        shutil.copyfile(args.marking_proof, output / "marking-proof.json")
    commands = []

    def ffmpeg_run(arguments):
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n", *map(str, arguments)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        commands.append(dict(command=command, exit_code=result.returncode, stderr=result.stderr))
        require(result.returncode == 0, "FFmpeg failed: " + result.stderr)

    scaled = output / "results-current-aircraft-encoded-5120x3584.png"
    ffmpeg_run(["-i", master, "-vf", "scale=5120:3584:flags=lanczos", "-frames:v", "1", "-threads", "1", scaled])
    with Image.open(scaled) as image:
        encoded_rgb = np.asarray(image.convert("RGB"))
    require(encoded_rgb.shape == (3584, 5120, 3), "Encoded whole master has wrong dimensions")
    protected_native = np.repeat(np.repeat(native_whole, SCALE, axis=0), SCALE, axis=1)
    authored_whole = np.concatenate((encoded_rgb.copy(), protected_native[:, :, 3:4]), axis=2)
    for x0, y0, x1, y1 in marking_rects:
        authored_whole[y0*SCALE:y1*SCALE, x0*SCALE:x1*SCALE] = protected_native[y0*SCALE:y1*SCALE, x0*SCALE:x1*SCALE]
    require(not np.any(authored_whole[:, :, 3] == 0), "Unexpected cutout in the opaque current Results region")
    region_rows, full_rows, manifest_lines = [], [], ["EIN_EXACT_REGIONS_V1"]
    for column, (page, words, native) in enumerate(pages):
        full_key = page["key"]
        x, y = page["page_xy"]
        raw_region = words[:224, :64].copy().astype("<u2").tobytes()
        region_key = f"{zlib.crc32(raw_region):08X}-00000000"
        strip_path = output / "encoded-strips" / (region_key + ".rgb.png")
        ffmpeg_run(["-i", scaled, "-vf", f"crop=1024:3584:{column*1024}:0", "-frames:v", "1", "-threads", "1", strip_path])
        with Image.open(strip_path) as image:
            require(np.array_equal(np.asarray(image.convert("RGB")), encoded_rgb[:, column*1024:(column+1)*1024]), "FFmpeg crop differs from whole-master pixels")
        strip = authored_whole[:, column*1024:(column+1)*1024].copy()
        nearest = np.repeat(np.repeat(native, SCALE, axis=0), SCALE, axis=1)
        full = nearest.copy()
        full[:3584, :1024] = strip
        require(np.array_equal(full[:, :, 3], nearest[:, :, 3]) and np.array_equal(full[:, 1024:], nearest[:, 1024:]) and
                np.array_equal(full[3584:, :1024], nearest[3584:, :1024]), "Full-page edit changed alpha or escaped the current used region")
        region_png = output / "pack/einhander-texture-replacements" / (region_key + ".png")
        full_png = output / "pack-fullpage/einhander-texture-replacements" / (full_key + ".png")
        Image.fromarray(strip).save(region_png)
        Image.fromarray(full).save(full_png)
        for path, expected in ((region_png, strip), (full_png, full)):
            with Image.open(path) as image:
                require(np.array_equal(np.asarray(image.convert("RGBA")), expected), "Packed PNG decode roundtrip differs")
        strict_region = output / "strict-source-footprint/pack/einhander-texture-replacements" / region_png.name
        strict_full = output / "strict-source-footprint/pack-fullpage/einhander-texture-replacements" / full_png.name
        shutil.copyfile(region_png, strict_region)
        shutil.copyfile(full_png, strict_full)
        for base in (output / "pack", output / "strict-source-footprint/pack"):
            (base / (region_key + ".words.bin")).write_bytes(raw_region)
            (base / (region_key + ".valid.bin")).write_bytes(bytes([1]) * (64*224))
            (base / (region_key + ".clut.bin")).write_bytes(b"")
            write(base / (region_key + ".source.json"), dict(key=region_key, full_page_key=full_key,
                frame=source_manifest["source_vram"]["frame"], width_words=64, height=224, depth=2,
                clut_xy=[0, 0], clut_words=0, known_words=64*224, total_words=64*224,
                page_xy=[x, y], reconstructed_crc32=region_key.split("-")[0],
                raw_origin="Exact current GPU-truth Results used region; contiguous64x224LE16words",
                fragments=[[x, y, 64, 224, 0, 0]]))
        manifest_lines.append(f"{region_key} {x} {y} 64 224 2 0 0")
        for suffix in (".png", ".words.bin", ".clut.bin", ".valid.bin", ".source.json"):
            shutil.copyfile(SOURCE / (full_key + suffix), output / "source-proof" / (full_key + suffix))
        common = dict(full_page_key=full_key, exact_region_key=region_key, source_page_xy=[x, y],
                      native_used_region_half_open=[0, 0, 64, 224], master_crop_half_open=[column*64, 0, (column+1)*64, 224],
                      source_words_sha256=sha(raw_region), source_native_rgba_sha256=sha(native[:224, :64].tobytes()),
                      native_alpha_stp_footprint_exact=True, source_clear_samples=0,
                      categorical_alpha_classes=[127, 255], main_alpha_displacement_native_pixels=0.0,
                      strict_source_footprint_comparison_identical=True,
                      generated_marking_transcription_verified=False, live_visual_accepted=False)
        region_rows.append(dict(common, key=region_key, path=str(region_png), sha256=sha_file(region_png),
                                dimensions=[1024, 3584], source_dimensions=[64, 224], strict_path=str(strict_region),
                                strict_sha256=sha_file(strict_region), source_archives=[ref(output / "pack" / (region_key + suffix))
                                  for suffix in (".words.bin", ".clut.bin", ".valid.bin", ".source.json")]))
        full_rows.append(dict(common, key=full_key, path=str(full_png), sha256=sha_file(full_png),
                              dimensions=[4096, 4096], source_dimensions=[256, 256], protected_outside_rgba_exact=True,
                              strict_path=str(strict_full), strict_sha256=sha_file(strict_full)))
    require(len({row["key"] for row in region_rows}) == 5, "Exact region key collision")
    exact_manifest = "\n".join(manifest_lines) + "\n"
    for base in (output / "pack", output / "strict-source-footprint/pack"):
        (base / "ExactRegions.tsv").write_text(exact_manifest, encoding="ascii")
    composed = np.concatenate([np.asarray(Image.open(row["path"]).convert("RGBA")) for row in region_rows], axis=1)
    require(np.array_equal(composed, authored_whole), "Adjacent packed regions do not reassemble exactly into the coherent whole master")
    Image.fromarray(authored_whole).save(output / "previews/encoded-complete-rgba.png")
    width, height = 1280, 896
    preview = Image.new("RGB", (width, height*2+64), "black")
    draw = ImageDraw.Draw(preview)
    draw.text((8, 8), "Current native Results source - displayed4x; categorical PSX classes shown opaque", fill="white")
    preview.paste(Image.fromarray(native_whole[:, :, :3]).resize((width, height), Image.Resampling.NEAREST), (0, 28))
    draw.text((8, height+36), "Current ImageGen restoration - same displayed scale; generated markings remain interpretation", fill="white")
    preview.paste(Image.fromarray(authored_whole[:, :, :3]).resize((width, height), Image.Resampling.LANCZOS), (0, height+64))
    preview.save(output / "previews/current-results-before-after-actual4x.png")
    Image.fromarray(native_whole[:, :, :3]).resize((1280, 896), Image.Resampling.NEAREST).save(output / "previews/native-current-actual4x.png")
    seams = []
    for column in range(1, 5):
        x = column * 1024
        delta = np.abs(authored_whole[:, x-1, :3].astype(np.int16) - authored_whole[:, x, :3].astype(np.int16))
        seams.append(dict(join_native_x=column*64, adjacent_rgb_difference_mean=float(delta.mean()), adjacent_rgb_difference_max=int(delta.max()),
                          exact_whole_master_strip_reassembly=True, live_seam_acceptance=False))
    write(output / "ffmpeg-receipts.json", commands)
    manifest = dict(
        schema_version=1, contract="verified-current-results-art-v1", created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_variant=source_manifest["source_variant"], region_asset_count=5, fullpage_asset_count=5,
        files=region_rows, fullpage_files=full_rows,
        master=dict(**ref(master), dimensions=generated_size, origin="built-in ImageGen edit", original_output=str(args.generated)),
        prompt=dict(**ref(output / "prompt.txt"), origin="Exact built-in ImageGen execution prompt", source_receipt=ref(args.prompt_file), source_asset_index=prompt_asset_index),
        encoded_master=dict(**ref(scaled), dimensions=[5120, 3584], method="Deterministic FFmpeg Lanczos scaling and tiny1499x1049aspect-rounding normalization; not native generation resolution"),
        exact_regions=dict(**ref(output / "pack/ExactRegions.tsv"), contract="EIN_EXACT_REGIONS_V1", runtime_support_required=True,
                           row_format="REGIONCRC-PALETTECRC X Y WIDTH_WORDS HEIGHT DEPTH CLUT_X CLUT_Y"),
        source_mapping=ref(SOURCE / "manifest.json"), source_proof_files=[ref(p) for p in sorted((output / "source-proof").iterdir())],
        ffmpeg_receipts=ref(output / "ffmpeg-receipts.json"), builder=ref(Path(__file__)),
        alpha_policy=dict(main="Exact native categoricalSTP127/255 inside the fully visible current Results region", strict="Separate native-source-footprint comparison outputs",
                          source_used_samples=71680, source_used_clear_samples=0, main_cutout_silhouette=None,
                          source_sdf_refinement_applied=False, maximum_boundary_displacement_native_pixels=0.0,
                          reason="Every sampled source texel is visible. Preserving its STP class cannot clip the restored RGB contour; opaque draw STP classes are retained without unnecessary displacement."),
        marking_protection=dict(source_rectangles=marking_rects, exact_native_rectangles_applied=bool(marking_rects),
                                proof=ref(output / "marking-proof.json") if marking_proof else None,
                                generated_wording_exactness_claimed=False,
                                remaining="Generated mechanical markings are interpretation; exact source glyph/wording fidelity remains unaccepted unless separately bound and restored."),
        seam_metrics=seams, shape_threshold_metrics=shape_metrics(native_whole, authored_whole),
        technical_checks=dict(independent_source_crc_decode_validity=True, source_region_crc_proofs=True,
                              png_roundtrip_exact=True, fullpage_outside_rgba_exact=True,
                              main_and_strict_alpha_exact_to_current_native=True, coherent_whole_master_reassembly_exact=True,
                              native_uv_and_page_positions_preserved=True),
        production_installed=False, game_actions=0, live_accepted=False, independent_visual_review_complete=False,
        pending=["Independent visual review of encoded whole source fidelity, markings and seams",
                 "New ExactRegions runtime admission and replacement submissions for all five region keys",
                 "Actual Results graph-mode/transition/re-entry and alpha/modulation/seam captures",
                 "Bind distinct Results artwork variants to their observed player selection states"],
        limits=["Generated1499x1049master dimensions and resampled5120x3584encoding are separate facts.",
                "The source variant is distinct from the historical five-page Results aircraft; it is not an alias.",
                "Shape threshold metrics depend on brightness and glow; they are descriptive checks, not automatic shape acceptance.",
                "No existing candidate, runtime or installed pack was modified."],
    )
    write(output / "manifest.json", manifest)
    print(json.dumps(dict(output=str(output), region_keys=[row["key"] for row in region_rows],
                          fullpage_keys=[row["key"] for row in full_rows], master_size=generated_size,
                          exact_regions=str(output / "pack/ExactRegions.tsv"), alpha_policy=manifest["alpha_policy"],
                          main_and_strict_identical=True, technical_checks=manifest["technical_checks"], live_accepted=False), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
