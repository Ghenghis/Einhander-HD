"""Encode the verified 8E1A UI tone geometry, independently of live CLUT colors.

UNACCEPTED AUTHORING PROTOTYPE. No runtime implementation or launcher inclusion.
This opt-in field is deliberately bounded above the footer/icon row. It is not
proof that a particular runtime word is drawn from the page. No palette aliases
or guessed fade colors are authored; the runtime must sample its current CLUT.
"""
from __future__ import annotations

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
BASE = ROOT / "remaster-audit/menu-restoration/palette-field-candidate-v7"
OUT = ROOT / "remaster-audit/menu-restoration/indexed-ui-field-candidate-v1"
QUEUE = Path("C:/github/REMASTER_STAGING/full-remaster/queue.json")
HUD = ROOT / "windows-x64/tools/build_hud_ui_candidate.py"
LIVE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5"
REGION = (0, 0, 256, 236)
SCALE = 16
CONTRACT = "verified-ui-indexed-field-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def encode(indices, scale=SCALE, region=REGION):
    """R tone/17; G gain/128; B nearest categorical index; A region guard."""
    source = np.asarray(indices, np.uint8)
    if source.ndim != 2 or source.min() < 0 or source.max() > 15:
        raise ValueError("Expected a 4bpp index plane")
    nearest = np.repeat(np.repeat(source, scale, 0), scale, 1)
    result = np.empty((*nearest.shape, 4), np.uint8)
    result[:, :, 0] = nearest * 17
    result[:, :, 1] = 128
    result[:, :, 2] = nearest
    result[:, :, 3] = 0
    x0, y0, x1, y1 = region
    crop = source[y0:y1, x0:x1]
    tone = np.clip(cv2.resize(crop.astype(np.float32),
                   ((x1-x0)*scale, (y1-y0)*scale), interpolation=cv2.INTER_CUBIC), 0, 15)
    gx = cv2.Sobel(tone, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(tone, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    normal = (-.6*gx-.8*gy)/np.maximum(magnitude, .01)
    bevel = np.sin(np.pi*(15-tone)/15)*np.clip(magnitude*scale/20, 0, 1)
    rim = np.clip((tone-9)/5, 0, 1)*np.clip((15-tone)/1.5, 0, 1)
    gain = (1+.14*normal*bevel)*(1-.16*rim)
    selected = result[y0*scale:y1*scale, x0*scale:x1*scale]
    selected[:, :, 0] = np.rint(tone*17).astype(np.uint8)
    selected[:, :, 1] = np.rint(np.clip(gain*128, 0, 255)).astype(np.uint8)
    selected[:, :, 2] = np.rint(tone).astype(np.uint8)
    selected[:, :, 3] = 255
    return result


def render_cpu(field, palette):
    """CPU reference at field texel centers; class lookup is never interpolated."""
    tone = field[:, :, 0].astype(np.float32)/17
    gain = field[:, :, 1].astype(np.float32)/128
    lo = np.floor(tone).astype(np.uint8)
    hi = np.minimum(lo+1, 15)
    part = (tone-lo)[:, :, None]
    rgb = (palette[lo, :3]*(1-part)+palette[hi, :3]*part)*gain[:, :, None]
    alpha = palette[field[:, :, 2], 3]
    return np.dstack((np.rint(np.clip(rgb, 0, 255)).astype(np.uint8), alpha))


def sampled_query_review():
    path = LIVE / "native-live-gameplay/capture.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    queries = [r for r in rows if r.get("event") == "source_draw_query_matched"
               and r.get("key", "").startswith("8E1A509D-")]
    groups = {}
    for row in queries:
        entry = groups.setdefault(row["key"], {"query_count": 0, "uv_bounds": set(),
                                  "first_frame": row["frame"], "last_frame": row["frame"]})
        entry["query_count"] += 1
        entry["last_frame"] = row["frame"]
        entry["uv_bounds"].add(tuple(row["uv_bounds"]))
    for entry in groups.values():
        entry["uv_bounds"] = sorted(map(list, entry["uv_bounds"]))
        entry["all_queries_inside_band"] = all(b[1] >= 0 and b[3] < 236 for b in entry["uv_bounds"])
        entry["any_query_inside_band"] = any(b[1] >= 0 and b[3] < 236 for b in entry["uv_bounds"])
    return {"source_log": str(path), "source_log_sha256": sha(path),
            "coverage": "sampled_activation_forward; not a full draw list or visibility proof",
            "warning": "Animated CLUT queries at UV[32,236,47,251] are excluded footer/icon draws, not established GAME OVER lettering.",
            "keys": groups}


def main():
    if OUT.exists():
        raise ValueError("Choose a new isolated output; candidates are immutable")
    cv2.setNumThreads(2)
    hud = load_module(HUD, "indexed_ui_hud")
    menu = load_module(BASE / "build-source.py", "indexed_ui_menu")
    items = [a for a in json.loads(QUEUE.read_bytes())["assets"]
             if a["key"].startswith("8E1A509D-") and a.get("source_verified")]
    if {a["key"] for a in items} != {"8E1A509D-4FE32821", "8E1A509D-8808F70A", "8E1A509D-C7A1F2F0"}:
        raise ValueError("Verified source palette set changed")
    reference = next(a for a in items if a["key"] == "8E1A509D-4FE32821")
    metadata, words, clut = hud.verify_stock(Path(reference["source"]).parent, reference["key"])
    if f"{zlib.crc32(words):08X}" != "8E1A509D":
        raise ValueError("Source CRC mismatch")
    indices = hud.decode_indices(words, metadata)
    with np.load(BASE / "masters/8E1A509D.npz") as cache:
        if not np.array_equal(cache["native_indices"], indices):
            raise ValueError("Accepted geometry source changed")
        accepted = cache["contour_indices"].copy()
    field = encode(indices)
    if not np.array_equal(field[:236*SCALE, :, 2], accepted[:236*SCALE]):
        raise ValueError("Categorical geometry diverged from accepted menu")
    for folder in ("pack", "native", "previews"):
        (OUT / folder).mkdir(parents=True)
    shutil.copyfile(__file__, OUT / "build-source.py")
    field_path = OUT / "pack/8E1A509D.ui-field.png"
    Image.fromarray(field, "RGBA").save(field_path)
    (OUT / "native/source.words.bin").write_bytes(words)
    (OUT / "native/source.clut.bin").write_bytes(clut)
    Image.fromarray(indices, "L").save(OUT / "native/source.indices.png")
    Image.open(reference["source"]).save(OUT / "native/source-reference.png")
    (OUT / "native/source.json").write_text(json.dumps(metadata, indent=2)+"\n")

    checks = []
    for item in sorted(items, key=lambda a: a["key"]):
        meta, raw, palette_bytes = hud.verify_stock(Path(item["source"]).parent, item["key"])
        if raw != words:
            raise ValueError("Palette variant geometry differs")
        palette = hud.palette_rgba(palette_bytes)
        actual = render_cpu(field, palette)
        original = np.asarray(Image.open(BASE / "pack/einhander-texture-replacements" / (item["key"]+".png")))
        delta = np.abs(actual[:236*SCALE, :, :3].astype(np.int16)-original[:236*SCALE, :, :3])
        if delta.max() > 3 or not np.array_equal(actual[:236*SCALE, :, 3], original[:236*SCALE, :, 3]):
            raise ValueError("Field differs materially from accepted RGBA output")
        checks.append({"key": item["key"], "rgb_quantization_max": int(delta.max()),
                       "rgb_quantization_mean": float(delta.mean()), "categorical_alpha_exact": True})
    # A verified current palette is a proof comparison, never an emitted alias.
    vram_path = LIVE / "post-gameover-vram.bin"
    vram = np.frombuffer(vram_path.read_bytes(), "<u2").reshape(512, 1024)
    current_words = vram[0:256, 512:576].astype("<u2").tobytes()
    current_clut = vram[480, 16:32].astype("<u2").tobytes()
    if current_words != words or f"{zlib.crc32(current_clut):08X}" != "02491337":
        raise ValueError("Live proof source/palette mismatch")
    (OUT / "native/live-02491337.clut.bin").write_bytes(current_clut)
    palette = hud.palette_rgba(current_clut)
    actual = render_cpu(field, palette)
    native = palette[indices]
    box = (0, 158, 256, 236)
    width, height = 1024, (236-158)*4
    canvas = Image.new("RGBA", (width, height*2+56), (12, 18, 25, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 5), "VERIFIED 02491337 CLUT: native source typography (4x)", fill="white")
    canvas.alpha_composite(Image.fromarray(native).crop(box).resize((width, height), Image.Resampling.NEAREST), (0, 24))
    draw.text((6, height+30), "Indexed contour field + same exact CLUT (4x); no runtime Game Over coverage claim", fill="white")
    canvas.alpha_composite(Image.fromarray(actual).crop(tuple(v*SCALE for v in box)).resize((width, height), Image.Resampling.LANCZOS), (0, height+54))
    canvas.convert("RGB").save(OUT / "previews/02491337-typography-actual4x.png")
    del actual, original, accepted
    reloaded = np.asarray(Image.open(field_path))
    if not np.array_equal(reloaded, field):
        raise ValueError("Field PNG did not round-trip exactly")
    descriptor = "\n".join([
        "contract="+CONTRACT, "source_crc32=8E1A509D", "depth=0",
        "native_size=256,256", "field_size=4096,4096", "allowed_native_region=0,0,256,236",
        "tone_divisor=17", "gain_divisor=128", "class_channel=B", "region_channel=A",
        "field_file=8E1A509D.ui-field.png", "field_sha256="+sha(field_path), ""])
    (OUT / "pack/indexed-ui-field.txt").write_text(descriptor, encoding="ascii")
    manifest = {
        "contract": CONTRACT, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "production_installed": False, "game_actions": 0,
        "source_crc32": "8E1A509D", "depth": 0, "native_size": [256, 256],
        "field_size": [4096, 4096], "allowed_native_regions": [list(REGION)],
        "field": {"path": str(field_path), "relative_path": "8E1A509D.ui-field.png", "sha256": sha(field_path)},
        "runtime_descriptor": {"path": str(OUT / "pack/indexed-ui-field.txt"), "sha256": sha(OUT / "pack/indexed-ui-field.txt")},
        "encoding": {"format": "RGBA8", "R": "continuous source palette coordinate = byte / 17",
                     "G": "scalar RGB gain = byte / 128", "B": "categorical source palette index, direct byte 0..15; nearest texelFetch only",
                     "A": "255 inside approved band; 0 outside; region admission guard",
                     "rgb": "linear mix current CLUT floor(tone)/min(floor(tone)+1,15), then multiply gain; clamp0..1",
                     "alpha": "current CLUT word at nearest categorical B; word0 cutout, bit15 set class255, otherwise class127",
                     "sampling": "R/G may filter linearly; B and A never interpolated", "tone_divisor": 17, "gain_divisor": 128},
        "runtime_requirements": ["exact RGBA key priority", "sourceCRC/depth/native-size/region admission",
                                 "live canonical VRAM CLUT with ordered writes", "no changes to native raster geometry/UV",
                                 "native fallback outside band or rejected metadata", "no material hue/tint on this palette-faithful field"],
        "source": {"key": reference["key"], "path": reference["source"], "sha256": sha(reference["source"]),
                   "words_sha256": hashlib.sha256(words).hexdigest(), "clut_sha256": hashlib.sha256(clut).hexdigest(),
                   "indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(), "metadata": metadata},
        "source_proof_files": [{"path": str(p), "sha256": sha(p)} for p in sorted((OUT / "native").iterdir())],
        "accepted_geometry": {"master": str(BASE / "masters/8E1A509D.npz"), "master_sha256": sha(BASE / "masters/8E1A509D.npz"),
                              "same_contour_indices_inside_band": True, "lighting": .14, "rim_strength": .16},
        "checks": {"field_png_roundtrip_exact": True, "source_crc_verified": True,
                   "outside_guard_zero": bool(np.all(field[236*SCALE:, :, 3] == 0)),
                   "class_index_range": [int(field[:, :, 2].min()), int(field[:, :, 2].max())], "existing_palette_comparisons": checks},
        "live_palette_proof": {"vram": str(vram_path), "vram_sha256": sha(vram_path), "frame": 46968,
                               "page_xy": [512, 0], "clut_xy": [16, 480], "clut_crc32": "02491337",
                               "use": "proof-only comparison; no exact RGBA alias emitted"},
        "coverage_limit": "Only this source band is improved for otherwise unknown CLUTs. Actual GAME OVER lettering/source binding remains unverified by sampled logs.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    (OUT / "sampled-query-review.json").write_text(json.dumps(sampled_query_review(), indent=2)+"\n")
    print(json.dumps({"output": str(OUT), "field_sha256": sha(field_path), "checks": checks}), flush=True)


if __name__ == "__main__":
    main()
