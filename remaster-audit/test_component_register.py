"""Coverage regressions that must fail closed in the seed register."""
import copy
import unittest

import build_component_register as register


class CoverageGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = register.load_inputs()
        cls.current = register.build()

    def test_current_evidence_register_validates(self):
        register.validate(self.current, self.data)

    def test_same_count_wrong_identity_is_rejected(self):
        corrupted = copy.deepcopy(self.current)
        enemy = next(x for x in corrupted["components"] if x["category"] == "enemy_model")
        enemy["id"] = "enemy/not_a_catalog_identity"
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)

    def test_historical_live_promotion_is_rejected(self):
        corrupted = copy.deepcopy(self.current)
        ui = next(x for x in corrupted["components"] if x["status"] == "integrated")
        ui["gates"]["live_verification"] = True
        ui["status"] = "live-verified"
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)

    def test_omitted_missing_variant_is_rejected(self):
        corrupted = copy.deepcopy(self.current)
        family = next(x for x in corrupted["technical_source_index"]
                      if x["id"].startswith("source/world/") and x["missing_from_v6_keys_at_audit"])
        family["missing_from_v6_keys_at_audit"].pop()
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)

    def test_missing_boss_phase_queue_is_rejected(self):
        corrupted = copy.deepcopy(self.current)
        boss_queue = next(x for x in corrupted["discovery_queues"] if x["id"].startswith("sweep/boss-phases/"))
        corrupted["discovery_queues"].remove(boss_queue)
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)

    def test_world_page_cannot_become_building(self):
        corrupted = copy.deepcopy(self.current)
        page = corrupted["technical_source_index"][0]
        page["semantic_owner"] = "building/assumed_from_page_crc"
        page["semantic_ownership_verified"] = True
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)

    def test_integrated_without_asset_receipts_is_rejected(self):
        corrupted = copy.deepcopy(self.current)
        ui = next(x for x in corrupted["components"] if x["status"] == "integrated")
        ui["authoring"]["hashes"] = []
        with self.assertRaises(AssertionError):
            register.validate(corrupted, self.data)


if __name__ == "__main__":
    unittest.main()
