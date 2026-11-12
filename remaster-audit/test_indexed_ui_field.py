"""Small meaningful reference checks for tone and categorical palette fields."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("field_builder", Path(__file__).with_name("build_indexed_ui_field_candidate.py"))
field_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field_builder)


class FieldEncodingTests(unittest.TestCase):
    def test_constant_geometry_roundtrips_each_index_and_explicit_rim_gain(self):
        for code in range(16):
            field = field_builder.encode(np.full((2, 2), code, np.uint8), scale=4, region=(0, 0, 2, 2))
            self.assertTrue(np.all(field[:, :, 0] == code*17))
            rim = np.clip((code-9)/5, 0, 1)*np.clip((15-code)/1.5, 0, 1)
            self.assertTrue(np.all(field[:, :, 1] == round(128*(1-.16*rim))))
            self.assertTrue(np.all(field[:, :, 2] == code))
            self.assertTrue(np.all(field[:, :, 3] == 255))

    def test_outside_region_guard_and_native_indices_remain_exact(self):
        source = np.arange(16, dtype=np.uint8).reshape(4, 4)
        field = field_builder.encode(source, scale=8, region=(1, 1, 3, 3))
        expected = np.repeat(np.repeat(source, 8, 0), 8, 1)
        outside = np.ones((32, 32), bool); outside[8:24, 8:24] = False
        self.assertTrue(np.all(field[:, :, 3][outside] == 0))
        self.assertTrue(np.all(field[8:24, 8:24, 3] == 255))
        self.assertTrue(np.array_equal(field[:, :, 0][outside], expected[outside]*17))
        self.assertTrue(np.array_equal(field[:, :, 2][outside], expected[outside]))
        self.assertTrue(np.all(field[:, :, 1][outside] == 128))

    def test_live_palette_color_and_classes_are_not_baked_into_geometry(self):
        field = np.array([[[0, 128, 0, 255], [128, 128, 8, 255], [255, 128, 15, 255]]], np.uint8)
        first = np.array([[255-10*i, 8*i, 0, [0, 127, 255][i % 3]] for i in range(16)], np.uint8)
        second = first.copy(); second[:, :3] = first[:, :3][:, ::-1]; second[:, 3] = np.roll(first[:, 3], 1)
        a = field_builder.render_cpu(field, first)
        b = field_builder.render_cpu(field, second)
        self.assertTrue(np.array_equal(a[:, :, 3], first[field[:, :, 2], 3]))
        self.assertTrue(np.array_equal(b[:, :, 3], second[field[:, :, 2], 3]))
        self.assertFalse(np.array_equal(a[:, :, :3], b[:, :, :3]))
        self.assertFalse(np.array_equal(a[:, :, 3], b[:, :, 3]))

    def test_continuous_tone_does_not_own_alpha_class(self):
        field = np.array([[[128, 128, 0, 255], [128, 128, 7, 255], [128, 128, 15, 255]]], np.uint8)
        palette = np.zeros((16, 4), np.uint8)
        palette[:, :3] = np.arange(16, dtype=np.uint8)[:, None]*16
        palette[:, 3] = 255; palette[0, 3] = 127; palette[15, 3] = 0
        rendered = field_builder.render_cpu(field, palette)
        self.assertTrue(np.array_equal(rendered[0, :, 3], [127, 255, 0]))
        self.assertTrue(np.array_equal(rendered[0, 0, :3], rendered[0, 1, :3]))

    def test_invalid_non_indexed_plane_rejected(self):
        with self.assertRaises(ValueError):
            field_builder.encode(np.array([[16]], np.uint8), scale=2, region=(0, 0, 1, 1))


if __name__ == "__main__":
    unittest.main()
