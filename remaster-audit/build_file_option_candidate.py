"""Restore the verified file/config/name-grid alphabet through menu tone fields."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
KEY = "AEE859DC-19EFC4BC"
OUT = ROOT/"remaster-audit/menu-restoration/file-option-field-candidate-v1"
MENU = ROOT/"remaster-audit/menu-restoration/palette-field-candidate-v7/build-source.py"
HUD = ROOT/"windows-x64/tools/build_hud_ui_candidate.py"
QUEUE = Path("C:/github/REMASTER_STAGING/full-remaster/queue.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main():
    if OUT.exists():
        raise ValueError("Existing candidates are immutable; choose a new output")
    row = next(x for x in json.loads(QUEUE.read_bytes())["assets"] if x["key"] == KEY)
    if not row["source_verified"]:
        raise ValueError("Source must be independently verified")
    cv2.setNumThreads(2)
    hud, menu = module(HUD, "file_option_hud"), module(MENU, "file_option_menu")
    source = Path(row["source"])
    metadata, raw, clut = hud.verify_stock(source.parent, KEY)
    indices, palette = hud.decode_indices(raw, metadata), hud.palette_rgba(clut)
    decoded = palette[indices]
    if hashlib.sha256(raw).hexdigest() != row["raw_sha256"] or hashlib.sha256(clut).hexdigest() != row["clut_sha256"] or hashlib.sha256(decoded.tobytes()).hexdigest() != row["source_pixel_sha256"]:
        raise ValueError("Independent source words/CLUT/pixels mismatch")
    # Source0 is white,1..14 are ascending dark-to-light and15 is black-STP.
    # Canonical0..14 descend bright-to-dark,15 remains black. This permutation
    # is reversible and leaves the original native RGBA image byte-identical.
    order = np.array([0, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 15], dtype=np.uint8)
    inverse = np.argsort(order).astype(np.uint8)
    canonical, ramp = inverse[indices], palette[order]
    if not np.array_equal(ramp[canonical], decoded):
        raise ValueError("Tonal canonicalization changed original colors/classes")
    if np.any(np.diff(np.max(ramp[:15, :3], axis=1).astype(int)) > 0):
        raise ValueError("Expected a descending verified tonal ramp")
    regions = [(0, 0, 256, 256)]
    rendered, selected = menu.menu_contour_indices(canonical, 16, regions)
    authored, nearest = menu.menu_render(canonical, rendered, ramp, regions)
    if not np.array_equal(authored[:, :, 3], nearest[:, :, 3]):
        raise ValueError("File-option original categorical coverage changed")
    for folder in ("pack/einhander-texture-replacements", "strict-mask-pack/einhander-texture-replacements", "previews", "masters"):
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, OUT/"build-source.py")
    shutil.copy2(MENU, OUT/"menu-field-library.py")
    shutil.copy2(HUD, OUT/"palette-contour-library.py")
    np.savez_compressed(OUT/"masters"/(KEY+".npz"), native_indices=indices, canonical_indices=canonical,
                        canonical_palette_order=order, contour_indices=rendered, native_scale=np.array(16))
    outputs = {}
    for variant in ("pack", "strict-mask-pack"):
        (OUT/variant/"Hashes.ini").write_text("", encoding="utf-8")
        path = OUT/variant/"einhander-texture-replacements"/(KEY+".png")
        Image.fromarray(authored).save(path)
        with Image.open(path) as reread:
            if reread.mode != "RGBA" or reread.tobytes() != authored.tobytes():
                raise ValueError("Written texture round-trip failed")
        outputs[variant] = {"path": str(path), "sha256": sha(path)}
    box = (0, 192, 256, 256)
    canvas = Image.new("RGB", (1536, 838), (12, 18, 25))
    draw = ImageDraw.Draw(canvas)
    for y, label, image in ((0, "ORIGINAL VERIFIED FILE/CONFIG/NAME ALPHABET", Image.fromarray(decoded).crop(box).resize((1536, 384), Image.Resampling.NEAREST)),
                             (419, "CONTINUOUS ORIGINAL TONES / SHARED BEVEL / DARK RIM", Image.fromarray(authored).crop(tuple(x*16 for x in box)).resize((1536, 384), Image.Resampling.LANCZOS))):
        draw.text((8, y+8), label, fill="white")
        canvas.paste(image.convert("RGB"), (0, y+30))
    canvas.save(OUT/"previews"/(KEY+"-alphabet-before-after.png"))
    asset = {"key": KEY, "role": "Startup/config/file-option prompts, score/data menu and name-grid alphabet; original Japanese text and Latin glyphs",
             "source": str(source), "source_sha256": sha(source), "source_words_sha256": hashlib.sha256(raw).hexdigest(),
             "source_clut_sha256": hashlib.sha256(clut).hexdigest(), "source_metadata": metadata,
             "source_size": [256, 256], "output_size": [4096, 4096], "selected_native_regions": regions,
             "canonical_palette_order": order.tolist(), "outputs": outputs,
             "checks": {"raw_crc_clut_independent_decode": True, "palette_permutation_native_rgba_exact": True,
                        "main_original_alpha_footprint_exact": True, "categorical_classes_only": True,
                        "png_roundtrip_exact": True},
             "changed_rgb_texels": int(np.any(authored[:, :, :3] != nearest[:, :, :3], axis=2).sum()),
             "in_game_acceptance": "pending isolated startup/config/file-option/name-grid review"}
    manifest = {"format": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(), "production_installed": False,
                "game_actions": 0, "geometry_version": "menu-continuous-palette-field-v1", "asset_count": 1,
                "method": "Reversible source tonal-ramp canonicalization followed by existing accepted menu continuous-field RGB reconstruction, shared directional bevel and narrow rim. Original glyph content/UV layout and entire alpha footprint retained.",
                "source_queue_sha256": sha(QUEUE), "implementation_sha256": sha(Path(__file__)),
                "menu_library_sha256": sha(MENU), "hud_library_sha256": sha(HUD), "assets": [asset],
                "limits": ["Atlas-derived wording and alphabet shapes require actual runtime state coverage; source validity is not proof that every prompt was observed.", "All samples retain original opaque-black-STP class255; file/menu green tint remains the game's vertex modulation."]}
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"pack": str(OUT/"pack"), "manifest": str(OUT/"manifest.json"), "checks": "PASS", "asset_count": 1}))


if __name__ == "__main__":
    main()
