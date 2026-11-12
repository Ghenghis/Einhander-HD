"""Snapshot the reviewed native UI evidence without controlling a game process."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
V4 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v4"
V3 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v3"
V5 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v5"
V6 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_ref(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "sha256": digest(data), "bytes": len(data)}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def screenshot(version, name):
    folder = {3:V3,4:V4,5:V5}[version]
    path = folder / "captures" / (name + ".png")
    ref = file_ref(path)
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(path)
    ref["width"], ref["height"] = struct.unpack(">II", data[16:24])
    receipt_path = path.with_suffix(".json")
    if receipt_path.exists():
        receipt = load(receipt_path)
        if receipt.get("sha256") != ref["sha256"]:
            raise ValueError("Screenshot receipt hash differs: " + str(path))
        ref.update(receipt=file_ref(receipt_path), frame_before=receipt.get("frame_before"),
                   frame_after=receipt.get("frame_after"), capture_scope=receipt.get("scope"))
    return ref


def state(key, expected, observed, evidence=(), pending=(), status="observed_partial"):
    return dict(id=key, expected=expected, status=status, observed=observed,
                screenshot_evidence=[screenshot(v, n) for v, n in evidence],
                remaining_acceptance=list(pending))


def component(key, kind, source, evidence, remaining, source_uv=None):
    return dict(id=key, treatment=kind, source_identity=source,
                known_native_uv=source_uv, observed_evidence=evidence,
                remaining_acceptance=remaining)


def main():
    hud = load(AUDIT / "hud-restoration/hud-semantic-map.json")
    menu = load(AUDIT / "menu-restoration/menu-semantic-map.json")
    candidate = load(V4 / "candidate.json")
    overlays = {
        "hud": AUDIT / "hud-restoration/candidate-20261112-coherent-v4/manifest.json",
        "menu": AUDIT / "menu-restoration/palette-field-candidate-v8/manifest.json",
        "extra_menu": AUDIT / "menu-restoration/file-option-field-candidate-v1/manifest.json",
        "font_strip": AUDIT / "menu-restoration/font-strip-candidate-v6/manifest.json",
        "art": AUDIT / "menu-restoration/title-art-candidate-v2/manifest.json",
        "copyright": AUDIT / "menu-restoration/copyright-square-candidate-v1/manifest.json",
        "banner_font": AUDIT / "menu-restoration/banner-font-candidate-v2/manifest.json",
        "blueprint": AUDIT / "menu-restoration/fighter-blueprint-candidate-v1/manifest.json",
        "diagram": AUDIT / "menu-restoration/control-diagram-candidate-v1/manifest.json",
        "results_palette": AUDIT / "menu-restoration/results-palette-024-candidate-v1/manifest.json",
        "results_art": AUDIT / "menu-restoration/results-art-candidate-v2/manifest.json",
    }
    inventory = {}
    for name, path in overlays.items():
        doc = load(path)
        rows = doc.get("files", doc.get("assets", []))
        if not rows and doc.get("key") and doc.get("outputs"):
            rows = [doc]
        if isinstance(rows, dict):
            rows = [dict(key=k, **v) for k, v in rows.items()]
        inventory[name] = dict(manifest=file_ref(path), source_keys=doc.get("source_keys", len(rows)),
            contract=doc.get("contract"), geometry_version=doc.get("geometry_version"),
            assets=[{k: r[k] for k in ("key", "kind", "role", "restored_native_regions",
                "selected_native_regions", "regions", "native_parent_region", "parent_key", "source_size",
                "source_crc_verified", "source_decode_verified") if k in r} for r in rows])

    states = [
        state("title", "Complete title, left/right art join, all choices and footer palettes",
              "v4 title illustration and wordmark visually accepted; both art keys were submitted in the screenshot bracket. Main-menu lettering and copyright still need final combined replay.",
              [(4, "title-full-art")], ["Replay all highlighted title choices with font39 and copyright3", "Capture the final combined title at 2880x2160", "Verify footer and right-edge wrap in motion"]),
        state("file_option", "Open File Option and execute all branches safely on private cards",
              "Actual File Option menu entered in v4. Its small native glyph strips were missing from v4 font14; final font39 now contains source-verified candidates.",
              [(4, "file-option-entered"), (4, "e2e-file-option-reopen")],
              ["Replay font39 and banner7 visually", "Verify Create/Discard/Score/Ranking/Load/Exit and selected palettes", "Verify B77 header admission and readability on actual final candidate"]),
        state("name_entry", "Name grid, ten-character limit, selection, Space/End, save confirmation",
              "Actual CREATE DATA FILE name grid seen in v4; small lettering remains visibly native in this pre-font39 capture.",
              [(4, "name-grid-final")], ["Replay final fonts on grid, header and prompts", "Exercise full ten-character entry/edit/Space/End", "Verify all selection/blink states"]),
        state("private_card_creation", "Create PILOT on private card, verify directory and reload after restart",
              "Root inspected the native private card: MC header, allocated BASCUS-94243 directory entry, SC payload, PILOT and directory XOR verified. This proves creation structure; restart/load remains pending.",
              [], ["Restart candidate and demonstrate successful native PILOT load", "Check load/overwrite/discard confirmations"], "native_creation_verified_reload_pending"),
        state("configuration", "Open Config and visit every submenu, restore altered settings",
              "Native controller, difficulty, screen adjustment and audio screens observed. The large CONFIGURATION header, ribbon and grid remain legacy-looking in v4.",
              [(4, "e2e-controller"), (4, "e2e-current-after-config")],
              ["Replay font39, banner7 and copyright overlay", "Verify every menu choice and exit", "Verify mapped B77 header in final candidate; panel source mapping remains separate"]),
        state("config_difficulty", "Easy/Normal/Hard navigation, highlight and retained/restored value",
              "Easy and Hard highlights captured in v4; root reported native selection journey.",
              [(4, "e2e-difficulty"), (4, "e2e-difficulty-easy"), (4, "e2e-difficulty-hard")],
              ["Replay final font palettes", "Verify intended final value after exiting/reopening"]),
        state("config_controller", "Controller diagram, each binding, assignment, restore and exit",
              "Root reported L1 briefly assigned Cross, then restored raw L1; actual assignment/restoration screenshots exist and highlighted Exit worked.",
              [(4, "e2e-controller-assignment"), (4, "e2e-controller-binding-restored"), (4, "e2e-controller-exit")],
              ["Final font39 replay including three new Config source keys", "Verify all controller rows and symbols", "Improve or explicitly accept legacy controller artwork"]),
        state("config_screen_adjust", "Open/move/reset/cancel/OK; preserve intended offsets",
              "Actual SCREEN ADJUST opened, offset moved and reset; distinct native capture references avoid the misleading e2e-screen-adjust label.",
              [(4, "e2e-screen-adjust-open"), (4, "e2e-screen-adjust-offset"), (4, "e2e-screen-adjust-reset")],
              ["Replay final font39 and banner7", "Confirm Cancel and OK paths and final X/Y", "Verify B77 header, map corner-marker geometry"]),
        state("config_audio", "Stereo/Monaural selections and exit/restoration",
              "Audio page and Monaural state captured in v4; no auditory quality or final persistence claim from stills.",
              [(4, "e2e-audio-open"), (4, "e2e-audio-monaural")],
              ["Verify both choices and intended restored value", "Replay final glyph palette and listen for continuity"]),
        state("fighter_arm_selection", "All craft, every allowed gunpod, locked/unlocked and highlighted palettes",
              "Subset of fighter/arm selection visited in v3; texture families authored, but all variants were not demonstrated.",
              [(3, "arm-selection")], ["Visit every craft and all twelve weapon names/illustrations", "Verify held/upper/lower slot prompts and locked variants", "Replay final combined candidate"]),
        state("gameplay_hud", "Live score, life, weapon name, ammo, GP plates and Hit Gauge in motion",
              "v3 live score600 and multiplier x1 captured, with empty green GP plates. Earlier source-semantic evidence separately establishes Cannon/ammo15; it is not final-candidate visual acceptance.",
              [(3, "hud-score-live")], ["Final candidate motion/readability review", "Score digit transitions and extra life", "Equipped and spare slots; all weapon labels and ammo classes"]),
        state("pause", "Pause/unpause/Continue/Quit, fighter counts and background compositing",
              "Actual 2880x2160 PAUSE screenshot exists with CONTINUE/QUIT/0 FIGHTERS LEFT. High-resolution capture works, but contour quality and every state still need manual acceptance.",
              [(3, "pause-menu-highres")], ["Verify all highlighted/blink/transparency states", "Review outlines at full resolution and actual window size", "Replay final candidate and resume gameplay"]),
        state("gp_durability", "Green/yellow/red GP durability and damage/drop transitions, active and occupied reserves",
              "Green plates alone are proven. They are untextured Gouraud geometry; exact source is in gp-panel-primitive-map.json.",
              [], ["Observe yellow/red variants with protection assists off", "Observe occupied spare slots and transitions", "Check original colors retained and crisp9x edges"], "source_mapped_variants_unobserved"),
        state("ammo_rollovers", "Finite/unlimited/energy displays; 100→99,10→9,1→0 and depletion/drop",
              "No complete final-candidate rollover sequence in reviewed evidence.", [],
              ["Capture each rollover and exhaustion state for actual equipped weapon", "Check glyph alignment, clipping, per-palette alpha and popup motion"], "unverified"),
        state("hit_gauge_chain", "Fill/decay, multiplier and every palette/flash transition",
              "Gauge identity and x1 live state proven; complete transitions are unverified.", [],
              ["Exercise fill/decay and higher multipliers", "Verify all palette cycles, transparency and clipping"], "observed_partial"),
        state("gallery", "Enter gallery, navigate every available item and return", "No reviewed actual Gallery state.", [],
              ["Reach through native menu flow", "Map text/art sources and verify every item/transition"], "unreached_in_reviewed_evidence"),
        state("results_evaluation", "Stage completion, field/fight totals, grades, bonuses and score", "Result atlases authored; no reviewed completed-stage result screen.", [],
              ["Finish a stage natively", "Verify every visible result counter, grade, highlight and tally animation"], "unreached_in_reviewed_evidence"),
        state("score_empty", "Open Score and inspect an empty private profile", "Actual SCORE / NO DATA screen independently inspected in v4; final glyphs are pending replay.",
              [(4, "e2e-file-score")], ["Replay font39 and banner7", "Exit successfully and compare populated score state if obtainable"]),
        state("high_score_ranking", "Score ranking entry/view, name and difficulty variants", "No verified completed ranking journey. Root explicitly rejected e2e-file-ranking as an early-input name-grid capture.", [],
              ["Open state-gated native ranking and verify rows, palette and navigation", "Verify qualifying score entry if reachable"], "unverified"),
        state("stage_select", "Stage numerals/locked choices/unlocked craft variants", "Authored source atlas only.", [],
              ["Reach native stage select with legitimate state", "Verify all available choices and return"], "unreached_in_reviewed_evidence"),
        state("instructions_demo", "Instructions, diagrams and DEMO PLAY text in all palettes", "Authored text atlas; no final composed-state acceptance.", [],
              ["Observe all instruction pages and demo transitions", "Review legacy diagrams, panel fills and outlines"], "unverified"),
        state("game_over_continue", "Game over, continue countdown, remaining fighters and final score", "Pause's zero-fighters caption does not prove Game Over/Continue screens.", [],
              ["Reach native game-over/continue journey", "Verify countdown and remaining-fighter variants"], "unreached_in_reviewed_evidence"),
    ]

    components = [
        component("title_illustration_wordmark", "rebuilt_and_actual_title_accepted", ["282438F3-00000000", "1D953D67-00000000"],
            [str(V4 / "title-art-acceptance.json")], ["Final combined 4K-height export and motion"],
            {"left": [0, 0, 254, 239], "right_visible_prefix": [0, 8, 63, 231], "right_tail": "one native wrapped column retained by renderer"}),
        component("copyright_square_footer", "rebuilt_candidate_pending_live", ["8E1A509D-4FE32821", "8E1A509D-8808F70A", "8E1A509D-C7A1F2F0"],
            [str(overlays["copyright"])], ["v4 still shows the legacy ©1997/1998 SQUARE strip", "Replay footer3 on final candidate"], [80, 236, 199, 248]),
        component("hud_glyphs_weapon_names", "rebuilt_candidate_partial_live_acceptance", ["BDAE4156", "913FE978", "913A6603", "font v3 aliases"],
            ["hud-semantic-map.json", "v3/hud-score-live", "v3/pause-menu-highres"], ["All weapon names, digits, life states and outlines in motion"]),
        component("hit_gauge", "rebuilt_bounded_regions", ["B24C6DA2", "8BA3BB4D"],
            ["HUD manifest exact restored_native_regions", "v3/hud-score-live"], ["Fill/decay and all multipliers/palettes", "Retain all non-UI pixels exactly"]),
        component("ammo_popup", "rebuilt_candidate_source_mapped_live_pending", ["44C16454"],
            ["HUD semantic map binding"], ["Per-weapon actual popup visibility, animation and ammo transitions"]),
        component("gp_green_plates", "original_untextured_geometry_rendered9x", ["GP0 opcode0x3A, untextured Gouraud quads"],
            ["gp-panel-primitive-map.json"], ["Deliberate panel/depth redesign has not been implemented", "Accept crisp9x geometry with exact native gradient/additive colors or author scoped replacement", "Yellow/red/occupied-reserve variants"], "No texture or UV"),
        component("menu_text_atlases", "rebuilt_selected_rectangles_unverified_states", [f["crc32"] for f in menu["families"]],
            ["menu-semantic-map.json", str(overlays["menu"])], ["Per-screen actual draw and palette acceptance; atlas completion alone is insufficient"]),
        component("small_file_config_name_fonts", "rebuilt39_candidate_pending_live", load(overlays["font_strip"])["expected_keys"],
            [str(overlays["font_strip"])], ["Final replay of File Option, grid and all Config pages", "39 includes14exact aliases and25standalone native sources; glyph semantics remain state-specific"]),
        component("large_native_menu_headers", "rebuilt7_candidate_source_mapped_live_pending", ["B77B98B9 seven verified CLUTs", "FILE OPTION", "CREATE DATA FILE", "CONFIGURATION", "SCREEN ADJUST", "SCORE"],
            ["v4/file-option-entered", "v4/name-grid-final", "v4/e2e-controller", "v4/e2e-screen-adjust-open"],
            ["v4 still shows old contours; banner7 was authored afterward", "Verify actual B77 header draws and all seven palettes in final candidate", "Font39 and banner7 have distinct source/UV scope"], [0,32,256,64]),
        component("ribbon_grid_panels", "original_or_nearest_source_preserved", ["Native yellow/red slanted ribbon", "cyan grid background", "panel fills/outlines"],
            ["v4 native menu screenshots", "menu map exclusions"], ["Sharper panels and depth have not been demonstrated", "Map source geometry/UV then scope improved assets"]),
        component("controller_diagrams_button_art", "original_nearest_source_preserved", ["1AD90FC9 exclusions", "E6B65424 exclusions"],
            ["menu-semantic-map.json", "v4/e2e-controller"], ["Review/rebuild controller buttons, circular SELECT, directional controller and slot diagrams"]),
        component("results_bottom_graphics", "original_nearest_source_preserved", ["8E1A509D exclusions: arrow controls, checkerboard, ABCDE"],
            ["menu-semantic-map.json"], ["Native results/state visit", "Review/rebuild remaining graphics separately from rebuilt copyright footer"]),
        component("non_ui_mixed_page_content", "deliberately_preserved_existing_base", ["B24C6DA2", "8BA3BB4D"],
            ["Independent prior audit:50main/strict outputs outside restored rectangles matched base/native nearest;46existing-base comparisons and4new-native comparisons"],
            ["No rich-artwork improvement claim outside bounded restored regions"]),
        component("boot_logo_fmv_text", "legacy_or_scope_not_established", ["SQUARESOFT boot", "story text"],
            ["v4/pilot-settings-menu is story/FMV, not Pilot settings"], ["Decide scope and establish sources; title illustration acceptance does not cover boot/story art"]),
    ]

    # These are explicit reviewed v5 observations, not acceptance inferred from filenames.
    by_state = {row["id"]:row for row in states}
    restart = by_state["private_card_creation"]
    restart.update(status="native_creation_and_restart_load_verified",
        observed="Private v4 PILOT card seeded into a fresh v5 process unchanged. Native MC/allocated0x51 BASCUS-94243/SC/PILOT/directory-XOR independently reverified; actual post-boot title displays PILOT. This state acceptance excludes copyright readiness.",
        screenshot_evidence=[screenshot(5,"e2e-title-copyright-and-loaded-pilot")],
        remaining_acceptance=["Verify overwrite/discard/load-error flows; successful native boot load is established"])
    reviewed = {
        "configuration":(["e2e-configuration-fonts-final","e2e-controller-final"],
            "Actual final font39/banner7 Configuration root and controller page visually inspected; labels/prompts readable with no obvious clipping in these1280x960 frames."),
        "config_difficulty":(["e2e-difficulty-final-normal","e2e-difficulty-final-easy","e2e-difficulty-final-hard"],
            "Final candidate Normal/Easy/Hard highlights captured; Hard visually independently inspected. Root reports intended Normal restored after the sweep."),
        "config_controller":(["e2e-controller-final","e2e-controller-final-reassigned","e2e-controller-final-restored"],
            "Final controller list and restored L1:Gunpod Select-left state visually inspected; root reports binding reassignment then restoration. Exact B77/font39 GL draws exist in controller screenshot bracket."),
        "config_screen_adjust":(["e2e-screen-adjust-final","e2e-screen-adjust-final-offset","e2e-screen-adjust-final-reset"],
            "Final SCREEN ADJUST X0/Y0 header/prompts visually inspected and offset/reset captures pinned. Exact B77 and font39 GL draws exist in the initial screenshot bracket."),
        "config_audio":(["e2e-audio-final-monaural"],
            "Final Monaural highlighted page independently visually inspected; actual font39 GL submissions bracket this screenshot. Stereo restoration and auditory continuity are not inferred from it."),
    }
    for key,(labels,observation) in reviewed.items():
        by_state[key]["screenshot_evidence"].extend(screenshot(5,label) for label in labels)
        by_state[key]["observed"] += " " + observation
        by_state[key]["status"] = "final_candidate_subset_visually_observed"
    by_state["gallery"].update(status="locked_in_observed_native_pilot_not_passed",
        observed="Root cycled actual native PILOT title choices: Game Start, File Option, Configuration only. Gallery is unavailable in this legitimate profile state; no unlocked task-owned fixture was found.",
        remaining_acceptance=["Obtain legitimate native unlocked profile/progression and visit Gallery", "Source atlas coverage does not count as Gallery acceptance"])
    by_state["gameplay_hud"]["screenshot_evidence"].append(screenshot(5,"e2e-after-arm-confirm"))
    by_state["gameplay_hud"]["observed"] += " Actual v5 flight after arm confirmation independently inspected: ship/world visible, score0,HitGauge x1 and green plate. The e2e-gameplay-entry-v5 label instead shows ARM SELECTION and is excluded."
    by_state["results_evaluation"].update(status="actual_total_evaluation_subset_observed",
        observed="Actual v5 Total Evaluation independently inspected after gameplay: Score400, ST1 Normal, six E grades and Field Graph/Exit prompts. Root also captured field/other graph pages. This does not prove a completed-stage clear/tally sequence or every grade.",
        screenshot_evidence=[screenshot(5,"e2e-total-evaluation-observed"),screenshot(5,"e2e-total-evaluation-field-graph"),screenshot(5,"e2e-total-evaluation-other-graph")],
        remaining_acceptance=["Replay latest combined fonts/art", "Stage-clear tally/bonus and other grades/counter variants", "Review diagram/art colors, clipping and motion"])
    by_state["high_score_ranking"].update(status="native_ranking_pages_observed_pending_latest_assets",
        observed="Actual v5 Score Ranking independently inspected (Normal, ranked score rows and craft/player names); root visited further ranking pages. The earlier v4 mislabeled ranking capture remains excluded.",
        screenshot_evidence=[screenshot(5,"e2e-ranking-final"),screenshot(5,"e2e-ranking-page-two"),screenshot(5,"e2e-ranking-page-three")],
        remaining_acceptance=["Replay banner v2 ranking digits and latest font variants", "Other difficulty tables and qualifying score entry", "Every highlight/scroll/exit state"])
    by_state["file_option"]["observed"] += " Root reports v5 Score/NO DATA, Ranking pages, Data Load Yes/No, Discard list and Exit journeys completed with private card hash preserved. Individual visual quality and latest-asset replay remain separate."
    for row in components:
        if row["id"] == "large_native_menu_headers":
            row.update(treatment="v1_actual_subset_observed_v2_revision_pending_live",
                observed_evidence=row["observed_evidence"]+["v5/e2e-controller-final","v5/e2e-screen-adjust-final","v5/final-menu-draw-brackets.json"],
                remaining_acceptance=["Root found v1 native-alpha outer pixel stairs on NO DATA; banner v2 fixes coverage offline and requires actual replay", "All other headers/digits and seven palette states", "Full2160export/motion quality review"])
        elif row["id"] == "small_file_config_name_fonts":
            row.update(treatment="v3_39_actual_subset_observed_v6_48_revision_pending_live",
                observed_evidence=row["observed_evidence"]+["v5/e2e-controller-final","v5/e2e-screen-adjust-final","v5/e2e-audio-final-monaural","v5/final-menu-draw-brackets.json"],
                remaining_acceptance=["Final48 replay, including nine description reconstructions, four bounded ARM rows and five ranking variants", "Final File Option/name-grid/score/menu journey coverage", "True2160export and motion acceptance"])
        elif row["id"] == "controller_diagrams_button_art":
            row.update(treatment="rebuilt6_bounded_diagram_candidate_pending_live",
                observed_evidence=row["observed_evidence"]+[str(overlays["diagram"])],
                remaining_acceptance=["Install in next isolated candidate and demonstrate native illustrated states", "Main output refines categorical alpha inside bounded regions; protected menu text/outside RGBA stays exact", "Verify every palette, animation and blend"])
        elif row["id"] == "copyright_square_footer":
            row.update(treatment="rebuilt_actual_fresh_v5_title_palette_observed",
                observed_evidence=row["observed_evidence"]+["v5/e2e-title-copyright-after-ready","v5/final-menu-draw-brackets.json"],
                visual_observation="Fresh v5 title independently inspected after readiness: copyright/year andSQUARE are legible with no obvious clipping; actual8808F70A footerUV GL submission at17008 precedes screenshot17029..17032. First title1983..1987 remains excluded for footer acceptance.",
                remaining_acceptance=["Other two palettes/blink states", "Final combined-v6 replay"])
    components.append(component("fighter_blueprint_hull_engine","rebuilt11_bounded_candidate_pending_live",
        load(overlays["blueprint"])["expected_keys"],[str(overlays["blueprint"])],
        ["Next isolated candidate actual fighter/arm animation/clipping review", "All craft/palette states; other unobserved atlas regions remain exact baseNN2"],
        [[0,0,127,84],[72,85,127,170],[0,109,71,180]]))
    components.append(component("results_aircraft_poster","imagegen_restored5_bounded_candidate_pending_live",
        [row["key"] for row in load(overlays["results_art"])["files"]],
        [str(overlays["results_art"]),"v5/results-poster-source-proof-v1/manifest.json"],
        ["Actual five-key final GL submissions and Results composed screenshot", "Seams, native vertex modulation, readability under overlaid text and motion", "Source-generated1499x1049 master is resampled to5120x3584; dimensions alone are not acceptance"],
        [0,0,64,224]))

    streams = []
    for path in sorted(list(V4.glob("native-*/capture.jsonl"))+list(V5.glob("native-*/capture.jsonl"))):
        raw = path.read_bytes()
        rows = []
        for line in raw.splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        frames = [r["frame"] for r in rows if isinstance(r.get("frame"), int)]
        streams.append(dict(path=str(path),sha256=digest(raw),bytes=len(raw),rows=len(rows), frame_min=min(frames) if frames else None,
            frame_max=max(frames) if frames else None, atomic_visibility_proof=False))

    observed_candidate = load(V5 / "candidate.json")
    performance = load(V5 / "performance-config-single-renderer.json")
    report = dict(schema_version=1, snapshot_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="Read-only gap inventory of reviewed native v3/v4/v5 evidence and final authored asset sources; no game input, launch or process changes by this auditor.",
        overall_status="incomplete_remaining_legacy_assets_and_unverified_journeys",
        acceptance_rule="Source identity, authored PNGs and high-resolution runtime tests do not establish every composed screen. Require actual final candidate visibility, native colors/alpha, smooth9x contours, clipping/seams, motion and readable prompts in each state.",
        active_observed_candidate={"receipt": file_ref(V5 / "candidate.json"), "source_counts": observed_candidate.get("source_counts"),
            "overlay_manifests": observed_candidate["overlay_manifests"], "note": "v5 has fontv3=39/menuv7/banner v1=7,copyright3; actual Config subset observed. Current final-source inventory has fontv6=48/menuv8/banner v2=7,blueprint11,diagram6 and024 typography; these revisions remain candidate-only until next isolated launch/replay. Earlier v4 used font14."},
        prepared_next_candidate={"receipt":file_ref(V6 / "candidate.json"),"preparation_revalidation":file_ref(V6 / "preparation-revalidation.json"),
            "private_card_seed":file_ref(V6 / "private-card-seed.json"),"seeded_card":file_ref(V6 / "state/card1.mcd"),
            "seed_sha256":"8156843599078d7776e54a385ffbb523415bd5ad32eeb0cd47fba44e362b2595","target_restart_load_verified":False,
            "launch_receipt_present":(V6 / "launch-candidate.json").exists(),"final_keys":1011,"note":"Prepared source/output integrity passed; no native UI/art live acceptance is inferred for this unlaunched candidate."},
        last_observed_handoff={"screenshot":screenshot(5,"handoff-after-continue"),
            "motion_receipt":file_ref(V5 / "handoff-motion-receipt.json"),
            "frame_progress_receipts":[file_ref(V5 / "commands/181524642991.json"),file_ref(V5 / "commands/181525346291.json")],
            "frame_progress":[104891,104920],"elapsed_seconds":0.703244,
            "visual_observation":"Actual city gameplay, visible player/enemies,score240,HitGauge x1 and no PAUSE overlay. This is a bounded resumed-game observation, not full-world quality or steady60fps acceptance."},
        render_evidence={"internal_render": "Authoritative GL scale9 =2880x2160 for320x240 display,4:3 preserved", "v4_v5_reviewed_pngs": "1280x960 present captures; do not label these4K exports", "true_hires_example": screenshot(3, "pause-menu-highres"),
            "performance": "v5 single-renderer Configuration sample averages16.667ms (~60intervals/s), max23.498ms over256samples. This is scene-specific and does not prove gameplay/story performance. Earlier v4 story avg30.098ms had concurrent original renderer; different scenes prevent a causal A/B claim. Timer queries include submission/idle and emu_cpu is derived total-minus-present.",
            "single_renderer_config":dict(receipt=file_ref(V5 / "performance-config-single-renderer.json"),samples=performance["samples"],all=performance["all"]),
            "process_inventory":file_ref(V5 / "renderer-process-inventory.json")},
        source_maps=[file_ref(AUDIT / "hud-restoration/hud-semantic-map.json"), file_ref(AUDIT / "menu-restoration/menu-semantic-map.json"), file_ref(AUDIT / "hud-restoration/gp-panel-primitive-map.json")],
        superseded_map_notes=["menu-semantic-map separate title-art pending statement is superseded only for actual title-art state by title-art-acceptance.json; its other pending-state rules remain valid."],
        final_asset_inventory=inventory, components=components, screen_states=states,
        card_proofs=[file_ref(V4 / "native-pilot-save.json"), file_ref(V4 / "native-pilot-directory-check.json"),file_ref(V5 / "private-card-seed.json"),file_ref(V5 / "private-card-restart-load-acceptance.json")],
        final_menu_draw_brackets=file_ref(V5 / "final-menu-draw-brackets.json"),
        final_composition_check=file_ref(AUDIT / "hud-restoration/final-composition-check.json"),
        completion_plan=file_ref(AUDIT / "REMASTER_COMPLETION_PLAN.md"),
        fixture_qualification="Root used v5 RAM for a bounded Game Over repeat fixture; lives0 underflowed on the next loss, was corrected to1 and recorded. Those captures establish UI/source observations only, not natural progression, survival, difficulty or life-count balance.",
        cold_loading_rejection="v5/e2e-title-copyright-and-loaded-pilot frame1983..1987 proves PILOT state only; footer first actual GL submissions occurred later. It is excluded from footer visual acceptance.",
        unlocked_fixture_inventory=file_ref(AUDIT / "hud-restoration/native-card-fixture-inventory.json"),
        open_quality_findings=[
            {"component":"B77 header font v1","observed_by":"root actual v5 NO DATA","finding":"Exact nearest native alpha clipped the rebuilt outer contour to native pixel stairs despite actual GL replacement draw","status":"banner_v2_candidate_fixed_actual_replay_pending","requirement":"Coherent categorical0/127/255alpha inside explicitly bounded reviewed region; protected outside stays exact. Keep native-alpha strict comparison separate."},
            {"component":"font39","observed_by":"root actual description/ARM/ranking review","finding":"Original-alpha clipping and etched description faces; missing ARM/ranking source variants","status":"font_v6_48_candidate_fixed_actual_replay_pending"},
            {"component":"blueprint11","observed_by":"menu agent independent source audit","finding":"All eleven native palettes are uniformly alpha255, so native-alpha equality does not clip its contours","status":"no_alpha_revision_needed_actual_art_replay_pending"},
            {"component":"Data Load Yes/No prompts","observed_by":"root actual v5","finding":"Black/teal specks around prompt edges","status":"under_investigation"}],
        deferred_indexed_runtime={"implemented":False,"production_installed":False,"existing_renderer_unchanged":True,"reason":"Observed dynamic8E1A palette queries are bottom icon UV[32,236,47,251], outside approved text band. No actual in-band dynamic benefit established; preserve validated runtimev3 and native fallback.","proposal":file_ref(AUDIT / "hud-restoration/8e1a-dynamic-palette-proposal.json")},
        native_capture_snapshots=streams,
        invalid_filename_inferences={"configuration-opened": "Actual title/PILOT highlight; does not prove Config opened", "pilot-settings-menu": "Actual story/FMV text", "file-options-final": "Intro/fade, not File Option", "saved-pilot-final": "File Option during scroll; not persistence proof", "e2e-screen-adjust": "Default/Exit menu, not actual adjustment; use-open/-offset/-reset", "e2e-file-ranking": "Root rejected: early inputs reached Create Data File/name grid; not Ranking proof", "e2e-file-data-load": "Root rejected: early inputs reached Create Data File/name grid; not Data Load proof"},
        raw_capture_limits="Recorder samples activation-forward and identity/UV. CRC-valid source archives and source-query records are not atomic visibility proof; CPU VRAM may be stale. Snapshot hashes pin current bytes, not future recorder appends.",
        per_component_acceptance=["Native source key/UV or exact untextured draw mapped", "Original palette colors and native0/127/255alpha classes retained unless explicitly scoped", "Sharp smooth9x edges with deliberate outline/depth where authored", "Actual final combined candidate submission and visual screenshot bracket", "No clipped text, seams, ghost pixels or transparent gaps", "Readability and animation/motion checked at actual window size and2880x2160 export", "All highlight/palette/counter/weapon variants observed rather than inferred"])
    out = AUDIT / "hud-restoration/e2e-coverage.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(path=str(out), sha256=digest(out.read_bytes()), states=len(states), components=len(components), native_streams=len(streams))))


if __name__ == "__main__":
    main()
