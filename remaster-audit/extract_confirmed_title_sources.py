"""Extract exact physical title pages from a root-captured GPU VRAM snapshot."""
from pathlib import Path
import hashlib
import json
import zlib

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT/"remaster-audit/dev-center-evidence/ui-continuation-20261112"
OUT = BASE/"title-source-20261112"
GP0 = BASE/"title-confirmed-gp0.json"
VRAM = BASE/"title-confirmed-vram.bin"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise ValueError("Source proofs are immutable; choose another folder")
    gp0 = json.loads(GP0.read_bytes())
    vram = np.frombuffer(VRAM.read_bytes(), dtype="<u2").reshape(512, 1024)
    OUT.mkdir()
    pages, images = [], []
    for x, width, expected in ((704, 256, "282438F3"), (960, 64, "1D953D67")):
        words = vram[:256, x:x+width].copy()
        raw = words.astype("<u2").tobytes()
        crc = f"{zlib.crc32(raw):08X}"
        if crc != expected:
            raise ValueError("Captured title page CRC changed")
        key = crc+"-00000000"
        rgba = np.stack(((words & 31) << 3, ((words >> 5) & 31) << 3, ((words >> 10) & 31) << 3,
                         np.where(words == 0, 0, np.where(words & 0x8000, 255, 127))), axis=2).astype(np.uint8)
        images.append(rgba)
        (OUT/(key+".words.bin")).write_bytes(raw)
        (OUT/(key+".valid.bin")).write_bytes(bytes([1])*words.size)
        (OUT/(key+".clut.bin")).write_bytes(b"")
        Image.fromarray(rgba).save(OUT/(key+".png"))
        metadata = {"key": key, "frame": 220063, "upload_serial": 0, "width_words": width,
                    "height": 256, "depth": 2, "clut_xy": [0, 0], "clut_words": 0,
                    "known_words": int(words.size), "total_words": int(words.size), "reconstructed_crc32": crc,
                    "raw_origin": "Display-ring full GPU VRAM snapshot; exact physical title texture page prefix",
                    "fragments": [[x, 0, width, 256, 0, 0]], "captured_vram_sha256": sha(VRAM),
                    "alpha_values": [int(a) for a in np.unique(rgba[:, :, 3])],
                    "admission_note": "Left full page already admitted" if width == 256 else "Physical64word prefix only. Actual primitive UV0..254 prevents current clipped-page admission; key alone is insufficient."}
        (OUT/(key+".source.json")).write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
        pages.append({"key": key, "physical_xy": [x, 0], "native_size": [width, 256],
                      "words_sha256": hashlib.sha256(raw).hexdigest(), "png_sha256": sha(OUT/(key+".png"))})
    composite = np.concatenate([a[:240] for a in images], axis=1)
    Image.fromarray(composite).save(OUT/"title-contiguous-native-320x240.png")
    Image.fromarray(composite).resize((1280, 960), Image.Resampling.NEAREST).save(OUT/"title-contiguous-source-review.png")
    report = {"gp0_path": str(GP0), "gp0_sha256": sha(GP0), "gp0_frame": gp0["frame"],
              "vram_path": str(VRAM), "vram_sha256": sha(VRAM), "vram_frame": 220063,
              "draw_offset": [160, 360], "draw_area_inclusive": [0, 248, 319, 471],
              "left_draw": {"seq": 20318364, "tpage": "0x010B", "physical_page_xy": [704, 0],
                            "screen_quad_after_offset": [[0, 240], [255, 240], [0, 480], [255, 480]],
                            "native_uv_corners": [[0, 0], [255, 0], [0, 240], [255, 240]],
                            "sampled_query_uv_inclusive": [0, 0, 254, 239]},
              "right_draw": {"seq": 20318363, "tpage": "0x010F", "physical_page_xy": [960, 0],
                             "screen_quad_after_offset": [[255, 240], [510, 240], [255, 480], [510, 480]],
                             "native_uv_corners": [[0, 0], [255, 0], [0, 240], [255, 240]],
                             "sampled_query_uv_inclusive": [0, 0, 254, 239],
                             "visible_screen_inclusive": [255, 248, 319, 471],
                             "visible_source_uv_estimate": [0, 8, 64, 231]},
              "source_pages": pages,
              "finding": "Title is repeated255pixel quads. The visible rightquad extends65pixels after drawing-offset/draw-area clipping. Current helper checks its full0..254 UV query against a64word physical prefix and rejects it before recording any source receipt.",
              "limits": ["GP0 and VRAM frames differ by2; this is sequential evidence rather than an atomic frame capture.",
                         "The nominal320pixel composite joins physical texture data and is not a rasterized screenshot. Native geometry uses255pixel page spacing.",
                         "A wrapped256word rightpage identity includes framebuffer words; it is not the admitted physical-prefix key.",
                         "Visible sourceUV values are derived from axis-aligned affine geometry; pixel-center and raster endpoint behavior still needs runtime verification."]}
    (OUT/"title-source-map.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "source_pages": pages, "current_right_admission": False}, indent=2))


if __name__ == "__main__":
    main()
