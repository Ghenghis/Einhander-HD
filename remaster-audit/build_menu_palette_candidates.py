"""Build isolated mapped menu typography through verified palette contours.

Uses the HUD builder's reviewed index-contour and lighting implementation while
keeping separate menu keys and bounded menu text regions. No game, runtime,
installed pack, substitute fonts or network operations are performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "remaster-audit/menu-restoration/palette-field-candidate-v6"
QUEUE = Path("C:/github/REMASTER_STAGING/full-remaster/queue.json")
HUD_SOURCE = ROOT / "windows-x64/tools/build_hud_ui_candidate.py"
EXPECTED_KEYS = {
    "1AD90FC9-02491337", "1AD90FC9-4315989E", "1AD90FC9-79902A90",
    "323B5FB0-1C7962B3", "8E1A509D-4FE32821", "8E1A509D-8808F70A",
    "8E1A509D-C7A1F2F0", "D0365088-79902A90", "D0365088-B5A45715",
    "E6B65424-4C1DD349", "E6B65424-611C5290", "E6B65424-97713DC6",
}
REGIONS = {
    "323B5FB0": [(0, 0, 112, 104), (128, 0, 256, 86)],
    "D0365088": [(0, 0, 252, 168), (0, 168, 136, 232), (136, 168, 248, 224)],
    "1AD90FC9": [(0, 0, 128, 160), (128, 0, 220, 88), (0, 160, 80, 224), (0, 224, 56, 256)],
    "8E1A509D": [(0, 0, 256, 236), (88, 236, 144, 247), (80, 247, 144, 256)],
    "E6B65424": [(0, 0, 256, 112), (0, 112, 144, 124), (96, 124, 224, 140)],
}
BOXES = {
    "323B5FB0": (0, 42, 112, 104),
    "D0365088": (0, 168, 248, 232),
    "1AD90FC9": (0, 0, 220, 48),
    "8E1A509D": (0, 158, 256, 236),
    "E6B65424": (96, 124, 224, 140),
}
ROLES = {
    "323B5FB0": "Main menu entries, craft names and name-entry alphabet",
    "D0365088": "Fighter/arm selection headings and multilingual glyphs",
    "1AD90FC9": "Craft/weapon specification labels and selection numerals",
    "8E1A509D": "Results/evaluation typography and multilingual glyphs",
    "E6B65424": "Instruction typography and exact DEMO PLAY wordmark",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_hud_builder(path):
    spec = importlib.util.spec_from_file_location("menu_hud_contour_library", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def menu_contour_indices(indices, scale, regions):
    """Reconstruct a continuous tonal field, including original outline details.

    A single bright-core mask loses thin menu stems and fills outlined letters.
    All five verified menu families use descending tonal ramps. Interpolating
    that shared scalar field keeps their internal etched lines and thin strokes
    coherent, without treating each antialias shade as an independent island.
    """
    source = np.asarray(indices, dtype=np.uint8)
    result = np.repeat(np.repeat(source, scale, axis=0), scale, axis=1)
    selected = np.zeros(result.shape, bool)
    for x0, y0, x1, y1 in regions:
        crop = source[y0:y1, x0:x1]
        field = cv2.resize(crop.astype(np.float32), (crop.shape[1]*scale, crop.shape[0]*scale), interpolation=cv2.INTER_CUBIC)
        winner = np.rint(np.clip(field, 0, 15)).astype(np.uint8)
        result[y0*scale:y1*scale, x0*scale:x1*scale] = winner
        selected[y0*scale:y1*scale, x0*scale:x1*scale] = True
    return result, selected


def menu_render(indices, rendered, palette, regions, scale=16, lighting=.14, rim_strength=.16, native_alpha=False):
    nearest_indices = np.repeat(np.repeat(indices, scale, axis=0), scale, axis=1)
    nearest = palette[nearest_indices]
    result = nearest.copy()
    for x0, y0, x1, y1 in regions:
        crop = indices[y0:y1, x0:x1]
        field = np.clip(cv2.resize(crop.astype(np.float32), ((x1-x0)*scale, (y1-y0)*scale), interpolation=cv2.INTER_CUBIC), 0, 15)
        lo = np.floor(field).astype(np.uint8)
        hi = np.minimum(lo+1, 15)
        part = (field-lo)[:, :, None]
        rgb = palette[lo, :3]*(1-part)+palette[hi, :3]*part
        # The original tonal transition is a bevel surface. A directional
        # light follows its continuous normal, rather than individual shades.
        gx = cv2.Sobel(field, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(field, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.hypot(gx, gy)
        normal = (-.6*gx-.8*gy)/np.maximum(magnitude, .01)
        bevel = np.sin(np.pi*(15-field)/15)*np.clip(magnitude*scale/20, 0, 1)
        rgb *= (1+lighting*normal*bevel)[:, :, None]
        # A narrow dark outer rim adds depth while retaining each CLUT hue.
        rim = np.clip((field-9)/5, 0, 1)*np.clip((15-field)/1.5, 0, 1)
        rgb *= (1-rim_strength*rim)[:, :, None]
        result[y0*scale:y1*scale, x0*scale:x1*scale, :3] = np.rint(np.clip(rgb, 0, 255)).astype(np.uint8)
        result[y0*scale:y1*scale, x0*scale:x1*scale, 3] = palette[rendered[y0*scale:y1*scale, x0*scale:x1*scale], 3]
    if native_alpha:
        result[:, :, 3] = nearest[:, :, 3]
    return result, nearest


def revise_d036(previous, output):
    """Copy ten accepted keys unchanged; rerender only two selection sheets."""
    previous = previous.resolve()
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT/"remaster-audit/menu-restoration").resolve()):
        raise ValueError("Use a new isolated menu-restoration output")
    manifest = json.loads((previous/"manifest.json").read_bytes())
    if {a['key'] for a in manifest['assets']} != EXPECTED_KEYS:
        raise ValueError("Revision source must be the complete twelve-key candidate")
    library = load_hud_builder(previous/"palette-contour-library.py")
    for asset in manifest['assets']:
        for variant, old in asset['outputs'].items():
            if sha(Path(old['path'])) != old['sha256']:
                raise ValueError('Source candidate changed: '+asset['key'])
    output.mkdir()
    for folder in ('pack', 'strict-mask-pack', 'previews', 'masters'):
        shutil.copytree(previous/folder, output/folder)
    shutil.copy2(previous/'palette-contour-library.py', output/'palette-contour-library.py')
    shutil.copy2(__file__, output/'build-source.py')
    for asset in manifest['assets']:
        family = asset['key'].split('-')[0]
        for variant, old in asset['outputs'].items():
            old['path'] = str(output/variant/'einhander-texture-replacements'/(asset['key']+'.png'))
        if family != 'D0365088':
            asset['revision'] = 'Byte-identical accepted v6 output'
            continue
        metadata, raw, clut = library.verify_stock(Path(asset['source']).parent, asset['key'])
        indices, palette = library.decode_indices(raw, metadata), library.palette_rgba(clut)
        with np.load(previous/'masters'/('D0365088.npz')) as cache:
            if not np.array_equal(indices, cache['native_indices']):
                raise ValueError('D036 source geometry changed')
            rendered = cache['contour_indices']
        authored, nearest = menu_render(indices, rendered, palette, REGIONS[family], lighting=.025, rim_strength=.02, native_alpha=True)
        for variant, item in asset['outputs'].items():
            Image.fromarray(authored).save(item['path'])
            item['sha256'] = sha(Path(item['path']))
        asset['checks']['native_center_alpha_classes_exact'] = True
        asset['checks']['strict_comparison_alpha_footprint_exact'] = True
        asset['checks']['main_original_alpha_footprint_exact'] = True
        asset['revision'] = 'Continuous original tones; restrained2.5percent directional light/2percent rim, original categorical alpha footprint'
        asset['changed_authored_texels'] = int(np.any(authored != nearest, axis=2).sum())
        if asset['key'] == 'D0365088-79902A90':
            preview(output/'previews'/'D0365088-before-after.png', family, asset['key'], Image.fromarray(palette[indices]), Image.fromarray(authored))
        print(json.dumps({'revised': asset['key'], 'native_alpha_footprint_exact': True}), flush=True)
    manifest['created_at_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['revision_source'] = str(previous)
    manifest['revision_source_manifest_sha256'] = sha(previous/'manifest.json')
    manifest['revision'] = 'Only D036 two selection keys rerendered; ten other keys copied byte-for-byte'
    manifest['d036_method'] = 'Continuous original palette tones, restrained2.5percent directional lighting/2percent rim and exact original alpha footprint; no bright-core mask or shade inversion'
    manifest['semantic_map'] = str(ROOT/'remaster-audit/menu-restoration/menu-semantic-map.json')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'pack': str(output/'pack'), 'assets':12, 'changed_keys':2, 'unchanged_keys':10}))


def preview(output, family, key, native, authored):
    box = BOXES[family]
    scale = 6
    width, height = (box[2]-box[0])*scale, (box[3]-box[1])*scale
    old = native.crop(box).resize((width, height), Image.Resampling.NEAREST)
    new = authored.crop(tuple(v*16 for v in box)).resize((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (max(width, 600), height*2+70), (12, 18, 25, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), key+" | NATIVE GEOMETRY / NEAREST REFERENCE", fill="white")
    canvas.alpha_composite(old, (0, 30))
    draw.text((8, height+38), "RECONSTRUCTED PALETTE CONTOURS / AUTHORED EDGE, BEVEL, GLINT, SHADOW", fill="white")
    canvas.alpha_composite(new, (0, height+65))
    canvas.convert("RGB").save(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--library", type=Path, default=HUD_SOURCE)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--revise-from", type=Path, help="Complete existing candidate; rerender only the two D036 keys")
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    if OUT.exists():
        raise ValueError("Choose a new isolated output; existing candidates are immutable")
    if not OUT.is_relative_to((ROOT/"remaster-audit/menu-restoration").resolve()):
        raise ValueError("Use an isolated output inside menu-restoration")
    cv2.setNumThreads(2)
    if args.revise_from:
        revise_d036(args.revise_from, OUT)
        return
    assets = [x for x in json.loads(args.queue.read_bytes())["assets"]
              if x.get("source_verified") and x["key"].split("-")[0] in REGIONS]
    if {item['key'] for item in assets} != EXPECTED_KEYS or len(assets) != len(EXPECTED_KEYS):
        raise ValueError("Expected exactly the twelve verified menu/palette keys")
    assets.sort(key=lambda item: item['key'])
    for folder in ("pack/einhander-texture-replacements", "strict-mask-pack/einhander-texture-replacements", "previews", "masters"):
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    for folder in ("pack", "strict-mask-pack"):
        (OUT/folder/"Hashes.ini").write_text("", encoding="utf-8")
    shutil.copyfile(__file__, OUT/"build-source.py")
    shutil.copyfile(args.library, OUT/"palette-contour-library.py")
    library = load_hud_builder(OUT/"palette-contour-library.py")
    rows, previews = [], set()
    current_family, current_indices, rendered, selected = None, None, None, None
    for item in assets:
        key, source = item["key"], Path(item["source"])
        family = key.split("-")[0]
        metadata, raw, clut = library.verify_stock(source.parent, key)
        indices, palette = library.decode_indices(raw, metadata), library.palette_rgba(clut)
        decoded = palette[indices]
        if hashlib.sha256(decoded.tobytes()).hexdigest() != item["source_pixel_sha256"]:
            raise ValueError("Source queue pixel mismatch: "+key)
        if family != current_family:
            rendered, selected = menu_contour_indices(indices, 16, REGIONS[family])
            np.savez_compressed(OUT/"masters"/(family+".npz"), native_indices=indices, contour_indices=rendered,
                                selected_native_regions=np.array(REGIONS[family]), native_scale=np.array(16))
            current_family = family
            current_indices = indices.copy()
        elif not np.array_equal(indices, current_indices):
            raise ValueError("A palette variant changed its family geometry: "+key)
        changed_center_indices = int(np.count_nonzero(indices != rendered[8::16, 8::16]))
        rgba = palette[rendered]
        authored, nearest = menu_render(indices, rendered, palette, REGIONS[family])
        # Restore incompatible alpha-class samples directly from nearest stock.
        # This is a strict coverage comparison; RGB lighting remains the same
        # authored pass wherever its coverage class already agrees with stock.
        strict_authored = authored.copy()
        incompatible = rgba[:, :, 3] != nearest[:, :, 3]
        strict_authored[incompatible] = nearest[incompatible]
        if not np.array_equal(authored[:, :, 3], rgba[:, :, 3]):
            raise ValueError("Lighting altered categorical coverage: "+key)
        if not np.array_equal(strict_authored[:, :, 3], nearest[:, :, 3]):
            raise ValueError("Strict categorical footprint changed: "+key)
        if not np.array_equal(authored[~selected], nearest[~selected]):
            raise ValueError("Authored text escaped selected regions: "+key)
        if not set(np.unique(authored[:, :, 3])) <= {0, 127, 255}:
            raise ValueError("Invented PSX alpha class: "+key)
        outputs = {}
        for name, pixels in (("pack", authored), ("strict-mask-pack", strict_authored)):
            path = OUT/name/"einhander-texture-replacements"/(key+".png")
            Image.fromarray(pixels).save(path)
            outputs[name] = {"path": str(path), "sha256": sha(path)}
        if family not in previews:
            preview(OUT/"previews"/(family+"-before-after.png"), family, key, Image.fromarray(decoded), Image.fromarray(authored))
            previews.add(family)
        rows.append({"key": key, "role": ROLES[family], "source": str(source), "source_sha256": sha(source),
                     "source_words_sha256": hashlib.sha256(raw).hexdigest(), "source_clut_sha256": hashlib.sha256(clut).hexdigest(),
                     "source_metadata": metadata, "source_size": list(indices.shape[::-1]), "output_size": list(authored.shape[1::-1]),
                     "selected_native_regions": REGIONS[family], "outputs": outputs,
                     "checks": {"raw_crc_clut_independent_decode": True,
                                "native_center_palette_indices_exact": changed_center_indices == 0,
                                "changed_native_center_indices": changed_center_indices,
                                "native_center_alpha_classes_exact": bool(np.array_equal(authored[8::16, 8::16, 3], decoded[:, :, 3])),
                                "categorical_classes_only": True,
                                "unselected_regions_exact": True, "strict_comparison_alpha_footprint_exact": True},
                     "changed_contour_texels": int(np.any(rgba != nearest, axis=2).sum()),
                     "changed_authored_texels": int(np.any(authored != nearest, axis=2).sum()),
                     "in_game_acceptance": "pending private-runtime state/animation/UV/semi-transparency review"})
        print(json.dumps({"key": key, "authored": rows[-1]["changed_authored_texels"]}), flush=True)
        del rgba, nearest, authored, strict_authored
        gc.collect()
    manifest = {"format": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "production_installed": False, "game_actions": 0, "scale": 16,
                "method": "A continuous field from the original descending16-shade palette ramp reconstructs smooth lettering contours and retains thin stems and internal etched outlines. Directional bevel lighting and a narrow dark rim are authored along this shared field, without competing shade islands or a single glyph threshold. Every output alpha sample is a categorical source palette class. Original wording, atlas coordinates and semantic layout are retained.",
                "geometry_version": "menu-continuous-palette-field-v1",
                "asset_count": len(rows), "family_count": len(REGIONS), "assets": rows,
                "source_queue": str(args.queue), "source_queue_sha256": sha(args.queue),
                "implementation_library": str(args.library), "implementation_library_sha256": sha(OUT/"palette-contour-library.py"),
                "semantic_map": str(ROOT/"remaster-audit/menu-restoration/menu-semantic-map.json"),
                "limits": ["Native-center index and alpha differences are measured per asset; no isolated center texels are forced into the refined contours. The strict comparison restores stock RGBA wherever authored alpha classes disagree, retaining the entire native alpha footprint.",
                           "Before/after previews use standard image alpha compositing as a visual approximation; PSX alpha values encode categorical STP behavior and require real-game verification.",
                           "Only mapped text rectangles are authored; non-text controls/icons/illustrations and unused atlas fill remain nearest-source outside them.",
                           "Source-valid typography for a state does not establish that the state has been visually verified or that every animation variant is captured.",
                           "All candidates require actual private-runtime comparisons; the title hand/background and baked wordmark are separate work."]}
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"pack": str(OUT/"pack"), "assets": len(rows), "checks": "PASS"}))


if __name__ == "__main__":
    main()
