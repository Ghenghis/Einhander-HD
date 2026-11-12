"""Export one immutable native source guide; never admit a replacement pack.

The B30D top-row atlas tile has its own source indices. It is not a palette
alias of the central 52F33418 facade. Run --verify to check an existing export.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "remaster-audit/world-sign-mapping/facade-neighbor-source-v1"
STAGING = ROOT.parent / "REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements"
FULL_KEY = "73BF9877-B30D16F0"
KEY = "74EF95B7-B30D16F0"
CENTRAL = ROOT / "remaster-audit/world-sign-mapping/facade-pilot-source-v2"
FRESH = ROOT / "remaster-audit/dev-center-evidence/facade-ab-20261112/architecture/native-city-discovery-02/capture.jsonl"
PATTERNS = ROOT / "remaster-audit/dev-center-evidence/stage1-source-patterns.json"
SUFFIXES = (".words.bin", ".clut.bin", ".valid.bin", ".source.json", ".png")


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def ref(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def crc(data):
    return f"{zlib.crc32(data):08X}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def palette_rgba(words):
    return [tuple([((word >> shift) & 31) << 3 for shift in (0, 5, 10)] +
                  [0 if word == 0 else 255 if word & 0x8000 else 127]) for word in words]


def decode(raw, clut):
    indices = bytes(index for byte in raw for index in (byte & 15, byte >> 4))
    colors = palette_rgba(struct.unpack("<16H", clut))
    rgba = bytes(channel for index in indices for channel in colors[index])
    # Independent addressing path: native 16-bit words, four indices per word.
    native_words = struct.unpack("<1024H", raw)
    word_indices = bytes((native_words[y * 16 + x // 4] >> ((x % 4) * 4)) & 15
                         for y in range(64) for x in range(64))
    require(indices == word_indices, "Byte and native-word decoders disagree")
    return indices, Image.frombytes("RGBA", (64, 64), rgba)


def bright_blue_components(image):
    # A reproducible color measurement, deliberately not a window recognizer.
    pixels = list(image.getdata())
    mask = bytes(255 if b >= 128 and b >= g + 16 and b >= r + 16 else 0
                 for r, g, b, a in pixels)
    pending = {(x, y) for y in range(64) for x in range(64) if mask[y * 64 + x]}
    components = []
    while pending:
        connected = [pending.pop()]
        for x, y in connected:
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in pending:
                    pending.remove(point)
                    connected.append(point)
        xs, ys = zip(*connected)
        components.append({"rect_half_open": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
                           "native_pixels": len(connected)})
    components.sort(key=lambda row: (row["rect_half_open"][1], row["rect_half_open"][0]))
    return mask, components


def source_inputs():
    source = {suffix: STAGING / (FULL_KEY + suffix) for suffix in SUFFIXES}
    raw, clut, valid = [source[suffix].read_bytes() for suffix in SUFFIXES[:3]]
    metadata = read(source[".source.json"])
    require(len(raw) == 32768 and len(clut) == 32 and len(valid) == 16384,
            "Unexpected full-page archive lengths")
    require(crc(raw) + "-" + crc(clut) == FULL_KEY, "Full-page CRC binding failed")
    require(set(valid) == {1}, "Full-page source has unknown words")
    require(metadata["key"] == FULL_KEY and metadata["depth"] == 0 and
            metadata["clut_xy"] == [16, 480] and metadata["known_words"] == 16384 and
            metadata["fragments"] == [[768, 0, 64, 256, 0, 0]], "Unexpected source geometry")
    # UV x128..191 is native word x32..47, physical VRAM x800..815.
    crop = b"".join(raw[y * 128 + 64:y * 128 + 96] for y in range(64))
    crop_valid = b"".join(valid[y * 64 + 32:y * 64 + 48] for y in range(64))
    require(crc(crop) + "-" + crc(clut) == KEY and crop_valid == b"\1" * 1024,
            "Neighbor crop CRC/validity binding failed")
    indices, image = decode(crop, clut)
    archived = Image.open(source[".png"]).convert("RGBA")
    require(archived.size == (256, 256) and
            image.tobytes() == archived.crop((128, 0, 192, 64)).tobytes(),
            "Independent decode differs from archived full-page PNG crop")
    return source, crop, clut, crop_valid, indices, image


def evidence():
    patterns = read(PATTERNS)
    runs = sorted({run for row in patterns["keys"] if row.get("texture_crc32") == "73BF9877"
                   for run in row.get("runs", [])})
    paths = [FRESH] + [ROOT / "windows-x64/tools/research-runs" / run / "native/capture.jsonl" for run in runs]
    paths.append(ROOT / "remaster-audit/dev-center-evidence/hud-world-region-candidate-20261112-v9/native-v9-world-gameover-results/capture.jsonl")
    records = []
    family_count = 0
    central_counts = Counter()
    alternate_target_draws = []
    for path in paths:
        for line_number, line in enumerate(path.open(encoding="utf-8"), 1):
            if '73BF9877' not in line and '52F33418' not in line:
                continue
            row = json.loads(line)
            if row.get("event") not in ("source_draw_query_matched", "replacement_gl_draw_submitted"):
                continue
            if row.get("depth") != 0 or row.get("page_xy") != [768, 0]:
                continue
            family_count += 1
            uv = row.get("uv_bounds", [])
            if len(uv) != 4:
                continue
            if 0 <= uv[0] <= uv[2] <= 63 and 0 <= uv[1] <= uv[3] <= 63:
                if row.get("clut_xy") == [0, 480] and row.get("key") in ("73BF9877-5E9B9AC3", "52F33418-5E9B9AC3"):
                    central_counts[row["event"]] += 1
                else:
                    alternate_target_draws.append({"path": str(path), "line": line_number, "record": row})
            if row.get("key") == FULL_KEY and row.get("clut_xy") == [16, 480] and \
                    128 <= uv[0] <= uv[2] <= 191 and 0 <= uv[1] <= uv[3] <= 63:
                records.append({"path": str(path.resolve()), "line": line_number, "record": row})
    require(any(x["record"]["event"] == "replacement_gl_draw_submitted" for x in records),
            "No actual neighbor-region GL submission in scoped evidence")
    return {"scope": "Fresh discovery plus all nine historical runs linked to the 22-key atlas family and v9 results capture",
            "source_logs": [ref(path) for path in paths], "patterns": ref(PATTERNS),
            "family_draw_query_records": family_count, "central_region_records": dict(central_counts),
            "proven_alternate_central_region_palette_records": alternate_target_draws,
            "neighbor_records": records,
            "qualification": "GL submission proves use of this UV region/palette; it does not prove unoccluded pixels, left/right building identity, or atomic screenshot ownership."}


def verify():
    manifest = read(OUTPUT / "manifest.json")
    for row in manifest["output_files"]:
        path = Path(row["path"])
        require(path.resolve().is_relative_to(OUTPUT.resolve()), "Unexpected output reference")
        require(ref(path)["sha256"] == row["sha256"], "Output hash mismatch: " + str(path))
    _, crop, clut, valid, indices, image = source_inputs()
    proof = OUTPUT / "source-proof"
    for suffix, expected in ((".words.bin", crop), (".clut.bin", clut), (".valid.bin", valid)):
        require((proof / (KEY + suffix)).read_bytes() == expected, "Output source sidecar mismatch")
    require((OUTPUT / "native-indices-u8.bin").read_bytes() == indices, "Native index mismatch")
    require(Image.open(proof / (KEY + ".png")).convert("RGBA").tobytes() == image.tobytes(),
            "Exported native RGBA mismatch")
    print(json.dumps({"verified": True, "manifest": str(OUTPUT / "manifest.json"),
                      "key": KEY, "output_files": len(manifest["output_files"]),
                      "native_decode_matches_archived_crop": True}))


def build():
    require(not OUTPUT.exists(), "New source-guide output required; existing guide left untouched")
    source, crop, clut, valid, indices, image = source_inputs()
    receipts = evidence()
    central_raw = (CENTRAL / "source-proof/52F33418-5E9B9AC3.words.bin").read_bytes()
    central_clut = (CENTRAL / "source-proof/52F33418-5E9B9AC3.clut.bin").read_bytes()
    require(crc(central_raw) + "-" + crc(central_clut) == "52F33418-5E9B9AC3", "Central source binding failed")
    central_indices, central_image = decode(central_raw, central_clut)
    mask, components = bright_blue_components(image)
    central_mask, central_components = bright_blue_components(central_image)
    layout = {"method": "Four-connected components of native pixels with B>=128, B>=G+16, B>=R+16",
              "qualification": "Color-threshold candidates only, not semantic window rectangles/counts. Shading can fragment one opening or join trim. No 24-window template is assumed.",
              "neighbor_components": components, "central_components": central_components,
              "native_index_difference_pixels": sum(a != b for a, b in zip(indices, central_indices)),
              "alpha_class_difference_pixels": sum(a != b for a, b in zip(image.getchannel("A").tobytes(), central_image.getchannel("A").tobytes())),
              "bright_blue_mask_difference_pixels": sum(bool(a) != bool(b) for a, b in zip(mask, central_mask)),
              "same_source_indices": indices == central_indices,
              "row_band_measurements": [{"native_y_half_open": [y0, y1],
                   "central_bright_blue_pixels": sum(bool(v) for v in central_mask[y0*64:y1*64]),
                   "neighbor_bright_blue_pixels": sum(bool(v) for v in mask[y0*64:y1*64])}
                  for y0, y1 in [(16, 24), (36, 43), (54, 61)]],
              "row_band_qualification": "Comparison intervals encompass native bright-blue rows; these are not proven complete floor, aperture or mesh boundaries."}
    OUTPUT.mkdir(parents=True)
    proof = OUTPUT / "source-proof"
    proof.mkdir()
    original = OUTPUT / "original-fullpage"
    original.mkdir()
    for suffix, path in source.items():
        shutil.copyfile(path, original / (FULL_KEY + suffix))
    for suffix, data in ((".words.bin", crop), (".clut.bin", clut), (".valid.bin", valid)):
        (proof / (KEY + suffix)).write_bytes(data)
    image.save(proof / (KEY + ".png"))
    image.save(OUTPUT / "facade-neighbor-native-64x64.png")
    image.getchannel("A").save(OUTPUT / "alpha-class-native-64x64.png")
    image.convert("RGB").resize((512, 512), Image.Resampling.NEAREST).save(OUTPUT / "facade-neighbor-RGB-nearest8x-reference.png")
    (OUTPUT / "native-indices-u8.bin").write_bytes(indices)
    Image.frombytes("L", (64, 64), indices).save(OUTPUT / "native-indices-values-0-to-15.png")
    Image.frombytes("L", (64, 64), mask).save(OUTPUT / "bright-blue-color-mask-64x64.png")
    counts = Counter(indices)
    colors = palette_rgba(struct.unpack("<16H", clut))
    palette = [{"index": i, "word_u16": word, "word_hex": f"0x{word:04X}",
                "native_rgba8": list(colors[i]), "native_pixel_count": counts[i],
                "class": "transparent" if word == 0 else "STP" if word & 0x8000 else "non-STP"}
               for i, word in enumerate(struct.unpack("<16H", clut))]
    write(OUTPUT / "palette-1555.json", {"clut_xy": [16, 480], "entries": palette,
          "decode": "Little-endian PSX 1555; RGB five-bit channels shifted left 3; A=0 for word0,255 for STP bit15,otherwise127. Alpha is categorical, not ordinary opacity."})
    write(OUTPUT / "source-layout-candidate-components.json", layout)
    write(OUTPUT / "actual-draw-receipts.json", receipts)
    write(proof / (KEY + ".source.json"), {"key": KEY, "width_words": 16, "height": 64,
          "depth": 0, "clut_xy": [16, 480], "clut_words": 16, "known_words": 1024,
          "total_words": 1024, "reconstructed_crc32": crc(crop),
          "raw_origin": "row-word crop from independently CRC/validity-verified draw-referenced native page archive",
          "fragments": [[800, 0, 16, 64, 0, 0]], "source_uv_half_open": [128, 0, 192, 64],
          "parent_archive": [ref(path) for path in source.values()],
          "registration_only": True, "runtime_replacement_admitted": False})
    review = Image.new("RGB", (1024, 1090), (25, 25, 25))
    draw = ImageDraw.Draw(review)
    for left, im, rects, label in [(0, central_image, central_components, "CENTRAL 52F33418 / 5E9B9AC3"), (512, image, components, "NEIGHBOR 74EF95B7 / B30D16F0")]:
        review.paste(im.convert("RGB").resize((512, 512), Image.Resampling.NEAREST), (left, 32))
        marked = im.convert("RGB").resize((512, 512), Image.Resampling.NEAREST)
        ink = ImageDraw.Draw(marked)
        for row in rects:
            x0, y0, x1, y1 = row["rect_half_open"]
            ink.rectangle((x0*8, y0*8, x1*8-1, y1*8-1), outline=(255, 220, 0), width=1)
        review.paste(marked, (left, 568))
        draw.text((left + 8, 8), label, fill="white")
    draw.text((8, 549), "Native data at nearest8x; boxes are bright-blue color components, NOT confirmed windows or new HD detail.", fill="white")
    review.save(OUTPUT / "central-vs-neighbor-source-review.png")
    write(OUTPUT / "manifest.json", {"schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
          "scope": "Native source guide only; no authored art, pack admission, region TSV, executable or runtime changes",
          "original_fullpage_key": FULL_KEY, "cropped_exact_source_key": KEY,
          "physical_source_rect_words": [800, 0, 16, 64], "source_uv_half_open": [128, 0, 192, 64],
          "depth": 0, "clut_xy": [16, 480], "native_dimensions": [64, 64],
          "source_index_alias_of_central": False, "native_index_difference_pixels": layout["native_index_difference_pixels"],
          "independent_decode_matches_archived_png_crop": True,
          "alpha_classes_and_counts": dict(Counter(image.getchannel("A").tobytes())),
          "known": ["Exact native words/palette/validity and source UV registration are verified", "Scoped actual GL submissions use this native UV region and CLUT", "Blue opening arrangements and source indices differ from the central facade; recoloring the central master is insufficient"],
          "unmapped": ["Exact left/right screenshot building ownership and unoccluded visibility", "Semantic window count/complete apertures, including dark unlit openings", "Physical floor or door semantics, mesh UV seam ownership and full repeat period", "Authored remaster quality and runtime integration"],
          "authoring_guidance": "Rebuild this distinct source layout before applying shared materials. Color-component boxes are a measured guide only. Preserve source categorical alpha independently from authored RGB.",
          "proven_alternate_central_region_palettes": [],
          "builder": ref(Path(__file__)), "inputs": [ref(path) for path in source.values()] +
                    [ref(CENTRAL / "manifest.json"), ref(CENTRAL / "source-proof/52F33418-5E9B9AC3.words.bin"), ref(CENTRAL / "source-proof/52F33418-5E9B9AC3.clut.bin")],
          "output_files": [ref(path) for path in sorted(OUTPUT.rglob("*")) if path.is_file()]})
    verify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify() if args.verify else build()
