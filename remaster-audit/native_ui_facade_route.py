"""Observed native title -> verified fighter -> ARM -> city/HUD gates.

Import enter_city(report) after launching an owned candidate. No process is
launched here, no RAM/state is written, and each verified prompt gets at most
one finite confirm. Every attempt owns a new evidence directory.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

import launch_ui_candidate as ui

ROOT = Path(__file__).resolve().parent
REFERENCES = {
    "title": ("dev-center-evidence/facade-ab-20261112/architecture/scene-native-03.png", "c744d01261785bd633c24287de3c488de32780c1950c274a1bda5763c8e020c6"),
    "fighter": ("dev-center-evidence/facade-ab-20261112/dark-optics/approach-state-01.png", "a0978a3bfa85e10e8e601062ccf9634dc8fc9934d176513ed480288a203717f7"),
    "arm": ("dev-center-evidence/typography-repair-20261112-v11/arm-native-gate.png", "cbd5aa5f25118d3ff9ac5a2c83811cfddb817dd772f0ed9447adaa9c88fb74e6"),
    "city": ("dev-center-evidence/facade-ab-20261112/dark-optics/after-fighter-confirm.png", "44b4c9b05583426fce7f9e99d638aba017d07b6e74a06703458f48a269c5f06d"),
}
STOCK_REFERENCES = {
    "title": ("dev-center-evidence/stage1-completion-20261112/native-reference-v1/title.png", "821a55f6cfc7873d593b5c3deae020a50f63dafac154ab6cfbc9d7af1dccb790"),
    "fighter": ("dev-center-evidence/stage1-completion-20261112/native-reference-v1/fighter.png", "884fb004ef5fdc1f9f16c2054d7aec0bbe57829c87299f19b868c7bc9ed0f43a"),
    "arm": ("dev-center-evidence/stage1-completion-20261112/native-reference-v1/arm.png", "753f73dbc0c2fb03f850704c6d89304283e108a1e6a5b0c05d39d28aefee50ce"),
    "city": ("dev-center-evidence/stage1-completion-20261112/native-reference-v1/city.png", "28f0cd1bd87fb912b5361b00bd0e0d6c5aa1a0b4459113badc82a6e0775e713a"),
}
CRAFT_REFERENCES = {
    "mk2": STOCK_REFERENCES["fighter"],
    "mk3": ("dev-center-evidence/stage1-completion-20261112/native-craft-choices-v1/hd-off_rewind-off/choice-1-native-2.png", "ee3a51532ac66b88d6fcccc83a444a8b511a98d3a1d5859f36dc3c529c79ae05"),
    "astraea": ("dev-center-evidence/stage1-completion-20261112/native-craft-choices-v1/hd-off_rewind-off/choice-2-native-2.png", "1ddf6c113c602d3ac4e245806d43f8dade53fe321b9da7e920d9aa5d7ea55337"),
}
ASTRAEA_ARM_REFERENCES = {
    "arm2": ("dev-center-evidence/stage1-completion-20261112/astraea-native-sources-v1/hd-on_rewind-off/native-facade-route-20261113-044730-307531/after-fighter-3.png", "5b99fb746cc6c9c4fa753acba04b39c50a14c126aa9cd9663b04361e8f81ccfc"),
    "arm1": ("dev-center-evidence/stage1-completion-20261112/astraea-native-sources-v1/hd-on_rewind-off/native-facade-route-20261113-044730-307531/failed-last-3.png", "e5d63120f087c12bf638c62d74e5fb0d97a98edb7748203a1684047669c3507d"),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_pixels(image):
    if image.size != (320, 240):
        raise ValueError("Native gate requires an actual 320x240 screenshot")
    return np.asarray(image.convert("RGB"))


def load_references(profile="hd"):
    if profile not in ("hd", "native-stock"):
        raise ValueError("Unknown native route reference profile")
    pixels, receipts = {}, {}
    for name, (relative, expected) in (STOCK_REFERENCES if profile == "native-stock" else REFERENCES).items():
        path = ROOT / relative
        actual = digest(path)
        if actual != expected:
            raise ValueError("Native reference changed: " + name)
        with Image.open(path) as image:
            pixels[name] = native_pixels(image)
        receipts[name] = dict(path=str(path), sha256=actual, dimensions=[320, 240])
    return pixels, receipts


def crop(a, rect):
    x0, y0, x1, y1 = rect
    return a[y0:y1, x0:x1].astype(np.int16)


def blue(a):
    return (a[:, :, 1] > 45) & (a[:, :, 2] > 70) & (a[:, :, 0] < 100) & (a[:, :, 2] > a[:, :, 0]+25)


def white(a):
    return (a.min(2) > 130) & ((a.max(2)-a.min(2)) < 90)


def dice(a, b):
    total = int(a.sum()+b.sum())
    return float(2*(a & b).sum()/total) if total else 0.0


def load_craft_references(registry=CRAFT_REFERENCES):
    pixels, receipts = {}, {}
    for name, (relative, expected) in registry.items():
        path = ROOT / relative
        if digest(path) != expected:raise ValueError("Native craft reference changed: " + name)
        with Image.open(path) as image:pixels[name] = native_pixels(image)
        receipts[name] = dict(path=str(path), sha256=expected)
    return pixels, receipts


def classify_arm_slot(pixels, references):
    def mask(image):
        return np.concatenate([white(crop(image, (15, 60, 135, 75))),
                               white(crop(image, (15, 127, 135, 142)))])
    observed=mask(pixels)
    scores=sorted(((dice(observed,mask(image)),name) for name,image in references.items()),reverse=True)
    score,name=scores[0];margin=score-scores[1][0]
    return dict(arm_slot=name if score>=.98 and margin>=.1 else "unverified",
                arm_slot_score=score,arm_slot_margin=margin)


def classify_craft(pixels, references):
    # Mk.II and Mk.III differ by just one narrow glyph. A broad .80 Dice gate
    # admits both; require an almost exact label and a lead over every other craft.
    label = white(crop(pixels, (5, 50, 135, 68)))
    scores = sorted(((dice(label, white(crop(image, (5, 50, 135, 68)))), name)
                     for name, image in references.items()), reverse=True)
    score, name = scores[0];margin = score-scores[1][0]
    return dict(craft=name if score >= .995 and margin >= .01 else "unverified",
                craft_label_score=score, craft_label_margin=margin)


def classify_native(pixels, references, profile="hd"):
    """Localized header/label/HUD masks; a 3D-looking scene is insufficient."""
    if pixels.shape != (240, 320, 3):
        raise ValueError("Native gate requires 320x240 RGB pixels")
    header = (0, 0, 300, 30)
    fighter = dice(blue(crop(pixels, header)), blue(crop(references["fighter"], header)))
    arm = dice(blue(crop(pixels, header)), blue(crop(references["arm"], header)))
    label = (5, 50, 135, 68)
    mk2 = dice(white(crop(pixels, label)), white(crop(references["fighter"], label)))
    start_rect = (110, 165, 208, 184)
    start = dice(white(crop(pixels, start_rect)), white(crop(references["title"], start_rect)))
    cyan_title = int(blue(crop(pixels, (20, 70, 300, 160))).sum())
    hud_rect = (224, 210, 232, 216)  # fixed multiplier x glyph, not changing digits
    if profile == "native-stock":
        # The original fixed multiplier X peaks at 104..112 gray. Its native
        # anti-aliased shape disappears under the HD glyph's >130 white mask.
        # Restrict this profile to neutral gray, keeping the same ROI and Dice gate.
        def hud_mask(a):
            return (a.min(2) > 88) & ((a.max(2) - a.min(2)) < 16)
    else:
        hud_mask = white
    hud = dice(hud_mask(crop(pixels, hud_rect)), hud_mask(crop(references["city"], hud_rect)))
    body = crop(pixels, (0, 30, 320, 195))
    scene_detail = float(np.abs(np.diff(body.astype(float), axis=1)).mean())
    state = "unknown"
    if fighter >= .80:
        state = "fighter" if mk2 >= .80 else "fighter_other_or_label_unverified"
    elif arm >= .80:
        state = "arm"
    elif start >= .78 and cyan_title > 300:
        state = "title"
    elif hud >= .85 and scene_detail > 3.0 and float((body.max(2)>30).mean()) > .2:
        state = "city"
    return dict(state=state, fighter_header=fighter, arm_header=arm, mk2_label=mk2,
                game_start=start, title_cyan=cyan_title, city_hud_x=hud, scene_detail=scene_detail)


def enter_city(report, *, timeout_per_state=60, poll_seconds=.25, stop_at="city", craft="mk2",
               _debug=None, _clock=time.monotonic, _sleep=time.sleep):
    """Return serializable route proof, or raise after saving failed evidence."""
    if not 0 < timeout_per_state <= 60 or not .05 <= poll_seconds <= 1:
        raise ValueError("State deadlines must be <=60 seconds; polling 0.05..1 second")
    if stop_at not in ("city", "fighter"):
        raise ValueError("Route stop must be city or fighter")
    profile = report.get("route_reference_profile", "hd")
    if craft not in CRAFT_REFERENCES or (craft != "mk2" and profile != "native-stock"):
        raise ValueError("Alternate craft require the pinned native-stock route")
    refs, receipts = load_references(profile)
    craft_refs, craft_receipts = load_craft_references() if craft != "mk2" else ({}, {})
    arm_refs, arm_receipts = load_craft_references(ASTRAEA_ARM_REFERENCES) if craft == "astraea" else ({}, {})
    root = Path(report["evidence"])
    directory = root / ("native-facade-route-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
    directory.mkdir()
    proof = dict(ok=False, debug_port=int(report["debug_port"]), evidence=str(directory),
                 helper=dict(path=str(Path(__file__).resolve()), sha256=digest(__file__)),
                 references=receipts, reference_profile=profile, requested_craft=craft,
                 craft_references=craft_receipts, arm_references=arm_receipts,
                 observations=[], gates=[], inputs=[], ram_writes=False,
                 state_loads=False, turbo_changed=False)
    old_port = ui.PORT
    ui.PORT = int(report["debug_port"])
    def bound_debug(command, **fields):
        reply = ui.command(report, json.dumps(dict(cmd=command, **fields)))
        if reply.get("ok") is not True and not (command == "screenshot" and reply.get("error") == "display disabled"):
            raise RuntimeError(command+": "+str(reply))
        return reply
    debug = _debug or bound_debug
    latest = deque(maxlen=3)
    sequence = 0

    def persist():
        (directory / "route-proof.json").write_text(json.dumps(proof, indent=2)+"\n", encoding="utf-8")

    def gate(allowed, stage, expected_craft=None, expected_arm=None):
        nonlocal sequence
        deadline, streak, previous = _clock()+timeout_per_state, [], None
        while _clock() < deadline:
            target = directory / "current-native.png"
            reply = debug("screenshot", path=target.as_posix())
            if not reply.get("ok", True):
                if reply.get("error") == "display disabled":
                    streak, previous = [], None
                    _sleep(poll_seconds)
                    continue
                raise RuntimeError("Native screenshot failed: " + str(reply))
            with Image.open(target) as image:
                pixels = native_pixels(image)
            sequence += 1
            observation = dict(sequence=sequence, stage=stage, frame=debug("get_registers").get("frame"),
                               elapsed=_clock(), **classify_native(pixels, refs, profile))
            if expected_craft and craft_refs:
                observation.update(classify_craft(pixels, craft_refs))
                if observation["fighter_header"] >= .80:
                    observation["state"] = "fighter" if observation["craft"] == expected_craft else "fighter_other_or_label_unverified"
            if expected_arm and observation["state"] == "arm":
                observation.update(classify_arm_slot(pixels,arm_refs))
                if observation["arm_slot"] != expected_arm:observation["state"]="arm_other_or_slot_unverified"
            proof["observations"].append(observation)
            latest.append((pixels.copy(), observation))
            current = observation["state"]
            if current in allowed:
                if current != previous:
                    streak = [(pixels.copy(), observation)]
                elif not streak or observation["frame"] > streak[-1][1]["frame"]:
                    streak.append((pixels.copy(), observation))
                previous = current
                if len(streak) >= 3:
                    captures = []
                    for index, (array, item) in enumerate(streak[-3:], 1):
                        path = directory / (stage+"-"+str(index)+".png")
                        Image.fromarray(array).save(path)
                        captures.append(dict(path=str(path), sha256=digest(path), frame=item["frame"]))
                    proof["gates"].append(dict(stage=stage, observed=current, consecutive=3, captures=captures))
                    persist()
                    return current
            else:
                streak, previous = [], None
            _sleep(poll_seconds)
        raise RuntimeError("Native route gate timed out: "+stage+"; last="+(previous or (latest[-1][1]["state"] if latest else "no frame")))

    def confirm(state):
        if any(entry["after_state"] == state for entry in proof["inputs"]):
            raise RuntimeError("Duplicate prompt confirmation refused: " + state)
        entry = dict(after_state=state, button="confirm", duration_seconds=.15)
        proof["inputs"].append(entry)
        try:
            entry["press"] = debug("set_input", buttons="0xBFFF")
            _sleep(.15)
        finally:
            entry["release"] = debug("clear_input")
            persist()

    try:
        debug("clear_input")
        gate({"title"}, "title-game-start")
        confirm("title")
        gate({"fighter"}, "fighter-mk2", "mk2")
        if craft != "mk2":
            for previous, selected in [("mk2", "mk3")] + ([("mk3", "astraea")] if craft == "astraea" else []):
                entry = dict(after_state="fighter-"+previous, button="down", duration_seconds=.12)
                proof["inputs"].append(entry)
                try:
                    entry["press"] = debug("set_input", buttons="0xFFBF")
                    _sleep(.12)
                finally:
                    entry["release"] = debug("clear_input")
                    persist()
                _sleep(.8)
                gate({"fighter"}, "fighter-"+selected, selected)
        if stop_at == "fighter":
            proof["ok"], proof["final_state"] = True, "fighter"
            return proof
        confirm("fighter")
        next_state = gate({"arm", "city"}, "after-fighter", expected_arm="arm2" if craft=="astraea" else None)
        if next_state == "arm":
            if craft=="astraea":
                confirm("arm2")
                gate({"arm"}, "astraea-arm1", expected_arm="arm1")
                confirm("arm1")
            else:confirm("arm")
            gate({"city"}, "city-hud")
        proof["ok"], proof["final_state"] = True, "city"
        return proof
    except Exception as exc:
        proof["error"] = str(exc)
        for index, (pixels, observation) in enumerate(latest, 1):
            path = directory / ("failed-last-"+str(index)+".png")
            Image.fromarray(pixels).save(path)
            observation["failure_capture"] = dict(path=str(path), sha256=digest(path))
        raise RuntimeError(str(exc)+"; evidence="+str(directory/"route-proof.json")) from exc
    finally:
        try:
            proof["final_input_release"] = debug("clear_input")
        finally:
            persist()
            ui.PORT = old_port
