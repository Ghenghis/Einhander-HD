from collections import defaultdict
import json
from pathlib import Path
import tempfile
import unittest

import test_research_novelty as fixtures
from research_novelty import fnv, load_run, sha256, summarize
from research_recover_sources import add_candidate, crc, merge_partial_words, read_clut, recover
from research_service import EVENT_VRAM_BYTES


class RecoveryTests(unittest.TestCase):
    # Share the finalized recorder-fixture writer, not its test cases.
    source = fixtures.NoveltyTests.source
    bundle = fixtures.NoveltyTests.bundle
    manifest = fixtures.NoveltyTests.manifest

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add_layouts(self, identity):
        capture = self.root/identity/"native/capture.jsonl"
        rows = [json.loads(line) for line in capture.read_bytes().splitlines()]
        for row in rows:
            row.update(native_words=[2, 2], depth=0, clut_xy=[0, 0])
        capture.write_text("".join(json.dumps(row)+"\n" for row in rows))
        self.manifest(identity)

    def test_exact_word_palette_join_is_separate_and_preserves_native_files(self):
        first = self.source()
        other = self.source(words=b"\5\0\6\0\7\0\10\0", clut=bytes(range(32)))
        target = first[0][:8]+"-"+other[0][9:]
        directory = self.bundle("run-a", [first, other], [target])
        self.add_layouts("run-a")
        before = {str(p): sha256(p) for p in directory.rglob("*") if p.is_file()}
        novelty = summarize([load_run(self.root, "run-a")])
        report, payloads = recover(self.root, novelty)
        self.assertEqual(report["summary"]["recovered_candidate_pairs"], 1)
        self.assertEqual(payloads[target], (first[2][0], other[2][2]))
        recovered = report["recovered"][0]
        self.assertFalse(recovered["atomic_pair_capture"])
        self.assertFalse(recovered["actor_ownership_verified"])
        self.assertTrue(recovered["candidate_only"])
        self.assertEqual(before, {str(p): sha256(p) for p in directory.rglob("*") if p.is_file()})

    def test_missing_words_are_left_unresolved_without_guessing(self):
        first = self.source()
        target = "12345678-"+first[0][9:]
        self.bundle("run-a", [first], [target])
        self.add_layouts("run-a")
        report, payloads = recover(self.root, summarize([load_run(self.root, "run-a")]))
        self.assertEqual(payloads, {})
        self.assertEqual(report["unresolved"][0]["word_candidates"], 0)
        self.assertEqual(report["remaining_include_batches"][0]["keys"], [target])

    def test_target_must_be_observed_and_manifest_receipt_must_match(self):
        first = self.source()
        self.bundle("run-a", [first], [])
        novelty = summarize([load_run(self.root, "run-a")])
        novelty["targets"] = [dict(key="12345678-87654321")]
        with self.assertRaisesRegex(ValueError, "actual upload draw"):
            recover(self.root, novelty)
        novelty["manifests"][0]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "manifest receipt changed"):
            recover(self.root, novelty)

    def test_observed_dimensions_must_match_original_words(self):
        first = self.source()
        other = self.source(words=b"\5\0\6\0\7\0\10\0", clut=bytes(range(32)))
        target = first[0][:8]+"-"+other[0][9:]
        self.bundle("run-a", [first, other], [target])
        self.add_layouts("run-a")
        capture = self.root/"run-a/native/capture.jsonl"
        row = json.loads(capture.read_bytes())
        row["native_words"] = [1, 4]
        capture.write_text(json.dumps(row)+"\n")
        self.manifest("run-a")
        report, payloads = recover(self.root, summarize([load_run(self.root, "run-a")]))
        self.assertEqual(payloads, {})
        self.assertEqual(report["unresolved"][0]["word_candidates"], 0)

    def test_clut_extraction_uses_native_row_wrap_and_bounds(self):
        vram = bytearray(EVENT_VRAM_BYTES)
        expected = b"".join(index.to_bytes(2, "little") for index in range(16))
        for index in range(16):
            offset = 2*(500*1024+((1020+index) & 1023))
            vram[offset:offset+2] = expected[2*index:2*index+2]
        self.assertEqual(read_clut(vram, 1020, 500, 0), expected)
        for x, y in ((-1, 0), (1024, 0), (0, 512), (True, 0)):
            with self.assertRaises(ValueError):
                read_clut(vram, x, y, 0)
        with self.assertRaises(ValueError):
            read_clut(bytes(100), 0, 0, 0)

    def test_ambiguous_bytes_are_kept_distinct_and_duplicates_merge_provenance(self):
        index = defaultdict(dict)
        add_candidate(index, "key", b"abc", dict(file="one"))
        add_candidate(index, "key", b"abc", dict(file="two"))
        add_candidate(index, "key", b"abd", dict(file="three"))
        self.assertEqual(len(index["key"]), 2)
        self.assertEqual(sorted(len(row["provenance"]) for row in index["key"].values()), [1, 2])

    def fragments(self, full=b"\1\0\2\0\3\0\4\0"):
        first, second = full[:4]+bytes(4), bytes(4)+full[4:]
        return [dict(data=first, valid=bytes([1, 1, 0, 0]), words_fnv1a32=fnv(first)),
                dict(data=second, valid=bytes([0, 0, 1, 1]), words_fnv1a32=fnv(second))]

    def test_complementary_partial_word_union_requires_exact_crc(self):
        full = b"\1\0\2\0\3\0\4\0"
        result = merge_partial_words(crc(full), (2, 2, 0), self.fragments(full))
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["data"], full)
        self.assertEqual(result["words_fnv1a32"], fnv(full))
        self.assertFalse(result["independent_full_fnv_available"])
        self.assertFalse(result["independent_full_fnv_verified"])
        verified = merge_partial_words(crc(full), (2, 2, 0), self.fragments(full), fnv(full))
        self.assertTrue(verified["independent_full_fnv_verified"])

    def test_conflicting_known_word_overlap_rejects_union(self):
        fragments = self.fragments()
        fragments[1].update(data=b"\0\0\7\0\3\0\4\0", valid=bytes([0, 1, 1, 1]))
        fragments[1]["words_fnv1a32"] = fnv(fragments[1]["data"])
        result = merge_partial_words("12345678", (2, 2, 0), fragments)
        self.assertEqual(result["status"], "conflicting_overlap")
        self.assertEqual(result["conflicting_word_offsets"], [1])
        self.assertNotIn("data", result)

    def test_partial_union_never_fills_unobserved_words(self):
        result = merge_partial_words("12345678", (2, 2, 0), self.fragments()[:1])
        self.assertEqual(result["status"], "insufficient_coverage")
        self.assertEqual(result["known_words"], 2)
        self.assertNotIn("data", result)

    def test_input_crc_and_independent_full_fnv_failures_are_rejected(self):
        full = b"\1\0\2\0\3\0\4\0"
        fragments = self.fragments(full)
        fragments[0]["words_fnv1a32"] ^= 1
        self.assertEqual(merge_partial_words(crc(full), (2, 2, 0), fragments)["status"], "source_checksum_mismatch")
        self.assertEqual(merge_partial_words("12345678", (2, 2, 0), self.fragments(full))["status"], "merged_crc_mismatch")
        self.assertEqual(merge_partial_words(crc(full), (2, 2, 0), self.fragments(full), fnv(full)^1)["status"], "merged_fnv_mismatch")

    def test_saved_partial_archives_recover_without_native_archive_changes(self):
        full = b"\1\0\2\0\3\0\4\0"
        complete = self.source(words=full)
        key = complete[0]
        partials = self.fragments(full)
        first = self.source(words=partials[0]["data"], valid=partials[0]["valid"], key=key)
        second = self.source(words=partials[1]["data"], valid=partials[1]["valid"], key=key)
        self.bundle("run-a", [first], [key])
        self.bundle("run-b", [second], [key])
        self.add_layouts("run-a")
        self.add_layouts("run-b")
        novelty = summarize([load_run(self.root, "run-a"), load_run(self.root, "run-b")])
        self.assertEqual(novelty["summary"]["complete_crc_valid_keys"], 0)
        report, payloads = recover(self.root, novelty)
        self.assertEqual(report["summary"]["recovered_candidate_pairs"], 1)
        self.assertEqual(report["summary"]["partial_word_families_merged"], 1)
        self.assertEqual(payloads[key][0], full)
        provenance = report["recovered"][0]["words_provenance"][0]
        self.assertEqual(provenance["kind"], "merged_complementary_partial_words")
        self.assertTrue(provenance["all_known_overlaps_agree"])
        self.assertFalse(provenance["independent_full_fnv_available"])
        self.assertTrue(report["native_archive_counts_unchanged"])


if __name__ == "__main__":
    unittest.main()
