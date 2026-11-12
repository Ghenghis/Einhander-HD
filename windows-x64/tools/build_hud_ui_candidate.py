"""Build isolated 16x UI/HUD palette-contour candidates from verified originals.

No fonts are substituted and no wording is invented. Original indexed texels
define nested signed-distance contours. Tonal layers share their silhouettes
instead of competing as independent islands. Palette lookup preserves PS1
alpha/STP classes; source sampling centers are measured, never forced.
The separate strict-mask variant additionally preserves the entire nearest
native class footprint, allowing controlled visual comparisons.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"remaster-audit"))
from build_three_asset_proof import verify_stock

REGIONS = {
    "DD0B6963": None,
    "BDAE4156": None,
    "913FE978": None,
    "44C16454": None,
    "B24C6DA2": [(0, 0, 64, 8)],
    "8BA3BB4D": [(0, 64, 64, 96)],
}
ROLES = {
    "DD0B6963": "native reusable menu word/glyph sheet; exact wording retained",
    "BDAE4156": "UI atlas: score/ammo digits, weapon labels, small glyphs and native menu wording",
    "913FE978": "HUD weapon-name/small glyph strip; CANNON source-local row1..5 observed",
    "44C16454": "small numeral strip; Cannon0014/0013 popup association remains a candidate",
    "B24C6DA2": "HUD arrow gauge at source-local0..63; remaining strip preserved",
    "8BA3BB4D": "mixed page; only HUD gauge/numeral rectangle0..63,64..95 restored",
}
GEOMETRY_VERSION = "coherent-glyph-rim-v4"
FAMILY_PROFILES = {"DD0B6963": "outline", "BDAE4156": "mixed-glyph-and-outline", "913FE978": "glyph"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode_indices(raw, metadata):
    if metadata["depth"] != 0:
        raise ValueError("This UI candidate supports verified native4bit indices only")
    words = np.frombuffer(raw, dtype="<u2").reshape(metadata["height"], metadata["width_words"])
    indices = np.empty((words.shape[0], words.shape[1]*4), dtype=np.uint8)
    for index, shift in enumerate((0, 4, 8, 12)):
        indices[:, index::4] = (words >> shift) & 15
    return indices


def palette_rgba(clut):
    values = np.frombuffer(clut, dtype="<u2")
    if len(values) != 16:
        raise ValueError("Expected a16color native UI CLUT")
    return np.stack(((values & 31) << 3, ((values >> 5) & 31) << 3, ((values >> 10) & 31) << 3,
                     np.where(values == 0, 0, np.where(values & 0x8000, 255, 127))), axis=1).astype(np.uint8)


def contour_indices(indices, scale=16, regions=None, profile="nested"):
    if not isinstance(scale, int) or scale < 2 or scale % 2:
        raise ValueError("Use an even integer scale of at least2")
    if profile not in ("nested", "glyph", "outline"):
        raise ValueError("Unknown source contour profile")
    source = np.asarray(indices)
    if source.ndim != 2 or source.size == 0 or not np.issubdtype(source.dtype, np.integer) or source.min() < 0 or source.max() > 15:
        raise ValueError("Expected a native4bit index sheet")
    source = source.astype(np.uint8, copy=False)
    height, width = source.shape
    result = np.repeat(np.repeat(source, scale, axis=0), scale, axis=1)
    selected = np.zeros(result.shape, dtype=bool)
    regions = [(0, 0, width, height)] if regions is None else regions
    for x0, y0, x1, y1 in regions:
        if not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height:
            raise ValueError("Restoration region outside native atlas")
        crop = source[y0:y1, x0:x1]
        target_size = ((x1-x0)*scale, (y1-y0)*scale)
        if profile in ("glyph", "outline"):
            # These verified lettering atlases use a descending tonal ramp:
            # bright face0..4, dark antialias fringe5..14, clear15. The fringe
            # is evidence of coverage, not a collection of little surfaces.
            # Recover one face and author a unified rim around it instead.
            face = crop <= (0 if profile == "outline" else 4)
            winner = np.full((target_size[1], target_size[0]), 15, dtype=np.uint8)
            if face.any():
                padded = np.pad(face, 1, constant_values=False)
                signed = (distance_transform_edt(padded)-distance_transform_edt(~padded)).astype(np.float32)
                field = cv2.resize(signed, ((crop.shape[1]+2)*scale, (crop.shape[0]+2)*scale), interpolation=cv2.INTER_CUBIC)
                field = cv2.GaussianBlur(field, (0, 0), scale*0.26, borderType=cv2.BORDER_REPLICATE)
                field = field[scale:-scale, scale:-scale]
                for threshold, index in ((-0.70, 14), (-0.50, 12), (-0.40, 10), (-0.30, 8),
                                         (-0.20, 6), (-0.10, 4), (0.0, 2), (0.10, 1), (0.20, 0)):
                    winner[field >= threshold] = index
            result[y0*scale:y1*scale, x0*scale:x1*scale] = winner
            selected[y0*scale:y1*scale, x0*scale:x1*scale] = True
            continue
        values = np.unique(crop)
        winner = np.full((target_size[1], target_size[0]), values[-1], dtype=np.uint8)
        # A glyph face and all its darker edge shades form nested regions.
        # Reconstructing each shade independently makes thin antialias bands
        # turn into beads, particularly at corners. Cumulative masks retain
        # the shared face/outline topology; intersecting successive masks
        # guarantees that no inner shade escapes its enclosing silhouette.
        enclosing = np.ones(winner.shape, dtype=bool)
        for index in values[-2::-1]:
            mask = crop <= index
            # Explicit padding gives atlas-edge glyphs the same boundary
            # convention as interior glyphs, without cropping their shape.
            padded = np.pad(mask, 1, constant_values=False)
            signed = (distance_transform_edt(padded)-distance_transform_edt(~padded)).astype(np.float32)
            field = cv2.resize(signed, ((crop.shape[1]+2)*scale, (crop.shape[0]+2)*scale), interpolation=cv2.INTER_CUBIC)
            field = cv2.GaussianBlur(field, (0, 0), scale*0.22, borderType=cv2.BORDER_REPLICATE)
            inside = field[scale:-scale, scale:-scale] >= 0
            inside &= enclosing
            winner[inside] = index
            enclosing = inside
        result[y0*scale:y1*scale, x0*scale:x1*scale] = winner
        selected[y0*scale:y1*scale, x0*scale:x1*scale] = True
    return result, selected


def restore_geometry(indices, family, scale=16):
    """Apply source-specific profiles without flattening mixed UI atlases."""
    profile = FAMILY_PROFILES.get(family, "nested")
    if profile != "mixed-glyph-and-outline":
        return contour_indices(indices, scale, REGIONS[family], profile=profile)
    rendered, selected = contour_indices(indices, scale, REGIONS[family], profile="nested")
    # Score/ammo digits have solid faces. Canonical menu words occupy the
    # lower half and use hollow metallic strokes. Symbols, small glyphs and
    # non-word UI artwork keep coherent original tones in their own UVs.
    for region, style in (((0, 0, 64, 32), "glyph"), ((0, 128, 256, 256), "outline")):
        layer, mask = contour_indices(indices, scale, [region], profile=style)
        rendered[mask] = layer[mask]
    return rendered, selected


def render_variants(indices, rendered, palette):
    scale = rendered.shape[0]//indices.shape[0]
    nearest_indices = np.repeat(np.repeat(indices, scale, axis=0), scale, axis=1)
    rgba = palette[rendered]
    nearest = palette[nearest_indices]
    strict = rgba.copy()
    incompatible = rgba[:, :, 3] != nearest[:, :, 3]
    strict[incompatible] = nearest[incompatible]
    return rgba, strict, nearest


def author_layers(rgba, selected, scale=16):
    """Author a palette-relative rim, inset bevel, glint and directional shadow.

    Coverage/classes come from reconstructed original contours. Lighting changes
    RGB only and never makes transparent or black-STP samples glow. Processing
    is confined to the selected source-UV rectangle on mixed pages.
    """
    result = rgba.copy()
    yy, xx = np.nonzero(selected)
    if len(xx) == 0:
        return result
    x0, x1, y0, y1 = xx.min(), xx.max()+1, yy.min(), yy.max()+1
    crop = result[y0:y1, x0:x1]
    permitted = selected[y0:y1, x0:x1]
    rgb = crop[:, :, :3].astype(np.float32)
    native_peak = np.max(rgb, axis=2)
    for alpha in (127, 255):
        mask = (crop[:, :, 3] == alpha) & permitted
        if not mask.any():
            continue
        distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
        distance = cv2.GaussianBlur(distance, (0, 0), scale*0.14)
        gx = cv2.Sobel(distance, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(distance, cv2.CV_32F, 0, 1, ksize=3)
        length = np.maximum(np.hypot(gx, gy), 0.001)
        light = (gx*0.6+gy*0.8)/length
        bevel = np.clip(1-distance/(scale*0.32), 0, 1)
        rim = np.clip(1-distance/(scale*0.105), 0, 1)
        glint = np.exp(-((distance-scale*0.19)/(scale*0.07))**2)*np.maximum(light, 0)
        shadow = np.maximum(-light, 0)*bevel
        brightness = 1+light*bevel*0.32-shadow*0.20-rim*0.38
        # Palette-relative highlights keep neutral HUD type neutral and retain
        # each authored CLUT hue during gauge/pulse animations.
        peak = np.max(rgb, axis=2)
        lifted = rgb*brightness[:, :, None]+peak[:, :, None]*glint[:, :, None]*0.22
        black_stp = (alpha == 255) & (np.max(rgb, axis=2) == 0)
        apply = mask & ~black_stp
        rgb[apply] = np.clip(lifted[apply], 0, 255)
        # Opaque glyph faces and their dark outline often share one alpha
        # class. A second inset boundary follows the original bright face,
        # rather than treating the complete black-backed tile as one surface.
        available = native_peak[mask & (native_peak > 24)]
        if available.size:
            face = mask & (native_peak >= float(np.max(available))*0.58)
            face_distance = cv2.distanceTransform(face.astype(np.uint8), cv2.DIST_L2, 5)
            face_distance = cv2.GaussianBlur(face_distance, (0, 0), scale*0.14)
            fx = cv2.Sobel(face_distance, cv2.CV_32F, 1, 0, ksize=3)
            fy = cv2.Sobel(face_distance, cv2.CV_32F, 0, 1, ksize=3)
            normal = np.maximum(np.hypot(fx, fy), 0.001)
            face_light = (fx*0.6+fy*0.8)/normal
            face_bevel = np.clip(1-face_distance/(scale*0.34), 0, 1)
            inset_rim = np.clip(1-face_distance/(scale*0.10), 0, 1)
            inset_glint = np.exp(-((face_distance-scale*0.20)/(scale*0.075))**2)*np.maximum(face_light, 0)
            face_rgb = rgb*(1+face_light[:, :, None]*face_bevel[:, :, None]*0.28-inset_rim[:, :, None]*0.16)
            face_rgb += native_peak[:, :, None]*inset_glint[:, :, None]*0.22
            rgb[face] = np.clip(face_rgb[face], 0, 255)
    crop[:, :, :3] = np.rint(rgb).astype(np.uint8)
    return result


def preview(path, key, native_reference, contour, strict):
    boxes = {"DD0B6963": (0, 0, 144, 20), "BDAE4156": (0, 0, 64, 32),
             "913FE978": (96, 0, 176, 8), "44C16454": (0, 0, 80, 8),
             "B24C6DA2": (0, 0, 64, 8), "8BA3BB4D": (0, 64, 64, 96)}
    box = tuple(value*16 for value in boxes[key.split("-")[0]])
    width, height = box[2]-box[0], box[3]-box[1]
    canvas = Image.new("RGB", (width, (height+38)*3), (12, 17, 24))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 23)
    for index, (label, data) in enumerate((("Native source x16 reference", native_reference),
                                         ("Authored contours, rim, bevel, highlight and shadow", contour),
                                         ("Same authored layers, strict original class footprint", strict))):
        y = index*(height+38)
        draw.text((10, y+4), label+" | "+key, font=font, fill=(220, 231, 242))
        canvas.paste(Image.fromarray(data[:, :, :3]).crop(box), (0, y+38))
    canvas.save(path)


def draw_evidence(families):
    result = {family: [] for family in families}
    for directory in sorted((ROOT/"windows-x64/tools/research-runs").iterdir()):
        if not (directory/"manifest.json").is_file() or not (directory/"native/capture.jsonl").is_file():
            continue
        manifest = json.loads((directory/"manifest.json").read_bytes())
        if manifest.get("status") != "finalized":
            continue
        for line_number, line in enumerate((directory/"native/capture.jsonl").read_bytes().splitlines(), 1):
            row = json.loads(line)
            family = row.get("key", "").split("-")[0]
            if family not in result:
                continue
            if len(result[family]) >= 64:
                continue
            result[family].append(dict(run=directory.name, line=line_number, event=row["event"], key=row["key"],
                                       frame=row["frame"], uv_bounds=row["uv_bounds"], source_word_xy=row["source_word_xy"],
                                       source_kind=row["source_kind"], xy=row["xy"], depth=row["depth"],
                                       native_words=row["native_words"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=Path("C:/github/REMASTER_STAGING/full-remaster/queue.json"))
    parser.add_argument("--output", type=Path, default=ROOT/"remaster-audit/hud-restoration/candidate-20261112")
    parser.add_argument("--geometry-cache", type=Path, help="Optional previous candidate masters; exact native indices are verified before reuse")
    args = parser.parse_args(argv)
    cv2.setNumThreads(2)
    if args.output.exists():
        raise ValueError("Candidate output already exists; choose a new isolated output")
    source_rows = [row for row in json.loads(args.queue.read_bytes())["assets"]
                   if row["source_verified"] and row["key"].split("-")[0] in REGIONS]
    evidence = draw_evidence(REGIONS)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ("pack", "strict-mask-pack"):
        (args.output/name/"einhander-texture-replacements").mkdir(parents=True)
        (args.output/name/"Hashes.ini").write_text("", encoding="utf-8")
    (args.output/"masters").mkdir()
    (args.output/"previews").mkdir()
    (args.output/"build-source.py").write_bytes(Path(__file__).read_bytes())
    geometries, rows = {}, []
    for item in source_rows:
        key, source_path = item["key"], Path(item["source"])
        metadata, raw, clut = verify_stock(source_path.parent, key)
        if sha(raw) != item["raw_sha256"] or sha(clut) != item["clut_sha256"]:
            raise ValueError("Source queue/raw hash mismatch: "+key)
        indices, palette = decode_indices(raw, metadata), palette_rgba(clut)
        source_rgba = palette[indices]
        if sha(source_rgba.tobytes()) != item["source_pixel_sha256"]:
            raise ValueError("Independent UI index/CLUT decode mismatch: "+key)
        family = key.split("-")[0]
        profile = FAMILY_PROFILES.get(family, "nested")
        geometry_key = (sha(raw), profile)
        regions = REGIONS[family]
        if geometry_key not in geometries:
            cached = args.geometry_cache/(family+".npz") if args.geometry_cache else None
            if cached and cached.is_file():
                with np.load(cached, allow_pickle=False) as values:
                    expected_regions = np.array(regions or [(0, 0, indices.shape[1], indices.shape[0])])
                    if "geometry_version" not in values or str(values["geometry_version"]) != GEOMETRY_VERSION or str(values["profile"]) != profile:
                        raise ValueError("Cached geometry uses a different reconstruction algorithm/profile")
                    if not np.array_equal(values["native_indices"], indices) or int(values["native_scale"]) != 16 or not np.array_equal(values["selected_native_regions"], expected_regions):
                        raise ValueError("Cached geometry does not match verified native source/regions")
                    rendered = values["contour_indices"].copy()
                selected = np.zeros(rendered.shape, dtype=bool)
                for x0, y0, x1, y1 in expected_regions:
                    selected[y0*16:y1*16, x0*16:x1*16] = True
            else:
                rendered, selected = restore_geometry(indices, family, 16)
            geometries[geometry_key] = (rendered, selected)
            np.savez_compressed(args.output/"masters"/(family+".npz"), native_indices=indices, contour_indices=rendered,
                                native_scale=np.array(16), selected_native_regions=np.array(regions or [(0, 0, indices.shape[1], indices.shape[0])]),
                                geometry_version=np.array(GEOMETRY_VERSION), profile=np.array(profile))
        rendered, selected = geometries[geometry_key]
        rgba, strict, nearest = render_variants(indices, rendered, palette)
        center = rgba[8::16, 8::16]
        changed_centers = int(np.count_nonzero(rendered[8::16, 8::16] != indices))
        changed_alpha_centers = int(np.count_nonzero(center[:, :, 3] != source_rgba[:, :, 3]))
        if not np.array_equal(strict[:, :, 3], nearest[:, :, 3]):
            raise ValueError("Strict native class footprint changed: "+key)
        if not np.array_equal(rgba[~selected], nearest[~selected]):
            raise ValueError("Unselected mixed-page region changed: "+key)
        if not set(np.unique(rgba[:, :, 3])).issubset({0, 127, 255}):
            raise ValueError("Invented alpha/STP class")
        authored = author_layers(rgba, selected)
        strict_authored = author_layers(strict, selected)
        if not np.array_equal(authored[:, :, 3], rgba[:, :, 3]) or not np.array_equal(strict_authored[:, :, 3], nearest[:, :, 3]):
            raise ValueError("Authored lighting changed categorical coverage")
        if not np.array_equal(authored[~selected], nearest[~selected]):
            raise ValueError("Authored layers escaped selected native UV bounds")
        outputs = {}
        for name, data in (("pack", authored), ("strict-mask-pack", strict_authored)):
            path = args.output/name/"einhander-texture-replacements"/(key+".png")
            Image.fromarray(data).save(path, compress_level=6)
            with Image.open(path) as reread:
                if reread.mode != "RGBA" or reread.tobytes() != data.tobytes():
                    raise ValueError("Written UI PNG roundtrip failed")
            outputs[name] = dict(path=str(path.resolve()), sha256=sha(path.read_bytes()), size=[data.shape[1], data.shape[0]])
        row = dict(key=key, role=ROLES[family], source=str(source_path), source_sha256=sha(source_path.read_bytes()),
                   raw_sha256=sha(raw), clut_sha256=sha(clut), source_size=[indices.shape[1], indices.shape[0]],
                   source_crc_verified=True, source_decode_verified=True, source_metadata=metadata,
                   method=("Source-specific solid glyph/outlined stroke silhouettes with compact palette-relative rim and directional bevel" if profile != "nested" else "Coherent nested palette-index contours with shared silhouettes"),
                   geometry_version=GEOMETRY_VERSION, contour_profile=profile,
                   restored_native_regions=regions or "whole verified UI atlas", outputs=outputs,
                   native_index_geometry_centers_exact=changed_centers == 0, native_alpha_centers_exact=changed_alpha_centers == 0,
                   changed_native_index_centers=changed_centers, changed_native_alpha_centers=changed_alpha_centers,
                   source_sampling_centers_forced=False,
                   source_palette_hues_preserved=True, original_palette_only=False,
                   authored_layers=["shared source face silhouette", "unified dark rim", "inset bevel", "top-left highlight", "lower-right shadow"],
                   alpha_stp_values=[int(value) for value in np.unique(rgba[:, :, 3])],
                   strict_mask_alpha_exact=True, mixed_page_outside_regions_exact=True,
                   contour_changed_rgba_pixels=int(np.count_nonzero(np.any(rgba != nearest, axis=2))),
                   contour_changed_class_pixels=int(np.count_nonzero(rgba[:, :, 3] != nearest[:, :, 3])),
                   authored_changed_rgb_pixels=int(np.count_nonzero(np.any(authored[:, :, :3] != rgba[:, :, :3], axis=2))),
                   draw_evidence=evidence[family], in_game_acceptance="pending isolated candidate draw and visual/motion comparison")
        rows.append(row)
        if key in ("DD0B6963-4C1DD349", "BDAE4156-E21112A6", "913FE978-E21112A6", "44C16454-72FBA1C5", "B24C6DA2-D6B2BFF7", "8BA3BB4D-D6B2BFF7"):
            preview(args.output/"previews"/(key+".png"), key, nearest, authored, strict_authored)
        print(json.dumps(dict(key=key, output_size=outputs["pack"]["size"], changed_pixels=row["contour_changed_rgba_pixels"])), flush=True)
    manifest = dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(), tool_sha256=sha(Path(__file__).read_bytes()),
                    queue_sha256=sha(args.queue.read_bytes()), scope="Verified UI/HUD source atlas candidates; no gameplay/card/process/runtime changes",
                    production_installed=False, source_keys=len(rows), geometry_version=GEOMETRY_VERSION, files=rows,
                    acceptance_pending=["Actual isolated candidate replacement GL submissions", "4K HUD text/number readability and layout review",
                                        "Pause/continue/countdown/selection wording and cursor states", "Palette cycling/STP blend and motion review",
                                        "Mixed-page regions and GPU texture-cache/frame pacing review"],
                    limitations=["The main pack intentionally replaces sampled tonal fringes with unified source-face contours; source center indices and alpha coverage can change, and changed counts are reported per asset. No center pixels are forced.",
                                 "Palette lookup retains categorical PS1 alpha/STP values and palette-relative hue. strict-mask-pack preserves the full original nearest alpha/STP footprint as a comparison only; it can retain original fringes.",
                                 "Ammo-popup interpretation remains a candidate until exact visible UV correlation is completed.",
                                 "Unmapped HUD plates, icon states, score/result variants and never-observed screens remain open."])
    (args.output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(manifest=str((args.output/"manifest.json").resolve()), source_keys=len(rows), production_installed=False)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
