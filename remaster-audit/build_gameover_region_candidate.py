"""Encode the ImageGen wordmark in its proven rotated 16-bit source region."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zlib

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
OUT = AUDIT / "menu-restoration/gameover-region-candidate-v1"
V6 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6"
RECEIPT = AUDIT / "menu-restoration/imagegen-session-20261112.json"
KEY = "5125FF82-00000000"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(rgb, threshold):
    y, x = np.where(rgb.max(2) > threshold)
    if not len(x):
        raise ValueError("Wordmark has no visible source pixels")
    return [int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)]


def main():
    if OUT.exists():
        raise ValueError("Existing authored candidates are immutable")
    receipt = json.loads(RECEIPT.read_bytes())
    generation = next(a for a in receipt["assets"] if a["role"] == "Game Over wordmark")
    vram_path = V6 / "natural-gameover-vram.bin"
    vram = np.frombuffer(vram_path.read_bytes(), dtype="<u2").reshape(512, 1024)
    words = vram[256:512, 448:512].copy()
    raw = words.tobytes()
    if f"{zlib.crc32(raw):08X}-00000000" != KEY:
        raise ValueError("Observed Game Over source changed")
    native = np.empty((256, 64, 4), dtype=np.uint8)
    for channel, shift in enumerate((0, 5, 10)):
        native[:, :, channel] = ((words >> shift) & 31) << 3
    native[:, :, 3] = np.where(words == 0, 0, np.where(words & 32768, 255, 127))
    if (native[:, :, 3] == 0).any():
        raise ValueError("This encoding contract requires the observed nonclear region")
    upright = np.rot90(native, -1)
    target_bounds = bounds(upright[:, :, :3], 24)
    master_path = Path(generation["generated"])
    with Image.open(master_path) as image:
        master_size = list(image.size)
        generated = np.asarray(image.convert("RGB"))
    generated_bounds = bounds(generated, 24)
    (OUT / "pack/einhander-texture-replacements").mkdir(parents=True)
    (OUT / "source-proof").mkdir()
    (OUT / "pack/Hashes.ini").write_text("")
    shutil.copyfile(master_path, OUT / "gameover-master.png")
    (OUT / "prompt.txt").write_text(generation["prompt"]+"\n")
    Image.fromarray(upright).save(OUT / "source-proof/gameover-native-upright.png")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Existing FFmpeg is required")
    x0, y0, x1, y1 = generated_bounds
    tx0, ty0, tx1, ty1 = target_bounds
    width, height = (tx1-tx0)*16, (ty1-ty0)*16
    scaled = OUT / "wordmark-encoded-crop.png"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-i", str(master_path),
               "-vf", f"crop={x1-x0}:{y1-y0}:{x0}:{y0},scale={width}:{height}:flags=lanczos",
               "-frames:v", "1", "-threads", "1", str(scaled)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError(result.stderr)
    encoded = np.zeros((1024, 4096, 3), dtype=np.uint8)
    encoded[ty0*16:ty1*16, tx0*16:tx1*16] = np.asarray(Image.open(scaled).convert("RGB"))
    # Rotate the entire quad back into the actual64x256 source orientation.
    rgb = np.rot90(encoded, 1)
    nearest = np.repeat(np.repeat(native, 16, 0), 16, 1)
    authored = nearest.copy()
    authored[:, :, :3] = rgb
    if not np.array_equal(authored[:, :, 3], nearest[:, :, 3]):
        raise ValueError("Categorical source/STP field changed")
    target = OUT / "pack/einhander-texture-replacements" / (KEY+".png")
    Image.fromarray(authored).save(target)
    with Image.open(target) as image:
        if image.convert("RGBA").tobytes() != authored.tobytes():
            raise ValueError("PNG roundtrip changed")
    directory = OUT / "source-proof"
    (directory / (KEY+".words.bin")).write_bytes(raw)
    (directory / (KEY+".valid.bin")).write_bytes(bytes([1])*words.size)
    (directory / (KEY+".clut.bin")).write_bytes(b"")
    Image.fromarray(native).save(directory / (KEY+".png"))
    metadata = dict(key=KEY, depth=2, page_xy=[448, 256], x=448, y=256,
                    width_words=64, height=256, clut_words=0, known_words=int(words.size),
                    total_words=int(words.size), source_authority="GPU-truth display-ring VRAM snapshot",
                    source_vram=dict(path=str(vram_path), sha256=sha(vram_path)),
                    temporal_bracket=str(V6 / "natural-gameover-bracket.json"))
    (directory / (KEY+".source.json")).write_text(json.dumps(metadata, indent=2)+"\n")
    Image.fromarray(encoded).save(OUT / "gameover-encoded-upright.png")
    manifest = dict(schema_version=1, contract="verified-gameover-region-art-v1",
                    generated_at_utc=datetime.now(timezone.utc).isoformat(), asset_count=1,
                    files=[dict(key=KEY, path=str(target), sha256=sha(target), size=[1024, 4096],
                                source_region_words=[448, 256, 64, 256], depth=2,
                                source_crc=f"{zlib.crc32(raw):08X}", palette_crc="00000000",
                                native_alpha_stp_exact=True, source_has_clear_samples=False,
                                source_proof=[dict(path=str(p), sha256=sha(p)) for p in sorted(directory.iterdir())])],
                    master=dict(path=str(OUT / "gameover-master.png"), sha256=sha(OUT / "gameover-master.png"),
                                generated_size=master_size, origin="built-in ImageGen edit"),
                    prompt=dict(path=str(OUT / "prompt.txt"), sha256=sha(OUT / "prompt.txt")),
                    source_ink_bounds=target_bounds, generated_ink_bounds=generated_bounds,
                    encoding="FFmpeg crops authored ink and fits original native ink bounds at16x;90degree counterclockwise source rotation",
                    ffmpeg=dict(command=command, exit_code=result.returncode),
                    references=[dict(path=str(p), sha256=sha(p)) for p in (RECEIPT, V6 / "natural-gameover-bracket.json", AUDIT / "hud-restoration/gameover-wordmark-map.json")],
                    live_verified=False, runtime_admission_verified=False,
                    limits=["Master is source-guided authored lettering; exact custom glyph identity still requires visual review",
                            "Nonclear original categorical/STP field cannot clip restored contours and is kept exact",
                            "Requires opt-in exact-region runtime support, then actual natural Game Over/fade replay"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    shutil.copyfile(__file__, OUT / "build-source.py")
    print(json.dumps(dict(output=str(OUT), key=KEY, dimensions=[1024, 4096], checks="PASS", live_verified=False)))


if __name__ == "__main__":
    main()
