"""CPU-only regression controls for preserving artwork outside an approved ROI."""
import importlib.util
from pathlib import Path
import unittest
import hashlib,tempfile
import numpy as np
from PIL import Image
spec=importlib.util.spec_from_file_location('composer',Path(__file__).with_name('build_stage1_frozen_candidate.py'))
composer=importlib.util.module_from_spec(spec);spec.loader.exec_module(composer)

class RoiControls(unittest.TestCase):
    def setUp(self):
        self.parent=np.arange(8*8*4,dtype=np.uint8).reshape(8,8,4);self.parent[:,:,3]=127
        self.authored=np.full((8,8,4),231,dtype=np.uint8);self.authored[:,:,3]=255
        self.policy=dict(native_size=[4,4],uv=[1,1,3,3])
    def apply(self,policy=None,parent=None,authored=None):
        return composer.apply_roi_overlay(Image.fromarray(self.parent if parent is None else parent),
            Image.fromarray(self.authored if authored is None else authored),self.policy if policy is None else policy)
    def test_preserves_latest_parent_outside_and_replaces_roi_rgba(self):
        original=self.parent.copy();image,receipt=self.apply();a=np.array(image)
        outside=np.ones((8,8),bool);outside[2:6,2:6]=False
        np.testing.assert_array_equal(a[outside],self.parent[outside])
        np.testing.assert_array_equal(a[2:6,2:6],self.authored[2:6,2:6])
        np.testing.assert_array_equal(self.parent,original)
        self.assertEqual(receipt['roi_pixels_changed'],16);self.assertEqual(receipt['outside_pixels'],48)
    def test_half_open_bottom_right_boundary(self):
        image,_=self.apply(dict(native_size=[4,4],uv=[3,3,4,4]));a=np.array(image)
        np.testing.assert_array_equal(a[:6],self.parent[:6])
        np.testing.assert_array_equal(a[6:,6:],self.authored[6:,6:])
        np.testing.assert_array_equal(a[6:,:6],self.parent[6:,:6])
    def test_equal_roi_records_zero_change(self):
        image,receipt=self.apply(authored=self.parent.copy())
        np.testing.assert_array_equal(np.array(image),self.parent);self.assertEqual(receipt['roi_pixels_changed'],0)
    def test_invalid_geometry_fails_closed(self):
        bad=[None,{},dict(native_size=[4,4],uv=[0,0,5,4]),dict(native_size=[4,4],uv=[2,1,2,3]),
            dict(native_size=[4,4],uv=[-1,0,1,2]),dict(native_size=[0,4],uv=[0,0,1,1]),
            dict(native_size=[4,4],uv=[True,0,2,2]),dict(native_size=[4,4],uv=[0.,0,2,2]),
            dict(native_size=[4],uv=[0,0,2,2]),dict(native_size=[4,4],uv=[0,0,2]),
            dict(native_size=[4,4],uv=[0,0,2,2],extra=1)]
        for policy in bad:
            with self.subTest(policy=policy),self.assertRaises(ValueError):
                composer.apply_roi_overlay(Image.fromarray(self.parent),Image.fromarray(self.authored),policy)
    def test_size_or_scale_mismatch_refused(self):
        cases=[(self.parent,self.authored[:4],self.policy),
            (self.parent,self.authored,dict(native_size=[3,4],uv=[0,0,2,2])),
            (self.parent,self.authored,dict(native_size=[4,2],uv=[0,0,2,2])),
            (self.parent,self.authored,dict(native_size=[16,16],uv=[0,0,2,2]))]
        for parent,authored,policy in cases:
            with self.subTest(policy=policy),self.assertRaises(ValueError):self.apply(policy,parent,authored)

    def test_frozen_roi_baseline_binding_and_later_parent_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'baseline.png';Image.fromarray(self.parent).save(path)
            metadata=dict(region='test uv [1,1]-[3,3] half-open',keys={'key':dict(live=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))})
            patch=self.parent.copy();patch[2:6,2:6]=self.authored[2:6,2:6]
            binding=composer.validate_roi_artifact(metadata,'key',self.policy,Image.fromarray(patch))
            self.assertTrue(binding['authored_outside_baseline_identical'])
            # A newer parent's other art must remain accepted and preserved.
            later=self.parent.copy();later[0,0,:3]=[91,92,93]
            image,_=self.apply(parent=later,authored=patch)
            np.testing.assert_array_equal(np.array(image)[0,0],later[0,0])
            for bad in [dict(native_size=[4,4],uv=[0,0,3,3]),dict(native_size=[4,4],uv=[1,1,2,3])]:
                with self.assertRaises(ValueError):composer.validate_roi_artifact(metadata,'key',bad,Image.fromarray(patch))
            patch[0,0,0]^=1
            with self.assertRaises(ValueError):composer.validate_roi_artifact(metadata,'key',self.policy,Image.fromarray(patch))
            with self.assertRaises(ValueError):composer.validate_roi_artifact(metadata,'missing',self.policy,Image.fromarray(self.parent))

    def test_non_rgba_parent_refused(self):
        with self.assertRaises(ValueError):composer.apply_roi_overlay(Image.fromarray(self.parent).convert('P'),Image.fromarray(self.authored),self.policy)

if __name__=='__main__':unittest.main()
