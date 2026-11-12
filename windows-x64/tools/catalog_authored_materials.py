"""Record facts about unchanged image_gen material assets; never resize them."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent / "skin_collection" / "materials"
SOURCES = {
    "gold-obsidian-engraved": ("Engraved Gold / Obsidian", "exec-5b3cbefd-fcf1-40e2-b2f2-774873582617.png"),
    "titanium-teal-nanoceramic": ("Titanium / Teal Nanoceramic", "exec-75096fdd-0cf4-4860-ac5b-9454f1b3fc78.png"),
    "crimson-gold-plating": ("Crimson / Gold Plating", "exec-0431f8d9-6b00-475a-9695-6406ab509420.png"),
    "neon-circuit-tracery": ("Neon Circuit Tracery", "exec-5e7b9878-248d-45c9-b43a-74730b3cc357.png"),
    "ultraviolet-plasma-grid": ("Ultraviolet Plasma Grid", "exec-4f12164a-69a7-4400-b767-db9a35d9546c.png"),
    "reactor-lime-hazard": ("Reactor Lime Hazard", "exec-36271938-f47c-4670-9862-4bdf4c42124d.png"),
}
GENERATED = Path("C:/Users/Admin/.codex/generated_images/01a1cfe7-48b2-7bc2-b23b-61c1086ea69e")


def rms(left, right):
    return math.sqrt(sum((a-b)**2 for a, b in zip(left, right)) / max(1, len(left)))


def main():
    prompts = json.loads((ROOT / "prompts.json").read_text(encoding="utf-8"))
    supplemental = ROOT / "neon-prompts.json"
    if supplemental.is_file():
        identities = {item["id"] for item in prompts["assets"]}
        prompts["assets"].extend(item for item in json.loads(supplemental.read_text(encoding="utf-8"))["assets"] if item["id"] not in identities)
        (ROOT / "prompts.json").write_text(json.dumps(prompts, indent=2) + "\n", encoding="utf-8")
    maps = []
    for identity, (label, filename) in SOURCES.items():
        path = ROOT / (identity + ".png")
        original = GENERATED / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != hashlib.sha256(original.read_bytes()).hexdigest():
            raise ValueError("Project asset differs from its original image_gen PNG: " + identity)
        with Image.open(path) as image:
            image.load()
            rgb = image.convert("RGB")
            width, height = rgb.size
            left = rgb.crop((0, 0, 1, height)).tobytes()
            right = rgb.crop((width-1, 0, width, height)).tobytes()
            top = rgb.crop((0, 0, width, 1)).tobytes()
            bottom = rgb.crop((0, height-1, width, height)).tobytes()
            opaque = image.convert("RGBA").getchannel("A").getextrema() == (255, 255)
            maps.append(dict(id=identity, label=label, width=width, height=height, mode=image.mode, opaque=opaque,
                             category="Neon-Cyberpunk" if identity in ("neon-circuit-tracery", "ultraviolet-plasma-grid", "reactor-lime-hazard") else "Vibrant-Elemental" if identity == "titanium-teal-nanoceramic" else "Gold",
                             image="/files/tools/skin_collection/materials/" + identity + ".png",
                             url="/files/tools/skin_collection/materials/" + identity + ".png", sha256=digest, bytes=path.stat().st_size,
                             source_generated_path=str(original), unchanged_generated_png=True, native_4k=width >= 3840 and height >= 3840,
                             usage="Optional RGB-only shader microdetail on allowlisted atlas keys; source texture alpha/STP remains authoritative",
                             wrap="mirrored_repeat", strength_default=0.12, scale_default=8,
                             seam_review=dict(opposite_edges_identical=left == right and top == bottom,
                                              horizontal_rgb_rms_0_255=round(rms(left, right), 3), vertical_rgb_rms_0_255=round(rms(top, bottom), 3),
                                              strategy="Mirrored repeat provides continuous edge sampling without modifying the authored PNG"),
                             visually_reviewed=True, in_game_verified=False,
                             prompt=next(item["prompt"] for item in prompts["assets"] if item["id"] == identity)))
    result = dict(schema_version=1, contract="ein-material-v3", generated_with="built-in image_gen", requested_dimensions=[4096, 4096],
                  maps=maps, status="Authored RGB material assets; native gameplay acceptance pending", limitations=[
                      "Actual PNG dimensions are measured; files are unchanged and are not upscaled to claim 4K.",
                      "Generated opposite edges are not guaranteed identical. Runtime and preview must use mirrored repeat, not ordinary repeat.",
                      "These images provide RGB surface detail, not normal, roughness, depth, PBR or mesh data.",
                      "Base-game UVs, texture ownership and alpha/STP classes remain authoritative. No game process was launched."])
    (ROOT / "materials.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(count=len(maps), assets=[dict(id=row["id"], dimensions=[row["width"], row["height"]], sha256=row["sha256"], seam_review=row["seam_review"]) for row in maps]), indent=2))


if __name__ == "__main__":
    main()
