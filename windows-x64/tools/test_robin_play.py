"""Behavioral coverage for Robin's pad-only acceptance route and read stalls."""
import unittest
from unittest.mock import patch
import ein_bridge as bridge

class ImmediateHalt:
    def wait(self,unused):pass
    def set(self):pass

class RobinPlayTests(unittest.TestCase):
    def test_greif_policy_uses_actual_encounter_and_keeps_each_sweep_one_way(self):
        bot=bridge.Robin();bot.apply(dict(movement='greif_lane'))
        def moves(g,y=100,first=1000):
            now=first+g
            return bot.draw_buttons(dict(ok=True,enabled=True,valid=True,frame=now,age_frames=0,
                bounds=[18,y-10,38,y+10],viewport=[320,224],greif_draw=dict(valid=True,
                first_frame=first,last_frame=now,age_frames=0)))
        # Poll continuously: a >150-frame gap deliberately starts a new life.
        for g in range(0,401,50):moves(g,14)
        self.assertEqual(['down'],moves(500,14))
        self.assertEqual([],moves(510,190))
        moves(600);moves(680)
        self.assertEqual(['up'],moves(750,200))
        self.assertEqual([],moves(760,14))
        self.assertEqual(1000,bot.position['greif_policy']['anchor'])
        self.assertEqual(760,bot.position['greif_policy']['elapsed'])

    def test_greif_policy_rejects_missing_future_or_reversed_guest_clock(self):
        bot=bridge.Robin();bot.position={}
        with self.assertRaises(ValueError):bot.greif_target(dict(frame=100,age_frames=0))
        with self.assertRaises(ValueError):bot.greif_target(dict(frame=100,age_frames=0,
            greif_draw=dict(valid=True,first_frame=101,last_frame=101,age_frames=0)))
        with self.assertRaises(ValueError):bot.greif_target(dict(frame=99,age_frames=0,
            greif_draw=dict(valid=False,age_frames=200)))

    def test_upper_lane_parking_uses_observed_position_without_open_loop_drift(self):
        bot=bridge.Robin();bot.apply(dict(movement='upper_lane',fire_mode='both'))
        def moves(x,y):return bot.draw_buttons(dict(ok=True,enabled=True,valid=True,
            bounds=[x-10,y-10,x+10,y+10],viewport=[320,224],source_set=3))
        self.assertEqual(['left','up'],moves(109,180))
        self.assertEqual(['right','up'],moves(20,40))
        self.assertEqual([],moves(28,14))
        self.assertEqual(['down'],moves(28,10))

    def test_ordinary_lane_with_hull_guard_uses_the_last_active_craft(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        bot.apply(dict(movement='upper_lane',revive=False,hull_guard=True))
        def command(obj,timeout=8):
            calls.append(obj)
            if obj['cmd']=='read_ram':return dict(ok=True,data='00')
            if obj['cmd']=='player_draw':return dict(ok=True,enabled=True,valid=True,source_set=3,
                bounds=[18,4,38,24],viewport=[320,224])
            if obj['cmd']=='get_registers':return dict(ok=True,frame=100)
            if obj['cmd']=='press':bot.request_stop()
            return dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertTrue(any(c['cmd']=='press' for c in calls))
        self.assertFalse(any(c['cmd']=='write_ram' for c in calls))

    def test_ordinary_lane_without_fresh_hull_stops_at_zero_lives(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        bot.apply(dict(movement='upper_lane',revive=False,hull_guard=True))
        def command(obj,timeout=8):
            calls.append(obj)
            return dict(ok=True,data='00') if obj['cmd']=='read_ram' else dict(ok=True,enabled=True,valid=False)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertFalse(any(c['cmd']=='press' for c in calls))

    def test_draw_feedback_corrects_screen_axes_with_hysteresis(self):
        bot=bridge.Robin()
        def moves(x,y,**kw):return bot.draw_buttons(dict(ok=True,enabled=True,valid=True,
            bounds=[x-10,y-10,x+10,y+10],viewport=[320,240],**kw))
        self.assertEqual(['left','down'],moves(160,120))
        self.assertEqual(['up'],moves(80,170))
        self.assertEqual(['right','down'],moves(30,60))
        self.assertEqual(['down'],moves(80,120))
        with self.assertRaises(ValueError):moves(20000,0)
        with self.assertRaises(ValueError):bot.draw_buttons(dict(ok=True,enabled=True,valid=False))

    def test_failed_ram_position_mode_is_not_exposed(self):
        with self.assertRaises(ValueError):bridge.Robin().apply(dict(movement='position_lane'))

    def test_last_craft_with_zero_spare_lives_is_not_a_continue_screen(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        bot.apply(dict(movement='draw_lane',revive=False,dodge=False))
        def command(obj,timeout=8):
            calls.append(obj)
            if obj['cmd']=='read_ram':return dict(ok=True,data='00')
            if obj['cmd']=='player_draw':return dict(ok=True,enabled=True,valid=True,
                bounds=[65,100,95,130],viewport=[320,240],frame=123,age_frames=0)
            if obj['cmd']=='press':bot.request_stop()
            return dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertEqual([bridge.btn_word('x')],[c['buttons'] for c in calls if c['cmd']=='press'])
        self.assertEqual('clear_input',calls[-1]['cmd'])

    def test_missing_hull_releases_input_and_stops_without_blind_fire(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        bot.apply(dict(movement='draw_lane',invincible=False))
        def command(obj,timeout=8):
            calls.append(obj)
            return dict(ok=True,data='03') if obj['cmd']=='read_ram' else dict(ok=True,enabled=True,valid=False)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertFalse(bot.running)
        self.assertEqual(40,sum(c['cmd']=='player_draw' for c in calls))
        self.assertFalse(any(c['cmd'] in ('press','write_ram') for c in calls))

    def test_respawn_gap_keeps_bounded_fire_without_guessing_movement(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();polls=0;calls=[]
        bot.apply(dict(movement='draw_lane',invincible=False,revive=False,fire_mode='both'))
        def command(obj,timeout=8):
            nonlocal polls
            calls.append((polls,obj))
            if obj['cmd']=='read_ram':return dict(ok=True,data='03' if polls==0 else '02')
            if obj['cmd']=='player_draw':
                polls+=1
                if polls==1:return dict(ok=True,enabled=True,valid=True,
                    bounds=[65,100,95,130],viewport=[320,224],frame=100,age_frames=0)
                return dict(ok=True,enabled=True,valid=False,age_frames=60 if polls==2 else 181)
            if obj['cmd']=='clear_input' and polls==3:bot.request_stop()
            return dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        gap=[c for phase,c in calls if phase==2 and c['cmd']=='press']
        self.assertEqual(2,len(gap))
        self.assertTrue(all(c['buttons']==bridge.btn_word('x','square') for c in gap))
        self.assertFalse(any(c['cmd']=='press' for phase,c in calls if phase==3))
        self.assertFalse(any(c['cmd']=='write_ram' for phase,c in calls))
        self.assertEqual('clear_input',calls[-1][1]['cmd'])

    def test_normal_respawn_can_exceed_forty_polls_without_blind_movement(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();polls=0;calls=[]
        bot.apply(dict(movement='draw_lane',revive=False,fire_mode='both'))
        def command(obj,timeout=8):
            nonlocal polls
            calls.append((polls,obj))
            if obj['cmd']=='read_ram':return dict(ok=True,data='02')
            if obj['cmd']=='player_draw':
                polls+=1
                if polls<=60:return dict(ok=True,enabled=True,valid=False,frame=1000,age_frames=200+polls*5)
                return dict(ok=True,enabled=True,valid=True,bounds=[65,100,95,130],viewport=[320,224],frame=1510,age_frames=0)
            if obj['cmd']=='press':bot.request_stop()
            return dict(ok=True)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertEqual(61,polls)
        self.assertFalse(any(c['cmd'] in ('press','write_ram') for phase,c in calls if phase<=60))
        self.assertTrue(any(c['cmd']=='press' for phase,c in calls if phase==61))

    def test_expired_guest_respawn_wait_stops_and_releases_input(self):
        bot=bridge.Robin();bot.running=True;bot._halt=ImmediateHalt();calls=[]
        bot.apply(dict(movement='draw_lane',revive=False))
        def command(obj,timeout=8):
            calls.append(obj)
            return dict(ok=True,data='02') if obj['cmd']=='read_ram' else dict(ok=True,enabled=True,valid=False,frame=1000,age_frames=721)
        with patch.object(bridge,'cmd',command):bot.run()
        self.assertFalse(bot.running)
        self.assertEqual(40,sum(c['cmd']=='player_draw' for c in calls))
        self.assertFalse(any(c['cmd'] in ('press','write_ram') for c in calls))
        self.assertEqual('clear_input',calls[-1]['cmd'])

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
