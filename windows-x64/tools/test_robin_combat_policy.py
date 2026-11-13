import unittest
from robin_combat_policy import CombatPolicy

def hull(f=100,y=80):return dict(frame=f,age_frames=0,bounds=[28,y-10,52,y+10],source_set=3)
def scene(f=100,y=130,family='uhu'):
    return dict(ok=True,enabled=True,valid=True,frame=f,age_frames=0,viewport=[320,224],objects=[
        dict(family=family,key='46D3938E-11111111',bounds=[170,y-15,210,y+15])])

class CombatTests(unittest.TestCase):
    def test_enemy_geometry_drives_aim_not_an_elapsed_time_weave(self):
        p=CombatPolicy();a=p.decide(hull(),scene());self.assertEqual(['down'],a['moves']);self.assertTrue(a['fire']);self.assertFalse(a['pod_fire'])
        b=p.decide(hull(110,y=130),scene(110));self.assertTrue(b['fire']);self.assertEqual('engage',b['mode']);self.assertEqual([],b['moves'])
        self.assertEqual(a['target']['track'],b['target']['track'])

    def test_enemy_motion_produces_lead_and_palette_fades_keep_target(self):
        p=CombatPolicy();p.decide(hull(),scene())
        r=scene(110,y=140);r['objects'][0]['key']='46D3938E-22222222'
        a=p.decide(hull(110),r);self.assertGreater(a['target']['lead_y'],140);self.assertEqual(1,a['target']['track'])

    def test_search_keeps_main_fire_and_conserves_pod_without_a_random_sweep(self):
        p=CombatPolicy();r=scene();r['objects']=[]
        a=p.decide(hull(),r);self.assertTrue(a['fire']);self.assertFalse(a['pod_fire']);self.assertEqual([],a['moves']);self.assertEqual('search',a['mode'])

    def test_outgoing_tracer_is_never_an_enemy_aim_target(self):
        p=CombatPolicy();a=p.decide(hull(),scene(family='tracer'))
        self.assertIsNone(a['target']);self.assertFalse(a['pod_fire'])

    def test_boss_pages_form_one_retained_aim_target(self):
        p=CombatPolicy();r=scene(family='greif');r['objects'].append(dict(family='greif',key='1263A036-33333333',bounds=[150,80,230,170]))
        a=p.decide(hull(),r);self.assertEqual('greif',a['target']['family']);self.assertEqual([150,80,230,170],a['target']['bounds'])

    def test_stale_geometry_releases_target_and_fire(self):
        p=CombatPolicy();p.decide(hull(),scene());a=p.decide(hull(200),scene())
        self.assertFalse(a['fire']);self.assertIsNone(a['target']);self.assertEqual([],a['moves'])

    def test_arm_replaces_body_union_and_mount_even_with_an_existing_lock(self):
        p=CombatPolicy();p.decide(hull(),scene(family='greif',y=80))
        r=scene(110,family='greif',y=80)
        r['objects'] += [dict(family='greif_arm',key='38DC02FE-3F675C0D',bounds=[220,110,250,122]),
                         dict(family='greif_mount',key='1263A036-724442F7',bounds=[220,75,250,90])]
        a=p.decide(hull(110),r)
        self.assertEqual('greif_arm',a['target']['family']);self.assertEqual([220,110,250,122],a['target']['bounds'])
        self.assertIn('down',a['moves']);self.assertFalse(a['pod_fire'])

    def test_fresh_mount_is_targeted_when_arm_is_absent(self):
        p=CombatPolicy();p.decide(hull(),scene(family='greif_arm',y=116))
        r=scene(110,family='greif_mount',y=116);r['objects'].append(dict(family='greif',key='1263A036-6E78D825',bounds=[190,45,270,90]))
        a=p.decide(hull(110,y=116),r)
        self.assertEqual('greif_mount',a['target']['family']);self.assertTrue(a['pod_fire'])
        self.assertTrue(a['threat']['fresh']);self.assertEqual(0,a['threat']['predicted'])

    def test_arm_target_does_not_disable_incoming_tracer_evasion(self):
        p=CombatPolicy();r=scene(family='greif_arm',y=80)
        r['objects'].append(dict(family='tracer',key='C7502427-00000000',bounds=[80,75,84,79]))
        p.decide(hull(),r);r['frame']=110;r['objects'][-1]['bounds']=[50,75,54,79]
        a=p.decide(hull(110),r)
        self.assertEqual('greif_arm',a['target']['family']);self.assertEqual('evade',a['mode']);self.assertTrue(a['moves'])

    def test_small_aim_error_uses_a_short_finite_pulse(self):
        p=CombatPolicy();a=p.decide(hull(y=120),scene(y=130))
        self.assertIn('down',a['moves']);self.assertLess(a['movement_frames'],6)

if __name__=='__main__':unittest.main()
