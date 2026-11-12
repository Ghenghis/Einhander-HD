"""Produce provenance and scoped handoff inputs, without controlling a game."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def reference(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def evidence_refs(value):
    found = {}
    def visit(node):
        if isinstance(node,dict):
            if isinstance(node.get("path"),str) and node.get("sha256"):
                path = Path(node["path"])
                if not path.is_absolute():
                    path = ROOT / path
                found[str(path)] = dict(path=str(path),sha256=node["sha256"])
            for child in node.values():
                visit(child)
        elif isinstance(node,list):
            for child in node:
                visit(child)
    visit(value)
    return list(found.values())


def main():
    base_path = ROOT / "windows-x64/hd-textures/stage1-v1/manifest.json"
    base = load(base_path)
    base_rows = {row["key"]:row for row in base["files"]}
    check_path = AUDIT / "hud-restoration/final-composition-check.json"
    check = load(check_path)
    selected = {key:dict(key=key,sha256=row["sha256"],origin="base",source_groups=["base"],
        base_method=row["method"],base_neural_detail=row["neural_detail"],base_png_replaced=False)
        for key,row in base_rows.items()}
    seen = {}
    overlay_manifests = {}
    inputs = []
    duplicate_identical = []
    duplicate_override = []
    order = ("hud","menu","extra_menu","font_strip","art","copyright","banner_font",
             "blueprint","diagram","results_palette","results_art")
    for group in order:
        receipt = check["overlay_manifests"][group]
        path = Path(receipt["path"])
        if reference(path)["sha256"] != receipt["sha256"]:
            raise ValueError("Final overlay manifest changed: "+group)
        doc = load(path)
        rows = doc.get("files",doc.get("assets",[]))
        if not rows and doc.get("key") and doc.get("outputs"):
            rows = [doc]
        if len(rows) != receipt["asset_count"]:
            raise ValueError("Final overlay asset count changed")
        overlay_manifests[group] = dict(**reference(path),asset_count=len(rows),
            contract=doc.get("contract"),method=doc.get("method"),live_acceptance=doc.get("live_acceptance",doc.get("live_accepted")))
        for row in rows:
            key = row["key"]
            output = row["outputs"]["pack"] if row.get("outputs") else row
            digest = output["sha256"]
            item = dict(key=key,sha256=digest,origin=group,path=output["path"],source_groups=[group],
                native_regions=row.get("selected_native_regions",row.get("restored_native_regions",row.get("region_half_open",row.get("regions")))),
                role=row.get("role",row.get("roles")),kind=row.get("kind"),manifest=str(path),
                base_method=base_rows.get(key,{}).get("method"),base_neural_detail=base_rows.get(key,{}).get("neural_detail"),
                base_png_replaced=key in base_rows)
            inputs.append(dict(key=key,sha256=digest,group=group))
            previous = seen.get(key)
            if previous and previous["sha256"] == digest:
                previous["source_groups"].append(group)
                duplicate_identical.append(dict(key=key,kept=previous["origin"],redundant=group))
                continue
            if previous:
                if previous["origin"] != "menu" or group not in {"copyright","diagram"}:
                    raise ValueError("Unexpected differing overlay duplicate")
                duplicate_override.append(dict(key=key,parent="menu",replacement=group,native_regions=item["native_regions"]))
                item["source_groups"] = previous["source_groups"]+[group]
            seen[key] = item
            selected[key] = item
    if len(selected) != check["final_count"]:
        raise ValueError("Reconstructed composition differs from validated final count")
    prepared_path = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6/candidate.json"
    prepared = load(prepared_path)
    if {row["name"][:-4]:row["sha256"] for row in prepared["files"]} != {key:row["sha256"] for key,row in selected.items()}:
        raise ValueError("Prepared v6 keys/hashes differ from reconstructed provenance")
    untouched = [row for row in selected.values() if row["origin"]=="base"]
    base_methods = dict(Counter(row["method"] for row in base_rows.values()))
    untouched_methods = dict(Counter(row["base_method"] for row in untouched))
    overlap = sorted(set(seen)&set(base_rows))
    new = sorted(set(seen)-set(base_rows))
    current_actor_launch = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v5/launch-candidate.json"
    launch = load(current_actor_launch)
    actor_settings = {key:value for key,value in launch["environment_overrides"].items() if key.startswith("PSXRECOMP_SKIN")}
    historical_path = AUDIT / "dev-center-evidence/stage1-coverage-ledger.json"
    historical = load(historical_path)
    catalog_path = ROOT / "windows-x64/tools/research_catalog.json"
    catalog = load(catalog_path)
    components = []
    for row in historical["component_requirements"]:
        components.append({**{k:row.get(k) for k in ("id","label","acceptance_scope","evidence_tier","candidate_keys","acceptance_met","semantic_mapping_verified","remaining","qualification")},
                           "source_ledger":str(historical_path),"evidence_locations":evidence_refs(row)})
    tasks = [{k:row.get(k) for k in ("id","label","category","catalog_verification_state","evidence_tier","candidate_keys","acceptance_met","remaining","qualification")}
             for row in historical["tasks"]]
    current_ui_path = AUDIT / "hud-restoration/e2e-coverage.json"
    ui = load(current_ui_path)
    expanded_path = Path("C:/github/REMASTER_STAGING/full-remaster/stage1-expanded/manifest.json")
    world_batch_path = Path("C:/github/REMASTER_STAGING/full-remaster/world-machines/manifest.json")
    expanded = load(expanded_path)
    expanded_rows = {row["key"]:row for row in expanded["files"]}
    world_batch = load(world_batch_path)
    common = set(expanded_rows)&set(selected)
    differing = [key for key in common if expanded_rows[key]["sha256"]!=selected[key]["sha256"]]
    fleet_path = AUDIT / "hud-restoration/fleet-weapon-skin-gap-audit-20261112.json"
    fleet = load(fleet_path)
    background_path = AUDIT / "background-audit-20261112/stage1-background-gap-inventory.json"
    background = load(background_path)
    locations = ["windows-x64/tools/research_catalog.json","windows-x64/tools/enemy_catalog.json",
        "windows-x64/tools/loadout_catalog.json","windows-x64/tools/effects_catalog.json",
        "remaster-audit/dev-center-evidence/skin-mapping.json","remaster-audit/dev-center-evidence/effects-mapping.json",
        "remaster-audit/dev-center-evidence/stage1-coverage-ledger.json","remaster-audit/dev-center-evidence/stage1-targeted-visual-review.json",
        "remaster-audit/dev-center-evidence/greif-finish-wasp-review.json","remaster-audit/dev-center-evidence/drache-visual-source-review.json",
        "remaster-audit/hud-restoration/hud-semantic-map.json","remaster-audit/hud-restoration/gp-panel-primitive-map.json",
        "remaster-audit/menu-restoration/menu-semantic-map.json","windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c",
        "windows-x64/psxrecomp/runtime/src/hd_skin_material.h","windows-x64/psxrecomp/runtime/src/hd_skin_detail.h"]
    scopes = [
        dict(id="player_ships",included=True,current_treatment="Original model geometry; selected source RGB neural upscales and narrowly keyed runtime recolor/detail layers. Final UI overlays add no player model texture replacements.",evidence=["skin-mapping.json","stage1-targeted-visual-review.json","live v5 launch material keys"],remaining="Every starter/hidden craft, body/wing/mechanical/gun separation, all requested finishes and gameplay-visible material generation proof"),
        dict(id="enemy_ships_bosses",included=True,current_treatment="Selected baseline upscales and six-key enemy material channel; source/family identity and reviewed bosses are partial.",evidence=["enemy_catalog.json","stage1-coverage-ledger.json","greif-finish-wasp-review.json","drache-visual-source-review.json"],remaining="Every named enemy family, model component and phase; spawning/destruction/occlusion; later stages"),
        dict(id="weapons_ammo_projectiles",included=True,current_treatment="HUD labels/digits authored and partial Cannon identity/fire evidence; world weapon/effect ownership remains distinct.",evidence=["research_catalog.json:12 gunpod tasks","effects-mapping.json","hud-semantic-map.json"],remaining="All twelve gunpods and built-in guns per craft; upper/lower/spares; muzzle/projectile/impact/recoil/depletion/pickup/drop effects and sound-linked timing"),
        dict(id="signs_lettering_backgrounds",included=True,current_treatment="Many source glyph/sign/palette-cycle assets intentionally nearest-only in the964 base; latest UI typography is separate and does not cover city signs.",evidence=["base manifest method tags","background/sign audit pending from menu agent"],remaining="Exact world-sign wording/UVs and temporal variants; skyline/roads/buildings and all later locations; author only mapped pixels"),
        dict(id="windows_lights_emissive_fx",included=True,current_treatment="Baseline nearest/neural RGB and partial160-palette effects source audit; no complete light/window ownership or ordered-animation acceptance.",evidence=["effects-mapping.json","stage1-coverage-ledger.json"],remaining="Separate windows/light fixtures/emissive sprites from actor/effect atlases; all glow/blink/fade/palette cycles and occlusion"),
        dict(id="animations",included=True,current_treatment="Original animation code/geometry retained. Higher resolution assets and tint settings do not establish animation coverage.",evidence=["effects-mapping.json:zero verified ordered animation sequences in its historical snapshot"],remaining="Ordered per-frame source/draw mapping for ships, weapons, enemies, lights, backgrounds, destruction and all transitions"),
        dict(id="hud_menus_art",included=True,current_treatment="118 unique final overlay keys derived from bounded typography, aliases, diagram/blueprint reconstructions and two restored logical illustrations; many revisions await next-candidate native replay.",evidence=[str(current_ui_path),str(check_path)],remaining="Final combined UI replay; clipping/transparency/motion; Gallery remains locked in legitimate PILOT; durability/ammo/hit/multiplier/life variants"),
        dict(id="whole_game_locations",included=True,current_treatment="Installed pack explicitly covers Stage1 candidate routes; no full-game coverage percentage is established.",evidence=[str(base_path),str(historical_path)],remaining="Multiple native passes across every location and branch, including later-stage actors/art/effects and legitimate unlock-state-dependent screens"),
    ]
    passes = [
        dict(id=1,name="Inventory and source mapping",work="Multiple native observation passes by location/craft/weapon/enemy. Capture source CRC+CLUT+UV, GP0 geometry, frame/state and unambiguous before/after action. Link original source and exact owner; preserve unknowns.",exit="Every visible component has an identified source/region or an explicit unresolved record; no exclusions by category."),
        dict(id=2,name="Authoring and identity review",work="Create genuine contour/detail/art improvements per mapped region, with original wording, palette behavior, silhouette and protected regions. Keep nearest/neural baselines classified by method rather than calling them completed authored4K.",exit="Per-component source/output review plus exact protected pixels/alpha and palette/animation design checks."),
        dict(id=3,name="Native integration and state replay",work="Isolated9x candidate with private cards. Warm required replacement draw admissions, then revisit every mapped component/state in actual gameplay and menus; repeat after fixes.",exit="Real visible assets, no seams/clips/transparency errors, readable at window and2880x2160 export; original animations behave correctly."),
        dict(id=4,name="Coverage and performance reconciliation",work="Repeat traversal and side cases for missed sources, every phase/variant and animated CLUT. Measure single-renderer steady scenes after loading; keep per-scene limits explicit.",exit="All accepted records have source/draw/visual proof; unresolved locations/locked content remain named and no unsupported completion percentage is invented."),
        dict(id=5,name="Reviewable next-scope signoff",work="Present the concrete per-component remaining plan and evidence to the user for the requested next signoff, while completing already authorized final UI integration.",exit="User reviews a bounded next scope with exact targets and acceptance checks; reversible candidate/rollback paths remain available."),
    ]
    result = dict(schema_version=1,generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="incomplete_full_game_remaster_coverage_not_established",scope="Read-only provenance and overall handoff inputs. Expanded scope includes every player/enemy ship, weapon, sign, background, window, light and animation; no category is excluded.",
        count_rule="File keys count palette variants/strip aliases/pages, not unique objects or quality completion. Raster scale9 and high pixel dimensions are not proof of authored detail or every-state acceptance.",
        counts=dict(installed_base_keys=len(base_rows),base_neural_rgb_upscale_keys=sum(row["neural_detail"] is True for row in base_rows.values()),
                    base_nearest_only_keys=sum(row["neural_detail"] is False for row in base_rows.values()),base_method_counts=base_methods,
                    final_key_count=len(selected),overlay_inputs=len(inputs),unique_overlay_keys=len(seen),new_keys=len(new),base_key_replacements=len(overlap),
                    unchanged_base_keys=len(untouched),unchanged_base_method_counts=untouched_methods,chosen_final_origin_counts=dict(Counter(r["origin"] for r in selected.values())),
                    identical_redundant_overlay_inputs=len(duplicate_identical),bounded_differing_overrides=len(duplicate_override),
                    logical_imagegen_illustrations=2,logical_imagegen_page_keys=7,full_game_coverage_percent=None),
        base=reference(base_path),base_scope=base.get("scope"),final_combination=reference(check_path),overlay_manifests=overlay_manifests,
        prepared_next_candidate=dict(receipt=reference(prepared_path),
            revalidation=reference(prepared_path.parent / "preparation-revalidation.json"),
            private_card_seed=reference(prepared_path.parent / "private-card-seed.json"),
            launch_receipt_present=(prepared_path.parent / "launch-candidate.json").exists(),
            qualification="1011prepared PNG keys exactly match these provenance rows; prepared file integrity is separate from native visible acceptance."),
        duplicate_identical=duplicate_identical,authorized_bounded_overrides=duplicate_override,new_key_list=new,replaced_base_key_list=overlap,
        selected_file_provenance=[selected[key] for key in sorted(selected)],
        runtime_materials=dict(launch=reference(current_actor_launch),settings=actor_settings,
            qualification="These are runtime allowlists/tint/detail controls, not additional authored pack files or verified named craft coverage. No indexed palette feature was integrated."),
        historical_gameplay_ledger=dict(**reference(historical_path),generated_at_utc=historical["generated_at_utc"],summary=historical["summary"],
            qualification="Historical16:18 snapshot, not recomputed across later v5/v6 UI runs. Five accepted component requirements have bounded scopes; the61 semantic catalog tasks remain unpromoted in this source."),
        semantic_catalog=dict(**reference(catalog_path),summary=catalog["summary"],qualification="Stored catalog states are conservative and were not promoted merely from captures or source counts."),
        historical_component_requirements=components,historical_task_map=tasks,
        current_ui_ledger=dict(**reference(current_ui_path),screen_states=[{k:r[k] for k in ("id","status","observed","remaining_acceptance")} for r in ui["screen_states"]]),
        last_observed_handoff=ui.get("last_observed_handoff"),
        staged_expanded_candidate=dict(manifest=reference(expanded_path),keys=len(expanded_rows),
            neural_rgb_upscale_keys=sum(row["neural_detail"] is True for row in expanded_rows.values()),
            method_counts=dict(Counter(row["method"] for row in expanded_rows.values())),
            batch_manifest=reference(world_batch_path),batch_keys=len(world_batch["assets"]),
            common_keys_with_final_ui=len(common),different_png_hashes_at_common_keys=len(differing),
            differing_common_keys_by_final_origin=dict(Counter(selected[key]["origin"] for key in differing)),
            expanded_only_keys=len(set(expanded_rows)-set(selected)),final_ui_only_keys=len(set(selected)-set(expanded_rows)),
            union_keys=len(set(expanded_rows)|set(selected)),not_merged=True,
            qualification="Manifest counts, not new independent live acceptance. The558batch includes actors as well as world assets. Reconcile exact source/region/palette identity and conflicts before merging; do not overwrite final UI with stale candidates."),
        fleet_weapon_skin_specialist=dict(**reference(fleet_path),summary=fleet["summary"],facts=fleet["root_facts"]),
        background_sign_window_light_specialist=dict(**reference(background_path),summary=background["summary"],
            provenance_baselines=background["provenance_baselines"],
            qualification="Ten mixed atlas families/324palette identities are not counts of signs/buildings/parallax layers;184are unchanged current base files and140known variants are absent."),
        source_location_index=[reference(ROOT/path) for path in locations if (ROOT/path).is_file()],
        authoritative_completion_plan=reference(AUDIT / "REMASTER_COMPLETION_PLAN.md"),
        all_content_scope=scopes,supplementary_handoff_passes=passes,
        limitations=["893base keys remain unchanged; neither a neural upscale nor nearest resize is a bespoke complete world-art rebuild.",
            "Final118overlay keys include derived aliases and bounded edits; protected/unmapped pixels inside those PNGs are often unchanged.",
            "Known body/effect source ownership is partial; one shared atlas/material channel cannot establish every named craft/weapon/enemy.",
            "Stage1 ledger/catalog are historical and explicitly qualify source/draw observations separately from visual semantic acceptance.",
            "Final UI/art revisions still require native combined-candidate review; GameOver word mapping and dynamic excluded icon palettes remain separate.",
            "Gallery is not accepted while locked; no progressed/unlocked task-owned card fixture was found."])
    out = AUDIT / "overall-remaster-coverage.json"
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(**reference(out),counts=result["counts"])))


if __name__ == "__main__":
    main()
