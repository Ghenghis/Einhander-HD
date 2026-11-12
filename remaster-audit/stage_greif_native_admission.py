"""Stage exact-source native-page PNGs solely to test replacement admission.

Never edits the installed pack, launches a process or calls the game. Output is
original resolution and is not restored artwork or a finished 4K texture pack.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zlib

from PIL import Image

from build_three_asset_proof import verify_stock
from extract_disc_stock import decode_tim

PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "remaster-audit/dev-center-evidence"
FAMILIES = {"1263A036", "38DC02FE"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc(data: bytes) -> str:
    return f"{zlib.crc32(data):08X}"


def native_image(words: bytes, palette: bytes, width_words: int, height: int,
                 key: str) -> Image.Image:
    if len(words) != width_words * height * 2 or len(palette) != 32:
        raise ValueError("Refusing malformed 4bpp page dimensions: " + key)
    if crc(words) + "-" + crc(palette) != key:
        raise ValueError("Refusing unmatched source/palette CRC: " + key)
    # Reuse the project's exact 1555 decoder and its 0/127/255 class contract.
    image, palette_hash = decode_tim(dict(bpp=0, width_words=width_words,
        height=height, pixels=words, palette=dict(colors=16, bytes=palette)), 0)
    if image is None or f"{palette_hash:08X}" != key.split("-")[1]:
        raise ValueError("Decoder palette identity mismatch")
    return image


def self_test() -> None:
    palette = struct.pack("<16H", 0, 0x001F, 0x8000, 0xFFFF, *([0] * 12))
    words = struct.pack("<H", 0x3210)
    image = native_image(words, palette, 1, 1, crc(words) + "-" + crc(palette))
    assert image.size == (4, 1)
    assert list(image.getdata()) == [(0, 0, 0, 0), (248, 0, 0, 127),
                                     (0, 0, 0, 255), (248, 248, 248, 255)]
    for invalid_words, invalid_palette, invalid_key in [
        (words[:-1], palette, crc(words) + "-" + crc(palette)),
        (words, palette[:-1], crc(words) + "-" + crc(palette)),
        (words, palette, "00000000-" + crc(palette)),
        (words, palette, crc(words) + "-00000000")]:
        try:
            native_image(invalid_words, invalid_palette, 1, 1, invalid_key)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed/mismatched source was accepted")
    print(json.dumps(dict(checks=6, failures=0,
                          scope="Exact source dimensions/CRC and transparent/opaque/STP-black decoder classes")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run", default="windows-x64/tools/research-runs/research-20261112-161558-481a5c19")
    parser.add_argument("--output", default="remaster-audit/dev-center-evidence/greif-native-admission-20261112")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    run = (PROJECT / args.run).resolve()
    output = (PROJECT / args.output).resolve()
    if not run.is_relative_to(PROJECT / "windows-x64/tools/research-runs"):
        raise ValueError("Use an owned research run")
    if not output.is_relative_to(EVIDENCE) or output.exists():
        raise ValueError("Use a new output directory under the evidence root")
    if not (run / "manifest.json").is_file():
        raise ValueError("Use a finalized run")
    capture_path = run / "native/capture.jsonl"
    rows = [json.loads(line) for line in capture_path.read_text(encoding="utf-8").splitlines()]
    wanted = sorted({row["key"] for row in rows if row.get("source_kind") == "native_page"
                     and row.get("key", "").split("-")[0] in FAMILIES})
    if not wanted:
        raise ValueError("No observed Greif candidate native pages in run")
    review_path = EVIDENCE / "greif-finish-wasp-review.json"
    review = json.loads(review_path.read_bytes())
    pages = {}
    for row in review["candidate_atlas_reviews"]:
        key = row["example_key"]
        family = key.split("-")[0]
        if family not in FAMILIES:
            continue
        png = Path(row["source_png"])
        metadata, words, palette = verify_stock(png.parent, key)
        if metadata["depth"] != 0 or metadata["width_words"] != 64 or metadata["height"] != 256:
            raise ValueError("Unexpected Greif page format")
        pages[family] = dict(metadata=metadata, words=words,
            path=png.with_name(key + ".words.bin"), original_png=png,
            original_png_sha256=sha(png.read_bytes()))
    needed_palettes = {key.split("-")[1] for key in wanted}
    palettes = {}
    search_roots = [PROJECT / "windows-x64/tools/research-runs",
        Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements"),
        Path("C:/github/REMASTER_STAGING/full-remaster")]
    scanned = 0
    for root in search_roots:
        for path in sorted(root.rglob("*.clut.bin")):
            scanned += 1
            data = path.read_bytes()
            if len(data) != 32:
                continue
            identity = crc(data)
            if identity not in needed_palettes:
                continue
            if identity in palettes and palettes[identity]["data"] != data:
                raise ValueError("Refusing conflicting bytes sharing a palette CRC")
            palettes.setdefault(identity, dict(data=data, path=path.resolve()))
    missing = [key for key in wanted if key.split("-")[0] not in pages
               or key.split("-")[1] not in palettes]
    # Resolve and validate every recoverable pair BEFORE creating any artifact.
    resolved = []
    for key in wanted:
        if key in missing:
            continue
        family, palette_identity = key.split("-")
        page, palette = pages[family], palettes[palette_identity]
        image = native_image(page["words"], palette["data"], 64, 256, key)
        resolved.append((key, page, palette, image))
    output.mkdir(parents=True)
    source_dir = output / "sources"
    replacement_dir = output / "pack/einhander-texture-replacements"
    source_dir.mkdir()
    replacement_dir.mkdir(parents=True)
    (replacement_dir.parent / "Hashes.ini").write_text("", encoding="utf-8")
    results = []
    for key, page, palette, image in resolved:
        words = page["words"]
        for extension, data in [("words.bin", words), ("valid.bin", bytes([1]) * (64 * 256)),
                                ("clut.bin", palette["data"])]:
            (source_dir / (key + "." + extension)).write_bytes(data)
        metadata = dict(key=key, frame=None, width_words=64, height=256, depth=0,
            clut_words=16, known_words=16384, total_words=16384,
            reconstructed_crc32=crc(words), raw_origin="cross_capture_crc_identical_components",
            atomic_same_frame=False, gpu_readback=False,
            source_words_path=str(page["path"]), source_clut_path=str(palette["path"]))
        (source_dir / (key + ".source.json")).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        source_png = source_dir / (key + ".png")
        image.save(source_png)
        # Independent project validator decodes words/CLUT afresh and verifies
        # every RGBA pixel and validity byte, including black STP texels.
        verify_stock(source_dir, key)
        destination = replacement_dir / (key + ".png")
        destination.write_bytes(source_png.read_bytes())
        with Image.open(destination) as check:
            if check.size != (256, 256) or check.convert("RGBA").tobytes() != image.tobytes():
                raise ValueError("Staged PNG roundtrip differs from decoded source")
        examples = [dict(frame=row.get("frame"), uv_bounds=row.get("uv_bounds"),
            page_xy=row.get("page_xy"), clut_xy=row.get("clut_xy"), xy=row.get("xy"))
            for row in rows if row.get("key") == key and row.get("source_kind") == "native_page"][:3]
        results.append(dict(key=key, png=str(destination), png_sha256=sha(destination.read_bytes()),
            source_size=[256, 256], output_size=[256, 256], resampled=False,
            source_words=dict(path=str(page["path"]), sha256=sha(words), crc32=crc(words),
                              independently_validated_original_png=str(page["original_png"])),
            source_clut=dict(path=str(palette["path"]), sha256=sha(palette["data"]), crc32=crc(palette["data"])),
            copied_source_bundle=str(source_dir / (key + ".source.json")),
            alpha_class_counts=dict(Counter(image.getchannel("A").tobytes())),
            source_decode_and_png_roundtrip_verified=True, observed_query_examples=examples,
            actor_ownership_verified=False, replacement_draw_verified=False,
            quality="original-resolution source admission proof only"))
    source_files = [Path(__file__), PROJECT / "remaster-audit/build_three_asset_proof.py",
                    PROJECT / "remaster-audit/extract_disc_stock.py"]
    manifest = dict(format=1, staged_at_utc=datetime.now(timezone.utc).isoformat(),
        purpose="Isolated source-admission proof supplement; no finished remaster or actor ownership acceptance",
        installed=False, game_or_process_actions=0, existing_pack_modified=False,
        capture_path=str(capture_path), capture_sha256=sha(capture_path.read_bytes()),
        finalized_run_manifest_sha256=sha((run / "manifest.json").read_bytes()),
        palette_files_scanned=scanned, observed_native_page_keys=len(wanted),
        recoverable_pairs=len(results), missing_keys=missing, files=results,
        pack_root=str(replacement_dir.parent), pack_scope="Only these native-page candidates; use an isolated test or compose with the base pack before full-game use.",
        source_scripts=[dict(path=str(path), sha256=sha(path.read_bytes())) for path in source_files],
        runtime_registry=dict(refresh_supported=False,
            reason="hd_texture_pack_create enumerates PNGs once into entries; request_decode only looks up those entries. No existing public refresh/register API.",
            next_step="Launch an isolated session referencing a composed candidate pack or recreate the pack via a deliberate runtime change; new files alone do not affect the running pack."),
        acceptance_pending=["Actual replacement GL submissions for each relevant page/palette", "Exact source/UV mapping and no unrelated actor/HUD/environment changes", "Per-part material scope and original stripe/glow behavior", "Temporal/palette-cycle and motion validation", "Authored high-resolution artwork and quality review"],
        limitations=["Word and palette components can come from different captures; exact CRC and full byte provenance establish content identity, not same-frame coherence.", "These are candidate Greif page families from visual/source evidence; shared atlas regions may belong to other objects.", "All output pixels are deterministic original-source decode, with original0/127/255 alpha/STP classes; no upscale or invented detail.", "This pack is staged only and does not alter the running or installed pack."])
    path = output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(manifest=str(path), observed=len(wanted), staged=len(results), missing=missing,
                         pack_root=str(replacement_dir.parent), installed=False)))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
