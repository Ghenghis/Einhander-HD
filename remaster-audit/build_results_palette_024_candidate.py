"""Author one independently verified results palette, without guessed fade aliases."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "remaster-audit/menu-restoration/results-palette-024-candidate-v1"
BASE = ROOT / "remaster-audit/menu-restoration/palette-field-candidate-v7"
LIVE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5"
KEY = "8E1A509D-02491337"
REGIONS = [(0, 0, 256, 236)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    if OUT.exists():
        raise ValueError("Choose a new isolated candidate")
    cv2.setNumThreads(2)
    hud = load(ROOT / "windows-x64/tools/build_hud_ui_candidate.py", "results024_hud")
    menu = load(BASE / "build-source.py", "results024_menu")
    reference = next(a for a in json.loads((BASE / "manifest.json").read_bytes())["assets"] if a["key"] == "8E1A509D-4FE32821")
    metadata, source_words, unused_clut = hud.verify_stock(Path(reference["source"]).parent, reference["key"])
    vram_path = LIVE / "post-gameover-vram.bin"
    receipt_path = LIVE / "post-gameover-vram.json"
    receipt = json.loads(receipt_path.read_bytes())
    if receipt["dump"]["frame"] != 46968 or receipt["dump"]["vram_words"] != 524288:
        raise ValueError("Live VRAM receipt changed")
    vram = np.frombuffer(vram_path.read_bytes(), "<u2").reshape(512, 1024)
    words = vram[0:256, 512:576].astype("<u2").tobytes()
    clut = vram[480, 16:32].astype("<u2").tobytes()
    if words != source_words or f"{zlib.crc32(words):08X}" != "8E1A509D" or f"{zlib.crc32(clut):08X}" != "02491337":
        raise ValueError("Native words/palette identity does not match exact key")
    indices = hud.decode_indices(words, metadata)
    palette = hud.palette_rgba(clut)
    contours, selected = menu.menu_contour_indices(indices, 16, REGIONS)
    with np.load(BASE / "masters/8E1A509D.npz") as accepted:
        if not np.array_equal(indices, accepted["native_indices"]) or not np.array_equal(contours[:236*16], accepted["contour_indices"][:236*16]):
            raise ValueError("Accepted text geometry differs")
    main_rgba, native = menu.menu_render(indices, contours, palette, REGIONS)
    strict_rgba = main_rgba.copy()
    incompatible = main_rgba[:, :, 3] != native[:, :, 3]
    strict_rgba[incompatible] = native[incompatible]
    if not np.array_equal(main_rgba[~selected], native[~selected]) or not np.array_equal(strict_rgba[:, :, 3], native[:, :, 3]):
        raise ValueError("Bounded/native alpha protection failed")
    for folder in ("pack/einhander-texture-replacements", "strict-mask-pack/einhander-texture-replacements", "source-proof", "previews"):
        (OUT / folder).mkdir(parents=True)
    for folder in ("pack", "strict-mask-pack"):
        (OUT / folder / "Hashes.ini").write_text("")
    outputs = {}
    for folder, rgba in (("pack", main_rgba), ("strict-mask-pack", strict_rgba)):
        path = OUT / folder / "einhander-texture-replacements" / (KEY+".png")
        Image.fromarray(rgba).save(path)
        if not np.array_equal(np.asarray(Image.open(path)), rgba):
            raise ValueError("Output round-trip failed")
        outputs[folder] = {"path": str(path), "sha256": sha(path), "dimensions": [4096, 4096]}
    proof = OUT / "source-proof"
    (proof / (KEY+".words.bin")).write_bytes(words)
    (proof / (KEY+".clut.bin")).write_bytes(clut)
    (proof / (KEY+".valid.bin")).write_bytes(bytes([1])*16384)
    Image.fromarray(palette[indices]).save(proof / (KEY+".png"))
    shutil.copyfile(receipt_path, proof / "vram-receipt.json")
    source_metadata = {"key": KEY, "frame": 46968, "width_words": 64, "height": 256, "depth": 0,
                       "clut_xy": [16, 480], "clut_words": 16, "known_words": 16384, "total_words": 16384,
                       "reconstructed_crc32": "8E1A509D", "page_xy": [512, 0],
                       "raw_origin": "verified full canonical VRAM snapshot; byte-exact accepted page geometry"}
    (proof / (KEY+".source.json")).write_text(json.dumps(source_metadata, indent=2)+"\n")
    # Independent source decoder checks its own written raw/palette/PNG proof.
    verified_meta, verified_raw, verified_clut = hud.verify_stock(proof, KEY)
    if verified_raw != words or verified_clut != clut:
        raise ValueError("Persisted proof changed")
    box = (0, 158, 256, 236); width, height = 1024, 312
    canvas = Image.new("RGBA", (width, height*2+56), (12, 18, 25, 255)); draw = ImageDraw.Draw(canvas)
    draw.text((6, 5), KEY+" verified native source typography (4x)", fill="white")
    canvas.alpha_composite(Image.fromarray(palette[indices]).crop(box).resize((width, height), Image.Resampling.NEAREST), (0, 24))
    draw.text((6, height+30), "Same exact CLUT, accepted continuous typography; footer/icon row excluded", fill="white")
    canvas.alpha_composite(Image.fromarray(main_rgba).crop(tuple(v*16 for v in box)).resize((width, height), Image.Resampling.LANCZOS), (0, height+54))
    canvas.convert("RGB").save(OUT / "previews/typography-actual4x.png")
    query_path = LIVE / "native-live-gameplay/capture.jsonl"
    queries = [json.loads(line) for line in query_path.read_text().splitlines()]
    queries = [r for r in queries if r.get("key") == KEY and r.get("event") == "source_draw_query_matched"]
    manifest = {"contract": "verified-results-palette-024-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "production_installed": False, "game_actions": 0, "key": KEY, "asset_count": 1, "scale": 16,
                "regions": [list(r) for r in REGIONS], "main_categorical_contour_alpha": True,
                "strict_original_alpha_footprint_exact": True, "protected_outside_regions_rgba_exact_to_native_nearest": True,
                "source": {"metadata": source_metadata, "vram": str(vram_path), "vram_sha256": sha(vram_path),
                           "receipt": str(receipt_path), "receipt_sha256": sha(receipt_path),
                           "words_sha256": hashlib.sha256(words).hexdigest(), "clut_sha256": hashlib.sha256(clut).hexdigest(),
                           "pixels_sha256": hashlib.sha256(palette[indices].tobytes()).hexdigest(),
                           "accepted_reference_key": reference["key"], "words_byte_exact_to_accepted_source": True},
                "method": "Same accepted menu-v7 continuous source-index tones,14percent directional light,16percent narrow rim, categorical current exact palette classes; no font substitution or guessed fade aliases",
                "outputs": outputs, "source_proof_files": [{"path": str(p), "sha256": sha(p)} for p in sorted(proof.iterdir())],
                "checks": {"source_crc32": "8E1A509D", "clut_crc32": "02491337", "source_decode_verified": True,
                           "accepted_contour_indices_inside_region_exact": True, "strict_alpha_exact": True,
                           "outside_rgba_exact": True, "alpha_classes": sorted(map(int, np.unique(main_rgba[:, :, 3])))},
                "native_queries": {"log": str(query_path), "log_sha256": sha(query_path), "query_count": len(queries),
                                   "uv_bounds": sorted(map(list, {tuple(r["uv_bounds"]) for r in queries})),
                                   "sample_receipt": queries[0] if queries else None},
                "coverage_limit": "Exact02491337 typography only. Sampled records do not prove the large GAME OVER word binding. Dynamic footer/icon palettes and all other unseen CLUTs remain native."}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "build-source.py")
    print(json.dumps({"output": str(OUT), "key": KEY, "outputs": outputs}), flush=True)


if __name__ == "__main__":
    main()
