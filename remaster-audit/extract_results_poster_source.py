"""Extract the five GP0-verified 16bpp Results poster pages, read-only."""
from pathlib import Path
import hashlib
import json
import shutil
import zlib

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5"
OUT = LIVE / "results-poster-source-proof-v1"
PAGES = [(320, 0, "F2BDBE54", 11137374), (384, 0, "69A29FD8", 11137372),
         (448, 0, "ABB8CC89", 11137370), (320, 256, "41855657", 11137368),
         (384, 256, "FC55F5E0", 11137366)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signed(value, bits):
    value &= (1 << bits)-1
    return value-(1 << bits) if value & (1 << (bits-1)) else value


def decode(words):
    return np.stack(((words & 31) << 3, ((words >> 5) & 31) << 3, ((words >> 10) & 31) << 3,
                     np.where(words == 0, 0, np.where(words & 32768, 255, 127))), 2).astype(np.uint8)


def main():
    if OUT.exists():
        raise ValueError("Choose a new immutable proof folder")
    gp0_path = LIVE / "results-gp0.json"
    vram_path = LIVE / "results-source-vram.bin"
    gp0 = json.loads(gp0_path.read_bytes())["dump"]
    receipt_path = LIVE / "results-source-vram.json"
    receipt = json.loads(receipt_path.read_bytes())
    if gp0["frame"] != 62303 or receipt["dump"]["frame"] != 62304:
        raise ValueError("Expected the reviewed sequential Results evidence")
    vram = np.frombuffer(vram_path.read_bytes(), "<u2").reshape(512, 1024)
    tpage, offset = 0, (0, 0)
    draws = {}
    for entry in gp0["entries"]:
        words = [int(w, 16) for w in entry["w"]]
        op = words[0] >> 24
        if op == 0xE1:
            tpage = words[0] & 0x7ff
        elif op == 0xE5:
            offset = signed(words[0], 11), signed(words[0] >> 11, 11)
        elif (op & 0xfc) == 0x64 and entry["seq"] in {p[3] for p in PAGES}:
            draws[entry["seq"]] = {"seq": entry["seq"], "opcode": f"{op:02X}", "tpage": f"{tpage:04X}",
                "page_xy": [(tpage & 15)*64, ((tpage >> 4) & 1)*256], "depth": (tpage >> 7) & 3,
                "screen_xy": [signed(words[1], 16)+offset[0], signed(words[1] >> 16, 16)+offset[1]],
                "source_uv": [words[2] & 255, (words[2] >> 8) & 255],
                "size": [words[3] & 65535, words[3] >> 16], "vertex_color_rgb": [words[0]&255, (words[0]>>8)&255, (words[0]>>16)&255],
                "raw_gp0": entry}
    OUT.mkdir()
    parts, rows = [], []
    for column, (x, y, expected, seq) in enumerate(PAGES):
        draw = draws.get(seq)
        if not draw or draw["depth"] != 2 or draw["page_xy"] != [x, y] or draw["screen_xy"] != [column*64, 8] or draw["size"] != [64, 224] or draw["source_uv"] != [0, 0]:
            raise ValueError("Poster draw/source geometry changed")
        words = vram[y:y+256, x:x+256].copy()
        raw = words.astype("<u2").tobytes()
        if f"{zlib.crc32(raw):08X}" != expected:
            raise ValueError("Page CRC mismatch")
        key = expected+"-00000000"
        (OUT / (key+".words.bin")).write_bytes(raw)
        (OUT / (key+".clut.bin")).write_bytes(b"")
        (OUT / (key+".valid.bin")).write_bytes(bytes([1])*65536)
        rgba = decode(words)
        Image.fromarray(rgba).save(OUT / (key+".png"))
        metadata = {"key": key, "frame": 62304, "width_words": 256, "height": 256, "depth": 2,
                    "clut_xy": [0, 0], "clut_words": 0, "known_words": 65536, "total_words": 65536,
                    "reconstructed_crc32": expected, "raw_origin": "verified canonical VRAM snapshot after complete Results GP0 frame",
                    "fragments": [[x, y, 256, 256, 0, 0]], "page_xy": [x, y]}
        (OUT / (key+".source.json")).write_text(json.dumps(metadata, indent=2)+"\n")
        parts.append(rgba[:224, :64])
        rows.append({"key": key, "native_size": [256, 256], "page_xy": [x, y], "draw": draw,
                     "replacement_region_half_open": [0, 0, 64, 224], "master_crop_half_open": [column*64, 0, (column+1)*64, 224],
                     "source_words_sha256": hashlib.sha256(raw).hexdigest(), "source_png_sha256": sha(OUT / (key+".png")),
                     "visible_prefix_crc32": f"{zlib.crc32(words[:224, :64].astype('<u2').tobytes()):08X}"})
    assembled = np.concatenate(parts, axis=1)
    Image.fromarray(assembled).save(OUT / "results-native-320x224.png")
    # Alpha bytes encode PSX classes, not opacity. A display reference treats
    # either nonzero class as visible; actual modulation/semitrans is per draw.
    display = assembled.copy(); display[:, :, 3] = np.where(display[:, :, 3] == 0, 0, 255)
    Image.fromarray(display).save(OUT / "results-native-display-320x224.png")
    Image.fromarray(display).resize((1280, 896), Image.Resampling.NEAREST).save(OUT / "results-native-actual4x.png")
    source_log = LIVE / "native-results-e2e/capture.jsonl"
    queries = [json.loads(line) for line in source_log.read_text().splitlines()]
    queries = [r for r in queries if r.get("event") == "source_draw_query_matched" and r.get("key") in {r["key"] for r in rows}]
    for row in rows:
        matching = [q for q in queries if q["key"] == row["key"]]
        if not matching or any(q["native_words"] != [256, 256] or q["page_xy"] != row["page_xy"] for q in matching):
            raise ValueError("Research native-page identity differs from GP0 extraction")
        row["research_query_count"] = len(matching)
        row["research_query_sample"] = matching[0]
    manifest = {"contract": "verified-results-poster-source-v1", "production_installed": False, "game_actions": 0,
        "source_master": {"path": str(OUT / "results-native-320x224.png"), "sha256": sha(OUT / "results-native-320x224.png"), "size": [320, 224]},
        "display_reference": {"path": str(OUT / "results-native-display-320x224.png"), "sha256": sha(OUT / "results-native-display-320x224.png")},
        "gp0": {"path": str(gp0_path), "sha256": sha(gp0_path), "frame": 62303},
        "vram": {"path": str(vram_path), "sha256": sha(vram_path), "frame": 62304, "receipt_path": str(receipt_path), "receipt_sha256": sha(receipt_path)},
        "source_log": {"path": str(source_log), "sha256": sha(source_log)}, "pages": rows,
        "restore_contract": "Restore the verified complete320x224 aircraft master. Split into five64x224 strips, insert each only into UV[0,0,64,224] of its corresponding256x256 original page; all outside RGBA byte-exact. Preserve categorical source alpha unless separately reviewed. Existing draw modulationRGB48 and geometry are untouched.",
        "limits": ["Sequential GP0 andVRAMframes differ by1; research queries corroborate exact sourcepageidentities.",
                   "Composite joins source pixels rather than rerasterizing GPU. Actual rectangle geometry is exactly64pixelswide and224high.",
                   "This is a source proof, not a restored candidate or runtime acceptance."]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "extract-source.py")
    print(json.dumps({"output": str(OUT), "pages": [r["key"] for r in rows], "master_sha256": manifest["source_master"]["sha256"]}))


if __name__ == "__main__":
    main()
