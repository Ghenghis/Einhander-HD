"""Author isolated source-faithful high-resolution menu lettering candidates.

The glyph geometry is reconstructed from verified original indexed texels, not
OCR, a substitute font, or image generation. Subpixel contours, nested edges,
directional bevels and restrained color are authored inside bounded glyph areas.
Only categorical PSX alpha values are emitted. No game or installed pack changes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_three_asset_proof import verify_stock

PROJECT = Path(__file__).resolve().parents[1]
STAGING = Path("C:/github/REMASTER_STAGING")
OUT = PROJECT / "remaster-audit/menu-restoration/layered-candidate-v1"
SCALE = 15  # 256 native pixels -> 3840 texels; odd scale has exact native centers.
FAMILIES = {
    "323B5FB0": {"role": "Main title menu entries, craft names and name-entry alphabet", "rects": [[0, 0, 112, 104], [128, 0, 256, 86]],
                 "known_words": ["GAME START", "CONFIGURATION", "FILE OPTION", "GALLERY"],
                 "confirmed_uv": [[0, 43, 88, 55]]},
    "D0365088": {"role": "Fighter/arm selection headings and specification text", "rects": [[0, 0, 256, 240]],
                 "known_words": ["FIGHTER SELECTION", "ARM SELECTION"],
                 "confirmed_uv": [[0, 210, 135, 230], [136, 216, 211, 224]]},
    "1AD90FC9": {"role": "Craft/weapon specification labels and text", "rects": [[0, 0, 256, 240]],
                 "known_words": [], "confirmed_uv": [[218, 64, 223, 74], [89, 151, 112, 159], [120, 39, 125, 47]]},
    "8E1A509D": {"role": "Menu and result typography, small copyright/symbol layers", "rects": [[0, 0, 256, 256]],
                 "known_words": ["Total", "Evaluation", "Score", "Shot Down", "Bonus"],
                 "confirmed_uv": [[64, 236, 79, 251], [80, 236, 198, 247]]},
    "E6B65424": {"role": "Additional menu typography including DEMO PLAY", "rects": [[0, 0, 256, 160]],
                 "known_words": ["DEMO PLAY"], "confirmed_uv": []},
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def glyph_mask(native, rects):
    pixels = np.asarray(native)
    rgb = pixels[:, :, :3].astype(np.float32)
    hi = rgb.max(axis=2)
    lo = rgb.min(axis=2)
    # Keep the orange/blue highlight palettes too. Dark black-background texels
    # are not glyphs, even when their original STP alpha class is nonzero.
    eligible = (pixels[:, :, 3] != 0) & (hi >= 64)
    allowed = np.zeros(eligible.shape, np.uint8)
    for x0, y0, x1, y1 in rects:
        allowed[y0:y1, x0:x1] = 1
    eligible &= allowed != 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(eligible.astype(np.uint8), 8)
    selected = np.zeros(eligible.shape, np.uint8)
    accepted = []
    for identity in range(1, count):
        x, y, width, height, area = map(int, stats[identity])
        # Exclude unused solid atlas padding and large non-type illustrations.
        if 2 <= area <= 8000 and height <= 40 and width <= 256:
            selected[labels == identity] = 1
            accepted.append([x, y, width, height, area])
    return selected, allowed, accepted


def author(native, mask, allowed):
    size = (native.width*SCALE, native.height*SCALE)
    original = np.asarray(native.resize(size, Image.Resampling.NEAREST)).copy()
    binary = mask.astype(np.uint8)
    positive = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    negative = cv2.distanceTransform(1-binary, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    field = cv2.resize(positive-negative, size, interpolation=cv2.INTER_CUBIC)
    allowed_hi = cv2.resize(allowed, size, interpolation=cv2.INTER_NEAREST) != 0
    # Remove the original low-luma antialias/shadow pixels around the contour
    # as well. Leaving those magnified squares behind would undercut the new
    # smooth contour, even though the core glyph itself was reconstructed.
    native_pixels = np.asarray(native)
    near_core = cv2.distanceTransform(1-binary, cv2.DIST_L2, 5) <= 1.6
    original_ink = (native_pixels[:, :, :3].max(axis=2) >= 8) & near_core & (allowed != 0)
    old_mask = cv2.resize(original_ink.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) != 0
    # Newly authored edge coverage stays less than one native texel from the
    # original contour. Distinct sprites retain their original atlas layout.
    coverage = (field >= -.26) & allowed_hi
    shift = max(1, round(SCALE*.13))
    shadow = np.zeros_like(coverage)
    shadow[shift:, shift:] = coverage[:-shift, :-shift]
    shadow &= allowed_hi
    affected = old_mask | coverage | shadow
    result = original.copy()
    rgba = np.asarray(native)
    # Reconstruct removed edge background from actual nearby non-glyph texels.
    # Some palettes use STP black, others transparent black; never assume them
    # equivalent. New contour texels inherit the nearest source glyph class.
    _, bg_labels = cv2.distanceTransformWithLabels(original_ink.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    bg_values = rgba[~original_ink]
    background_native = bg_values[bg_labels-1]
    background_hi = cv2.resize(background_native, size, interpolation=cv2.INTER_NEAREST)
    _, fg_labels = cv2.distanceTransformWithLabels(1-binary, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    fg_values = rgba[binary != 0]
    foreground_native = fg_values[fg_labels-1]
    foreground_hi = cv2.resize(foreground_native, size, interpolation=cv2.INTER_NEAREST)
    result[affected] = background_hi[affected]
    edge_alpha = foreground_hi[:, :, 3]
    result[shadow, :3] = (3, 9, 13)
    result[shadow, 3] = edge_alpha[shadow]
    # The nested dark edge, cool rim and directional face are real authored
    # high-resolution layers, rather than a nearest-neighbour copy.
    result[coverage, :3] = (7, 22, 29)
    result[coverage, 3] = edge_alpha[coverage]
    rim = coverage & (field >= .08)
    result[rim, :3] = (42, 129, 142)
    result[rim, 3] = edge_alpha[rim]
    bevel = coverage & (field >= .38)
    gy, gx = np.gradient(field)
    light = np.clip((gx-gy)*.32+.52, 0, 1)
    bevel_rgb = np.stack([91+light*150, 143+light*105, 151+light*100], axis=2).astype(np.uint8)
    result[bevel, :3] = bevel_rgb[bevel]
    result[bevel, 3] = edge_alpha[bevel]
    face = coverage & (field >= 1.05)
    # Smooth source palette lighting inside each original shape, so the face
    # does not preserve magnified low-resolution shading squares. Normalized
    # convolution keeps black background out of the glyph color.
    weight = cv2.GaussianBlur(binary.astype(np.float32), (0, 0), .68)
    weighted_rgb = cv2.GaussianBlur(rgba[:, :, :3].astype(np.float32)*binary[:, :, None], (0, 0), .68)
    smooth_native = weighted_rgb / np.maximum(weight[:, :, None], .001)
    source_rgb = cv2.resize(smooth_native, size, interpolation=cv2.INTER_CUBIC)
    source_peak = np.maximum(source_rgb.max(axis=2, keepdims=True), 1)
    source_hue = source_rgb/source_peak
    yy = np.arange(size[1], dtype=np.float32)[:, None]
    face_gain = (.98 - .07*yy/max(size[1]-1, 1))[:, :, None]
    authored_face = np.clip((source_hue*.97+.03)*232*face_gain + 5, 0, 255).astype(np.uint8)
    result[face, :3] = authored_face[face]
    result[face, 3] = edge_alpha[face]
    # Original classes remain authoritative at exact native texel centers.
    # The user-authorized contour refinements happen between those centers.
    center = SCALE//2
    result[center::SCALE, center::SCALE, 3] = rgba[:, :, 3]
    return Image.fromarray(result, "RGBA"), affected, mask, field


def main():
    cv2.setNumThreads(2)
    queue_path = STAGING / "full-remaster/queue.json"
    queue = json.loads(queue_path.read_text())["assets"]
    assets = [x for x in queue if x.get("source_verified") and x["key"].split("-")[0] in FAMILIES]
    replacements = OUT / "einhander-texture-replacements"
    replacements.mkdir(parents=True, exist_ok=True)
    (OUT / "Hashes.ini").write_text("", encoding="utf-8")
    previews = OUT / "previews"
    previews.mkdir(exist_ok=True)
    records = []
    for item in assets:
        key = item["key"]
        source_path = Path(item["source"])
        metadata, raw, palette = verify_stock(source_path.parent, key)
        native = Image.open(source_path).convert("RGBA")
        family = FAMILIES[key.split("-")[0]]
        mask, allowed, components = glyph_mask(native, family["rects"])
        if not components:
            raise ValueError("No source glyphs identified: " + key)
        authored, affected, _, _ = author(native, mask, allowed)
        output = replacements / (key + ".png")
        authored.save(output)
        check = np.asarray(Image.open(output).convert("RGBA"))
        original = np.asarray(native.resize(authored.size, Image.Resampling.NEAREST))
        center = SCALE//2
        assert set(np.unique(check[:, :, 3])) <= {0, 127, 255}
        assert np.array_equal(check[center::SCALE, center::SCALE, 3], np.asarray(native)[:, :, 3])
        assert np.array_equal(check[~affected], original[~affected])
        changed = np.any(check != original, axis=2)
        # A native-center mask only is not reported as contour improvement.
        assert int(changed.sum()) > 1000
        if key.startswith("323B5FB0"):
            rect = (0, 40, 114, 106)
            old = native.crop(rect).resize(((rect[2]-rect[0])*SCALE, (rect[3]-rect[1])*SCALE), Image.Resampling.NEAREST)
            new = authored.crop(tuple(v*SCALE for v in rect))
            preview = Image.new("RGBA", (old.width, old.height*2+72), (15, 23, 31, 255))
            draw = ImageDraw.Draw(preview)
            draw.text((12, 10), "ORIGINAL GEOMETRY / NEAREST REFERENCE", fill="white")
            preview.alpha_composite(old, (0, 36))
            draw.text((12, old.height+46), "SOURCE-DERIVED CONTOURS / AUTHORED RIM + BEVEL + FACE", fill="white")
            preview.alpha_composite(new, (0, old.height+72))
            preview.convert("RGB").save(previews / "main-menu-before-after.png")
        records.append({"key": key, "role": family["role"], "known_words": family["known_words"],
            "source": str(source_path), "source_sha256": sha(source_path), "source_size": list(native.size),
            "source_words_sha256": digest(raw), "source_palette_sha256": digest(palette),
            "source_crc_and_independent_decode_verified": True, "source_metadata": metadata,
            "output": str(output), "output_sha256": sha(output), "output_size": list(authored.size),
            "scale": SCALE, "glyph_components": len(components), "native_author_regions": family["rects"],
            "confirmed_page_uv_examples": family["confirmed_uv"],
            "changed_output_texels": int(changed.sum()),
            "native_center_alpha_classes_exact": True, "untouched_regions_exact": True,
            "categorical_alpha_values": [int(x) for x in np.unique(check[:, :, 3])],
            "style": "source-derived subpixel contours; dark extrusion, cool nested rim, directional silver bevel and palette-aware face",
            "status": "isolated authored candidate; actual menu/state and animation QA pending"})
        print(json.dumps({"key": key, "glyph_components": len(components), "changed_texels": int(changed.sum())}), flush=True)
    report = {"format": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Concrete high-resolution menu/title-entry/selection/results lettering candidates; original words, atlas positions and game logic retained",
        "production_installed": False, "game_actions": 0, "queue": str(queue_path), "queue_sha256": sha(queue_path),
        "assets": records, "summary": {"candidate_textures": len(records), "families": len({x['key'].split('-')[0] for x in records}),
            "all_source_crc_decode_checks_passed": True, "all_native_center_alpha_checks_passed": True,
            "all_untouched_region_checks_passed": True},
        "limits": ["High-resolution edge coverage is intentionally authored between exact native texel centers; it is not an exact nearest alpha footprint.",
            "No OCR or substitute typeface is used; the original glyph silhouettes and wording are the authority.",
            "This pack does not contain the title hand/background or baked Einhänder wordmark.",
            "Pause/continue/loading canonical DD0B/BDAE work is owned by the separate HUD/font candidate pack.",
            "All menu states, palette/blink variants, tiny characters and semi-transparency require actual private-runtime visual QA."]}
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"pack": str(OUT), **report["summary"]}))


if __name__ == "__main__":
    main()
