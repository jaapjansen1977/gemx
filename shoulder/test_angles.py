import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from .angles import decompose,unwrap_runs


class ShoulderTests(unittest.TestCase):
    def test_known_bilateral_movements_and_reconstruction(self):
        for plane,elevation,axial in [(0,45,0),(90,70,0),(25,110,30),(-40,30,-55)]:
            right=Rotation.from_euler('YXY',[plane,-elevation,axial],degrees=True).as_matrix()
            for side in ('right','left'):
                mirror=np.diag([1.,1.,-1.]); r=right if side=='right' else mirror@right@mirror
                angles,valid,singular=decompose(r,side)
                np.testing.assert_allclose(angles,[plane,elevation,axial],atol=1e-10)
                self.assertTrue(valid); self.assertFalse(singular)
    def test_singularity_and_no_unwrap_across_gap(self):
        angle,valid,singular=decompose(np.eye(3),'right')
        self.assertTrue(singular); self.assertFalse(valid)
        self.assertTrue(np.isnan(angle[[0,2]]).all()); self.assertEqual(angle[1],0)
        out=unwrap_runs(np.array([179.,-179.,0.,-80.,-70.]),np.array([True,True,False,True,True]))
        np.testing.assert_allclose(out[[0,1,3,4]],[179,181,-80,-70]); self.assertTrue(np.isnan(out[2]))


if __name__=='__main__': unittest.main()
