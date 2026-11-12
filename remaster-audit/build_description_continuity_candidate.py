"""Reconstruct proven glyph regions once, then bind full-page/row outputs.

The renderer can fall back to a full page when a glyph crosses an eight-row
upload. Both paths must share the same authored field. No installed files or
running game are changed; all unrelated source regions remain byte-identical.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from build_coherent_font_candidate import glyph_field, module
from build_three_asset_proof import verify_stock

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
OUT = AUDIT / "menu-restoration/description-continuity-candidate-v3"
PARENT = AUDIT / "menu-restoration/font-strip-candidate-v6/manifest.json"
MAP = AUDIT / "hud-restoration/description-glyph-coverage.json"
V6 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6/candidate.json"
BASE_KEY = "BDAE4156-B88C038E"
REGIONS = [(0, 32, 64, 104), (192, 32, 256, 104),
           (0, 112, 64, 120), (192, 112, 256, 120)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def main():
    if OUT.exists():
        raise ValueError("Authored candidates are immutable")
    prior = json.loads(PARENT.read_bytes())
    candidate = json.loads(V6.read_bytes())
    files = {r["name"][:-4]: r for r in candidate["files"]}
    glyph_map = json.loads(MAP.read_bytes())
    if glyph_map.get("summary", {}).get("row_aliases_exact_raw_clut_verified") != 10:
        raise ValueError("A captured ten-row ownership map is required")
    proof_row = next(r for r in prior["files"] if r["key"] == "2C781811-B88C038E")
    source = Path(proof_row["raw_parent"]["source"])
    metadata, raw, clut = verify_stock(source.parent, BASE_KEY)
    if hashlib.sha256(raw).hexdigest() != proof_row["raw_parent"]["source_words_sha256"]:
        raise ValueError("Full-page source changed")
    hud = module(PARENT.parent / "palette-contour-library.py", "continuity_palette")
    indices = hud.decode_indices(raw, metadata)
    palette = hud.palette_rgba(clut)
    # The original bevel's dark indices10..14 also carry real stroke coverage.
    # Using only its bright midpoint disconnects strokes (notably L/C/g/p).
    # Preserve all nonclear source coverage and its true counters, then apply
    # one solid face/rim field equally to whole-page and row-upload paths.
    coverage_indices = np.where(indices < 15, 0, 15).astype(np.uint8)
    rebuilt, selected = glyph_field(coverage_indices, palette, REGIONS)
    base_path = Path(files[BASE_KEY]["composed_path"])
    if sha(base_path) != files[BASE_KEY]["sha256"]:
        raise ValueError("Existing full-page candidate changed")
    base = np.asarray(Image.open(base_path).convert("RGBA"))
    if base.shape != rebuilt.shape or base.shape != (4096, 4096, 4):
        raise ValueError("Unexpected source-to-authoring scale")
    authored = base.copy()
    authored[selected] = rebuilt[selected]
    aliases = []
    for row in prior["files"]:
        if row.get("base_key") == BASE_KEY and row.get("base_output_region") is not None:
            x0, y0, x1, y1 = row["base_output_region"]
        else:
            matches = [r for r in row.get("all_raw_matches", []) if r.get("key") == BASE_KEY]
            if len(matches) != 1:
                continue
            x0, y0, x1 = 0, matches[0]["native_row"], 256
            y1 = y0 + 8
        if (x0, x1, y1-y0) != (0, 256, 8) or y0 not in (32, 40, 48, 56, 64, 72, 80, 88, 96, 112):
            continue
        native_source = Path(row["source"])
        sm, words, colors = verify_stock(native_source.parent, row["key"])
        if words != raw[y0*128:y1*128] or colors != clut:
            raise ValueError("Row alias lacks exact raw/CLUT equality: " + row["key"])
        aliases.append((row, y0, y1, native_source))
    if len(aliases) != 10 or "913FE978-B88C038E" not in {r[0]["key"] for r in aliases}:
        raise ValueError("All ten observed row paths, including row88, must be covered")
    (OUT / "pack/einhander-texture-replacements").mkdir(parents=True)
    (OUT / "source-proof").mkdir()
    map_snapshot = OUT / "source-proof/description-glyph-coverage.json"
    shutil.copyfile(MAP, map_snapshot)
    (OUT / "pack/Hashes.ini").write_text("")
    rows = []

    def write(key, pixels, baseline, mask, source_path, region, parent_row=None):
        if not np.array_equal(pixels[~mask], baseline[~mask]):
            raise ValueError("Protected content changed: " + key)
        if not set(map(int, np.unique(pixels[:, :, 3]))) <= {0, 127, 255}:
            raise ValueError("Alpha classes changed: " + key)
        target = OUT / "pack/einhander-texture-replacements" / (key+".png")
        Image.fromarray(pixels).save(target)
        with Image.open(target) as check:
            if check.convert("RGBA").tobytes() != pixels.tobytes():
                raise ValueError("PNG round trip changed")
        source_refs = []
        for suffix in (".png", ".words.bin", ".clut.bin", ".valid.bin", ".source.json"):
            original = source_path.with_suffix(suffix)
            copied = OUT / "source-proof" / original.name
            shutil.copyfile(original, copied)
            source_refs.append(ref(copied))
        old = files[key]
        rows.append(dict(key=key, path=str(target), sha256=sha(target),
                         size=[pixels.shape[1], pixels.shape[0]],
                         rgba_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
                         baseline=dict(path=old["composed_path"], sha256=old["sha256"]),
                         source_proof=source_refs, selected_native_regions=region,
                         changed_pixels=int(np.any(pixels != baseline, axis=2).sum()),
                         protected_outside_exact=True, source_crc_clut_verified=True,
                         alpha_classes=sorted(map(int, np.unique(pixels[:, :, 3]))),
                         exact_fullpage_selected_rgba_crop=parent_row is not None,
                         parent_native_row=parent_row, live_verified=False))

    write(BASE_KEY, authored, base, selected, source, [list(r) for r in REGIONS])
    for row, y0, y1, native_source in aliases:
        key = row["key"]
        path = Path(files[key]["composed_path"])
        if sha(path) != files[key]["sha256"]:
            raise ValueError("Existing alias changed: " + key)
        baseline = np.asarray(Image.open(path).convert("RGBA"))
        mask = selected[y0*16:y1*16]
        crop = authored[y0*16:y1*16]
        pixels = baseline.copy()
        pixels[mask] = crop[mask]
        if not np.array_equal(pixels[mask], crop[mask]):
            raise ValueError("Full-page/row continuity mismatch")
        write(key, pixels, baseline, mask, native_source,
              [[0, 0, 64, 8], [192, 0, 256, 8]], y0)
    manifest = dict(schema_version=1, contract="verified-description-continuity-v1",
                    created_at_utc=datetime.now(timezone.utc).isoformat(), asset_count=len(rows), files=rows,
                    references=[ref(PARENT), ref(map_snapshot), ref(V6)],
                    method="Single continuous source-nonclear coverage field in captured description columns; original indices0..14 carry coverage and15 retains counters/background. Exact selected RGBA crops cover all ten raw-equal row aliases including row88 and full-page descenders.",
                    ink_policy="all_original_nonclear_indices_0_through_14",
                    protected=["central native x64..191 logos", "unmapped native rows104..111", "all other source pixels"],
                    scope="Observed glyph-path repair; no broad atlas repaint or final visual acceptance",
                    remaining=["Fighter/ARM replay", "glyph counters, descenders and seams at actual display scale", "all other UI and game states"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "build-source.py")
    print(json.dumps(dict(output=str(OUT), asset_count=len(rows), checks="PASS", live_verified=False)))


if __name__ == "__main__":
    main()
