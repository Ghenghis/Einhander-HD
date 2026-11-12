"""Prepare and launch an isolated 4:3 HUD/menu candidate; never touch port 4370.

Default operation prepares files only. --check is entirely read-only. After
preparation, use --evidence DIR --launch, or --evidence DIR --command JSON.
--rollback --launch starts a separate stock-pack baseline using original video
settings, after the candidate has been closed. No process is stopped here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "windows-x64"
ALLOWED = ROOT / "remaster-audit/dev-center-evidence"
BASE = PROJECT / "hd-textures/stage1-v1"
PORT = 4371
TITLE = "Einhander - HUD 4K candidate"
# An empty PSX_LOAD_SLOT still passes getenv() and atoi("") requests slot 0.
# Omit both variables so startup matches the baseline's native behavior.
CLEANED_ENVIRONMENT_KEYS = ("PSX_LOAD_SLOT", "PSX_HLE_SCHEDULER")
PNG_NAME = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{8}\.png")
FONT_V2_KEYSET_SHA256 = "1fbfcd7b1efd907049fb4ec89015a6106f3db1f89bc95d3623c5d448be5d93a7"
FONT_V3_KEYSET_SHA256 = "cec5103956db39a47b4b6e5d285610f0220dc91854c8a439000cabc3e36d9395"
FONT_V6_KEYSET_SHA256 = "f82b4c93eae812edfe563613443363b2b8e4d8be5eb4a5a5239aeb161a19786d"
sys.path.insert(0, str(PROJECT / "tools"))
from launch_material import prepare_launch
from material_profiles import saved_selection


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def owned(path, parent=ROOT):
    path = Path(path).resolve()
    if not path.is_relative_to(parent.resolve()) or path == parent.resolve():
        raise ValueError("Path must be inside " + str(parent))
    return path


def png_directory(path):
    path = owned(path)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Pack must be an existing owned directory: " + str(path))
    if any(PNG_NAME.fullmatch(p.name) for p in path.glob("*.png")):
        return path
    children = [p for p in path.iterdir() if p.is_dir() and p.name.endswith("-texture-replacements")]
    if len(children) != 1:
        raise ValueError("Expected numeric PNGs or one replacement directory: " + str(path))
    return children[0]


def inventory(path, origin):
    directory = png_directory(path)
    rows = []
    for path in sorted(directory.glob("*.png")):
        if not PNG_NAME.fullmatch(path.name) or path.is_symlink() or not path.is_file():
            raise ValueError("Invalid replacement PNG: " + str(path))
        with path.open("rb") as stream:
            header = stream.read(33)
        if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise ValueError("Invalid PNG header: " + str(path))
        width, height = struct.unpack(">II", header[16:24])
        if not 1 <= width <= 16384 or not 1 <= height <= 16384:
            raise ValueError("Invalid replacement dimensions: " + str(path))
        rows.append(dict(name=path.name.upper().replace(".PNG", ".png"), path=str(path),
                         sha256=sha(path), bytes=path.stat().st_size,
                         dimensions=[width, height], origin=origin))
    if not rows:
        raise ValueError("Pack contains no replacements: " + str(directory))
    if len({row["name"] for row in rows}) != len(rows):
        raise ValueError("Pack has duplicate case-insensitive replacement names")
    return directory, rows


def verify_base(rows):
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    expected = {row["key"].upper() + ".png": row["sha256"] for row in manifest["files"]}
    actual = {row["name"]: row["sha256"] for row in rows}
    if actual != expected:
        raise ValueError("Base PNGs do not match the installed manifest")


def verify_overlay(directory, rows, role, count):
    candidates = [directory / "manifest.json", directory.parent / "manifest.json",
                  directory.parent.parent / "manifest.json"]
    manifest_path = next((p for p in candidates if p.is_file()), None)
    if manifest_path is None:
        raise ValueError(role + " pack has no completed manifest; partial packs are refused")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files", manifest.get("assets", []))
    allowed_counts = (count,) if isinstance(count, int) else tuple(count)
    if len(rows) not in allowed_counts or len(entries) != len(rows):
        raise ValueError(role + " pack must contain a complete manifest with asset count " + str(allowed_counts))
    actual_count = len(rows)
    if role == "HUD" and manifest.get("source_keys") != actual_count:
        raise ValueError("HUD manifest source_keys must be " + str(actual_count))
    if "asset_count" in manifest and manifest["asset_count"] != actual_count:
        raise ValueError(role + " manifest asset_count mismatch")
    expected = {}
    actual_paths = {Path(row["path"]).resolve(): row["name"] for row in rows}
    for entry in entries:
        key = entry.get("key", "").upper() + ".png"
        digest = None
        for output in entry.get("outputs", {}).values():
            if Path(output.get("path", "")).resolve() in actual_paths:
                digest = output.get("sha256")
                break
        if digest is None:
            digest = entry.get("sha256")
        if not digest or key in expected:
            raise ValueError(role + " manifest is missing an unambiguous output hash")
        expected[key] = digest
    if expected != {row["name"]: row["sha256"] for row in rows}:
        raise ValueError(role + " PNGs do not match completed manifest output hashes")
    return dict(path=str(manifest_path), sha256=sha(manifest_path), asset_count=actual_count)


def runtime_override(executable):
    executable = Path(executable).resolve()
    staging = Path("C:/github/REMASTER_STAGING").resolve()
    if not (executable.is_relative_to(ROOT) or executable.is_relative_to(staging)):
        raise ValueError("Runtime override must be an owned workspace or remaster-staging build")
    receipt_path = executable.parent / "build.json"
    if not executable.is_file() or not receipt_path.is_file():
        raise ValueError("Runtime override requires an executable and sibling build.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if Path(receipt.get("executable", "")).resolve() != executable:
        raise ValueError("Runtime build receipt names a different executable")
    digest = sha(executable)
    if digest != receipt.get("sha256") or receipt.get("link_exit", 0) != 0:
        raise ValueError("Runtime override hash or link result does not match build.json")
    return dict(executable=str(executable), sha256=digest,
                build_receipt=str(receipt_path), build_receipt_sha256=sha(receipt_path))


def verify_provenance(report):
    for receipt in report["overlay_manifests"].values():
        if sha(receipt["path"]) != receipt["sha256"]:
            raise ValueError("Overlay manifest changed since candidate validation")
        for reference in receipt.get("referenced_files", []):
            if sha(reference["path"]) != reference["sha256"]:
                raise ValueError("Overlay source evidence changed: " + reference["path"])
    override = report.get("runtime_override")
    if override and runtime_override(override["executable"]) != override:
        raise ValueError("Explicit runtime build changed since candidate validation")


def verify_standalone_font(row, directory, checked, refined_alpha=False):
    from PIL import Image
    key = row["key"]
    required = ("source_crc_verified", "source_decode_verified", "source_validity_complete",
                "canonical_native_rgba_exact", "source_local_uv_coordinates_preserved") + (() if refined_alpha else ("native_alpha_footprint_exact",))
    if (any(row.get(field) is not True for field in required) or row.get("base_key") is not None or
            row.get("base_output_region") is not None or row.get("source_size") != [256, 8] or
            row.get("canonical_source_codes") != [15,14,13,12,11,10,0] or
            row.get("canonical_levels") != [0,3,6,9,11,13,15]):
        raise ValueError("Unverified standalone font contract: " + key)
    if refined_alpha and (row.get("native_alpha_footprint_exact") is not False or
            row.get("alpha_policy") != "categorical_contour_inside_authored_regions" or
            row.get("selected_native_regions") != [[0,0,256,8]] or
            any(row.get(flag) is not True for flag in ("main_contour_alpha_refined","strict_native_alpha_footprint_exact",
                "main_rgb_exact_to_v3","protected_outside_exact_to_v3"))):
        raise ValueError("Unreviewed standalone font alpha revision")

    def reference(path, digest):
        path = owned(path)
        if str(path) in checked and checked[str(path)] != digest:
            raise ValueError("Conflicting font evidence hashes")
        if str(path) not in checked and sha(path) != digest:
            raise ValueError("Font source evidence hash mismatch: " + str(path))
        checked[str(path)] = digest
        return path

    archives = row.get("source_archives", {})
    if set(archives) != {"words", "clut", "validity", "metadata"}:
        raise ValueError("Standalone font requires four complete source archives: " + key)
    paths = {name:reference(info["path"], info["sha256"]) for name,info in archives.items()}
    raw, clut, valid = (paths[name].read_bytes() for name in ("words", "clut", "validity"))
    metadata = json.loads(paths["metadata"].read_text())
    if (metadata != row.get("source_metadata") or metadata.get("key") != key or
            [metadata.get("width_words"),metadata.get("height"),metadata.get("depth"),metadata.get("clut_words")] != [64,8,0,16] or
            metadata.get("known_words") != 512 or metadata.get("total_words") != 512 or
            len(raw) != 1024 or len(clut) != 32 or len(valid) != 512 or any(value != 1 for value in valid)):
        raise ValueError("Incomplete standalone native font archive: " + key)
    if f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key:
        raise ValueError("Standalone font texture/CLUT CRC mismatch: " + key)
    palette = struct.unpack("<16H", clut)
    native = bytearray()
    used = set()
    for word in struct.unpack("<512H",raw):
        for shift in (0,4,8,12):
            index = (word >> shift) & 15
            used.add(index)
            value = palette[index]
            native.extend(((value&31)<<3,((value>>5)&31)<<3,((value>>10)&31)<<3,
                           0 if value == 0 else 255 if value&0x8000 else 127))
    if not used <= {0,10,11,12,13,14,15} or not {0,15} <= used:
        raise ValueError("Standalone source is outside the reviewed font ramp: " + key)
    if hashlib.sha256(native).hexdigest() != row.get("native_rgba_sha256"):
        raise ValueError("Standalone independent native RGBA decode mismatch: " + key)
    source = reference(row["source"],row["source_sha256"])
    with Image.open(source) as image:
        if image.size != (256,8) or image.convert("RGBA").tobytes() != native:
            raise ValueError("Standalone source PNG differs from raw decode: " + key)
    output = next((entry for entry in row["outputs"].values()
                   if Path(entry["path"]).resolve().parent == directory.resolve()), None)
    if output is None:
        raise ValueError("Missing selected standalone output")
    with Image.open(output["path"]) as image:
        rgba = image.convert("RGBA")
        alpha = Image.frombytes("L",(256,8),bytes(native[3::4])).resize((4096,128),Image.Resampling.NEAREST)
        main_refined = refined_alpha and output is row["outputs"].get("pack")
        if (rgba.size != (4096,128) or
                (not main_refined and rgba.getchannel("A").tobytes() != alpha.tobytes()) or
                not set(rgba.getchannel("A").getdata()) <= {0,127,255} or
                hashlib.sha256(rgba.tobytes()).hexdigest() != output.get("rgba_sha256")):
            raise ValueError("Standalone font coverage or decoded output changed: " + key)
    if not row.get("native_ui_receipts") or not row.get("composed_ui_capture_refs"):
        raise ValueError("Standalone font requires native and composed menu evidence")
    for native_receipt in row["native_ui_receipts"]:
        reference(native_receipt["metadata_path"], native_receipt["metadata_sha256"])
        reference(native_receipt["capture_path"], native_receipt["capture_sha256"])
        if not any(draw.get("key") == key and draw.get("native_words") == [64,8]
                   for draw in native_receipt.get("draws",[])):
            raise ValueError("Standalone font has no corresponding native draw receipt: " + key)
    for composed in row["composed_ui_capture_refs"]:
        reference(composed["receipt"],composed["receipt_sha256"])
        reference(composed["image"],composed["image_sha256"])
    return dict(key=key,kind="standalone_native_font",role=row["role"],
                independent_raw_decode_verified=True,native_alpha_footprint_exact=not main_refined,
                alpha_policy="categorical_contour_inside_authored_regions" if main_refined else "exact_native_footprint",
                parent_key=None,native_parent_region=None)


def verify_font_strip_map(directory, rows, hud_manifest, extra_menu_manifest=None):
    receipt = verify_overlay(directory, rows, "font strip", (14,36,39,48))
    manifest = json.loads(Path(receipt["path"]).read_text(encoding="utf-8"))
    if manifest.get("contract") == "verified-font-strip-v6":
        return verify_font_strip_v6(directory,rows,receipt,manifest,hud_manifest,extra_menu_manifest)
    v4 = manifest.get("contract") == "verified-font-strip-v4"
    v3 = v4 or manifest.get("contract") == "verified-font-strip-v3"
    v2 = v3 or manifest.get("contract") == "verified-font-strip-v2"
    expected_count = 39 if v3 else 36
    standalone_count = 25 if v3 else 22
    keyset_digest = FONT_V3_KEYSET_SHA256 if v3 else FONT_V2_KEYSET_SHA256
    checked = {}
    prior_rows = None
    if v2:
        keys = sorted(row["key"] for row in manifest["files"])
        if (manifest.get("format") != (4 if v4 else 3 if v3 else 2) or manifest.get("source_keys") != expected_count or keys != manifest.get("expected_keys") or
                hashlib.sha256("\n".join(keys).encode()).hexdigest() != keyset_digest or
                manifest.get("exact_font_row_alias_count") != 14 or manifest.get("standalone_native_font_count") != standalone_count or
                manifest.get("missing_source_archives")):
            raise ValueError("Font revision must contain its complete reviewed key set")
        refs = manifest.get("parent_manifest_refs",{})
        if set(refs) != ({"hud","aee","font_v1","font_v2","font_v3"} if v4 else {"hud","aee","font_v1","font_v2"} if v3 else {"hud","aee","font_v1"}) or not extra_menu_manifest:
            raise ValueError("Font v2 requires the selected HUD/AEE and verified v1 parent manifests")
        for name, parent_receipt in refs.items():
            path = owned(parent_receipt["path"])
            if sha(path) != parent_receipt["sha256"]:
                raise ValueError("Font v2 parent changed: " + name)
            checked[str(path)] = parent_receipt["sha256"]
        for name, selected in (("hud",hud_manifest),("aee",extra_menu_manifest)):
            if (Path(refs[name]["path"]).resolve() != Path(selected["path"]).resolve() or
                    refs[name]["sha256"] != selected["sha256"]):
                raise ValueError("Font v2 does not match the selected " + name + " pack")
        prior = json.loads(Path(refs["font_v1"]["path"]).read_text())
        if prior.get("source_keys") != 14:
            raise ValueError("Font v2 requires a complete 14-key v1 parent")
        prior_rows = {row["key"]:row for row in prior["files"]}
        if v3:
            prior_v2 = json.loads(Path(refs["font_v2"]["path"]).read_text())
            current_rows = {row["key"]:row for row in manifest["files"]}
            old_keys = sorted(row["key"] for row in prior_v2["files"])
            if (prior_v2.get("contract") != "verified-font-strip-v2" or len(old_keys) != 36 or
                    hashlib.sha256("\n".join(old_keys).encode()).hexdigest() != FONT_V2_KEYSET_SHA256 or
                    manifest.get("prior_outputs_preserved") != 36 or manifest.get("new_source_keys") != 3):
                raise ValueError("Font v3 requires its complete reviewed v2 predecessor")
            comparison_rows = current_rows
            if v4:
                from PIL import Image
                prior_v3 = json.loads(Path(refs["font_v3"]["path"]).read_text())
                comparison_rows = {row["key"]:row for row in prior_v3["files"]}
                old_keys_v3 = sorted(comparison_rows)
                corrected = {row["key"] for row in manifest["files"] if row.get("kind") == "standalone_native_font"}
                if (prior_v3.get("contract") != "verified-font-strip-v3" or len(old_keys_v3) != 39 or
                        hashlib.sha256("\n".join(old_keys_v3).encode()).hexdigest() != FONT_V3_KEYSET_SHA256 or
                        set(manifest.get("corrected_standalone_alpha_keys",[])) != corrected or len(corrected) != 25 or
                        manifest.get("prior_strict_outputs_preserved") != 39 or manifest.get("prior_alias_main_outputs_preserved") != 14):
                    raise ValueError("Font v4 requires its complete reviewed v3 predecessor and25 alpha corrections")
                for row in manifest["files"]:
                    old = comparison_rows[row["key"]]
                    if (row.get("source_sha256") != old.get("source_sha256") or
                            {name:info["sha256"] for name,info in row.get("source_archives",{}).items()} !=
                            {name:info["sha256"] for name,info in old.get("source_archives",{}).items()} or
                            row["outputs"]["strict-mask-pack"]["sha256"] != old["outputs"]["strict-mask-pack"]["sha256"]):
                        raise ValueError("Font v4 changed native sources or strict comparison: "+row["key"])
                    for old_info in old["outputs"].values():
                        path = owned(old_info["path"])
                        if sha(path) != old_info["sha256"]:
                            raise ValueError("Font v4 predecessor PNG changed")
                        checked[str(path)] = old_info["sha256"]
                    for info in row["outputs"].values():
                        path = owned(info["path"])
                        if sha(path) != info["sha256"]:
                            raise ValueError("Font v4 PNG hash changed")
                        checked[str(path)] = info["sha256"]
                    if row.get("kind") == "standalone_native_font":
                        with Image.open(row["outputs"]["pack"]["path"]) as image:
                            current_main = image.convert("RGBA")
                        with Image.open(old["outputs"]["pack"]["path"]) as image:
                            old_main = image.convert("RGBA")
                        changed_alpha = sum(a!=b for a,b in zip(current_main.getchannel("A").tobytes(),old_main.getchannel("A").tobytes()))
                        if (current_main.size != (4096,128) or current_main.convert("RGB").tobytes() != old_main.convert("RGB").tobytes() or
                                not changed_alpha or changed_alpha != row.get("changed_alpha_texels")):
                            raise ValueError("Font v4 correction changed RGB or did not match declared alpha-only change")
                    elif row["outputs"]["pack"]["sha256"] != old["outputs"]["pack"]["sha256"]:
                        raise ValueError("Font v4 changed a reviewed exact row alias")
            for old in prior_v2["files"]:
                current = comparison_rows.get(old["key"])
                if not current or {k:v["sha256"] for k,v in current["outputs"].items()} != {k:v["sha256"] for k,v in old["outputs"].items()}:
                    raise ValueError("Font v3 changed a reviewed v2 PNG: " + old["key"])
    else:
        if manifest.get("source_keys") != 14 or manifest.get("new_row_aliases") != 11 or manifest.get("existing_identity_keys") != 3:
            raise ValueError("Font strip manifest must describe 11 verified aliases and 3 identity keys")
        if (Path(manifest.get("parent_manifest", "")).resolve() != Path(hud_manifest["path"]).resolve() or
                manifest.get("parent_manifest_sha256") != hud_manifest["sha256"]):
            raise ValueError("Font strips must derive from the selected, unchanged HUD atlas manifest")
    parent = json.loads(Path(hud_manifest["path"]).read_text(encoding="utf-8"))
    parent_keys = {row["key"]: row for row in parent["files"]}
    family_rows = {"2C781811": 48, "5C02D3C1": 72, "5F101F62": 96,
                   "786B98BF": 40, "913A6603": 80, "921FC559": 56,
                   "AAA5C104": 112, "D050AD1B": 64, "E1F18F98": 32}
    bindings = []
    for row in manifest["files"]:
        if v2 and row.get("kind") == "standalone_native_font":
            bindings.append(verify_standalone_font(row,directory,checked,refined_alpha=v4))
            continue
        key, base_key = row["key"], row.get("base_key", "")
        if v2:
            old = prior_rows.get(key)
            if (row.get("kind") != "exact_font_row_alias" or not old or
                    {k:v["sha256"] for k,v in row["outputs"].items()} != {k:v["sha256"] for k,v in old["outputs"].items()}):
                raise ValueError("A reviewed v1 font output changed in v2: " + key)
        family, palette = key.split("-")
        identity = row.get("existing_identity_key") is True
        region = row.get("base_output_region")
        if identity:
            valid_map = family == "913FE978" and base_key == key and region == [0, 0, 256, 8]
        else:
            y = family_rows.get(family)
            valid_map = y is not None and base_key == "BDAE4156-" + palette and region == [0, y, 256, y + 8]
        required_checks = ("source_crc_verified", "source_decode_verified", "exact_source_words_and_clut_match",
                           "source_local_uv_coordinates_preserved")
        if (not valid_map or row.get("source_size") != [256, 8] or
                row.get("role") != "Verified font atlas eight-row upload alias" or
                any(row.get(check) is not True for check in required_checks) or base_key not in parent_keys):
            raise ValueError("Unverified font strip family/role mapping: " + key)
        output = next((entry for entry in row["outputs"].values()
                       if Path(entry.get("path", "")).resolve().parent == directory.resolve()), None)
        parent_hashes = {entry["sha256"] for entry in parent_keys[base_key]["outputs"].values()}
        if (not output or output.get("exact_parent_rgba_crop") is not True or
                output.get("parent_png_sha256") not in parent_hashes):
            raise ValueError("Font strip lacks an exact selected-atlas crop receipt: " + key)
        bindings.append(dict(key=key, role=row["role"], parent_key=base_key,
                             native_parent_region=region, existing_identity_key=identity))
    if sum(row.get("existing_identity_key",False) for row in bindings) != 3:
        raise ValueError("Font strip identity-key count mismatch")
    receipt["family_role_bindings"] = bindings
    if v2:
        if sum(row.get("kind") == "standalone_native_font" for row in bindings) != standalone_count:
            raise ValueError("Font v2 standalone count mismatch")
        receipt["contract"] = manifest["contract"]
        receipt["reviewed_keyset_sha256"] = keyset_digest
        receipt["referenced_files"] = [dict(path=path,sha256=digest) for path,digest in checked.items()]
    return receipt


def verify_font_strip_v6(directory, rows, receipt, manifest, hud_manifest, extra_menu_manifest):
    from PIL import Image
    import numpy as np
    keys = sorted(row["key"] for row in manifest["files"])
    descriptions = {family+"-B88C038E":y for family,y in
        {"2C781811":48,"5C02D3C1":72,"5F101F62":96,"786B98BF":40,"913A6603":80,
         "921FC559":56,"AAA5C104":112,"D050AD1B":64,"E1F18F98":32}.items()}
    arms = {"3DA22883-678CA3BD":104,"41E75A55-678CA3BD":80,"7D2C7E3C-678CA3BD":72,"AAE3C8F2-678CA3BD":88}
    ranking = {"2C6866AA-30A66678","2C6866AA-B1A4FC51","8D0FCF8A-30A66678","C544AC0D-30A66678","C544AC0D-B1A4FC51"}
    if (manifest.get("format") != 6 or manifest.get("source_keys") != 48 or keys != manifest.get("expected_keys") or
            hashlib.sha256("\n".join(keys).encode()).hexdigest() != FONT_V6_KEYSET_SHA256 or
            [manifest.get(k) for k in ("exact_font_row_alias_count","standalone_native_font_count","reconstructed_font_row_count")] != [5,30,13] or
            set(manifest.get("reconstructed_existing_description_keys",[])) != set(descriptions) or
            set(manifest.get("new_arm_keys",[])) != set(arms) or set(manifest.get("new_ranking_keys",[])) != ranking or
            manifest.get("prior_strict_outputs_preserved") != 39 or manifest.get("prior_main_outputs_preserved") != 30 or
            manifest.get("missing_source_archives")):
        raise ValueError("Font v6 requires the complete reviewed48-key set and exact13 reconstruction scopes")
    refs = manifest.get("parent_manifest_refs",{})
    if set(refs) != {"hud","aee","font_v1","font_v2","font_v3","font_v4"} or not extra_menu_manifest:
        raise ValueError("Font v6 predecessor chain is incomplete")
    checked = {}
    staging = Path("C:/github/REMASTER_STAGING").resolve()
    def reference(path,digest):
        path = Path(path).resolve()
        if not (path.is_relative_to(ROOT) or path.is_relative_to(staging)) or not path.is_file() or sha(path) != digest:
            raise ValueError("Font v6 source/base evidence changed: "+str(path))
        checked[str(path)] = digest
        return path
    for name,info in refs.items():
        reference(info["path"],info["sha256"])
    for name,selected in (("hud",hud_manifest),("aee",extra_menu_manifest)):
        if refs[name] != {"path":selected["path"],"sha256":selected["sha256"]}:
            raise ValueError("Font v6 differs from selected HUD/AEE parents")
    prior = json.loads(Path(refs["font_v4"]["path"]).read_text())
    if prior.get("contract") != "verified-font-strip-v4":
        raise ValueError("Font v6 requires reviewed font v4")
    prior_directory,prior_inventory = inventory(Path(prior["files"][0]["outputs"]["pack"]["path"]).parent,"font strip")
    prior_receipt = verify_font_strip_map(prior_directory,prior_inventory,hud_manifest,extra_menu_manifest)
    for info in prior_receipt.get("referenced_files",[]):
        checked[info["path"]] = info["sha256"]
    old_rows = {row["key"]:row for row in prior["files"]}
    bindings = []
    for row in manifest["files"]:
        key = row["key"]
        old = old_rows.get(key)
        if old:
            if row["outputs"]["strict-mask-pack"]["sha256"] != old["outputs"]["strict-mask-pack"]["sha256"]:
                raise ValueError("Font v6 changed an existing strict comparison")
            if key not in descriptions and row["outputs"]["pack"]["sha256"] != old["outputs"]["pack"]["sha256"]:
                raise ValueError("Font v6 changed an unselected accepted main output")
        images = {}
        for name,info in row["outputs"].items():
            path = reference(info["path"],info["sha256"])
            with Image.open(path) as image:
                if image.size != (4096,128):
                    raise ValueError("Font v6 output dimensions differ")
                images[name] = np.asarray(image.convert("RGBA"))
            if info.get("rgba_sha256") and hashlib.sha256(images[name].tobytes()).hexdigest() != info["rgba_sha256"]:
                raise ValueError("Font v6 RGBA output receipt differs")
        if set(images) != {"pack","strict-mask-pack"} or not set(np.unique(images["pack"][:,:,3])) <= {0,127,255}:
            raise ValueError("Font v6 output variants/alpha classes differ")
        if row.get("kind") == "exact_font_row_alias":
            if not old or key in descriptions or old.get("kind") != "exact_font_row_alias":
                raise ValueError("Font v6 invented a new exact alias")
            bindings.append(dict(key=key,kind=row["kind"],existing_identity_key=row.get("existing_identity_key",False)))
            continue
        archives = row.get("source_archives",{})
        if set(archives) != {"words","clut","validity","metadata"}:
            raise ValueError("Font v6 requires complete native archives")
        paths = {name:reference(info["path"],info["sha256"]) for name,info in archives.items()}
        raw,clut,valid = (paths[name].read_bytes() for name in ("words","clut","validity"))
        metadata = json.loads(paths["metadata"].read_text())
        if (len(raw) != 1024 or len(clut) != 32 or valid != bytes([1])*512 or
                f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key or metadata != row.get("source_metadata") or
                metadata.get("key") != key or [metadata.get(k) for k in ("width_words","height","depth","clut_words","known_words","total_words")] != [64,8,0,16,512,512] or
                any(row.get(flag) is not True for flag in ("source_crc_verified","source_decode_verified","source_validity_complete","canonical_native_rgba_exact","source_local_uv_coordinates_preserved"))):
            raise ValueError("Font v6 original source CRC/CLUT/validity differs: "+key)
        words = np.frombuffer(raw,dtype="<u2").reshape(8,64)
        indices = ((words[:,:,None] >> np.array([0,4,8,12]))&15).astype(np.uint8).reshape(8,256)
        values = np.frombuffer(clut,dtype="<u2")
        palette = np.column_stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                    np.where(values==0,0,np.where(values&0x8000,255,127)))).astype(np.uint8)
        native = palette[indices]
        source = reference(row["source"],row["source_sha256"])
        with Image.open(source) as image:
            if image.size != (256,8) or image.convert("RGBA").tobytes() != native.tobytes():
                raise ValueError("Font v6 independent native decode differs")
        native_alpha = np.repeat(np.repeat(native[:,:,3],16,axis=0),16,axis=1)
        if (hashlib.sha256(native.tobytes()).hexdigest() != row.get("native_rgba_sha256") or
                not np.array_equal(images["strict-mask-pack"][:,:,3],native_alpha)):
            raise ValueError("Font v6 strict/source native alpha differs")
        if key in descriptions or key in arms:
            regions = [[0,0,64,8],[192,0,256,8]] if key in descriptions else [[0,0,128,8]]
            if (row.get("kind") != "reconstructed_font_row" or row.get("selected_native_regions") != regions or
                    row.get("canonical_profile") != "source_midpoint_glyph_silhouette" or row.get("glyph_silhouette_cutoff") != 8 or
                    row.get("canonical_source_codes") != list(range(16)) or row.get("canonical_levels") != list(range(16)) or
                    row.get("exact_parent_rgba_crop") is not False or row.get("protected_outside_exact_to_base") is not True):
                raise ValueError("Font v6 reconstructed row escaped its reviewed glyph scope")
            base_path = reference(row["base_path"],row["base_sha256"])
            if old and row["base_sha256"] != old["outputs"]["pack"]["sha256"]:
                raise ValueError("Font v6 description base differs from reviewed v4")
            with Image.open(base_path) as image:
                if image.size != (4096,128):
                    raise ValueError("Font v6 reconstructed base dimensions differ")
                before = np.asarray(image.convert("RGBA"))
            outside = np.ones((128,4096),dtype=bool)
            for x0,y0,x1,y1 in regions:
                outside[y0*16:y1*16,x0*16:x1*16] = False
            if not np.array_equal(images["pack"][outside],before[outside]):
                raise ValueError("Font v6 changed protected icon/logo/right-half pixels")
            if key in arms and not np.array_equal(images["strict-mask-pack"][outside],before[outside]):
                raise ValueError("Font v6 strict ARM comparison changed protected right-half pixels")
            parent = row["raw_parent"]
            parent_raw = reference(parent["source_words_path"],parent["source_words_sha256"]).read_bytes()
            parent_clut = reference(parent["source_clut_path"],parent["source_clut_sha256"]).read_bytes()
            expected_parent = "BDAE4156-B88C038E" if key in descriptions else "1AD90FC9-79902A90"
            y = descriptions.get(key,arms.get(key))
            if (parent.get("key") != expected_parent or parent.get("native_row") != y or
                    f"{zlib.crc32(parent_raw):08X}" != expected_parent[:8] or parent_raw[y*128:(y+8)*128] != raw or
                    len(parent_clut)!=32 or f"{zlib.crc32(parent_clut):08X}" != expected_parent.split("-")[1] or
                    (key in descriptions and (parent_clut != clut or parent.get("clut_exact") is not True)) or
                    (key in arms and parent.get("clut_exact") is not False)):
                raise ValueError("Font v6 original raw-parent row/CLUT proof differs")
        elif not old and key in ranking:
            if (row.get("kind") != "standalone_native_font" or row.get("canonical_profile") != "seven_used_source_anchors" or
                    row.get("canonical_source_codes") != [15,14,13,12,11,10,0] or row.get("canonical_levels") != [0,3,6,9,11,13,15] or
                    row.get("selected_native_regions") != [[0,0,256,8]] or not set(np.unique(indices)) <= {0,10,11,12,13,14,15}):
                raise ValueError("Font v6 new ranking source profile differs")
        elif not old or row.get("kind") != "standalone_native_font":
            raise ValueError("Font v6 unreviewed row kind")
        if not row.get("native_ui_receipts"):
            raise ValueError("Font v6 needs actual native draw provenance")
        for native_receipt in row["native_ui_receipts"]:
            reference(native_receipt["capture_path"],native_receipt["capture_sha256"])
            if not any(draw.get("key")==key and draw.get("native_words")==[64,8] for draw in native_receipt.get("draws",[])):
                raise ValueError("Font v6 native row ownership receipt missing")
        bindings.append(dict(key=key,kind=row["kind"],native_regions=row.get("selected_native_regions"),independent_source_crc_clut_decode_verified=True))
    receipt.update(contract=manifest["contract"],reviewed_keyset_sha256=FONT_V6_KEYSET_SHA256,family_role_bindings=bindings,
                   protected_main_outputs_preserved=30,protected_strict_outputs_preserved=39,
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in checked.items()])
    return receipt


def verify_menu_map(directory, rows):
    receipt = verify_overlay(directory,rows,"menu",12)
    manifest = json.loads(Path(receipt["path"]).read_text())
    if manifest.get("contract") != "verified-menu-d036-alpha-v8":
        return receipt
    from PIL import Image
    import numpy as np
    previous_path = owned(Path(manifest["revision_source"])/"manifest.json")
    expected_previous_sha = "c70a9cd7a9b6fbac30139a92def8750bc0ab67a326d580c78228df4b7a5936d7"
    if (manifest.get("revision_source_manifest_sha256") != expected_previous_sha or
            sha(previous_path) != expected_previous_sha or manifest.get("scale") != 16):
        raise ValueError("Menu v8 requires the exact reviewed v7 predecessor")
    previous = json.loads(previous_path.read_text())
    old_rows = {row["key"]:row for row in previous["assets"]}
    if {row["key"] for row in manifest["assets"]} != set(old_rows) or len(old_rows) != 12:
        raise ValueError("Menu v8 changed its reviewed twelve-key set")
    changed = {"D0365088-79902A90","D0365088-B5A45715"}
    regions = [[0,0,252,168],[0,168,136,232],[136,168,248,224]]
    references = {str(previous_path):expected_previous_sha}
    for row in manifest["assets"]:
        old = old_rows[row["key"]]
        if any(row.get(field) != old.get(field) for field in ("source_sha256","source_words_sha256","source_clut_sha256",
                "source_metadata","source_size","selected_native_regions")):
            raise ValueError("Menu v8 changed reviewed native source identity or UV scope")
        for kind in ("pack","strict-mask-pack"):
            old_info,info = old["outputs"][kind],row["outputs"][kind]
            for item in (old_info,info):
                path = owned(item["path"])
                if sha(path) != item["sha256"]:
                    raise ValueError("Menu v8 predecessor/output hash changed")
                references[str(path)] = item["sha256"]
            if (kind == "strict-mask-pack" or row["key"] not in changed) and info["sha256"] != old_info["sha256"]:
                raise ValueError("Menu v8 changed a protected predecessor output")
        if row["key"] in changed:
            if (row.get("selected_native_regions") != regions or
                    any(row.get("checks",{}).get(check) is not True for check in
                        ("main_contour_alpha_categorical","outside_selected_rgba_exact_to_v7","strict_output_byte_exact_to_v7"))):
                raise ValueError("Menu v8 D036 source scope differs")
            with Image.open(old["outputs"]["pack"]["path"]) as image:
                before = np.asarray(image.convert("RGBA"))
            with Image.open(row["outputs"]["pack"]["path"]) as image:
                after = np.asarray(image.convert("RGBA"))
            outside = np.ones((4096,4096),dtype=bool)
            for x0,y0,x1,y1 in regions:
                outside[y0*16:y1*16,x0*16:x1*16] = False
            if (before.shape != (4096,4096,4) or after.shape != before.shape or
                    not np.array_equal(before[:,:,:3],after[:,:,:3]) or
                    not np.array_equal(before[outside],after[outside]) or
                    not set(np.unique(after[:,:,3])) <= {0,127,255} or
                    np.array_equal(before[:,:,3],after[:,:,3])):
                raise ValueError("Menu v8 escaped its alpha-only D036 revision scope")
    receipt.update(contract=manifest["contract"],compatible_parent_manifest_sha256=expected_previous_sha,
                   d036_alpha_only_verified=True,protected_outputs_preserved=22,
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])
    return receipt


def verify_results_palette(directory, rows):
    from PIL import Image
    import numpy as np
    candidates = (directory/"manifest.json",directory.parent/"manifest.json",directory.parent.parent/"manifest.json")
    path = next((path for path in candidates if path.is_file()),None)
    if path is None:
        raise ValueError("Results024 pack requires its completed manifest")
    manifest = json.loads(path.read_text())
    key = "8E1A509D-02491337"
    region = [[0,0,256,236]]
    if (len(rows)!=1 or rows[0]["name"] != key+".png" or manifest.get("contract") != "verified-results-palette-024-v1" or
            manifest.get("key") != key or manifest.get("asset_count") != 1 or manifest.get("scale") != 16 or
            manifest.get("regions") != region or any(manifest.get(flag) is not True for flag in
                ("main_categorical_contour_alpha","strict_original_alpha_footprint_exact","protected_outside_regions_rgba_exact_to_native_nearest"))):
        raise ValueError("Results palette overlay must be the complete bounded exact024 asset")
    references = {}
    def reference(path,digest):
        path = owned(path)
        if sha(path) != digest:
            raise ValueError("Results024 source/output evidence changed")
        references[str(path)] = digest
        return path
    source = manifest["source"]
    vram_path = reference(source["vram"],source["vram_sha256"])
    reference(source["receipt"],source["receipt_sha256"])
    proof = {}
    for info in manifest.get("source_proof_files",[]):
        p = reference(info["path"],info["sha256"])
        proof[p.name] = p
    needed = {key+suffix for suffix in (".words.bin",".clut.bin",".valid.bin",".source.json",".png")}
    if not needed <= set(proof):
        raise ValueError("Results024 original source archives incomplete")
    raw,clut,valid = (proof[key+suffix].read_bytes() for suffix in (".words.bin",".clut.bin",".valid.bin"))
    meta = json.loads(proof[key+".source.json"].read_text())
    raw_vram = vram_path.read_bytes()
    if (len(raw_vram) != 1024*512*2 or len(raw)!=32768 or len(clut)!=32 or valid!=bytes([1])*16384 or
            f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key or meta != source.get("metadata") or
            meta.get("page_xy") != [512,0] or meta.get("clut_xy") != [16,480] or
            [meta.get(k) for k in ("width_words","height","depth","clut_words","known_words","total_words")] != [64,256,0,16,16384,16384] or
            hashlib.sha256(raw).hexdigest() != source.get("words_sha256") or hashlib.sha256(clut).hexdigest() != source.get("clut_sha256")):
        raise ValueError("Results024 source/page/CLUT proof differs")
    vram = np.frombuffer(raw_vram,dtype="<u2").reshape(512,1024)
    if vram[:256,512:576].copy().tobytes()!=raw or vram[480,16:32].copy().tobytes()!=clut:
        raise ValueError("Results024 archives differ from canonical VRAM snapshot")
    words = np.frombuffer(raw,dtype="<u2").reshape(256,64)
    indices = ((words[:,:,None] >> np.array([0,4,8,12]))&15).astype(np.uint8).reshape(256,256)
    values = np.frombuffer(clut,dtype="<u2")
    palette = np.column_stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                np.where(values==0,0,np.where(values&0x8000,255,127)))).astype(np.uint8)
    native = Image.fromarray(palette[indices])
    with Image.open(proof[key+".png"]) as image:
        if image.convert("RGBA").tobytes() != native.tobytes() or image.size != (256,256):
            raise ValueError("Results024 source PNG differs from independent decode")
    if hashlib.sha256(native.tobytes()).hexdigest() != source.get("pixels_sha256"):
        raise ValueError("Results024 native pixel proof differs")
    before = native.resize((4096,4096),Image.Resampling.NEAREST)
    outputs = manifest.get("outputs",{})
    if set(outputs) != {"pack","strict-mask-pack"}:
        raise ValueError("Results024 requires main and strict comparison PNGs")
    for variant,info in outputs.items():
        output_path = reference(info["path"],info["sha256"])
        with Image.open(output_path) as image:
            after = image.convert("RGBA")
        if (after.size != (4096,4096) or not set(after.getchannel("A").getdata()) <= {0,127,255} or
                after.crop((0,3776,4096,4096)).tobytes() != before.crop((0,3776,4096,4096)).tobytes() or
                (variant=="strict-mask-pack" and after.getchannel("A").tobytes()!=before.getchannel("A").tobytes())):
            raise ValueError("Results024 alpha/protected footer scope differs")
    selected = next((info for info in outputs.values() if Path(info["path"]).resolve()==Path(rows[0]["path"]).resolve()),None)
    if not selected or selected["sha256"] != rows[0]["sha256"]:
        raise ValueError("Results024 selected output differs from manifest")
    return dict(path=str(path),sha256=sha(path),asset_count=1,contract=manifest["contract"],native_regions=region,
                independent_source_crc_clut_decode_verified=True,protected_outside_exact=True,
                referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])


def verify_results_art(directory, rows):
    from PIL import Image
    import numpy as np
    receipt = verify_overlay(directory,rows,"results art",5)
    manifest = json.loads(Path(receipt["path"]).read_text())
    order = [key+"-00000000" for key in ("F2BDBE54","69A29FD8","ABB8CC89","41855657","FC55F5E0")]
    page_positions = [[320,0],[384,0],[448,0],[320,256],[384,256]]
    assets = manifest.get("assets",manifest.get("files",[]))
    if manifest.get("contract") != "verified-results-art-v1" or {r["key"] for r in assets} != set(order):
        raise ValueError("Results art requires the complete reviewed five-page poster")
    references = {}
    def reference(path,digest):
        path = owned(path)
        if sha(path) != digest:
            raise ValueError("Results art source/output evidence changed: "+str(path))
        references[str(path)] = digest
        return path
    for name in ("master","encoded_master","prompt","source_mapping","ffmpeg_receipts"):
        info = manifest[name]
        reference(info["path"],info["sha256"])
    mapping = json.loads(Path(manifest["source_mapping"]["path"]).read_text())
    if mapping.get("contract") != "verified-results-poster-source-v1" or {p["key"] for p in mapping.get("pages",[])} != set(order):
        raise ValueError("Results art native source-page mapping incomplete")
    for name in ("source_master","display_reference","gp0","vram","source_log"):
        info = mapping[name]
        reference(info["path"],info["sha256"])
    reference(mapping["vram"]["receipt_path"],mapping["vram"]["receipt_sha256"])
    raw_vram = Path(mapping["vram"]["path"]).read_bytes()
    if len(raw_vram) != 1024*512*2:
        raise ValueError("Results art canonical VRAM snapshot incomplete")
    vram = np.frombuffer(raw_vram,dtype="<u2").reshape(512,1024)
    with Image.open(manifest["master"]["path"]) as image:
        if list(image.size) != manifest["master"]["size"] or image.size != (1499,1049):
            raise ValueError("Results art generated master dimensions differ")
    with Image.open(manifest["encoded_master"]["path"]) as image:
        if image.size != (5120,3584) or manifest["encoded_master"]["size"] != [5120,3584]:
            raise ValueError("Results art encoded master dimensions differ")
        encoded = np.asarray(image.convert("RGB"))
    ffmpeg = json.loads(Path(manifest["ffmpeg_receipts"]["path"]).read_text())
    if len(ffmpeg)!=6 or any(row.get("exit_code")!=0 for row in ffmpeg):
        raise ValueError("Results art scale/five-strip conversion receipt incomplete")
    selected = {row["name"]:row for row in rows}
    mapped = {page["key"]:page for page in mapping["pages"]}
    for asset in assets:
        key = asset["key"]
        i = order.index(key)
        page = mapped[key]
        px,py = page_positions[i]
        if (asset.get("region_half_open") != [0,0,64,224] or
                asset.get("master_crop_half_open") != [64*i,0,64*(i+1),224] or
                asset.get("source_page_xy") != [px,py] or page.get("page_xy") != [px,py] or
                page.get("replacement_region_half_open") != [0,0,64,224] or
                [page.get("draw",{}).get(k) for k in ("depth","size","source_uv")] != [2,[64,224],[0,0]] or
                any(asset.get(flag) is not True for flag in ("native_alpha_stp_footprint_exact","protected_outside_rgba_exact","clear_source_samples_rgba_exact"))):
            raise ValueError("Results art escaped verified page/strip geometry")
        source = reference(asset["source"],asset["source_sha256"])
        raw_path = reference(source.with_suffix(".words.bin"),asset["source_words_sha256"])
        clut_path = reference(source.with_suffix(".clut.bin"),asset["source_clut_sha256"])
        valid_path = source.with_suffix(".valid.bin")
        meta_path = source.with_suffix(".source.json")
        reference(valid_path,sha(valid_path)); reference(meta_path,sha(meta_path))
        raw,clut = raw_path.read_bytes(),clut_path.read_bytes()
        metadata = json.loads(meta_path.read_text())
        if (len(raw)!=131072 or clut or valid_path.read_bytes()!=bytes([1])*65536 or
                f"{zlib.crc32(raw):08X}-00000000" != key or
                [metadata.get(k) for k in ("key","width_words","height","depth","known_words","total_words")] != [key,256,256,2,65536,65536] or
                page.get("source_words_sha256") != asset["source_words_sha256"] or
                vram[py:py+256,px:px+256].copy().tobytes()!=raw):
            raise ValueError("Results art native source CRC/format/canonical VRAM differs")
        words = np.frombuffer(raw,dtype="<u2").reshape(256,256)
        native = np.stack(((words&31)<<3,((words>>5)&31)<<3,((words>>10)&31)<<3,
                    np.where(words==0,0,np.where(words&0x8000,255,127))),axis=2).astype(np.uint8)
        with Image.open(source) as image:
            if image.size!=(256,256) or image.convert("RGBA").tobytes()!=native.tobytes():
                raise ValueError("Results art source PNG differs from independent native decode")
        before = np.repeat(np.repeat(native,16,axis=0),16,axis=1)
        chosen = selected[key+".png"]
        with Image.open(chosen["path"]) as image:
            if image.size!=(4096,4096):
                raise ValueError("Results art output dimensions differ")
            after = np.asarray(image.convert("RGBA"))
        if (not np.array_equal(after[:,:,3],before[:,:,3]) or
                not np.array_equal(after[:,1024:],before[:,1024:]) or not np.array_equal(after[3584:,:1024],before[3584:,:1024]) or
                not np.array_equal(after[before[:,:,3]==0],before[before[:,:,3]==0])):
            raise ValueError("Results art changed source alpha, clear RGBA or unrelated page pixels")
        visible = before[:3584,:1024,3]!=0
        crop = encoded[:,i*1024:(i+1)*1024]
        if not np.array_equal(after[:3584,:1024,:3][visible],crop[visible]):
            raise ValueError("Results art authored pixels differ from exact whole-master crop")
    receipt.update(contract=manifest["contract"],native_region=[0,0,64,224],
                   independent_native_source_verified=True,full_native_alpha_and_clear_rgba_exact=True,protected_outside_exact=True,
                   source_generated_size=[1499,1049],encoded_master_size=[5120,3584],
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])
    return receipt


def verify_copyright_map(directory, rows, menu_manifest, menu_rows):
    from PIL import Image
    receipt = verify_overlay(directory, rows, "copyright", 3)
    manifest = json.loads(Path(receipt["path"]).read_text())
    region = [80,236,199,248]
    expected = {"8E1A509D-" + palette for palette in ("4FE32821","8808F70A","C7A1F2F0")}
    assets = manifest.get("assets",[])
    if ({row["key"] for row in assets} != expected or manifest.get("region_native_half_open") != region or
            manifest.get("base_manifest_sha256") not in {value for value in (menu_manifest["sha256"],menu_manifest.get("compatible_parent_manifest_sha256")) if value}):
        raise ValueError("Copyright overlay must be the complete bounded three-palette menu-v7 supplement")
    parents = {row["name"]:row for row in menu_rows}
    result_rows = {row["name"]:row for row in rows}
    references = []
    for asset in assets:
        name = asset["key"] + ".png"
        parent = parents.get(name)
        chosen = result_rows[name]
        base_path = owned(asset.get("base",""))
        if (not parent or sha(base_path) != parent["sha256"] or
                asset.get("base_sha256") != parent["sha256"] or asset.get("selected_native_regions") != [region] or
                any(asset.get("checks",{}).get(check) is not True for check in
                    ("source_crc_clut_decode_exact","outside_copyright_region_byte_exact_to_v7","categorical_classes_only","png_roundtrip_exact"))):
            raise ValueError("Unverified copyright parent/scope: " + name)
        with Image.open(parent["path"]) as image:
            before = image.convert("RGBA")
        with Image.open(chosen["path"]) as image:
            after = image.convert("RGBA")
        if before.size != (4096,4096) or after.size != before.size:
            raise ValueError("Copyright atlas dimensions changed")
        x0,y0,x1,y1 = [value*16 for value in region]
        protected = [(0,0,4096,y0),(0,y0,x0,y1),(x1,y0,4096,y1),(0,y1,4096,4096)]
        if any(before.crop(box).tobytes() != after.crop(box).tobytes() for box in protected):
            raise ValueError("Copyright edit escaped its bounded source rectangle: " + name)
        if not set(after.getchannel("A").getdata()) <= {0,127,255}:
            raise ValueError("Copyright overlay invented an alpha class")
        chosen["authorized_overlay_parent"] = {key:parent[key] for key in ("origin","path","sha256")}
        chosen["authorized_override_scope"] = region
        references.append(dict(path=parent["path"],sha256=parent["sha256"]))
        references.append(dict(path=str(base_path),sha256=parent["sha256"]))
    receipt.update(native_region=region,referenced_files=references,
                   override_rule="Only these three verified menu-v7 files; all RGBA outside the footer rectangle is byte-exact")
    return receipt


def verify_banner_font_map(directory, rows):
    from PIL import Image
    import numpy as np
    receipt = verify_overlay(directory, rows, "banner font", 7)
    manifest = json.loads(Path(receipt["path"]).read_text())
    v2 = manifest.get("contract") == "verified-banner-font-v2"
    region = [0,32,256,80 if v2 else 64]
    palettes = {"C04998CA":224,"C04F65C0":176,"B1A4FC51":288,
                "8EAF967E":192,"30A66678":208,"166E4BE3":256,"CB9F39AB":240}
    assets = manifest.get("assets",[])
    if (manifest.get("schema_version") != 1 or manifest.get("source_frame") != 67050 or
            manifest.get("region_native_half_open") != region or
            {row["key"] for row in assets} != {"B77B98B9-"+p for p in palettes} or
            manifest.get("source_vram_sha256") != "c6aaac99a6b54dd5aca673a470500b683879cfccff0e4819edbb5d0a13525c17"):
        raise ValueError("Banner font requires the complete reviewed seven-palette B77 header overlay")
    snapshot = owned(manifest["source_vram"])
    if sha(snapshot) != manifest["source_vram_sha256"]:
        raise ValueError("Banner source VRAM snapshot changed")
    raw_vram = snapshot.read_bytes()
    if len(raw_vram) != 1024*512*2:
        raise ValueError("Banner source VRAM snapshot is incomplete")
    vram = np.frombuffer(raw_vram,dtype="<u2").reshape(512,1024)
    raw = vram[:256,640:704].copy().astype("<u2").tobytes()
    words = np.frombuffer(raw,dtype="<u2").reshape(256,64)
    indices = ((words[:,:,None] >> np.array([0,4,8,12])) & 15).astype(np.uint8).reshape(256,256)
    if not set(np.unique(indices[32:region[3]])) <= {0,10,11,12,13,14,15}:
        raise ValueError("Banner source header is outside the reviewed original glyph ramp")
    references = {str(snapshot):sha(snapshot)}
    for asset in assets:
        key = asset["key"]
        suffix = key.split("-")[1]
        source_root = Path(receipt["path"]).parent / "sources"
        paths = {name:owned(source_root/(key+extension)) for name,extension in
                 (("words",".words.bin"),("clut",".clut.bin"),("validity",".valid.bin"),
                  ("metadata",".source.json"),("png",".png"))}
        clut = vram[487,palettes[suffix]:palettes[suffix]+16].copy().astype("<u2").tobytes()
        metadata = json.loads(paths["metadata"].read_text())
        checks = ("raw_source_crc_exact","clut_crc_exact","canonical_native_rgba_exact",
                  "outside_header_band_nearest_source_exact","png_roundtrip_exact") + (
                  ("main_categorical_contour_alpha","strict_original_alpha_footprint_exact") if v2 else
                  ("entire_original_alpha_footprint_exact",))
        if (f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key or
                paths["words"].read_bytes() != raw or paths["clut"].read_bytes() != clut or
                paths["validity"].read_bytes() != bytes([1])*16384 or
                sha(paths["words"]) != asset.get("source_words_sha256") or
                sha(paths["clut"]) != asset.get("source_clut_sha256") or
                metadata != asset.get("source_metadata") or
                metadata.get("clut_xy") != [palettes[suffix],487] or
                [metadata.get("width_words"),metadata.get("height"),metadata.get("depth"),metadata.get("known_words")] != [64,256,0,16384] or
                asset.get("selected_native_regions") != [region] or
                any(asset.get("checks",{}).get(check) is not True for check in checks)):
            raise ValueError("Banner source/CLUT/coverage proof differs: "+key)
        values = np.frombuffer(clut,dtype="<u2")
        palette = np.column_stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                    np.where(values==0,0,np.where(values&0x8000,255,127)))).astype(np.uint8)
        native = Image.fromarray(palette[indices])
        with Image.open(paths["png"]) as image:
            if image.size != (256,256) or image.convert("RGBA").tobytes() != native.tobytes():
                raise ValueError("Banner source PNG differs from independent native decode: "+key)
        before = native.resize((4096,4096),Image.Resampling.NEAREST)
        chosen = next(row for row in rows if row["name"] == key+".png")
        with Image.open(chosen["path"]) as image:
            after = image.convert("RGBA")
        if (after.size != before.size or
                (not v2 and after.getchannel("A").tobytes() != before.getchannel("A").tobytes()) or
                not set(after.getchannel("A").getdata()) <= {0,127,255} or
                any(after.crop(box).tobytes() != before.crop(box).tobytes() for box in
                    ((0,0,4096,512),(0,region[3]*16,4096,4096)))):
            raise ValueError("Banner font escaped its header band or changed native alpha: "+key)
        if v2:
            outputs = asset.get("outputs",{})
            if set(outputs) != {"pack","strict-mask-pack"}:
                raise ValueError("Banner v2 requires both authored and native-alpha comparison outputs")
            variants = {}
            for name,info in outputs.items():
                path = owned(info["path"])
                if sha(path) != info["sha256"]:
                    raise ValueError("Banner v2 comparison PNG changed")
                references[str(path)] = info["sha256"]
                with Image.open(path) as image:
                    variants[name] = image.convert("RGBA")
            main,strict = variants["pack"],variants["strict-mask-pack"]
            if (main.size != (4096,4096) or strict.size != main.size or
                    strict.getchannel("A").tobytes() != before.getchannel("A").tobytes() or
                    main.convert("RGB").tobytes() != strict.convert("RGB").tobytes() or
                    not set(main.getchannel("A").getdata()) <= {0,127,255} or
                    any(main.crop(box).tobytes() != before.crop(box).tobytes() for box in
                        ((0,0,4096,512),(0,region[3]*16,4096,4096)))):
                raise ValueError("Banner v2 authored/strict alpha or protected-outside scope differs")
        references.update({str(path):sha(path) for path in paths.values()})
    receipt.update(native_region=region,source_frame=67050,independent_source_crc_clut_decode_verified=True,
                   entire_original_alpha_footprint_exact=not v2,strict_original_alpha_footprint_exact=True,
                   alpha_policy="categorical_contour_inside_authored_region" if v2 else "exact_native_footprint",
                   outside_header_band_nearest_source_exact=True,
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])
    return receipt


def verify_blueprint_map(directory, rows, base_rows):
    from PIL import Image
    import numpy as np
    receipt = verify_overlay(directory,rows,"fighter blueprint",11)
    manifest = json.loads(Path(receipt["path"]).read_text())
    expected = {"ECFB77E3-"+p for p in ("0001B466","236629BD","411C62A8","4FE32821","8CBA9638",
                "B5956369","C1CAA268","DD532904","F6FBE721","F798F5B6","FB10C304")}
    regions = [[0,0,127,84],[72,85,127,170],[0,109,71,180]]
    if (manifest.get("contract") != "verified-fighter-blueprint-v1" or manifest.get("source_keys") != 11 or
            set(manifest.get("expected_keys",[])) != expected or len(manifest.get("expected_keys",[])) != 11 or
            {r["key"] for r in manifest.get("files",[])} != expected):
        raise ValueError("Fighter blueprint requires all eleven reviewed source/palette keys")
    references = {}
    staging = Path("C:/github/REMASTER_STAGING").resolve()
    def reference(path,digest):
        path = Path(path).resolve()
        if not (path.is_relative_to(ROOT) or path.is_relative_to(staging)) or not path.is_file():
            raise ValueError("Blueprint evidence must be an owned file")
        if sha(path) != digest:
            raise ValueError("Blueprint source/base evidence changed: "+str(path))
        if str(path) in references and references[str(path)] != digest:
            raise ValueError("Blueprint conflicting evidence hashes")
        references[str(path)] = digest
        return path
    if manifest.get("source_queue_sha256") != "c5eb8b63322c54c0ef214eea4baf530a5cf05a0297d9ac19def5d12fdbcf9cb4":
        raise ValueError("Blueprint queue revision is not the reviewed source set")
    reference(manifest["source_queue"],manifest["source_queue_sha256"])
    capture = manifest.get("native_capture",{})
    reference(capture["path"],capture["sha256"])
    selected_base = {row["name"]:row for row in base_rows}
    outside = np.ones((4096,4096),dtype=bool)
    for x0,y0,x1,y1 in regions:
        outside[y0*16:y1*16,x0*16:x1*16] = False
    for row in manifest["files"]:
        key = row["key"]
        if (row.get("kind") != "bounded_blueprint_lineart" or row.get("source_size") != [256,256] or
                row.get("base_size") != [2048,2048] or row.get("selected_native_regions") != regions or
                any(row.get(flag) is not True for flag in ("source_crc_verified","source_decode_verified",
                    "source_validity_complete","outside_regions_exact","native_alpha_footprint_exact",
                    "base_alpha_footprint_exact","source_local_uv_coordinates_preserved"))):
            raise ValueError("Blueprint source/region contract changed: "+key)
        archives = row.get("source_archives",{})
        if set(archives) != {"words","clut","validity","metadata"}:
            raise ValueError("Blueprint requires complete original source archives")
        paths = {name:reference(info["path"],info["sha256"]) for name,info in archives.items()}
        raw,clut,valid = (paths[name].read_bytes() for name in ("words","clut","validity"))
        metadata = json.loads(paths["metadata"].read_text())
        if (len(raw) != 32768 or len(clut) != 32 or valid != bytes([1])*16384 or
                f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key or
                metadata != row.get("source_metadata") or metadata.get("key") != key or
                [metadata.get("width_words"),metadata.get("height"),metadata.get("depth"),metadata.get("clut_words"),metadata.get("known_words"),metadata.get("total_words")] != [64,256,0,16,16384,16384]):
            raise ValueError("Blueprint original source CRC/CLUT/validity differs: "+key)
        words = np.frombuffer(raw,dtype="<u2").reshape(256,64)
        indices = ((words[:,:,None] >> np.array([0,4,8,12])) & 15).astype(np.uint8).reshape(256,256)
        values = np.frombuffer(clut,dtype="<u2")
        palette = np.column_stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                    np.where(values==0,0,np.where(values&0x8000,255,127)))).astype(np.uint8)
        native = Image.fromarray(palette[indices])
        source_path = reference(row["source"],row["source_sha256"])
        with Image.open(source_path) as image:
            if image.size != (256,256) or image.convert("RGBA").tobytes() != native.tobytes():
                raise ValueError("Blueprint source PNG differs from independent original decode: "+key)
        base_row = selected_base.get(key+".png")
        if not base_row or row.get("base_sha256") != base_row["sha256"]:
            raise ValueError("Blueprint was authored against a different selected base: "+key)
        base_path = reference(row["base_path"],row["base_sha256"])
        with Image.open(base_path) as image:
            if image.size != (2048,2048):
                raise ValueError("Blueprint base dimensions differ")
            before = np.asarray(image.convert("RGBA").resize((4096,4096),Image.Resampling.NEAREST))
        output = next((info for info in row["outputs"].values() if Path(info["path"]).resolve().parent == directory.resolve()),None)
        if not output:
            raise ValueError("Blueprint selected output missing")
        with Image.open(output["path"]) as image:
            if image.size != (4096,4096):
                raise ValueError("Blueprint output dimensions differ")
            after = np.asarray(image.convert("RGBA"))
        native_alpha = np.asarray(native.getchannel("A").resize((4096,4096),Image.Resampling.NEAREST))
        if (not np.array_equal(after[:,:,3],native_alpha) or not np.array_equal(after[:,:,3],before[:,:,3]) or
                not np.array_equal(after[outside],before[outside]) or
                hashlib.sha256(after.tobytes()).hexdigest() != output.get("rgba_sha256")):
            raise ValueError("Blueprint alpha/protected-outside/output contract differs: "+key)
    receipt.update(native_regions=regions,independent_source_crc_clut_decode_verified=True,
                   entire_original_alpha_footprint_exact=True,protected_outside_selected_base_exact=True,
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])
    return receipt


def verify_diagram_map(directory, rows, menu_manifest, menu_rows):
    from PIL import Image
    import numpy as np
    receipt = verify_overlay(directory,rows,"diagram",6)
    manifest = json.loads(Path(receipt["path"]).read_text())
    families = {"1AD90FC9":(["02491337","4315989E","79902A90"],[[224,40,256,74],[144,96,212,152],[96,160,160,232]]),
                "E6B65424":(["4C1DD349","611C5290","97713DC6"],[[144,112,192,124],[0,124,96,140],[0,140,100,188]])}
    expected = {family+"-"+p for family,(palettes,_) in families.items() for p in palettes}
    if (manifest.get("format") != 1 or {r["key"] for r in manifest.get("assets",[])} != expected or
            manifest.get("base_manifest_sha256") not in {value for value in (menu_manifest["sha256"],menu_manifest.get("compatible_parent_manifest_sha256")) if value}):
        raise ValueError("Diagram overlay requires all six reviewed menu-v7 source/palette keys")
    staging = Path("C:/github/REMASTER_STAGING").resolve()
    references = {}
    def reference(path,digest=None):
        path = Path(path).resolve()
        if not (path.is_relative_to(ROOT) or path.is_relative_to(staging)) or not path.is_file():
            raise ValueError("Diagram evidence must be an owned file")
        actual = sha(path)
        if digest is not None and actual != digest:
            raise ValueError("Diagram source evidence changed: "+str(path))
        references[str(path)] = actual
        return path
    parents = {row["name"]:row for row in menu_rows}
    chosen_rows = {row["name"]:row for row in rows}
    for row in manifest["assets"]:
        key = row["key"]
        regions = families[key.split("-")[0]][1]
        parent = parents.get(key+".png")
        checks = ("raw_crc_clut_decode_exact","outside_selected_regions_byte_exact_to_v7","categorical_classes_only","png_roundtrip_exact")
        if (not parent or sha(owned(row.get("base",""))) != parent["sha256"] or
                row.get("base_sha256") != parent["sha256"] or row.get("selected_native_regions") != regions or
                any(row.get("checks",{}).get(check) is not True for check in checks)):
            raise ValueError("Diagram selected menu parent/regions differ: "+key)
        source = reference(row["source"],row["source_sha256"])
        raw_path = reference(source.with_suffix(".words.bin"),row["source_words_sha256"])
        clut_path = reference(source.with_suffix(".clut.bin"),row["source_clut_sha256"])
        valid_path = reference(source.with_suffix(".valid.bin"))
        meta_path = reference(source.with_suffix(".source.json"))
        raw,clut,valid = raw_path.read_bytes(),clut_path.read_bytes(),valid_path.read_bytes()
        metadata = json.loads(meta_path.read_text())
        if (len(raw) != 32768 or len(clut) != 32 or valid != bytes([1])*16384 or
                f"{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}" != key or
                metadata != row.get("source_metadata") or metadata.get("key") != key or
                [metadata.get("width_words"),metadata.get("height"),metadata.get("depth"),metadata.get("clut_words"),metadata.get("known_words"),metadata.get("total_words")] != [64,256,0,16,16384,16384]):
            raise ValueError("Diagram original source CRC/CLUT/validity differs: "+key)
        words = np.frombuffer(raw,dtype="<u2").reshape(256,64)
        indices = ((words[:,:,None] >> np.array([0,4,8,12])) & 15).astype(np.uint8).reshape(256,256)
        values = np.frombuffer(clut,dtype="<u2")
        palette = np.column_stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                    np.where(values==0,0,np.where(values&0x8000,255,127)))).astype(np.uint8)
        with Image.open(source) as image:
            if image.size != (256,256) or image.convert("RGBA").tobytes() != palette[indices].tobytes():
                raise ValueError("Diagram source PNG differs from independent native decode: "+key)
        reference(parent["path"],parent["sha256"])
        reference(row["base"],row["base_sha256"])
        with Image.open(parent["path"]) as image:
            before = np.asarray(image.convert("RGBA"))
        chosen = chosen_rows[key+".png"]
        with Image.open(chosen["path"]) as image:
            after = np.asarray(image.convert("RGBA"))
        if before.shape != (4096,4096,4) or after.shape != before.shape:
            raise ValueError("Diagram atlas dimensions changed")
        outside = np.ones((4096,4096),dtype=bool)
        for x0,y0,x1,y1 in regions:
            outside[y0*16:y1*16,x0*16:x1*16] = False
        if not np.array_equal(after[outside],before[outside]) or not set(np.unique(after[:,:,3])) <= {0,127,255}:
            raise ValueError("Diagram edit escaped illustration regions or alpha classes: "+key)
        chosen["authorized_overlay_parent"] = {field:parent[field] for field in ("origin","path","sha256")}
        chosen["authorized_override_scope"] = regions
    receipt.update(native_regions={family:info[1] for family,info in families.items()},
                   independent_source_crc_clut_decode_verified=True,protected_menu_text_outside_exact=True,
                   referenced_files=[dict(path=path,sha256=digest) for path,digest in references.items()])
    return receipt


def merge_replacements(base_rows, overlay_rows):
    merged = {row["name"]: dict(row) for row in base_rows}
    seen = {}
    for row in overlay_rows:
        name = row["name"]
        source = {key: row[key] for key in ("origin", "path", "sha256")}
        if name in seen:
            if seen[name]["sha256"] != row["sha256"]:
                parent = row.get("authorized_overlay_parent")
                previous = seen[name]
                if (row["origin"] not in {"copyright","diagram"} or not parent or previous["origin"] != "menu" or
                        any(parent[key] != previous[key] for key in ("origin","path","sha256"))):
                    raise ValueError("Overlays contain different PNGs for the same key: " + name)
                chosen = dict(row, overlay_sources=previous["overlay_sources"] + [source],
                              overlay_override=dict(name=name,parent=parent,replacement=source,
                                                    native_region=row["authorized_override_scope"]))
                seen[name] = chosen
                merged[name] = chosen
                continue
            seen[name]["overlay_sources"].append(source)
        else:
            chosen = dict(row, overlay_sources=[source])
            seen[name] = chosen
            merged[name] = chosen
    redundant = [dict(name=name, sha256=row["sha256"], sources=row["overlay_sources"])
                 for name, row in seen.items() if len(row["overlay_sources"]) > 1 and
                 all(source["sha256"] == row["sha256"] for source in row["overlay_sources"])]
    return merged, redundant


def settings_override(original, pack):
    values = dict(supersampling="9", window_width="1280", rewind_depth="0",
                  aspect_ratio='"4:3"', fullscreen="0", hd_textures="true",
                  hd_texture_root=json.dumps(str(pack).replace("\\", "/")))
    lines = original.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "[video]"), None)
    if start is None:
        raise ValueError("Original settings have no [video] section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    section = lines[start + 1:end]
    for key, value in values.items():
        found = [i for i, line in enumerate(section) if re.match(r"^\s*" + re.escape(key) + r"\s*=", line)]
        if len(found) > 1:
            raise ValueError("Duplicate video setting: " + key)
        if found:
            section[found[0]] = key + " = " + value
        else:
            section.append(key + " = " + value)
    return "\n".join(lines[:start + 1] + section + lines[end:]) + "\n"


def copy_verified(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    digest = sha(source)
    if sha(target) != digest:
        raise ValueError("Copy hash mismatch: " + str(target))
    return digest


def launch_environment(overrides, inherited=None):
    environment = dict(os.environ if inherited is None else inherited)
    environment.update(overrides)
    for key in CLEANED_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    return environment


def plan(args):
    evidence = owned(args.evidence, ALLOWED)
    if evidence.exists():
        raise ValueError("Preparation requires a fresh evidence directory")
    if not args.hud_pack or not args.menu_pack:
        raise ValueError("Preparation requires --hud-pack and --menu-pack")
    selected = saved_selection(PROJECT)
    if not selected.get("valid"):
        raise ValueError(selected.get("error", "No valid saved skin profile"))
    prepared = prepare_launch(PROJECT, selected["config_path"])
    explicit_runtime = runtime_override(args.runtime_executable) if args.runtime_executable else None
    if explicit_runtime:
        prepared["runtime"] = dict(prepared["runtime"],
                                   executable=explicit_runtime["executable"], sha256=explicit_runtime["sha256"],
                                   selection="explicit candidate build", build_receipt=explicit_runtime["build_receipt"],
                                   build_receipt_sha256=explicit_runtime["build_receipt_sha256"])
        prepared["arguments"][0] = explicit_runtime["executable"]
    base_directory, base_rows = inventory(BASE, "base")
    verify_base(base_rows)
    hud_directory, hud_rows = inventory(args.hud_pack, "HUD")
    menu_directory, menu_rows = inventory(args.menu_pack, "menu")
    manifests = dict(hud=verify_overlay(hud_directory, hud_rows, "HUD", 34),
                     menu=verify_menu_map(menu_directory, menu_rows))
    font_directory, font_rows = inventory(args.font_strip_pack, "font strip") if args.font_strip_pack else (None, [])
    extra_menu_directory, extra_menu_rows = inventory(args.extra_menu_pack, "extra menu") if args.extra_menu_pack else (None, [])
    if extra_menu_directory:
        manifests["extra_menu"] = verify_overlay(extra_menu_directory, extra_menu_rows, "extra menu", 1)
        if not extra_menu_rows[0]["name"].startswith("AEE859DC-"):
            raise ValueError("Extra menu pack must contain exactly the verified AEE859DC file/options family")
    if font_directory:
        manifests["font_strip"] = verify_font_strip_map(font_directory, font_rows, manifests["hud"], manifests.get("extra_menu"))
    art_directory, art_rows = inventory(args.art_pack, "art") if args.art_pack else (None, [])
    if art_directory:
        manifests["art"] = verify_overlay(art_directory, art_rows, "art", (1, 2))
    copyright_directory, copyright_rows = inventory(args.copyright_pack,"copyright") if args.copyright_pack else (None,[])
    if copyright_directory:
        manifests["copyright"] = verify_copyright_map(copyright_directory,copyright_rows,manifests["menu"],menu_rows)
    banner_directory, banner_rows = inventory(args.banner_font_pack,"banner font") if args.banner_font_pack else (None,[])
    if banner_directory:
        manifests["banner_font"] = verify_banner_font_map(banner_directory,banner_rows)
    blueprint_directory, blueprint_rows = inventory(args.blueprint_pack,"fighter blueprint") if args.blueprint_pack else (None,[])
    if blueprint_directory:
        manifests["blueprint"] = verify_blueprint_map(blueprint_directory,blueprint_rows,base_rows)
    diagram_directory, diagram_rows = inventory(args.diagram_pack,"diagram") if args.diagram_pack else (None,[])
    if diagram_directory:
        manifests["diagram"] = verify_diagram_map(diagram_directory,diagram_rows,manifests["menu"],menu_rows)
    results_directory, results_rows = inventory(args.results_palette_pack,"results palette") if args.results_palette_pack else (None,[])
    if results_directory:
        manifests["results_palette"] = verify_results_palette(results_directory,results_rows)
    results_art_directory, results_art_rows = inventory(args.results_art_pack,"results art") if args.results_art_pack else (None,[])
    if results_art_directory:
        manifests["results_art"] = verify_results_art(results_art_directory,results_art_rows)
    overlay_rows = hud_rows + menu_rows + extra_menu_rows + font_rows + art_rows + copyright_rows + banner_rows + blueprint_rows + diagram_rows + results_rows + results_art_rows
    original_settings = PROJECT / "build-release/settings.toml"
    if not original_settings.is_file():
        raise ValueError("Original settings.toml is required")
    merged, redundant = merge_replacements(base_rows, overlay_rows)
    runtime_data = Path(prepared["runtime"]["executable"]).read_bytes()
    required = [b"screenshot_hires", b"present_shot_seq", b"internal scale %dx"]
    if any(token not in runtime_data for token in required):
        raise ValueError("Runtime does not expose the required high-resolution capture commands")
    return dict(at_utc=stamp(), evidence=str(evidence), base_root=str(BASE),
                hud_root=str(hud_directory), menu_root=str(menu_directory),
                extra_menu_root=str(extra_menu_directory) if extra_menu_directory else None,
                font_strip_root=str(font_directory) if font_directory else None,
                art_root=str(art_directory) if art_directory else None,
                copyright_root=str(copyright_directory) if copyright_directory else None,
                banner_font_root=str(banner_directory) if banner_directory else None,
                blueprint_root=str(blueprint_directory) if blueprint_directory else None,
                diagram_root=str(diagram_directory) if diagram_directory else None,
                results_palette_root=str(results_directory) if results_directory else None,
                results_art_root=str(results_art_directory) if results_art_directory else None,
                overlay_manifests=manifests,
                runtime_override=explicit_runtime,
                runtime=prepared["runtime"], arguments=prepared["arguments"],
                environment_overrides=prepared["environment_overrides"],
                cleaned_environment_keys=list(CLEANED_ENVIRONMENT_KEYS),
                settings_source=str(original_settings), settings_source_sha256=sha(original_settings),
                base_manifest_sha256=sha(BASE / "manifest.json"), files=list(merged.values()),
                source_counts=dict(base=len(base_rows), hud=len(hud_rows), menu=len(menu_rows), extra_menu=len(extra_menu_rows), font_strip=len(font_rows), art=len(art_rows),copyright=len(copyright_rows),banner_font=len(banner_rows),blueprint=len(blueprint_rows),diagram=len(diagram_rows),results_palette=len(results_rows),results_art=len(results_art_rows)),
                authorized_overlay_overrides=[row["overlay_override"] for row in merged.values() if "overlay_override" in row],
                overlay_input_count=len(overlay_rows), redundant_overlay_keys=redundant,
                redundant_key_count=len(redundant),
                redundant_source_count=sum(len(row["sources"])-1 for row in redundant),
                final_count=len(merged), debug_port=PORT, window_title=TITLE,
                raster_scale=9, requested_hires_size=[2880, 2160], window_width=1280,
                aspect_ratio="4:3", game_launched=False, production_installed=False,
                original_game_untouched=True,
                limitations=["4K-height 4:3 gameplay is 2880x2160; no widescreen stretch.",
                             "Actual raster scale, replacement hits and every UI state still need live acceptance.",
                             "Base files are hardlinked: never edit a composed base PNG in place."])


def prepare(report):
    evidence = Path(report["evidence"])
    evidence.mkdir(parents=True, exist_ok=False)
    replacements = evidence / "pack/einhander-texture-replacements"
    replacements.mkdir(parents=True)
    verify_provenance(report)
    for row in report["files"]:
        for source_receipt in row.get("overlay_sources", []):
            if sha(source_receipt["path"]) != source_receipt["sha256"]:
                raise ValueError("Redundant overlay source changed after planning: " + source_receipt["path"])
        source, target = Path(row["path"]), replacements / row["name"]
        if sha(source) != row["sha256"]:
            raise ValueError("Source changed after planning: " + str(source))
        if row["origin"] == "base":
            os.link(source, target)
            if not os.path.samefile(source, target):
                raise ValueError("Base hardlink verification failed")
            row["composition"] = "immutable base hardlink"
        else:
            copy_verified(source, target)
            row["composition"] = "independent overlay copy"
            if os.path.samefile(source, target):
                raise ValueError("Overlay copy shares source inode")
        if sha(target) != row["sha256"]:
            raise ValueError("Composed hash mismatch: " + str(target))
        row["composed_path"] = str(target)
    # Numeric keys resolve directly. Do not import mappings to replaced images.
    (evidence / "pack/Hashes.ini").write_text("", encoding="utf-8")
    original_settings = Path(report["settings_source"]).read_text(encoding="utf-8")
    if sha(report["settings_source"]) != report["settings_source_sha256"]:
        raise ValueError("Original settings changed during preparation")
    (evidence / "settings-original.toml").write_text(original_settings, encoding="utf-8")
    runtime_source = Path(report["runtime"]["executable"])
    report["launches"] = {}
    for mode in ("candidate", "rollback"):
        runtime = evidence / ("runtime" if mode == "candidate" else "runtime-rollback")
        runtime.mkdir()
        exe = runtime / "Einhander_Recompiled.exe"
        digest = copy_verified(runtime_source, exe)
        if digest != report["runtime"]["sha256"]:
            raise ValueError("Runtime changed during preparation")
        cache = PROJECT / "build-release/cache"
        if cache.is_dir():
            shutil.copytree(cache, runtime / "cache")
        settings = settings_override(original_settings, evidence / "pack") if mode == "candidate" else original_settings
        (runtime / "settings.toml").write_text(settings, encoding="utf-8")
        state = evidence / ("state" if mode == "candidate" else "state-rollback")
        state.mkdir()
        pack = evidence / "pack" if mode == "candidate" else BASE
        overrides = dict(report["environment_overrides"])
        overrides.update(PSXRECOMP_HD_TEXTURE_ROOT=str(pack), PSXRECOMP_HD_SOURCE_SIDECARS="1",
                         EIN_DEBUG_PORT=str(PORT), EIN_DEV_URL="",
                         PSX_OVERLAY_CAPTURES=str(runtime / "overlay_captures.json"),
                         PSX_OVERLAY_AUTOCOMPILE_OFF="1")
        for key in CLEANED_ENVIRONMENT_KEYS:
            overrides.pop(key, None)
        arguments = [str(exe)] + [item for item in report["arguments"][1:] if item != "--launcher"]
        arguments += ["--no-launcher", "--debug-port", str(PORT), "--memcard-dir", str(state),
                      "--window-title", TITLE if mode == "candidate" else "Einhander - HUD stock rollback"]
        launch = dict(arguments=arguments, cwd=str(PROJECT), environment_overrides=overrides,
                      cleaned_environment_keys=list(CLEANED_ENVIRONMENT_KEYS),
                      executable_sha256=digest, settings_sha256=sha(runtime / "settings.toml"),
                      writable_state=str(state), user_cards_mounted=False, game_launched=False)
        report["launches"][mode] = launch
        flag = " --rollback" if mode == "rollback" else ""
        # No shell-built user text: paths are fixed local preparation outputs.
        launcher = '@echo off\r\n"' + sys.executable + '" "' + str(Path(__file__).resolve()) + '" --evidence "%~dp0." --launch' + flag + '\r\n'
        (evidence / ("launch-" + mode + ".cmd")).write_text(launcher, encoding="utf-8")
    report["prepared_at_utc"] = stamp()
    (evidence / "candidate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def load_report(evidence):
    evidence = owned(evidence, ALLOWED)
    report = json.loads((evidence / "candidate.json").read_text(encoding="utf-8"))
    if Path(report["evidence"]).resolve() != evidence or report["debug_port"] != PORT:
        raise ValueError("Invalid candidate receipt")
    return report


def launch(report, rollback):
    mode = "rollback" if rollback else "candidate"
    evidence = Path(report["evidence"])
    marker = evidence / ("launch-" + mode + ".json")
    if marker.exists():
        raise ValueError("This mode already owns a launch; use a fresh evidence directory")
    with socket.socket() as check:
        try:
            check.settimeout(.5)
            check.connect(("127.0.0.1", PORT))
        except (ConnectionRefusedError, TimeoutError):
            pass
        else:
            raise ValueError("Candidate port 4371 is occupied; close that candidate before launching")
    spec = report["launches"][mode]
    verify_provenance(report)
    exe = owned(spec["arguments"][0], evidence)
    if sha(exe) != spec["executable_sha256"] or sha(exe.parent / "settings.toml") != spec["settings_sha256"]:
        raise ValueError("Prepared runtime or settings changed")
    if not rollback:
        for row in report["files"]:
            if sha(owned(row["composed_path"], evidence)) != row["sha256"]:
                raise ValueError("Prepared PNG changed: " + row["name"])
    environment = launch_environment(spec["environment_overrides"])
    with (evidence / (mode + ".stdout.log")).open("xb") as out, (evidence / (mode + ".stderr.log")).open("xb") as err:
        process = subprocess.Popen(spec["arguments"], cwd=spec["cwd"], env=environment,
                                   stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    receipt = dict(at_utc=stamp(), mode=mode, pid=process.pid, debug_port=PORT,
                   **{k:v for k,v in spec.items() if k not in ("game_launched", "cleaned_environment_keys", "environment_overrides")},
                   game_launched=True, cleaned_environment_keys=list(CLEANED_ENVIRONMENT_KEYS),
                   environment_overrides={k:v for k,v in spec["environment_overrides"].items() if k not in CLEANED_ENVIRONMENT_KEYS})
    marker.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return dict(ok=True, mode=mode, pid=process.pid, debug_port=PORT, receipt=str(marker))


def command(report, raw):
    evidence = Path(report["evidence"])
    if not any((evidence / ("launch-" + mode + ".json")).is_file() for mode in ("candidate", "rollback")):
        raise ValueError("Candidate must have a recorded launch before debug commands")
    request = json.loads(raw)
    if not isinstance(request, dict) or not isinstance(request.get("cmd"), str):
        raise ValueError("--command must be a JSON command object")
    request["id"] = 1
    with socket.create_connection(("127.0.0.1", PORT), timeout=8) as connection:
        connection.settimeout(15)
        connection.sendall(json.dumps(request).encode("utf-8") + b"\n")
        received = bytearray()
        while b"\n" not in received:
            block = connection.recv(65536)
            if not block:
                raise ValueError("Candidate debug connection closed without a reply")
            received.extend(block)
            if len(received) > 8 * 1024 * 1024:
                raise ValueError("Candidate debug reply exceeded 8 MiB")
    reply = json.loads(received.split(b"\n", 1)[0])
    receipt = dict(at_utc=stamp(), port=PORT, request=request, reply=reply)
    directory = Path(report["evidence"]) / "commands"
    directory.mkdir(exist_ok=True)
    (directory / (datetime.now(timezone.utc).strftime("%H%M%S%f") + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--hud-pack", type=Path)
    parser.add_argument("--menu-pack", type=Path)
    parser.add_argument("--extra-menu-pack", type=Path, help="Optional one-asset manifested AEE859DC file/options overlay")
    parser.add_argument("--font-strip-pack", type=Path, help="Complete reviewed font overlay: v1=14, v2=36, v3/v4=39, v6=48 assets")
    parser.add_argument("--art-pack", type=Path, help="Optional complete one- or two-asset manifested title-art overlay")
    parser.add_argument("--runtime-executable", type=Path, help="Explicit isolated runtime with hash-verified sibling build.json")
    parser.add_argument("--copyright-pack", type=Path, help="Exact bounded three-palette copyright/SQUARE supplement to selected menu pack")
    parser.add_argument("--banner-font-pack", type=Path, help="Exact bounded seven-palette B77 header font from verified frame67050 snapshot")
    parser.add_argument("--blueprint-pack", type=Path, help="Exact bounded eleven-palette ECF fighter hull/engine line-art supplement")
    parser.add_argument("--diagram-pack", type=Path, help="Exact bounded six-palette 1AD/E6 illustrations supplement to selected menu pack")
    parser.add_argument("--results-palette-pack", type=Path, help="Exact bounded one-key 8E1A509D-02491337 results typography overlay")
    parser.add_argument("--results-art-pack", type=Path, help="Exact bounded five-page restored Results aircraft illustration")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true")
    operation.add_argument("--launch", action="store_true")
    operation.add_argument("--command")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    try:
        if args.rollback and not args.launch:
            raise ValueError("--rollback requires --launch")
        if args.launch:
            result = launch(load_report(args.evidence), args.rollback)
        elif args.command:
            result = command(load_report(args.evidence), args.command)
        else:
            report = plan(args)
            if not args.check:
                report = prepare(report)
            result = {key: value for key, value in report.items() if key not in ("files", "arguments", "environment_overrides", "launches")}
            result.update(ok=True, check_only=args.check, prepared=not args.check)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps(dict(ok=False, error=str(error), game_launched=False), indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
