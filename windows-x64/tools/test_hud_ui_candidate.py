import unittest

import cv2
import numpy as np

from build_hud_ui_candidate import author_layers, contour_indices, decode_indices, palette_rgba, render_variants, restore_geometry


class HudCandidateTests(unittest.TestCase):
    def test_index_decode_retains_original_nibble_positions(self):
        raw = bytes.fromhex("10325476")
        result = decode_indices(raw, dict(depth=0, width_words=2, height=1))
        self.assertEqual(result.tolist(), [[0, 1, 2, 3, 4, 5, 6, 7]])

    def test_palette_zero_and_black_stp_classes_are_distinct(self):
        values = np.array([0, 0x8000, 0x7FFF]+[0]*13, dtype="<u2")
        rgba = palette_rgba(values.tobytes())
        self.assertEqual(rgba[0].tolist(), [0, 0, 0, 0])
        self.assertEqual(rgba[1].tolist(), [0, 0, 0, 255])
        self.assertEqual(rgba[2].tolist(), [248, 248, 248, 127])

    def test_nested_contours_recover_diagonal_edges_without_forced_centers(self):
        original = np.array([[15, 15, 0, 0], [15, 0, 0, 15], [0, 0, 15, 15], [0, 15, 15, 15]], dtype=np.uint8)
        rendered, selected = contour_indices(original, scale=8)
        self.assertTrue(np.array_equal(rendered[4::8, 4::8], original))
        nearest = np.repeat(np.repeat(original, 8, axis=0), 8, axis=1)
        self.assertGreater(np.count_nonzero(rendered != nearest), 0)
        self.assertTrue(selected.all())

    def test_glyph_profile_removes_detached_antialias_fringe_without_losing_face(self):
        source = np.full((12, 16), 15, dtype=np.uint8)
        source[3:9, 3:6] = 0
        source[2, 12] = 13  # A detached old gray fringe sample, never a glyph face.
        source[4:8, 6] = 4
        rendered, _ = contour_indices(source, scale=16, profile="glyph")
        self.assertTrue((rendered[32:48, 192:208] == 15).all())
        self.assertEqual(int(rendered[4*16+8, 4*16+8]), 0)
        components, _ = cv2.connectedComponents((rendered < 15).astype(np.uint8))
        self.assertEqual(components-1, 1)
        # This catches the former exact-center write, which put the blob back.
        self.assertNotEqual(int(rendered[2*16+8, 12*16+8]), int(source[2, 12]))

    def test_glyph_profile_retains_bowl_counter_dot_and_separate_strokes(self):
        source = np.full((14, 24), 15, dtype=np.uint8)
        source[2:11, 2:9] = 0
        source[4:9, 4:7] = 15  # Original bowl/counter.
        source[3:10, 13:15] = 0
        source[3:10, 18:20] = 0
        source[11, 22] = 0  # Single source-pixel punctuation remains visible.
        rendered, _ = contour_indices(source, scale=16, profile="glyph")
        self.assertEqual(int(rendered[6*16+8, 5*16+8]), 15)
        self.assertEqual(int(rendered[6*16+8, 16*16+8]), 15)
        self.assertEqual(int(rendered[11*16+8, 22*16+8]), 0)
        components, _ = cv2.connectedComponents((rendered < 15).astype(np.uint8))
        self.assertEqual(components-1, 4)

    def test_reconstructed_glyph_palette_animation_retains_black_stp_and_class_values(self):
        source = np.full((8, 8), 15, dtype=np.uint8)
        source[2:6, 3:5] = 0
        rendered, _ = contour_indices(source, scale=8, profile="glyph")
        palettes = []
        for hue in ([200, 220, 240], [240, 120, 20]):
            palette = np.zeros((16, 4), dtype=np.uint8)
            palette[:15, :3] = np.array(hue)[None, :]*np.linspace(1, 0.05, 15)[:, None]
            palette[:, 3] = 255
            palette[0, 3] = 127
            palettes.append(palette)
        first, _, _ = render_variants(source, rendered, palettes[0])
        second, _, _ = render_variants(source, rendered, palettes[1])
        self.assertTrue(np.array_equal(first[:, :, 3], second[:, :, 3]))
        self.assertTrue((first[rendered == 15] == [0, 0, 0, 255]).all())
        self.assertTrue(set(np.unique(first[:, :, 3])) <= {127, 255})
        self.assertFalse(np.array_equal(first[:, :, :3], second[:, :, :3]))

    def test_glyph_profile_and_empty_regions_stay_within_explicit_uv_bounds(self):
        source = np.full((8, 8), 13, dtype=np.uint8)
        source[3:5, 3:5] = 0
        nearest = np.repeat(np.repeat(source, 8, axis=0), 8, axis=1)
        rendered, selected = contour_indices(source, scale=8, regions=[(2, 2, 6, 6)], profile="glyph")
        self.assertTrue(np.array_equal(rendered[~selected], nearest[~selected]))
        empty, selection = contour_indices(source, scale=8, regions=[], profile="glyph")
        self.assertTrue(np.array_equal(empty, nearest))
        self.assertFalse(selection.any())

    def test_mixed_atlas_keeps_outline_words_distinct_from_solid_score_digits(self):
        source = np.full((256, 256), 15, dtype=np.uint8)
        source[8:16, 8:16] = 4  # Solid numeral antialias/face region.
        source[70:78, 8:16] = 4  # Another UI region retains its original tone.
        source[140:152, 8:20] = 0
        source[142:150, 10:18] = 4  # Shaded interior of an outlined word stroke.
        rendered, _ = restore_geometry(source, "BDAE4156", scale=2)
        self.assertEqual(int(rendered[12*2+1, 12*2+1]), 0)
        self.assertEqual(int(rendered[74*2+1, 12*2+1]), 4)
        self.assertEqual(int(rendered[146*2+1, 14*2+1]), 15)
        self.assertEqual(int(rendered[140*2+1, 14*2+1]), 0)

    def test_mixed_page_outside_selected_rectangle_is_byte_exact(self):
        original = np.array([[1, 2, 3, 4], [5, 0, 15, 6], [7, 15, 0, 8], [9, 10, 11, 12]], dtype=np.uint8)
        rendered, selected = contour_indices(original, scale=4, regions=[(1, 1, 3, 3)])
        nearest = np.repeat(np.repeat(original, 4, axis=0), 4, axis=1)
        self.assertTrue(np.array_equal(rendered[~selected], nearest[~selected]))

    def test_strict_variant_preserves_entire_native_class_footprint(self):
        original = np.array([[15, 0, 1], [0, 1, 15], [1, 15, 0]], dtype=np.uint8)
        palette = np.zeros((16, 4), dtype=np.uint8)
        palette[0] = [220, 230, 240, 127]
        palette[1] = [30, 80, 90, 255]
        rendered, _ = contour_indices(original, scale=8)
        rgba, strict, nearest = render_variants(original, rendered, palette)
        self.assertTrue(np.array_equal(strict[:, :, 3], nearest[:, :, 3]))
        self.assertTrue(set(np.unique(rgba[:, :, 3])) <= {0, 127, 255})

    def test_authored_rim_bevel_and_highlight_change_rgb_without_class_or_uv_changes(self):
        rgba = np.zeros((64, 64, 4), dtype=np.uint8)
        rgba[12:52, 20:44] = [150, 170, 190, 127]
        rgba[6:10, 6:10] = [0, 0, 0, 255]
        selected = np.zeros((64, 64), dtype=bool)
        selected[4:60, 4:60] = True
        authored = author_layers(rgba, selected, scale=16)
        self.assertTrue(np.array_equal(authored[:, :, 3], rgba[:, :, 3]))
        self.assertTrue(np.array_equal(authored[~selected], rgba[~selected]))
        self.assertTrue(np.array_equal(authored[6:10, 6:10], rgba[6:10, 6:10]))
        self.assertGreater(np.count_nonzero(authored[:, :, :3] != rgba[:, :, :3]), 0)
        self.assertGreater(np.max(authored[:, :, :3]), 190)
        self.assertLess(np.min(authored[12:52, 20:44, :3]), 150)

    def test_invalid_region_or_scale_fails_without_silent_atlas_clipping(self):
        source = np.zeros((4, 4), dtype=np.uint8)
        for scale in (1, 3, 2.5):
            with self.assertRaises(ValueError):
                contour_indices(source, scale=scale)
        with self.assertRaises(ValueError):
            contour_indices(source, regions=[(0, 0, 5, 4)])
        with self.assertRaises(ValueError):
            contour_indices(np.array([[-1, 0], [1, 2]]))
        with self.assertRaises(ValueError):
            contour_indices(source, profile="unknown")


if __name__ == "__main__":
    unittest.main()
