import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from .analysis import analyze


class AnalysisTests(unittest.TestCase):
    def run_angles(self, relative):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);times=np.arange(len(relative))*.1
            arrays={'times_s':times}
            for side in ('left','right'):
                arrays[side+'_relative']=relative
                arrays[side+'_angles_deg']=np.zeros((len(relative),3))
            np.savez(p/'source.npz',**arrays)
            analyze(p/'source.npz',p/'result',neutral_seconds=.15)
            result=np.load(p/'result/shoulder-review.npz')
            return {k:result[k].copy() for k in result.files},json.loads((p/'result/report.json').read_text())

    def test_neutral_offset_removed_as_rotation_not_scalar_subtraction(self):
        offset=Rotation.from_euler('xyz',[15,20,-10],degrees=True).as_matrix()
        motions=Rotation.from_euler('z',np.array([0,0,30,60])[:,None],degrees=True).as_matrix()
        result,report=self.run_angles(motions@offset)
        np.testing.assert_allclose(result['right_angles_deg'][:,1],[0,0,30,60],atol=1e-5)
        self.assertFalse(result['right_valid'][0])
        self.assertEqual(report['reference_frames'],2)

    def test_twist_visible_when_yxy_is_singular(self):
        offset=Rotation.from_euler('x',18,degrees=True).as_matrix()
        motions=Rotation.from_euler('y',np.array([0,0,25,40])[:,None],degrees=True).as_matrix()
        result,_=self.run_angles(motions@offset)
        np.testing.assert_allclose(result['right_twist_deg'],[0,0,25,40],atol=1e-6)
        np.testing.assert_allclose(result['left_twist_deg'],[0,0,-25,-40],atol=1e-6)
        self.assertFalse(result['right_valid'].any())


if __name__=='__main__':unittest.main()
