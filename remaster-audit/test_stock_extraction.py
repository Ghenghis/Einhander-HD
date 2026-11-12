"""Regression checks for archive bounds and raw STP preservation."""
import struct
import unittest

from extract_stock_archives import entries, ALIGN
from extract_disc_stock import validate_tim, decode_tim


class StockExtractionTests(unittest.TestCase):
    def test_archive_bounds_and_terminator(self):
        index = struct.pack('<HHHH', 1, 2, 0, 0).ljust(ALIGN, b'\0')
        self.assertEqual(entries(index, [3*ALIGN]), [(0,0,ALIGN,2*ALIGN)])
        with self.assertRaisesRegex(ValueError, 'Out-of-bounds'):
            entries(index, [2*ALIGN])
        with self.assertRaisesRegex(ValueError, 'terminator'):
            entries(struct.pack('<HH',0,1)*(ALIGN//4), [ALIGN])
        with self.assertRaises(ValueError):
            entries(index[:-1], [ALIGN])

    def test_paletted_tim_keeps_stp_black_and_duplicate_colors(self):
        palette = [0,0x8000,0x001f,0x801f] + [0]*12
        clut = struct.pack('<16H',*palette)
        pixels = bytes([0x10,0x32])
        data = (struct.pack('<II',16,8) + struct.pack('<IHHHH',44,0,480,16,1) + clut
                + struct.pack('<IHHHH',14,960,384,1,1) + pixels)
        tim = validate_tim(data,0)
        self.assertIsNotNone(tim)
        self.assertEqual(tim['palette']['bytes'],clut)
        self.assertEqual(tim['pixels'],pixels)
        image,_ = decode_tim(tim,0)
        self.assertEqual(list(image.getdata()),[(0,0,0,0),(0,0,0,255),(248,0,0,127),(248,0,0,255)])


if __name__=='__main__':
    unittest.main()
