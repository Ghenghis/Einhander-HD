"""Prepare source-bound S1 dark/light facade comparisons without launching.

The source masters are 4096 square; runtime replacements deliberately match
the other A/B trials at 2048 square. Existing builders, artwork and parent
files are read-only. Outputs are versioned and must not already exist.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from PIL import Image

import build_facade_ab_candidates as base


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
OUTPUT = AUDIT / "dev-center-evidence/facade-tonal-ab-20261112"
AUTHORING = AUDIT / "comfy-authoring/facade-v3-architecture"
REGISTRY = AUDIT / "world-sign-mapping/building-coverage-registry-v1.json"
VARIANTS = {"dark": 4377, "light": 4378}
RUNTIME_SIZE = 2048


def configure():
    base.OUTPUT = OUTPUT
    base.VARIANTS = dict(VARIANTS)
    base.SIZE = RUNTIME_SIZE


def checked_inputs(variant):
    directory = AUTHORING / variant
    manifest_path = directory / "s1-manifest.json"
    manifest = base.read(manifest_path)
    if manifest.get("variant") != variant or manifest.get("exact_key") != base.KEY or manifest.get("size") != [4096, 4096]:
        raise ValueError("S1 source manifest identity differs: " + variant)
    refs = [base.ref(manifest_path)]
    for name, expected in manifest["files"].items():
        path = directory / name
        if path.parent != directory or base.ui.sha(path) != expected:
            raise ValueError("S1 authoring input hash differs: " + name)
        with Image.open(path) as image:
            image.load()
            if image.size != (4096, 4096):
                raise ValueError("S1 master dimensions differ: " + name)
        refs.append(base.ref(path))
    for field in ("layout", "native"):
        path = Path(manifest[field])
        if base.ui.sha(path) != manifest[field + "_sha256"]:
            raise ValueError("S1 source registration differs: " + field)
        refs.append(base.ref(path))
    return manifest_path, directory / "s1-albedo-4096.png", refs


def unchanged(receipts):
    for receipt in receipts:
        if base.ui.sha(receipt["path"]) != receipt["sha256"]:
            raise ValueError("Read-only preparation input changed: " + receipt["path"])


def verify_variant(variant):
    configure()
    report = base.read(OUTPUT / variant / "candidate.json")
    result = base.check(report)
    proof = report["preparation_wrapper"]
    unchanged(proof["immutable_inputs"])
    if proof["wrapper"] != base.ref(__file__):
        raise ValueError("Preparation wrapper differs from recorded version")
    if report["debug_port"] != VARIANTS[variant] or report["registration"]["runtime_dimensions"] != [2048, 2048]:
        raise ValueError("Tonal port or runtime resolution differs")
    if report["authoring_input"]["dimensions"] != [4096, 4096]:
        raise ValueError("Tonal source master dimensions differ")
    parent = base.read(base.PARENT / "candidate.json")
    current = {row["name"]: row for row in report["files"]}
    for row in parent["files"]:
        target = current[row["name"]]
        if target["sha256"] != row["sha256"] or not Path(target["composed_path"]).samefile(row["composed_path"]):
            raise ValueError("Parent replacement was not preserved: " + row["name"])
    target = OUTPUT / variant / "pack/einhander-texture-replacements" / (base.KEY + ".png")
    with Image.open(target) as image:
        image.load()
        pixels = np.asarray(image.convert("RGBA"))
    result.update(source_master_dimensions=[4096, 4096], runtime_dimensions=[2048, 2048],
                  native_alpha_classes=sorted(int(x) for x in np.unique(pixels[:, :, 3])),
                  wrapper_sha256=proof["wrapper"]["sha256"], immutable_input_files=len(proof["immutable_inputs"]),
                  parent_hardlinks_preserved=1194, launched=False)
    return result


def prepare_variant(variant):
    configure()
    manifest, image, inputs = checked_inputs(variant)
    inputs += [base.ref(base.__file__), base.ref(base.PARENT / "candidate.json"), base.ref(base.SOURCE / "manifest.json")]
    wrapper = base.ref(__file__)
    base.prepare(variant, image, manifest)
    unchanged(inputs)
    report_path = OUTPUT / variant / "candidate.json"
    report = base.read(report_path)
    report["preparation_wrapper"] = dict(wrapper=wrapper, immutable_inputs=inputs,
        source_master_dimensions=[4096, 4096], runtime_dimensions=[2048, 2048],
        method="Existing facade A/B builder; S1 dark/light inputs with equal 2048 runtime registration")
    report["native_4k_authored"] = False
    report["source_master_is_4096_structural_art"] = True
    report["authoring_stage"] = "S1 structural/lighting base; material and live visual acceptance pending"
    report["known_limits"] = ["4096 source master is packed at 2048 for equal A/B comparison",
        "Structural lighting base does not establish finished material detail or accepted realism",
        "Dark/light variants are authored alternatives, not decoded native lighting states",
        "No PBR/HDR engine claim; lighting is baked RGB",
        "Exact-region draw readiness, near/far, partial bands, seams and scrolling require live review"]
    base.write(report_path, report)
    result = verify_variant(variant)
    base.write(OUTPUT / variant / "wrapper-preparation-verification.json", result)
    return dict(variant=variant, port=VARIANTS[variant], candidate=base.ref(report_path), verification=result)


def building_registry(preparations):
    if REGISTRY.exists():
        raise ValueError("Immutable building registry already exists")
    gap_path = AUDIT / "background-audit-20261112/stage1-background-gap-inventory.json"
    backlog_path = AUDIT / "background-audit-20261112/world-source-backlog-revalidation.json"
    patterns_path = AUDIT / "dev-center-evidence/stage1-source-patterns.json"
    native_path = base.SOURCE / "manifest.json"
    draws_path = base.SOURCE / "actual-draw-receipts.json"
    guide_path = AUDIT / "world-sign-mapping/facade-semantic-layout-v3.json"
    gap, native, draws, guide = (base.read(p) for p in (gap_path, native_path, draws_path, guide_path))
    parent = base.read(base.PARENT / "candidate.json")
    parent_keys = {r["name"][:-4] for r in parent["files"]}
    families = []
    for family in gap["family_inventory"]:
        keys = family["known_queue_palette_keys"]
        families.append(dict(texture_crc32=family["texture_crc32"], palette_keys=keys,
            palette_key_count=len(keys), current_parent_present_keys=sorted(set(keys) & parent_keys),
            sampled_native_source=family["sample_source"],
            source_validation="Attributed historical raw/CLUT/validity/independent decode checks; not rerun by this registry",
            candidate_content_review=family["source_content_review"], ownership_verified=False,
            layers=[], layer_assignment_status="unmapped", building_count=None,
            protected_native_uv_half_open=family["protected_native_uv_rectangles_half_open"],
            historical_draw_counts=family["historical_finalized_capture_technical_evidence"],
            historical_distinct_uv_rectangles=family["baseline_distinct_observed_uv_rectangles"],
            draw_witness_examples=family["exact_draw_witness_examples"]))
    known_keys = {key for family in families for key in family["palette_keys"]}
    kinds = Counter(d["event"] for d in draws)
    bounds = [(max(v[0] for v in d["xy"])-min(v[0] for v in d["xy"]),
               max(v[1] for v in d["xy"])-min(v[1] for v in d["xy"])) for d in draws]
    result = dict(schema_version=1, created_at_utc=base.ui.stamp(),
        status="incomplete_source_referenced_seed_registry_not_exhaustive_building_census",
        scope="Stage 1 architectural source candidates and one bounded facade tile; no full-game or full-layer acceptance",
        builder=base.ref(__file__), game_actions=0, art_or_runtime_mutations=False,
        evidence={name:base.ref(path) for name,path in (
            ("historical_gap_audit",gap_path),("source_backlog",backlog_path),("source_patterns",patterns_path),
            ("facade_source",native_path),("facade_draws",draws_path),("semantic_guide",guide_path),
            ("current_parent",base.PARENT/"candidate.json"))},
        counts=dict(mixed_source_families=len(families), known_palette_keys=len(known_keys),
            present_in_current_parent=len(known_keys & parent_keys), bounded_facade_regions=1,
            verified_complete_buildings=None, verified_placements=None, verified_parallax_layers=None,
            verified_skyline_sources=0, accepted_ordered_environment_cycles=0),
        count_contract=["Pages, CLUT variants, UV rectangles, draw events and buildings have different units",
            "Near/mid/far ownership cannot be inferred from a filename or projected size alone",
            "Shared source words establish reuse, not a complete object model or animation loop",
            "All sizes, faces, routes, lit/unlit windows, occlusion and temporal states remain in scope"],
        source_families=families,
        mapped_regions=[dict(id="stage1/facade/blue-window-tile", fullpage_key=native["original_fullpage_key"],
            exact_key=native["cropped_exact_source_key"], native_dimensions=native["native_dimensions"],
            uv_half_open=native["source_uv_half_open"], physical_source_rect_words=native["physical_source_rect_words"],
            clut_xy=native["clut_xy"], depth=native["depth"],
            source_proof=native["source_proof"], status="bounded_source_mapped_art_not_live_accepted",
            draw_event_counts=dict(kinds), frame_range=[min(d["frame"] for d in draws),max(d["frame"] for d in draws)],
            observed_uv_bounds_inclusive=native["actual_uv_variants"],
            projected_vertex_bbox_range=dict(width=[min(x[0] for x in bounds),max(x[0] for x in bounds)],
                                             height=[min(x[1] for x in bounds),max(x[1] for x in bounds)]),
            layer=None, placement_count=None, window_model_count=None,
            visible_blue_source_groups=guide["visible_blue_groups"],
            structural_regions_approximate=guide["structural_regions_approximate"],
            uv_cuts_are_proven_floor_boundaries=False, source_group_confidence=guide["confidence"],
            palette_guard=native["palette_guard"], repeat_notes=native["repeat_and_uv_notes"],
            alpha_contract=guide["corrected_psx_policy"], mipmaps=native["mipmaps"],
            authoring_comparisons=preparations, authoring_comparisons_are_native_light_states=False)],
        unmapped=[dict(id="stage1/"+name,status="unmapped",verified_keys=[],complete_count=None,
                       capture_needed=work) for name,work in (
            ("near-building-faces","Associate visible faces and changing projections with source/UV/packet identity"),
            ("mid-building-faces","Trace repeated and distinct facades through occlusion and view changes"),
            ("far-buildings-and-skyline","Capture exposed skyline behind passing structures; include an unfiltered discovery segment"),
            ("window-patterns-and-cycles","Separate source design, placement, lit/unlit state and ordered CLUT/geometry modulation"),
            ("roofs-side-faces-and-occluders","Capture all visible roofs, side angles, foreground occluders and route alternatives"),
            ("lights-reflections-and-fog","Distinguish procedural/untextured draws, palette effects and shared weapon/boss sources"))],
        capture_queue=[dict(id="facade-exact",source_keys=[native["original_fullpage_key"],base.KEY],
                           scene="Observed repeated facade field; pair direct visible frames and actual submissions",
                           checks=["partial bands","skew","near/far minification","tile seams","scrolling stability"])] +
            [dict(id="family-"+crc, source_keys=next(f["palette_keys"] for f in families if f["texture_crc32"]==crc),
                  scene="Actual Stage 1 city traversal; semantic owner/layer must be visually paired",
                  source_filter_scope="raw source collection only; not proof of exhaustive coverage")
             for crc in ["73BF9877","95A3BCF8","AB2DB563","AB58BBA4"]] +
            [dict(id="skyline-discovery",source_keys=None,source_policy="bounded-unfiltered",
                  scene="Skyline revealed between and behind passing buildings",
                  checks=["ordered GP0/state/source bracket","visible occlusion correspondence","cross-frame parallax",
                          "record newly discovered sources before narrowing filters"])],
        remaining=["Complete Stage 1 plus applicable routes and all building sizes/angles/window states",
            "Discover and map skyline and far layers independently of the pilot",
            "Link every authored region to exact source/palette/UV and final runtime submissions",
            "Compare light/medium/dark alternatives at equal runtime resolution while scrolling",
            "Full-game environmental inventory and repeated omission sweeps remain open"])
    if len(families)!=10 or len(known_keys)!=324 or len(known_keys & parent_keys)!=324:
        raise ValueError("Historical/current technical inventory differs; refresh registry inputs")
    if kinds != Counter(source_draw_query_matched=23,replacement_gl_draw_submitted=23):
        raise ValueError("Facade draw evidence differs")
    base.write(REGISTRY,result)
    assert base.read(REGISTRY)==result
    return base.ref(REGISTRY)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant",choices=[*VARIANTS,"all"],nargs="?",default="all")
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--registry",action="store_true",help="Write the new source-referenced building registry after both preparations")
    args=parser.parse_args()
    selected=list(VARIANTS) if args.variant=="all" else [args.variant]
    if args.registry and selected!=list(VARIANTS):
        parser.error("--registry requires both tonal preparations")
    if not args.check:
        for variant in selected:
            checked_inputs(variant)
            if (OUTPUT/variant).exists():raise ValueError("Immutable variant already exists: "+variant)
    results=[dict(variant=v,port=VARIANTS[v],verification=verify_variant(v)) if args.check else prepare_variant(v) for v in selected]
    summary=dict(ok=True,wrapper=base.ref(__file__),source_master_dimensions=[4096,4096],
                 runtime_dimensions=[2048,2048],variants=results,game_actions=0,launched=False)
    if not args.check:base.write(OUTPUT/"preparation-summary.json",summary)
    if args.registry:summary["building_registry"]=building_registry(results)
    print(json.dumps(summary),flush=True)


if __name__=="__main__":main()
