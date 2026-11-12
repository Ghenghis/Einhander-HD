"""Reconcile boss atlas/strip identities without changing packs or live settings.

Exact indexed-word equality establishes a texture-layout relationship, not actor
ownership. Palette equality and complete source validation are separate checks.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zlib

PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "remaster-audit/dev-center-evidence"
RUNS = PROJECT / "windows-x64/tools/research-runs"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def placements(page: bytes, page_width: int, width: int, height: int,
               words: bytes) -> list[list[int]]:
    """Find complete 2D word rectangles; no similarity/CRC-only matches."""
    if min(page_width, width, height) <= 0 or len(page) % (page_width * 2):
        return []
    if len(words) != width * height * 2 or width > page_width:
        return []
    page_height = len(page) // (page_width * 2)
    if height > page_height:
        return []
    row_bytes = width * 2
    first = words[:row_bytes]
    answer = []
    offset = -1
    while True:
        offset = page.find(first, offset + 1)
        if offset < 0:
            break
        if offset % 2:
            continue
        y, x_bytes = divmod(offset, page_width * 2)
        x = x_bytes // 2
        if x + width > page_width or y + height > page_height:
            continue
        if all(page[offset + row * page_width * 2:
                    offset + row * page_width * 2 + row_bytes] ==
               words[row * row_bytes:(row + 1) * row_bytes]
               for row in range(height)):
            answer.append([x, y, width, height])
    return answer


def checked_source(path: Path) -> tuple[dict, bytes, bytes]:
    meta = json.loads(path.read_bytes())
    key = meta["key"]
    base = path.parent
    words = (base / (key + ".words.bin")).read_bytes()
    palette = (base / (key + ".clut.bin")).read_bytes()
    valid = (base / (key + ".valid.bin")).read_bytes()
    count = meta["width_words"] * meta["height"]
    if (len(words) != count * 2 or len(valid) != count or not all(v == 1 for v in valid)
            or meta["known_words"] != count or meta["total_words"] != count):
        raise ValueError("source incomplete or malformed")
    if f"{zlib.crc32(words):08X}" != key.split("-")[0]:
        raise ValueError("word CRC mismatch")
    if palette and f"{zlib.crc32(palette):08X}" != key.split("-")[1]:
        raise ValueError("palette CRC mismatch")
    if len(palette) != meta["clut_words"] * 2:
        raise ValueError("palette dimensions mismatch")
    return meta, words, palette


def read_sources() -> tuple[dict, list[dict]]:
    result = {}
    rejected = []
    for path in sorted(RUNS.glob("*/native/*.source.json")):
        # Finalized directories only: an in-progress source can change while read.
        if not (path.parent.parent / "manifest.json").is_file():
            continue
        try:
            meta, words, palette = checked_source(path)
        except (ValueError, KeyError, OSError) as exc:
            rejected.append(dict(path=str(path), reason=str(exc)))
            continue
        key = meta["key"]
        old = result.get(key)
        if old and (old["words"] != words or old["palette"] != palette):
            raise ValueError("Conflicting complete source identity: " + key)
        result[key] = dict(meta=meta, words=words, palette=palette,
                           path=str(path), words_sha256=sha(words), palette_sha256=sha(palette))
    return result, rejected


def atlas_pages() -> dict:
    report = json.loads((EVIDENCE / "drache-visual-source-review.json").read_bytes())
    pages = {}
    # The inspected historical full-page components have independent raw CRC
    # verification; their original palette is not assumed valid for every draw.
    paths = [Path(row["png"]).with_suffix(".source.json")
             for row in report["original_atlas_verification"]
             if row["semantic"] != "environment_excluded_from_boss_binding"]
    for row in report["source_component_decodes"]:
        paths.append(Path(row["source_words"]).with_name(
            Path(row["source_words"]).name.replace(".words.bin", ".source.json")))
    for path in paths:
        meta, words, palette = checked_source(path)
        family = meta["key"].split("-")[0]
        if family in pages and pages[family]["words"] != words:
            raise ValueError("Conflicting atlas family words")
        pages[family] = dict(meta=meta, words=words, path=str(path),
                              words_sha256=sha(words), original_palette_sha256=sha(palette))
    return pages


def static_material_contract() -> dict:
    header = PROJECT / "windows-x64/psxrecomp/runtime/src/hd_skin_material.h"
    text = header.read_text(encoding="utf-8")
    player = ["5CC44E5F-053D9A00"]
    player_block = text.split("hd_skin_player_keys[] = {", 1)[1].split("};", 1)[0]
    enemy_block = text.split("hd_skin_enemy_keys[] = {", 1)[1].split("};", 1)[0]
    pair = re.compile(r"\{0x([A-Fa-f0-9]{8})u,0x([A-Fa-f0-9]{8})u\}")
    player += [a.upper() + "-" + b.upper() for a, b in pair.findall(player_block)]
    enemy = [a.upper() + "-" + b.upper() for a, b in pair.findall(enemy_block)]
    return dict(path=str(header), sha256=sha(header.read_bytes()), player_keys=player,
                enemy_keys=enemy, boss_keys_allowlisted=[],
                live_set_fields=["player_profile", "player_strength_percent",
                                 "enemy_profile", "enemy_strength_percent", "diagnostic_player_keys",
                                 "diagnostic_enemy_keys", "preserve_accents"],
                next_launch_only=["configured key scope", "authored detail map", "detail strength", "detail scale"],
                temporary_diagnostic_scope=dict(max_keys_per_channel=8, resident_replacement_required=True,
                    animated_effect_families_rejected=True, detail_disabled=True,
                    reset_value="configured", ownership_status="candidate_only"),
                preserves_source_luma=True, preserves_original_warm_stripe_RGB="optional preserve_accents; default false",
                effects_keys_excluded=["E584DC41-*", "1FD36785-*"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        # Word-aligned 2D crop, rejected row-wrap false positive, repeated zero
        # region ambiguity, corrupt/short payload and too-large crop.
        page = bytes(range(32))
        crop = page[10:14] + page[18:22]
        assert placements(page, 4, 2, 2, crop) == [[1, 1, 2, 2]]
        assert placements(page, 4, 2, 1, page[6:10]) == []
        assert len(placements(bytes(32), 4, 2, 1, bytes(4))) == 12
        assert placements(page, 4, 2, 2, crop[:-1]) == []
        assert placements(page, 4, 5, 1, bytes(10)) == []
        assert placements(page[:-1], 4, 2, 1, bytes(4)) == []
        print(json.dumps(dict(checks=6, failures=0)))
        return 0

    sources, rejected = read_sources()
    pages = atlas_pages()
    palette_families = defaultdict(set)
    for key, source in sources.items():
        palette_families[sha(source["palette"])].add(key.split("-")[1])
    aliases = []
    for family, page in sorted(pages.items()):
        for key, source in sorted(sources.items()):
            m = source["meta"]
            if m["depth"] != page["meta"]["depth"] or m["height"] >= page["meta"]["height"]:
                continue
            found = placements(page["words"], page["meta"]["width_words"],
                               m["width_words"], m["height"], source["words"])
            if not found:
                continue
            aliases.append(dict(atlas_family=family, upload_key=key,
                                word_rectangles=found, unambiguous_layout=len(found) == 1,
                                source_path=source["path"],
                                source_words_sha256=source["words_sha256"],
                                palette_sha256=source["palette_sha256"],
                                decoded_pixel_scale=4 >> m["depth"],
                                independently_crc_valid=True,
                                actor_ownership_verified=False,
                                candidate_only=True))

    wanted = {row["upload_key"] for row in aliases}
    counts = defaultdict(Counter)
    uv = defaultdict(set)
    ranges = defaultdict(list)
    by_run = defaultdict(lambda: defaultdict(lambda: dict(counts=Counter(), frames=[], examples=[])))
    for path in sorted(RUNS.glob("*/native/capture.jsonl")):
        if not (path.parent.parent / "manifest.json").is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = row.get("key")
            if key not in wanted:
                continue
            counts[key][row.get("event", "unknown")] += 1
            scoped = by_run[key][path.parent.parent.name]
            scoped["counts"][row.get("event", "unknown")] += 1
            if len(scoped["examples"]) < 2:
                scoped["examples"].append(dict(path=str(path), frame=row.get("frame"),
                    event=row.get("event"), uv_bounds=row.get("uv_bounds"), xy=row.get("xy"),
                    source_word_xy=row.get("source_word_xy"), page_xy=row.get("page_xy"),
                    clut_xy=row.get("clut_xy")))
            if row.get("uv_bounds"):
                uv[key].add(tuple(row["uv_bounds"]))
            if isinstance(row.get("frame"), int):
                ranges[key].append(row["frame"])
                scoped["frames"].append(row["frame"])
    for row in aliases:
        key = row["upload_key"]
        row["retained_draw_events"] = dict(counts[key])
        row["sampled_uv_bounds"] = [list(v) for v in sorted(uv[key])]
        row["observed_frame_range"] = [min(ranges[key]), max(ranges[key])] if ranges[key] else None
        row["frame_range_scope"] = "aggregate numerical extrema; separate processes/runs are not one timeline"
        row["run_observations"] = [dict(run=run, counts=dict(obs["counts"]),
            frame_range=[min(obs["frames"]), max(obs["frames"])] if obs["frames"] else None,
            examples=obs["examples"]) for run, obs in sorted(by_run[key].items())]
    contract = static_material_contract()
    for row in aliases:
        row["material_allowlisted"] = row["upload_key"] in contract["player_keys"] + contract["enemy_keys"]
    report = dict(format=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  method="Complete-source CRC validation and exact word-by-word 2D rectangle matching; read-only captures/static code, no engine calls or pack/settings writes.",
                  material_contract=contract,
                  atlas_families=[dict(family=k, source=v["path"], words_sha256=v["words_sha256"],
                                       dimensions_words=[v["meta"]["width_words"], v["meta"]["height"]])
                                  for k, v in sorted(pages.items())],
                  summary=dict(complete_distinct_source_keys=len(sources),
                               skipped_incomplete_or_invalid_occurrences=len(rejected),
                               exact_atlas_upload_aliases=len(aliases),
                               unambiguous_aliases=sum(row["unambiguous_layout"] for row in aliases),
                               aliases_with_replacement_submission=sum(bool(row["retained_draw_events"].get("replacement_gl_draw_submitted")) for row in aliases),
                               aliases_allowlisted_for_material=sum(row["material_allowlisted"] for row in aliases)),
                  aliases=aliases, rejected_sources=rejected,
                  root_causes=[
                      "Recorder quota and sampling omissions do not explain every unskinned part: the material allowlist contains no boss source keys.",
                      "Full-page native queries and actual upload-strip replacements have different texture CRCs; atlas/strip relations must be resolved before deciding a source is absent.",
                      "Palette CRC changes can represent lighting/damage/palette cycling of one indexed source; they do not automatically identify another model or phase.",
                      "Original live setters could not alter target keys. The updated source supports reversible exact resident-key diagnostic scopes, without changing configured ownership; the rebuilt runtime must be installed and gameplay-tested to use them.",
                      "The color shader keeps source luma. Existing behavior remaps warm stripes to profile accent; the new optional preserve_accents gate protects orange/yellow source colors in palette and detail passes. Brightness/emission remains separate."
                  ],
                  required_acceptance=[
                      "Fresh targeted source capture at boss entry, followed by source/CLUT integrity validation and same-encounter draw correlation.",
                      "Original versus player-only versus enemy-only versus combined output with matched gameplay state and settings; verify every visible hull part.",
                      "Part/UV-specific exclusion or original-accent mask before broad boss recolor; exclude environment, HUD and animated effects.",
                      "Isolated no-fire/fire/hit sequences to identify transient glow and weapon effects, then phase and palette-variant repetition.",
                      "Renderer CPU/GPU alpha/STP regression checks, followed by live visual/motion validation; no automatic ownership promotion from aliases."
                  ],
                  limitations=["Layout equality is not actor identity or exclusivity.",
                               "Source files and draw records can originate from different frames; this report does not claim atomic synchronization.",
                               "Only complete finalized sources are matched. Missing aliases do not prove an actor lacks a texture.",
                               "All rows remain candidates. This report does not install or approve any new material target."])
    out = EVIDENCE / "skin-source-alias-audit.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(out), **report["summary"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
