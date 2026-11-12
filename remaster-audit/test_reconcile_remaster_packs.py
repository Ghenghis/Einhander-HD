"""Isolated composition tests; no project packs, runtime or game are touched."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from reconcile_remaster_packs import candidate_ledger_report, sha, validate_legacy_composition


KEYS = [f"{number:08X}-00000000" for number in range(1, 6)]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_png(path, color):
    def chunk(name, payload):
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes([0, color, color, color]))) + chunk(b"IEND", b""))
    return {"path": str(path), "sha256": sha(path)}


class CandidateLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "base/manifest.json"
        self.expanded = self.root / "expanded/manifest.json"
        self.queue = self.root / "queue.json"
        self.candidate = self.root / "current/candidate.json"
        self.parent = self.root / "parent/candidate.json"
        self.manifest = self.root / "supplement/manifest.json"

        base_rows, expanded_rows = [], []
        for index, key in enumerate(KEYS[:2]):
            receipt = write_png(self.base.parent / "einhander-texture-replacements" / (key + ".png"), 20 + index)
            base_rows.append({"key": key, "sha256": receipt["sha256"]})
        write_json(self.base, {"files": base_rows})
        for index, key in enumerate(KEYS[:4]):
            receipt = write_png(self.expanded.parent / "einhander-texture-replacements" / (key + ".png"), 20 + index)
            expanded_rows.append({"key": key, "sha256": receipt["sha256"]})
        write_json(self.expanded, {"files": expanded_rows})
        write_json(self.queue, {"assets": [{"key": key} for key in KEYS]})

        self.first = write_png(self.root / "overlay-first" / (KEYS[0] + ".png"), 70)
        self.last = write_png(self.root / "supplement" / (KEYS[0] + ".png"), 90)
        rows = []
        for index, key in enumerate(KEYS[:3]):
            selected = (self.last if index == 0 else
                        {"path": str(self.base.parent / "einhander-texture-replacements" / (key + ".png")), "sha256": base_rows[1]["sha256"]} if index == 1 else
                        {"path": str(self.expanded.parent / "einhander-texture-replacements" / (key + ".png")), "sha256": expanded_rows[2]["sha256"]})
            output = self.candidate.parent / "pack/einhander-texture-replacements" / (key + ".png")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(Path(selected["path"]).read_bytes())
            rows.append({"name": key + ".png", **selected, "dimensions": [1, 1], "composed_path": str(output),
                         "overlay_sources": [self.first, self.last] if index == 0 else [selected] if index == 2 else []})
        parent_rows = copy.deepcopy(rows)
        parent_rows[0].update(self.first)
        write_json(self.parent, {"files": parent_rows})
        write_json(self.manifest, {"files": [{"key": KEYS[0], "outputs": {"pack": self.last}}]})
        self.doc = {"final_count": 3, "base_manifest_sha256": sha(self.base), "files": rows,
                    # A provenance-only report containing fake files must not
                    # become an accidental overlay merely because of its shape.
                    "overlay_manifests": {"non_overlay_report": {"path": str(self.queue), "sha256": sha(self.queue)}},
                    "typography_composition": {"parent": {"path": str(self.parent), "sha256": sha(self.parent)},
                        "changed_keys": 1, "unchanged_keys": 2,
                        "changes": [{"key": KEYS[0], "parent": self.first, "output": self.last,
                                     "manifest": {"path": str(self.manifest), "sha256": sha(self.manifest)}}]}}
        write_json(self.candidate, self.doc)

    def report(self):
        write_json(self.candidate, self.doc)
        return candidate_ledger_report(self.candidate, self.base, self.expanded, self.queue, workers=1)

    def kinds(self, report):
        return {failure["kind"] for failure in report["integrity_failures"]}

    def test_ordered_overlay_and_explicit_supplement_override(self):
        result = self.report()
        self.assertEqual([], result["integrity_failures"])
        self.assertEqual(3, result["counts"]["current_ui_keys"])
        self.assertEqual(2, result["counts"]["queue_keys_missing_current_ui"])
        self.assertEqual([KEYS[3]], result["explicit_omissions"]["expanded_not_in_ui"])
        self.assertEqual(1, result["composition"]["changed_keys"])
        self.assertEqual(2, result["records"][0]["provenance"]["overlay_count"])
        self.assertEqual("base_bytes_preserved", result["records"][1]["provenance"]["kind"])

    def test_earlier_overlay_cannot_override_later_selection(self):
        self.doc["files"][0]["overlay_sources"].reverse()
        self.assertIn("last_overlay_does_not_select_final_bytes", self.kinds(self.report()))

    def test_undeclared_parent_change_is_rejected(self):
        self.doc["typography_composition"]["changes"] = []
        self.assertIn("composition_change_set_mismatch", self.kinds(self.report()))

    def test_supplement_must_match_its_authoring_manifest(self):
        write_json(self.manifest, {"files": [{"key": KEYS[0], "outputs": {"pack": self.first}}]})
        self.doc["typography_composition"]["changes"][0]["manifest"]["sha256"] = sha(self.manifest)
        self.assertIn("composition_output_not_bound_to_authoring_manifest", self.kinds(self.report()))

    def test_stale_hash_bound_parent_is_rejected(self):
        parent = json.loads(self.parent.read_text())
        parent["new_metadata"] = True
        write_json(self.parent, parent)
        self.assertIn("hash_mismatch", self.kinds(self.report()))

    def add_source_supplement(self, source_verified):
        key = KEYS[3]
        source = write_png(self.root / "new-key-source" / (key + ".png"), 40)
        output = write_png(self.root / "new-key-art" / (key + ".png"), 120)
        manifest = self.root / "new-key-art/manifest.json"
        write_json(manifest, {"files": [{"key": key, "source_verified_new_key": source_verified,
                                        "parent": source, "outputs": {"pack": output}}]})
        target = self.candidate.parent / "pack/einhander-texture-replacements" / (key + ".png")
        target.write_bytes(Path(output["path"]).read_bytes())
        self.doc["files"].append({"name": key + ".png", **output, "dimensions": [1, 1],
                                 "composed_path": str(target), "overlay_sources": [output]})
        self.doc["final_count"] = 4
        self.doc["typography_composition"]["changed_keys"] = 2
        self.doc["typography_composition"]["changes"].append({"key": key, "parent": source, "output": output,
              "manifest": {"path": str(manifest), "sha256": sha(manifest)}})

    def test_explicit_new_key_supplement_has_source_parent(self):
        self.add_source_supplement(True)
        result = self.report()
        self.assertEqual([], result["integrity_failures"])
        self.assertEqual(1, result["composition"]["added_keys"])
        self.assertEqual(1, result["composition"]["replaced_keys"])

    def test_new_key_without_source_admission_is_rejected(self):
        self.add_source_supplement(False)
        self.assertIn("composition_new_key_lacks_bound_source_parent", self.kinds(self.report()))

    def test_actual_selected_source_mutation_is_rejected(self):
        write_png(Path(self.last["path"]), 180)
        self.assertIn("hash_mismatch", self.kinds(self.report()))

    def test_source_redirect_cannot_hide_corrupted_candidate_pack(self):
        row = self.doc["files"][1]
        actual_pack = Path(row["composed_path"])
        row["composed_path"] = row["path"]
        write_png(actual_pack, 190)
        result = self.report()
        self.assertIn("candidate_composed_path_not_canonical", self.kinds(result))
        self.assertIn("hash_mismatch", self.kinds(result))
        self.assertEqual(str(actual_pack), result["records"][1]["variants"]["ui"]["path"])

    def add_title_layer(self):
        parent = self.root / "v12/candidate.json"
        write_json(parent, copy.deepcopy(self.doc))
        title_manifest = self.root / "title/manifest.json"
        changes, authored = [], []
        for index in range(2):
            row = self.doc["files"][index]
            previous = {key: row[key] for key in ("path", "sha256")}
            key = KEYS[index]
            output = write_png(self.root / "title" / (key + ".png"), 140 + index)
            Path(row["composed_path"]).write_bytes(Path(output["path"]).read_bytes())
            row.update(output)
            row["overlay_sources"].append(output)
            authored.append({"key": key, **output, "parent": previous})
            changes.append({"key": key, "parent": previous, "output": output})
        write_json(title_manifest, {"files": authored})
        self.doc["title_e_composition"] = {"parent": {"path": str(parent), "sha256": sha(parent)},
            "manifest": {"path": str(title_manifest), "sha256": sha(title_manifest)},
            "changes": changes, "changed_keys": 2, "unchanged_keys": 1}

    def test_title_layer_selects_two_changes_over_inherited_typography(self):
        self.add_title_layer()
        result = self.report()
        self.assertEqual([], result["integrity_failures"])
        self.assertEqual("title_e_composition", result["composition"]["layer"])
        self.assertEqual(2, result["composition"]["changed_keys"])
        self.assertEqual(1, result["composition"]["unchanged_keys"])

    def test_latest_title_layer_cannot_hide_undeclared_change(self):
        self.add_title_layer()
        self.doc["title_e_composition"]["changes"].pop()
        self.assertIn("composition_change_set_mismatch", self.kinds(self.report()))

    def test_inherited_typography_claims_must_match_title_parent(self):
        self.add_title_layer()
        self.doc["typography_composition"]["changed_keys"] = 400
        self.assertIn("inherited_typography_composition_differs_from_title_parent", self.kinds(self.report()))

    def test_missing_files_never_compare_as_identical(self):
        Path(self.doc["files"][1]["composed_path"]).unlink()
        (self.expanded.parent / "einhander-texture-replacements" / (KEYS[1] + ".png")).unlink()
        result = self.report()
        self.assertIn("file_unreadable", self.kinds(result))
        self.assertEqual("conflict_keep_ui_pending_region_review", result["records"][1]["reconciliation"])

    def test_legacy_snapshot_rejects_later_count_or_overlay(self):
        snapshot = {"final_count": 3, "overlay_manifests": {"menu": {"sha256": "old"}}}
        with self.assertRaisesRegex(ValueError, "final_count"):
            validate_legacy_composition({"final_count": 4}, snapshot)
        with self.assertRaisesRegex(ValueError, "stale or mismatching overlay"):
            validate_legacy_composition({"final_count": 3, "overlay_manifests": {"menu": {"sha256": "new"}}}, snapshot)
        validate_legacy_composition({"final_count": 3, "overlay_manifests": snapshot["overlay_manifests"]}, snapshot)


if __name__ == "__main__":
    unittest.main()
