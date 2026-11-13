import unittest
from robin_threat_policy import ThreatPolicy

def reply(frame,bounds,family='tracer'):
    return dict(ok=True,enabled=True,valid=True,frame=frame,age_frames=0,viewport=[320,224],
        dropped=0,objects=[dict(family=family,key='C7502427-00000000',bounds=bounds)])

class ThreatPolicyTests(unittest.TestCase):
    def test_incoming_projectile_requires_motion_and_causes_committed_escape(self):
        p=ThreatPolicy();h=[16,80,40,110]
        self.assertIsNone(p.target_y(reply(100,[120,90,124,94]),h,100))
        y=p.target_y(reply(110,[90,90,94,94]),h,110)
        self.assertIsNotNone(y);self.assertGreater(abs(y-95),15)
        self.assertEqual(y,p.target_y(reply(120,[60,90,64,94]),h,120))

    def test_outgoing_player_fire_is_not_an_approaching_tracer(self):
        p=ThreatPolicy();h=[16,80,40,110]
        p.target_y(reply(100,[45,90,49,94]),h,100)
        self.assertIsNone(p.target_y(reply(110,[75,90,79,94]),h,110))

    def test_native_palette_phase_change_keeps_motion_correspondence(self):
        p=ThreatPolicy();h=[16,80,40,110]
        p.target_y(reply(100,[120,90,124,94]),h,100)
        changed=reply(110,[90,90,94,94]);changed['objects'][0]['key']='C7502427-11111111'
        self.assertIsNotNone(p.target_y(changed,h,110))

    def test_close_uhu_cluster_causes_escape_without_velocity_history(self):
        p=ThreatPolicy();y=p.target_y(reply(100,[36,70,100,120],'uhu'),[16,80,40,110],100)
        self.assertIsNotNone(y)

    def test_empty_completed_frame_clears_old_geometry_and_stale_data_is_ignored(self):
        p=ThreatPolicy();h=[16,80,40,110]
        p.target_y(reply(100,[120,90,124,94]),h,100)
        empty=reply(110,[90,90,94,94]);empty['objects']=[]
        self.assertIsNone(p.target_y(empty,h,110));self.assertEqual([],p.previous)
        self.assertIsNone(p.target_y(reply(90,[10,90,20,94]),h,120))

    def test_malformed_geometry_cannot_produce_direction(self):
        for b in ([0,0,400,20],[0,0,True,20],[0,0,0,20]):
            p=ThreatPolicy();self.assertIsNone(p.target_y(reply(100,b,'uhu'),[16,80,40,110],100))
        p=ThreatPolicy();r=reply(100,[20,80,40,100],'uhu');r['objects']*=65
        self.assertIsNone(p.target_y(r,[16,80,40,110],100))

if __name__=='__main__':unittest.main()
