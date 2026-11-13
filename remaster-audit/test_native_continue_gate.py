"""Continue gates against actual gameplay, results and successive countdowns."""
import unittest
from PIL import Image
import numpy as np
import native_continue_gate as gate
from native_ui_facade_route import native_pixels

class ContinueTests(unittest.TestCase):
    def test_real_countdown_sequence(self):
        g=gate.ContinueGate()
        for i in range(3):
            with Image.open(gate.REFERENCE.with_name(f'terminal-{148+i:04d}.png')) as image:
                result=g.observe(native_pixels(image),100+i)
        self.assertTrue(result['ready']);g.mark_issued()
        with self.assertRaises(RuntimeError):g.mark_issued()
        self.assertFalse(g.observe(g.reference,104)['ready'])
        g.resumed(lives=3,hull_valid=True)
        self.assertFalse(g.issued)

    def test_gameplay_and_other_menus_cannot_confirm(self):
        g=gate.ContinueGate();refs=[]
        for name in ['title.png','fighter.png','arm.png','frame-0030.png','frame-0180.png']:
            with Image.open(gate.REFERENCE.with_name(name)) as image:refs.append(native_pixels(image))
        for image in [*refs,np.zeros((240,320,3),np.uint8)]:
            for frame in range(3):self.assertFalse(g.observe(image,frame)['ready'])
            with self.assertRaises(RuntimeError):g.mark_issued()

    def test_frozen_or_regressing_frames_and_fresh_hull_block(self):
        g=gate.ContinueGate()
        for frame in [2,2,1,1,1]:self.assertFalse(g.observe(g.reference,frame)['ready'])
        for frame in range(3):self.assertFalse(g.observe(g.reference,frame,hull_valid=True)['ready'])

    def test_missing_question_or_choices_blocks(self):
        for rect in [(88,45,232,68),(88,192,222,214)]:
            g=gate.ContinueGate();image=g.reference.copy();x,y,r,b=rect;image[y:b,x:r]=0
            for frame in range(3):self.assertFalse(g.observe(image,frame)['ready'])

    def test_resume_requires_positive_lives_and_hull(self):
        g=gate.ContinueGate()
        for frame in range(3):g.observe(g.reference,frame)
        g.mark_issued()
        for lives,hull in [(0,True),(3,False)]:
            with self.assertRaises(RuntimeError):g.resumed(lives=lives,hull_valid=hull)

if __name__=='__main__':unittest.main()
