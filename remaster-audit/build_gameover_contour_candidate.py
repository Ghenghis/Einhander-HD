"""Rebuild the original wordmark's level-set contours without changing glyphs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
SOURCE = AUDIT / "menu-restoration/gameover-region-candidate-v1/source-proof"
OUT = AUDIT / "menu-restoration/gameover-region-candidate-v3"
KEY = "5125FF82-00000000"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise ValueError("Existing candidates are immutable")
    native = np.asarray(Image.open(SOURCE / (KEY+".png")).convert("RGBA"))
    if native.shape != (256, 64, 4) or (native[:, :, 3] == 0).any():
        raise ValueError("Unexpected proven16-bit wordmark source")
    upright = np.rot90(native, -1)
    # Retain every original5-bit RGB anchor. A binary threshold would promote
    # the low-intensity face/glow to white, destroying the hollow wordmark.
    # Continuous channel level sets reconstruct each original tone boundary.
    channels = []
    cv2.setNumThreads(2)
    for channel in range(3):
        source_levels = upright[:, :, channel] // 8
        tonal = np.zeros((1024, 4096), dtype=np.float32)
        for level in range(1, int(source_levels.max())+1):
            mask = np.pad(source_levels >= level, 1, constant_values=False)
            signed = (distance_transform_edt(mask)-distance_transform_edt(~mask)).astype(np.float32)
            field = cv2.resize(signed, ((256+2)*16, (64+2)*16), interpolation=cv2.INTER_CUBIC)
            field = cv2.GaussianBlur(field, (0, 0), 16*.18, borderType=cv2.BORDER_REPLICATE)[16:-16, 16:-16]
            tonal += np.clip(field+.5, 0, 1)
        channels.append(np.rint(tonal*8).clip(0, 248).astype(np.uint8))
    rgb = np.stack(channels, axis=2)
    if not np.array_equal(rgb[8::16, 8::16], upright[:, :, :3]):
        raise ValueError("Original RGB tone anchors at native pixel centers changed")
    authored = np.repeat(np.repeat(native, 16, 0), 16, 1)
    original_alpha = authored[:, :, 3].copy()
    authored[:, :, :3] = np.rot90(rgb, 1)
    if not np.array_equal(original_alpha, authored[:, :, 3]):
        raise ValueError("Source/STP classes changed")
    (OUT / "pack/einhander-texture-replacements").mkdir(parents=True)
    shutil.copytree(SOURCE, OUT / "source-proof")
    (OUT / "pack/Hashes.ini").write_text("")
    target = OUT / "pack/einhander-texture-replacements" / (KEY+".png")
    Image.fromarray(authored).save(target)
    Image.fromarray(rgb).save(OUT / "gameover-encoded-upright.png")
    with Image.open(target) as check:
        if check.convert("RGBA").tobytes() != authored.tobytes():
            raise ValueError("PNG roundtrip changed")
    proof = [dict(path=str(p), sha256=sha(p)) for p in sorted((OUT / "source-proof").iterdir())]
    manifest = dict(schema_version=1, contract="verified-gameover-region-art-v3",
                    generated_at_utc=datetime.now(timezone.utc).isoformat(), asset_count=1,
                    files=[dict(key=KEY, path=str(target), sha256=sha(target), size=[1024,4096],
                                source_region_words=[448,256,64,256], depth=2,
                                source_crc="5125FF82", palette_crc="00000000",
                                native_alpha_stp_exact=True, source_has_clear_samples=False,
                                source_proof=proof)],
                    method="Continuous signed-distance level sets for every original5-bit RGB channel threshold; all original source RGB tone anchors, hollow silver outlines, teal rim, glyph spacing and rotated source UVs are preserved at native pixel centers.",
                    original_rgb_tone_centers_exact=True,
                    original_ink_and_counter_centers_exact=True,
                    excluded_master=dict(path=str(AUDIT / "menu-restoration/gameover-region-candidate-v1/gameover-master.png"),
                                         reason="ImageGenv1 changes serif geometry; binary-fieldv2 overbrightens shaded faces. Both are excluded from this source-tone candidate"),
                    live_verified=False, runtime_admission_verified=False,
                    remaining=["Independent wordmark geometry/appearance review", "Final runtime admission and complete natural fade/re-entry replay"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "build-source.py")
    print(json.dumps(dict(output=str(OUT), checks="PASS", original_ink_centers_exact=True, source_stp_exact=True)))


if __name__ == "__main__":
    main()
