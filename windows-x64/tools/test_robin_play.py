"""Behavioral coverage for Robin's pad-only acceptance route and read stalls."""
import unittest
import struct
from unittest.mock import patch
import ein_bridge as bridge

class ImmediateHalt:
    def wait(self,unused):pass
    def set(self):pass

class RobinPlayTests(unittest.TestCase):
    def test_position_feedback_corrects_both_axes_without_timer_drift(self):
        bot=bridge.Robin()
        def moves(x,y):return bot.position_buttons(struct.pack('<ii',y,x))
        self.assertEqual(['left','down'],moves(128,0))
        self.assertEqual(['up'],moves(220,60))
        self.assertEqual(['right','down'],moves(300,-60))
        self.assertEqual(['down'],moves(220,0))
        with self.assertRaises(ValueError):moves(20000,0)
        with self.assertRaises(ValueError):bot.position_buttons(b'bad')

    def test_calibrated_city_and_night_pulses_use_integer_global_coordinates(self):
        self.assertEqual('0x80081E18',bridge.ADDR_PLAYER_POSITION)
        for start_x,start_y in ((128,-9),(238,-37)):
            bot=bridge.Robin();bot.apply(dict(dodge=False))
            raw=lambda x,y:struct.pack('<ii',y,x)
            for x in (start_x,start_x-114,start_x-228,start_x-114,start_x):
                bot.position_buttons(raw(x,start_y))
                self.assertEqual(x,bot.position['x'])
                self.assertEqual(start_y,bot.position['y'])

    def test_revival_disabled_does_not_confirm_continue_with_autofire(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt()
        bot.apply(dict(revive=False,autofire=True,invincible=False))
        calls=[]
        def command(obj,timeout=8):
            calls.append(obj)
            return dict(ok=True,data='00') if obj['cmd']=='read_ram' else dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertFalse(bot.running)
        self.assertEqual(['read_ram','clear_input'],[c['cmd'] for c in calls])

    def test_lane_uses_guest_progress_and_does_not_drift_horizontally(self):
        bot=bridge.Robin();bot.apply(dict(movement='left_lane',fire_mode='both'))
        self.assertEqual(['left','x','square'],bot.lane_buttons(100))
        self.assertEqual(['left','x','square'],bot.lane_buttons(100))
        self.assertEqual(['down','x','square'],bot.lane_buttons(124))
        self.assertEqual(['up','x','square'],bot.lane_buttons(142))
        self.assertEqual(['down','x','square'],bot.lane_buttons(160))
        self.assertNotIn('right',bot.lane_buttons(400))

    def test_guest_reset_releases_route_instead_of_replaying_stale_movement(self):
        bot=bridge.Robin();bot.running=True
        bot.lane_buttons(400)
        self.assertEqual([],bot.lane_buttons(10))
        self.assertFalse(bot.running)

    def test_invalid_route_config_is_atomic(self):
        bot=bridge.Robin()
        with self.assertRaises(ValueError):bot.apply(dict(autofire=False,movement='teleport'))
        self.assertTrue(bot.autofire)

    def test_failed_reads_release_input_without_revival_or_cheats(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        def command(obj,timeout=8):
            calls.append(obj)
            return dict(ok=False,error='timed out')
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertFalse(bot.running)
        self.assertEqual(3,sum(c['cmd']=='read_ram' for c in calls))
        self.assertTrue(all(c['cmd'] in ('read_ram','clear_input') for c in calls))

    def test_one_read_stall_recovers_to_pad_play(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt()
        bot.apply(dict(movement='left_lane',fire_mode='both',invincible=False))
        calls=[];reads=0
        def command(obj,timeout=8):
            nonlocal reads
            calls.append(obj)
            if obj['cmd']=='read_ram':
                reads+=1
                return dict(ok=False,error='timed out') if reads==1 else dict(ok=True,data='03')
            if obj['cmd']=='get_registers':return dict(ok=True,frame=100)
            if obj['cmd']=='press':bot.request_stop()
            return dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        presses=[c for c in calls if c['cmd']=='press']
        self.assertEqual(1,len(presses))
        self.assertEqual(bridge.btn_word('left','x','square'),presses[0]['buttons'])
        self.assertFalse(any(c['cmd']=='write_ram' for c in calls))
        self.assertEqual('clear_input',calls[-1]['cmd'])

if __name__=='__main__':unittest.main()
