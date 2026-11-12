"""Technically encode one ImageGen-restored whole Results aircraft master.

Creative editing is done by built-in ImageGen; FFmpeg performs the deterministic
scale/split. Packing binds exact native categorical alpha and protects all other
page pixels. This script never operates a running game or installed pack.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5/results-poster-source-proof-v1"
OUT = ROOT / "remaster-audit/menu-restoration/results-art-candidate-v2"
GENERATED = Path("C:/Users/Admin/.codex/generated_images/01a1d0a6-f0c2-75d1-9642-cf4e532a7fc4/exec-78c506ba-8328-45ee-bbc4-2643cbc75cd6.png")
PROMPT = """Use case: precise-object-edit. Asset type: remastered in-game Results screen artwork, one complete aircraft master before deterministic texture-strip splitting. The supplied image is the EDIT TARGET and exact geometry/color reference, not loose inspiration. Restore this same blue/yellow/white science fiction aircraft at much higher visual fidelity. Preserve the exact 10:7 rectangular composition, exact silhouette, proportions, pose/perspective, every wing and appendage arrangement, long lower-left blue-and-black mechanical pod, white forward fuselage with small red accent and green lens, yellow wing joints, dark navy wing faces, cyan edge lighting, and generous solid black backdrop. Keep the object at the same position and size with the same crop and negative space. Reconstruct crisp metal panels, precise seams, clean anti-aliased contours, small highlights and restrained surface depth guided by the visible original; smooth the low-resolution steps and blur. Retain the soft narrow blue glow around the existing edges. Do not redesign or add structures. No extra weapons, fins, engines, objects, labels, text, logos, stars, scenery, gradients in the black background, watermark, or border. One whole faithful restored aircraft on black, not a sprite sheet. Preserve geometry aggressively while making materials and contours visibly sharper."""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise ValueError("Choose a new isolated candidate; previous builds are immutable")
    source_manifest = json.loads((SOURCE / "manifest.json").read_bytes())
    if source_manifest["contract"] != "verified-results-poster-source-v1" or len(source_manifest["pages"]) != 5:
        raise ValueError("Expected verified five-page Results source")
    spec = importlib.util.spec_from_file_location("results_art_hud", ROOT / "windows-x64/tools/build_hud_ui_candidate.py")
    hud = importlib.util.module_from_spec(spec); spec.loader.exec_module(hud)
    for folder in ("pack/einhander-texture-replacements", "encoded-strips", "source-proof", "previews"):
        (OUT / folder).mkdir(parents=True)
    (OUT / "pack/Hashes.ini").write_text("")
    (OUT / "prompt.txt").write_text(PROMPT+"\n")
    master = OUT / "results-aircraft-master.png"
    shutil.copyfile(GENERATED, master)
    master_size = list(Image.open(master).size)
    if abs((master_size[0]/master_size[1])/(10/7)-1) > .001:
        raise ValueError("Whole generated master must retain the native10:7 aspect within one-pixel rounding")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for deterministic master scaling/splitting")
    commands = []

    def ffmpeg_run(args):
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n", *map(str, args)]
        result = subprocess.run(command, capture_output=True, text=True)
        commands.append({"command": command, "exit_code": result.returncode, "stderr": result.stderr})
        if result.returncode:
            raise RuntimeError(result.stderr)

    scaled = OUT / "results-aircraft-encoded-5120x3584.png"
    ffmpeg_run(["-i", master, "-vf", "scale=5120:3584:flags=lanczos", "-frames:v", "1", "-threads", "1", scaled])
    rows, visible_strips = [], []
    for column, source in enumerate(source_manifest["pages"]):
        key = source["key"]
        metadata, words, clut = hud.verify_stock(SOURCE, key)
        if hashlib.sha256(words).hexdigest() != source["source_words_sha256"] or sha(SOURCE / (key+".png")) != source["source_png_sha256"]:
            raise ValueError("Verified page source changed")
        native = np.asarray(Image.open(SOURCE / (key+".png")).convert("RGBA"))
        nearest = np.repeat(np.repeat(native, 16, 0), 16, 1)
        authored = nearest.copy()
        strip_path = OUT / "encoded-strips" / (key+".rgb.png")
        ffmpeg_run(["-i", scaled, "-vf", f"crop=1024:3584:{column*1024}:0", "-frames:v", "1", "-threads", "1", strip_path])
        strip = np.asarray(Image.open(strip_path).convert("RGB"))
        authored[:3584, :1024, :3] = strip
        # Clear samples remain exact black so filtering cannot expose unrelated
        # generated RGB through a categorical cutout boundary.
        clear = authored[:, :, 3] == 0
        authored[clear, :3] = nearest[clear, :3]
        selected = np.zeros((4096, 4096), bool); selected[:3584, :1024] = True
        if not np.array_equal(authored[:, :, 3], nearest[:, :, 3]) or not np.array_equal(authored[~selected], nearest[~selected]):
            raise ValueError("Native alpha or protected page pixels changed")
        output = OUT / "pack/einhander-texture-replacements" / (key+".png")
        Image.fromarray(authored).save(output)
        written = np.asarray(Image.open(output).convert("RGBA"))
        if not np.array_equal(written, authored):
            raise ValueError("Encoded PNG round-trip failed")
        for suffix in (".png", ".words.bin", ".clut.bin", ".valid.bin", ".source.json"):
            shutil.copyfile(SOURCE / (key+suffix), OUT / "source-proof" / (key+suffix))
        visible_strips.append(authored[:3584, :1024].copy())
        rows.append({"key": key, "path": str(output), "sha256": sha(output), "size": [4096, 4096],
                     "source": str(SOURCE / (key+".png")), "source_sha256": source["source_png_sha256"],
                     "source_words_sha256": source["source_words_sha256"], "source_clut_sha256": hashlib.sha256(clut).hexdigest(),
                     "source_page_xy": source["page_xy"], "region_half_open": [0, 0, 64, 224],
                     "master_crop_half_open": source["master_crop_half_open"],
                     "native_alpha_stp_footprint_exact": True, "protected_outside_rgba_exact": True,
                     "clear_source_samples_rgba_exact": True,
                     "changed_rgb_samples_inside": int(np.any(authored[:3584, :1024, :3] != nearest[:3584, :1024, :3], 2).sum())})
    assembled = np.concatenate(visible_strips, axis=1)
    Image.fromarray(assembled).save(OUT / "previews/encoded-complete-rgba.png")
    display = assembled.copy(); display[:, :, 3] = np.where(display[:, :, 3] == 0, 0, 255)
    old = np.asarray(Image.open(SOURCE / "results-native-display-320x224.png").convert("RGBA"))
    width, height = 1280, 896
    canvas = Image.new("RGBA", (width, height*2+56), (0, 0, 0, 255)); draw = ImageDraw.Draw(canvas)
    draw.text((6, 5), "Native Results aircraft source (actual4x); PSX nonzero classes displayed opaque", fill="white")
    canvas.alpha_composite(Image.fromarray(old).resize((width, height), Image.Resampling.NEAREST), (0, 24))
    draw.text((6, height+30), "ImageGen restored whole master, deterministic FFmpeg split, exact native alpha footprint (actual4x)", fill="white")
    canvas.alpha_composite(Image.fromarray(display).resize((width, height), Image.Resampling.LANCZOS), (0, height+54))
    canvas.convert("RGB").save(OUT / "previews/results-before-after-actual4x.png")
    seam = []
    for column in range(1, 5):
        delta = np.abs(assembled[:, column*1024-1, :3].astype(np.int16)-assembled[:, column*1024, :3])
        seam.append({"join_native_x": column*64, "adjacent_rgb_difference_mean": float(delta.mean()), "adjacent_rgb_difference_max": int(delta.max())})
    (OUT / "ffmpeg-receipts.json").write_text(json.dumps(commands, indent=2)+"\n")
    manifest = {"format": 1, "contract": "verified-results-art-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "asset_count": 5, "files": rows,
                "master": {"path": str(master), "size": master_size, "sha256": sha(master), "origin": "built-in ImageGen edit", "original_output": str(GENERATED)},
                "encoded_master": {"path": str(scaled), "size": [5120, 3584], "sha256": sha(scaled), "method": "FFmpeg Lanczos scaling and tiny1499x1049 rounding-aspect normalization to exact10:7; not native generation resolution"},
                "prompt": {"path": str(OUT / "prompt.txt"), "sha256": sha(OUT / "prompt.txt")},
                "source_mapping": {"path": str(SOURCE / "manifest.json"), "sha256": sha(SOURCE / "manifest.json")},
                "ffmpeg_receipts": {"path": str(OUT / "ffmpeg-receipts.json"), "sha256": sha(OUT / "ffmpeg-receipts.json")},
                "method": "Built-in ImageGen faithful whole-aircraft restoration; deterministic FFmpeg scale and five-strip crop; exact original fullpage categorical alpha and outside-region RGBA protection",
                "seam_rgb_adjacent_column_difference": seam,
                "source_proof_files": [{"path": str(p), "sha256": sha(p)} for p in sorted((OUT / "source-proof").iterdir())],
                "production_installed": False, "game_actions": 0, "live_accepted": False,
                "pending": ["Independent output/source verification", "Actual five-key replacement submissions and Results screenshot", "Actual seams, native modulation, alpha and unrelated page content review"],
                "limits": ["Generated surface detail is a source-guided interpretation; the categorical silhouette/alpha footprint is exact by technical binding.",
                           "Master generated dimensions are recorded honestly; 5120x3584 is deterministic resampling.",
                           "This candidate is isolated and has not been accepted in gameplay."]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "build-source.py")
    print(json.dumps({"output": str(OUT), "master_size": master_size, "files": rows, "seams": seam}), flush=True)


if __name__ == "__main__":
    main()
