import unittest
from robin_stage_policy import StagePolicy
import ein_bridge as bridge

class StagePolicyTests(unittest.TestCase):
    def test_actual_hull_drives_home_and_fighter_wave_sweep(self):
        p=StagePolicy()
        for f in range(0,1701,100):p.moves(dict(frame=f,age_frames=0),28,14)
        self.assertEqual(['down'],p.moves(dict(frame=1701,age_frames=0),28,14))
        self.assertEqual('fighter wave 3',p.last['label'])
        self.assertEqual([],p.moves(dict(frame=1710,age_frames=0),28,190))

    def test_home_keeps_hull_inside_visible_top_band_without_chatter(self):
        self.assertEqual(['down'],StagePolicy().moves(dict(frame=10,age_frames=0),28,4))
        self.assertEqual([],StagePolicy().moves(dict(frame=10,age_frames=0),28,25))
        self.assertEqual(['left','up'],StagePolicy().moves(dict(frame=10,age_frames=0),100,120))

    def test_death_gap_uses_inferred_checkpoint_and_preserves_receipt(self):
        p=StagePolicy()
        p.note_lives(3)
        for f in range(100,4401,100):p.observe(f)
        p.absent(4700);p.note_lives(2);p.observe(4900)
        self.assertEqual(2,p.life);self.assertEqual(3882,p.checkpoint)
        self.assertEqual(4238,p.deaths[0]['stage'])
        self.assertEqual(4900,p.start)

    def test_camera_gap_without_native_life_loss_does_not_reset_stage(self):
        p=StagePolicy();p.note_lives(3);p.observe(100)
        p.absent(700);p.note_lives(3);p.moves(dict(frame=800,age_frames=0),28,25)
        self.assertEqual(1,p.life);self.assertEqual(700,p.last['stage']);self.assertEqual([],p.deaths)

    def test_continue_restores_lives_without_inventing_another_death(self):
        p=StagePolicy();p.note_lives(1);p.observe(100);p.observe(4100)
        p.note_lives(0);p.note_lives(3);p.observe(4700)
        self.assertEqual(2,p.life);self.assertEqual(1,len(p.deaths));self.assertEqual(3882,p.checkpoint)

    def test_continuous_greif_sweep_never_reverses_into_volley(self):
        p=StagePolicy()
        for f in range(0,5601,100):p.moves(dict(frame=f,age_frames=0),28,14)
        self.assertEqual(['down'],p.moves(dict(frame=5630,age_frames=0),28,14))
        self.assertEqual([],p.moves(dict(frame=5640,age_frames=0),28,210))
        for f in range(5700,5901,100):p.moves(dict(frame=f,age_frames=0),28,200)
        self.assertEqual(['up'],p.moves(dict(frame=5910,age_frames=0),28,200))

    def test_stale_missing_boolean_future_or_reversed_clock_fails_closed(self):
        p=StagePolicy()
        for state in [dict(frame=1),dict(frame=True,age_frames=0),dict(frame=1,age_frames=13)]:
            with self.assertRaises(ValueError):p.moves(state,28,14)
        p.moves(dict(frame=100,age_frames=0),28,14)
        with self.assertRaises(ValueError):p.moves(dict(frame=99,age_frames=0),28,14)
        bot=bridge.Robin();bot.apply(dict(movement='stage_lane'))
        with self.assertRaises(ValueError):bot.draw_buttons(dict(ok=True,enabled=True,valid=True,
            frame=100,age_frames=0,bounds=[18,4,38,24],viewport=[320,224],
            greif_draw=dict(valid=True,first_frame=101,last_frame=101,age_frames=0)))

if __name__=='__main__':unittest.main()
