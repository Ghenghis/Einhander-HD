"""Hash-bound offline review of the isolated v6 menu replay.

No game I/O. New screenshots default to unreviewed. Visual observations below
are bound to inspected image bytes, not names or successful input commands.
Recorder snapshots are activation-forward samples, not complete draw histories.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
V6 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v6"

# digest: (actual visible state, stable-state evidence, bounded observation)
# Identical image bytes receive the same observation even under different names.
REVIEWS = {
    "6c888e9b351385c014612777370b3454c58c4fb1f6a5997f8aefa641f137ba06":
        ("boot_publisher_text", True, "Sony Computer Entertainment America Presents on black; boot progression only, no restored-menu acceptance."),
    "489cf39ec33d8669343b7ed3f53a54dff469c45832fdb42d6d3d4d2888e07a0f":
        ("black_boot_interval", False, "Black frame; no visible title, menu or load-state assertion."),
    "32ea8db419dc6e49ef6f3c7b123f25edf11cfe7a3a0b806dc966ece7615888d3":
        ("title_with_pilot", True, "Title, GAME START and PILOT visible. Supports private seeded profile recognition; predates recorder, so excluded from replacement-readiness acceptance."),
    "f6bef599a2260e46414365749e1e7ae8e096b0a5283b0bc24879e1ba2c4ff1ad":
        ("attract_prologue_text", False, "Scrolling prologue text, not Configuration. Filename is a rejected state inference."),
    "77a992bb466c5707075782af2e6a808dce891f9e285cbcc36d964e665893a4a0":
        ("configuration_root", True, "Difficulty, Controller, Screen Adjust, Audio and Exit are readable and contained. One still does not prove blink/slide completeness."),
    "3a417e696515e4baa4f046604600ec177a87410a7d0600dd0a9a582bb020496d":
        ("difficulty_normal_highlight", True, "Easy/Normal/Hard and prompts visible; Normal is brighter. Visible selection only, not saved-setting persistence."),
    "fd11b86378f80001be6f7a8eb24d0c4218ad83d3a6354b5a45b85afabd8b3be3":
        ("difficulty_easy_highlight", True, "Easy is brighter; three choices remain readable and separated. No broad palette-cycle acceptance."),
    "7f39c77141baaeda5f2f986f8e3b5399a0b9d125e798842176d23d69b6ae8a4f":
        ("difficulty_hard_highlight", True, "Hard is brighter; choices and prompt fit within the display."),
    "05957f07128cc6a08a69e1d62fb62be8e097545cd65eeb93ec3156deadfc3093":
        ("controller_configuration_exit_highlight", True, "Controller list includes Arm1/Arm2/Move Manipulator, speed controls and both Gunpod Select directions; Exit and End are visible. This is the binding list, not the ARM illustration/slot diagram screen."),
    "2cef0836022a83f60b5a9832745b036df9c2497220b906f046d406520a5fab9f":
        ("controller_to_configuration_transition", False, "Text is visibly sliding off the display; excluded from settled-menu clipping/missing-text assertions."),
    "abea7cde1451f6815d9006fb6293c6861e8ae64ed30ac3ba31b1590d5a6de95c":
        ("configuration_root_controller_highlight", True, "Full five-row Configuration menu after confirmed Controller Exit; no persistent blank-text defect visible."),
    "e623dd2b5f225b7e73f2d640fdd44e0e5120bcdc70e820d1d4ae5764b134fe23":
        ("screen_adjust_zero", True, "SCREEN ADJUST, X:0/Y:0, orange corner brackets and Reset/Cancel/OK prompts are readable; initial and reset captures have identical pixels."),
    "ade4c4e4e1ec148b4ce5bdcf07df329f4c6a5b1b61e3ba14db42b282bdecddea":
        ("screen_adjust_offset_one", True, "Screen-adjust values X:1/Y:1 visible, distinct from the X:0/Y:0 state. Setting persistence outside this page is unverified."),
    "985e75f28cde49d9c8b2536bc34bd0c89c797d5276bcb7725bd95e2d6d64012b":
        ("audio_stereo_highlight", True, "Monaural and Stereo visible; Stereo brighter. This does not prove auditory output."),
    "301bc9833bbaef78375ef3619a9ba724bffade8ef84f2f5b75e47c0e8e233da9":
        ("audio_monaural_highlight", True, "Monaural brighter; menu text and prompts remain readable. No audio-quality or saved-preference assertion."),
    "dc9be61f3b8ad52eb219f12213d9a887f62de461cf16323d3e6c110ffd41893b":
        ("title_after_replacement_admission", True, "GAME START and copyright/year/SQUARE are readable with contained outer contours; no obvious strip gap in title art. PILOT visible. Pixelated orange arrows are not included in authored-lettering acceptance. One still does not pass all footer blink palettes or animation."),
    "44ce17e61bc19b3ea486f598c13361653181b1e0639b76ef5bec04bdbe381a60":
        ("file_option_root", True, "Create data file, Discard data file, Score, Score Ranking, Data Load and Exit visible. Header and glyphs are readable; destructive/save/load outcomes are not inferred."),
    "ea1f598b9d2da15d018e1ed4614e31b61be6438fb50c874e3bb808e2eada9b6f":
        ("score_no_data", True, "SCORE / NO DATA with Exit; not Ranking and not three ranking pages. Header and NO DATA readable, retaining the source block style. Ranking-digit acceptance excluded."),
    "a5bc4d26074c1a6db6dd6041b4254cb94e8c0d6428ca68307276bd21faba8284":
        ("data_load_confirmation_dialog", True, "DATA LOAD / Load? / Yes / No modal visible. Dialog entry only, not completed load. Small dark/cyan specks near the choices require a native-source transparency comparison."),
    "582ec8915d76f173307f86dffaea46f3e1c3d6d0775cea1556116e82427600ea":
        ("score_ranking_normal_default_scores", True, "Actual SCORE RANKING, Normal difficulty, five default scores and Next/Exit prompts readable. Three identically hashed captures establish this one page only; no distinct ranking-page traversal inferred."),
    "1c01d630df6d7d8bbe32568760d7f4ad0f4f8fed47764a5b8a834d08c4b87703":
        ("configuration_root_difficulty_highlight", True, "Actual Configuration root with Difficulty highlighted; filename mentioning title is not title-state proof."),
    "dc584dffd842ec650124a672e6f8eb7adeff7ae354abaa7031c785e75adaa8c4":
        ("fighter_selection_endymion_mkii", True, "Endymion FRS Mk.II, six-line description and loadout counts visible. Uneven gray/outlined letter faces require repair; cold entry cannot alone qualify final typography."),
    "460df5f3e1b083a2209b14b7a83b15874852e12a289ae70670cced66f6a4433b":
        ("fighter_selection_endymion_mkii_settled", True, "Settled Mk.II description remains readable but several e/g/p and other glyph sections have gray/dark centers with bright rims alongside white letters. Persistent quality failure against coherent solid-face requirement, not merely cold loading."),
    "052b316c2ad71ce7b451eaeb481e207642e33bb50454719a056373d56f5f0a30":
        ("fighter_selection_endymion_mki", True, "Endymion FRS Mk.I description and machine-guns x2 / gunpods x1 visible. Mixed letterface treatment persists. Blueprint is visible; tiny annotation detail remains soft."),
    "51666af826d73cda80f99432d7925a03bb31c3ff448faa2d5dd8e95e8198a762":
        ("fighter_selection_astraea_mki", True, "Astraea FGA Mk.I and its distinct description/loadout visible. Mixed gray/outlined versus solid white letterface treatment persists; final typography not accepted."),
    "6818bf5dc2253cad6bcafc931e77fb517855ae0c6c67d1dfb1a2d071836f82ae":
        ("arm_selection_machine_gun_manipulator", True, "ARM I MACHINE GUN and ARM II MANIPULATOR, weapon specification and bottom description visible. Description face inconsistency and irregular specification contours remain open."),
    "972492169e4554cea04a323ca19baaaf2c43444258208b6299d1d8534f6039a5":
        ("arm_selection_machine_gun_manipulator_settled", True, "Same description/specification quality issues persist after settling. Blueprint silhouette visible, tiny labels soft; no complete illustration/detail acceptance."),
    "6803b465b82bb1d81502435bdd2de4e29eb52d8e96288c48dbd0179212e81fd4":
        ("arm_selection_text_transition", False, "ARM heading and blueprint remain while text panels are temporarily empty. Excluded as a settled ARM state or missing-text defect."),
    "43c1d93b602aacd2c15251a1d0e2cb1140e302af0b02795a72c41df2f70e760e":
        ("stage_one_gameplay_with_hud", True, "Actual city gameplay with one player craft, six nearby enemies, life/ammo HUD elements. One still does not pass every ship/weapon/world/HUD state, motion or pacing."),
    "c774df90cb37631afddd1886a1713dd68493dfb7a6953cb84dab35a1a803fd30":
        ("natural_game_over_wordmark", True, "Large outlined GAME OVER visibly centered on black. Functional wordmark-state evidence only; ownership mapping and authored restoration remain unaccepted pending source validation."),
    "5774f2bea571a1608180bca390337274a9a15ab7c0e8dc10aced465f4f264e87":
        ("game_over_wordmark_fade", False, "Very dark GAME OVER outline fading on black; confirms a temporal fade sample only. Excluded from settled readability or restoration acceptance."),
    "8e0f47bfe07bbc6202031159eef9659bb582089ce69e7a9da7a7d326d0a4f5cc":
        ("results_total_graph", True, "Total results radar graph, six categories and E grades visible. Labels retain inconsistent gray/outlined faces; aircraft backdrop has vertical strip discontinuities. Final typography/art quality not accepted."),
    "899618083b5aa46d2f70b1d23b8c9a4521079ac3713cc3468db8866e2d2cc0a3":
        ("results_field_graph", True, "Field / Shot Down comparison graph and Total/Fight/Exit prompts visible. This is distinct graph-state functionality, not final aircraft/art or all metrics acceptance."),
    "d8036fd09e00179d603dc95270ad2b31332e5c77864b576ec4f465e15683bdcf":
        ("results_fight_evaluation_graph", True, "Fight Evaluation / Shot Down / Average 5.0 graph visible. Aircraft backdrop and uneven Field Graph letter faces remain unaccepted."),
    "5b9fde5e190d69f02350a70aa2ba44c40dff7f2c12c260ec7b0f2eba5ae7e03e":
        ("results_fight_evaluation_graph_later", True, "Later Fight Evaluation frame retains long vertical brightness/edge discontinuities at strip-aligned boundaries. These extend through glow/aircraft across different parts, rather than only following deliberate panel contours. Not accepted; source-versus-render cause unresolved."),
}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def reference(path):
    data = path.read_bytes()
    return dict(path=str(path), sha256=sha_bytes(data), bytes=len(data))


def event_summary(row):
    return {k: row[k] for k in ("stream", "line", "event", "key", "frame", "source_kind", "native_words", "depth",
        "semi", "page_xy", "clut_xy", "uv_bounds", "xy", "replacement_size", "not_visibility_proof") if k in row}


def main():
    candidate_path = V6 / "candidate.json"
    candidate = json.loads(candidate_path.read_text())
    files = {r["name"][:-4]: r for r in candidate["files"]}
    streams = sorted(V6.glob("native-v6*/capture.jsonl"))
    snapshots = []
    rows = []
    for stream in streams:
        # read_bytes pins one snapshot while the recorder may continue appending.
        raw = stream.read_bytes()
        lines = raw.splitlines()
        trailing = 0
        for line, value in enumerate(lines, 1):
            try:
                row = json.loads(value)
            except json.JSONDecodeError:
                if line == len(lines) and not raw.endswith(b"\n"):
                    trailing += 1
                    continue
                raise
            row.update(line=line, stream=str(stream))
            rows.append(row)
        snapshots.append(dict(path=str(stream), sha256=sha_bytes(raw), bytes=len(raw),
                              incomplete_trailing_lines_ignored=trailing))
    rows.sort(key=lambda r: (r.get("frame", 0), r["stream"], r["line"]))
    draws = [r for r in rows if r.get("event") == "replacement_gl_draw_submitted"]
    failures = []
    pngs = {}
    for key in sorted({r["key"] for r in draws}):
        if key not in files:
            failures.append(dict(kind="submitted_key_absent_candidate", key=key))
            continue
        item = files[key]
        path = Path(item["composed_path"])
        info = reference(path)
        with path.open("rb") as handle:
            head = handle.read(24)
        dimensions = list(struct.unpack(">II", head[16:24]))
        if info["sha256"] != item["sha256"] or dimensions != item["dimensions"]:
            failures.append(dict(kind="candidate_png_mismatch", key=key, path=str(path)))
        sizes = {tuple(r["replacement_size"]) for r in draws if r["key"] == key}
        if sizes != {tuple(dimensions)}:
            failures.append(dict(kind="submitted_size_mismatch", key=key, submitted=sorted(sizes), actual=dimensions))
        pngs[key] = dict(**info, dimensions=dimensions, origin=item.get("origin"),
                         first_observed_gl_submission=min(r["frame"] for r in draws if r["key"] == key),
                         last_observed_gl_submission=max(r["frame"] for r in draws if r["key"] == key))
    captures = []
    for receipt_path in sorted((V6 / "captures").glob("*.json")):
        receipt = json.loads(receipt_path.read_text())
        image_path = Path(receipt["path"])
        info = reference(image_path)
        if info["sha256"] != receipt["sha256"]:
            failures.append(dict(kind="capture_hash_mismatch", path=str(image_path)))
        lo, hi = receipt["frame_before"], receipt["frame_after"]
        exact = [r for r in draws if lo <= r["frame"] <= hi]
        nearby = [r for r in draws if lo-120 <= r["frame"] < lo]
        review = REVIEWS.get(info["sha256"])
        observation = (dict(status="visually_reviewed_bounded_still", actual_state=review[0],
                            settled_state_evidence=review[1], observation=review[2]) if review else
                       dict(status="unreviewed", actual_state=None, settled_state_evidence=False,
                            observation="New image bytes require independent visual inspection; filename is not state proof."))
        if review and not review[1]:
            observation["quality_acceptance"] = "excluded_transition_or_no_visible_scene"
        elif review and hi < min(r["frame"] for r in draws):
            observation["quality_acceptance"] = "functional_state_only_predates_recorder"
        elif review:
            observation["quality_acceptance"] = "bounded_readability_and_containment_observation_only"
        if review and review[0].startswith(("fighter_selection", "arm_selection_machine")):
            observation["quality_acceptance"] = "not_accepted_final_letterface_quality"
            observation["open_finding"] = "mixed_description_letterfaces"
        if review and review[0].startswith("results_"):
            observation["quality_acceptance"] = "not_accepted_results_art_integration_and_typography"
            observation["open_finding"] = "results_poster_unreplaced_variant_and_strip_discontinuities"
        item = dict(label=receipt.get("label"), image=info, receipt=reference(receipt_path),
                    frame_bracket=[lo, hi], visual_review=observation,
                    exact_bracket_submissions=[event_summary(r) for r in exact],
                    sampled_prior_120_frames=[event_summary(r) for r in nearby],
                    admission_evidence=("exact_bracket_sample" if exact else "nearby_prior_sample" if nearby else "no_nearby_sample"),
                    qualification="A submission is not visibility proof. Nearby samples may include the prior menu during a transition; per-component UV identity and visual state must agree.")
        if receipt.get("hires"):
            hires = receipt["hires"]
            internal = reference(Path(hires["path"]))
            if internal["sha256"] != hires["sha256"]:
                failures.append(dict(kind="hires_capture_hash_mismatch", path=hires["path"]))
            item["hires"] = dict(**internal, width=hires["width"], height=hires["height"],
                                  qualification="Sequential internal-surface capture, not atomic with composed screenshot frame bracket; not all internal images were visually reviewed.")
        captures.append(item)

    # A specific footer draw is stronger evidence than warming an unrelated key.
    title = next((r for r in captures if r["visual_review"]["actual_state"] == "title_after_replacement_admission"), None)
    title_proof = None
    if title:
        lo, hi = title["frame_bracket"]
        footer = [r for r in draws if r["frame"] <= hi and r["key"] == "8E1A509D-8808F70A"
                  and r.get("uv_bounds") == [80, 236, 198, 247]]
        lettering = [r for r in draws if r["frame"] <= hi and r["key"] == "323B5FB0-1C7962B3"
                     and r.get("uv_bounds") == [0, 43, 88, 55]]
        title_proof = dict(capture=title["image"], frame_bracket=[lo, hi],
            latest_footer_submission=event_summary(footer[-1]) if footer else None,
            latest_game_start_submission=event_summary(lettering[-1]) if lettering else None,
            both_precede_capture=bool(footer and lettering and max(footer[-1]["frame"], lettering[-1]["frame"]) < lo),
            acceptance="Bounded visible GAME START and copyright/SQUARE observation after matching final-source submissions; all alternate footer palettes and motion remain open.")
    seed_path = V6 / "private-card-seed.json"
    seed = json.loads(seed_path.read_text())
    launch_path = V6 / "launch-candidate.json"
    launch = json.loads(launch_path.read_text())
    results_manifest_path = AUDIT / "menu-restoration/results-art-candidate-v2/manifest.json"
    results_keys = {r["key"] for r in json.loads(results_manifest_path.read_text())["files"]}
    live_results_keys = {"118DB76A-00000000", "986250B4-00000000", "F6796FFD-00000000",
                         "D5602570-00000000", "8942621A-00000000"}
    queried_results = [r for r in rows if r.get("event") == "source_draw_query_matched"
                       and r.get("key") in live_results_keys and 29800 <= r.get("frame", 0) <= 29856]
    game_over_path = V6 / "natural-gameover-bracket.json"
    game_over = json.loads(game_over_path.read_text()) if game_over_path.exists() else None
    result = dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="bounded_replay_review_in_progress", candidate=reference(candidate_path),
        recorder_snapshots=snapshots,
        sampled_draw_range=[min(r["frame"] for r in draws), max(r["frame"] for r in draws)],
        integrity_status="PASS" if not failures else "FAIL", integrity_failures=failures,
        counts=dict(captures=len(captures), reviewed=sum(c["visual_review"]["status"] != "unreviewed" for c in captures),
            unreviewed=sum(c["visual_review"]["status"] == "unreviewed" for c in captures),
            actual_gl_submissions=len(draws), submitted_candidate_keys=len(pngs)),
        private_profile=dict(seed_receipt=reference(seed_path), launch_receipt=reference(launch_path),
            seed_profile=seed.get("profile"), user_cards_mounted=launch.get("user_cards_mounted"),
            writable_state=launch.get("writable_state"),
            observation="PILOT visibly recognized on the cold-start title. This is the seeded isolated native profile, not an unlocked/progressed Gallery fixture or full save/load/discard replay."),
        submitted_png_integrity=pngs, title_authored_region_proof=title_proof, captures=captures,
        results_art_admission=dict(prepared_art_manifest=reference(results_manifest_path),
            prepared_art_keys=sorted(results_keys),
            observed_prepared_art_submissions=sum(r["key"] in results_keys for r in draws),
            observed_current_poster_source_keys=sorted(live_results_keys),
            nearby_total_graph_source_queries=[event_summary(r) for r in queried_results],
            qualification="All five observed current-poster source-query records report replacement_size[0,0]. Prepared artwork has a different five-key family and cannot be accepted from these Results screenshots. Missing submission is evaluated in the immutable sampled stream; source queries positively identify unreplaced current strips."),
        natural_game_over=(dict(bracket=reference(game_over_path),
            receipt_declares={k:game_over.get(k) for k in ("ram_writes", "assisted", "input_injected", "observed")},
            qualification="Actual image independently shows GAME OVER. Source/GP0/VRAM bracket is retained for the component specialist; this review does not promote ownership mapping or modify earlier v5 fixture claims.") if game_over else None),
        rejected_filename_inferences={"resume-v6-configuration-ready":"Actual attract/prologue text; excluded as Configuration evidence.",
            "resume-v6-ranking-page1/2/3":"Actual SCORE / NO DATA. Identical composed pixels; not Ranking pages or ranking digits.",
            "resume-v6-score-ranking-confirmed-1/2/3":"Actual SCORE RANKING Normal page, but all three identical pixels, not three distinct pages.",
            "resume-v6-title-choice-left-entry":"Actual Configuration root, not title.",
            "resume-v6-after-controller-cancel":"Controller submenu remains visible; Cancel did not establish return to root Configuration.",
            "resume-v6-config-confirm-followup":"Visible text transition, not settled root Configuration."},
        visual_quality_findings=[dict(id="mixed_description_letterfaces", status="observed_persistent_not_accepted",
            component="Fighter and ARM description typography; ARM specification contours",
            observations="Several e/g/p and other glyph sections appear gray/outlined while adjacent glyphs are solid white, across settled Mk.II, Mk.I, Astraea and ARM stills. ARM specification outlines are uneven. This does not meet the intended coherent solid-face treatment.",
            source_diagnosis="Mixed provenance is a candidate, not a proven per-glyph cause: v6 narrow-row submissions coexist with older full HUD-page BDAE4156-B88C038E and 913FE978 alias output. Exact selected PNG hashes and dimensions pass; replacements were admitted before/in affected captures.",
            source_keys_to_trace=["BDAE4156-B88C038E", "913FE978-B88C038E", "2C781811-B88C038E", "913A6603-B88C038E",
                "3DA22883-678CA3BD", "41E75A55-678CA3BD", "7D2C7E3C-678CA3BD", "AAE3C8F2-678CA3BD"],
            evidence_labels=["resume-v6-fighter-mkii-settled", "resume-v6-fighter-next-1", "resume-v6-fighter-next-2", "resume-v6-arm-selection-settled"]),
            dict(id="blueprint_tiny_annotations", status="unaccepted_detail_coverage", component="Fighter/ARM blueprint art",
                 observations="Distinct ship silhouettes and colored structure are visible, but tiny annotation lettering remains soft at the reviewed window size. Full detail and all eleven palette states are not accepted from these stills."),
            dict(id="load_dialog_choice_specks", status="requires_native_comparison", component="Load confirmation transparency",
                 observations="Small dark/cyan specks visible near Yes/No; compare matching native/source frame before classifying as an authored transparency regression."),
            dict(id="results_poster_unreplaced_variant_and_strip_discontinuities", status="integration_coverage_failure_and_visible_seam_failure",
                component="Current Results aircraft backdrop and graph typography",
                observations="Persistent long vertical brightness/edge discontinuities align with the 64-native-pixel strip boundaries (approximately x256/512/768/1024 in the composed window), including through glow/aircraft rather than only mechanical panel contours. Several graph labels also retain the same uneven gray/outlined faces seen in descriptions.",
                diagnosis="The visible poster is not the prepared five-strip authored aircraft: observed depth2 keys are118DB76A,986250B4,F6796FFD,D5602570,8942621A -00000000 and report replacement_size[0,0]. None of the prepared five art keys has a sampled GL submission. The encoded prepared master is visibly seamless, but it is a different aircraft composition; it has no native visible acceptance from this replay. Seam cause remains source/renderer investigation, not an established v2 authoring fault.",
                evidence_labels=["resume-v6-results-settled", "resume-v6-results-field", "resume-v6-results-fight", "resume-v6-results-current"])],
        outstanding=["Independently review each newly appended capture; unreviewed files remain unaccepted.",
            "Distinct Score Ranking pages and all ranking digit/palette states; Normal page is now observed.",
            "Repair persistent Fighter/ARM typography quality; finish ARM illustrations/slot diagrams and all palette/weapon states.",
            "Map/rebuild/integrate the newly observed current Results poster variant and resolve strip discontinuities; repair graph typography. Total/Field/Fight graph states are observed but art quality remains unaccepted.",
            "Complete native save/load/discard-cancel and cold restart replay; Gallery/unlock/end states.",
            "Alternate menu/footer palettes, blink and slide cycles, text clipping during intended motion.",
            "Gameplay HUD variants, all component ownership and full-game E2E/pacing."],
        limitations=["This run performs no game commands and changes no runtime or pack files.",
            "Visual review concerns inspected composed stills at their current window scale. It is not all-component or full UI acceptance.",
            "4096px source images and 2880x2160 internal raster dimensions do not establish bespoke restoration quality.",
            "The recorder's not_visibility_proof flags remain authoritative: source identity, submission and visual judgment are separate evidence tiers."])
    out = V6 / "replay-acceptance.json"
    out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=reference(out), integrity=result["integrity_status"], counts=result["counts"], title_after_admission=title_proof["both_precede_capture"] if title_proof else None)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
