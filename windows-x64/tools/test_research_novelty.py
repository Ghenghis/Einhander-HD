import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zlib

from research_novelty import fnv, load_run, main, summarize


class NoveltyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, words=b"\1\0\2\0\3\0\4\0", clut=bytes(32), valid=bytes([1]*4), key=None):
        key = key or f"{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}"
        return key, dict(key=key, frame=100, width_words=2, height=2, total_words=4, known_words=sum(valid), depth=0,
                         clut_words=16, words_fnv1a32=fnv(words), clut_fnv1a32=fnv(clut), raw_origin="test_cpu_upload"), (words, valid, clut)

    def bundle(self, identity, sources=(), observed=(), finalized=True):
        directory = self.root/identity
        (directory/"native").mkdir(parents=True)
        for key, metadata, payloads in sources:
            (directory/"native"/(key+".source.json")).write_text(json.dumps(metadata))
            for suffix, data in zip(("words.bin", "valid.bin", "clut.bin"), payloads):
                (directory/"native"/(key+"."+suffix)).write_bytes(data)
        rows = [dict(event="source_draw_query_matched", source_kind="upload", key=key, frame=100+index) for index, key in enumerate(observed)]
        (directory/"native/capture.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        self.manifest(identity, finalized)
        return directory

    def manifest(self, identity, finalized=True):
        directory = self.root/identity
        files = [dict(path=p.relative_to(directory).as_posix(), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in directory.rglob("*") if p.is_file() and p.name != "manifest.json"]
        manifest = dict(id=identity, status="finalized" if finalized else "recording", started_at=identity,
                        native_capture=dict(stop=dict(caps=dict(sources=True))), files=files)
        (directory/"manifest.json").write_text(json.dumps(manifest))

    def test_deduplication_counts_valid_complete_keys_and_partial_only_targets(self):
        good = self.source()
        partial = self.source(valid=bytes([1, 0, 1, 0]), key="12345678-87654321")
        missing = "ABCDEF01-ABCDEF02"
        self.bundle("run-a", [good, partial], [good[0], partial[0], missing])
        self.bundle("run-b", [good], [good[0]])
        report = summarize([load_run(self.root, "run-b"), load_run(self.root, "run-a")])
        self.assertEqual(report["summary"]["source_archives"], 3)
        self.assertEqual(report["summary"]["distinct_source_keys"], 2)
        self.assertEqual(report["summary"]["complete_crc_valid_keys"], 1)
        self.assertEqual(report["summary"]["partial_only_keys"], 1)
        self.assertEqual(report["summary"]["observed_keys_without_archive"], 1)
        self.assertEqual(report["per_run"][1]["new_complete_keys"], 0)
        self.assertEqual({row["reason"] for row in report["targets"]}, {"partial_only", "no_raw_archive"})
        self.assertEqual(set(report["capture_plan"]["source_filter_batches"][0]["keys"]), {partial[0], missing})

    def test_before_after_measures_recovery_and_new_complete_keys(self):
        first = self.source()
        recovered = self.source(words=b"\5\0\6\0\7\0\10\0")
        self.bundle("run-a", [first], [first[0], recovered[0]])
        self.bundle("run-b", [recovered], [recovered[0]])
        report = summarize([load_run(self.root, "run-a"), load_run(self.root, "run-b")], ["run-a"])
        self.assertEqual(report["comparison"]["added_complete_keys"], [recovered[0]])
        self.assertEqual(report["comparison"]["recovered_baseline_targets"], [recovered[0]])
        self.assertEqual(report["comparison"]["remaining_baseline_targets"], [])
        self.assertEqual(report["summary"]["unfinished_keys"], 0)

    def test_palette_variants_are_families_and_not_actor_claims(self):
        first = self.source()
        variant = first[0].split("-")[0]+"-ABCDEF02"
        self.bundle("run-a", [first], [variant])
        report = summarize([load_run(self.root, "run-a")])
        self.assertEqual(report["targets"][0]["family"], "palette_variant_of_complete_texture")
        self.assertTrue(report["targets"][0]["candidate_only"])

    def test_tampered_tracked_payload_is_rejected(self):
        source = self.source()
        directory = self.bundle("run-a", [source], [source[0]])
        (directory/"native"/(source[0]+".words.bin")).write_bytes(bytes(8))
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            load_run(self.root, "run-a")

    def test_complete_crc_mismatch_is_rejected_even_when_manifest_is_consistent(self):
        source = self.source(key="12345678-87654321")
        self.bundle("run-a", [source], [])
        with self.assertRaisesRegex(ValueError, "CRC mismatch"):
            load_run(self.root, "run-a")

    def test_invalid_validity_mask_is_rejected(self):
        self.bundle("run-a", [self.source(valid=bytes([1, 2, 0, 1]))])
        with self.assertRaisesRegex(ValueError, "validity mask"):
            load_run(self.root, "run-a")

    def test_active_or_unlisted_or_traversing_runs_are_rejected(self):
        directory = self.bundle("run-a", finalized=False)
        with self.assertRaisesRegex(ValueError, "finalized"):
            load_run(self.root, "run-a")
        self.manifest("run-a")
        (directory/"unlisted.txt").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "Unlisted"):
            load_run(self.root, "run-a")
        with self.assertRaisesRegex(ValueError, "Invalid run ID"):
            load_run(self.root, "../outside")

    def test_no_overwrite_and_target_batch_bound(self):
        keys = [f"{index:08X}-87654321" for index in range(300)]
        self.bundle("run-a", observed=keys)
        report = summarize([load_run(self.root, "run-a")])
        batches = report["capture_plan"]["source_filter_batches"]
        self.assertEqual([len(batch["keys"]) for batch in batches], [224, 76])
        target = self.root/"report.json"
        target.write_text("preserve")
        with contextlib.redirect_stdout(io.StringIO()):
            result = main(["--runs-root", str(self.root), "--run", "run-a", "--output", str(target)])
        self.assertEqual(result, 1)
        self.assertEqual(target.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
