import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from .visualize_calibration import transform, elevation_arc


class CalibrationViewTests(unittest.TestCase):
    def test_display_basis_preserves_geometry_and_handedness(self):
        origin=np.array([1.,2.,3.])
        frame=Rotation.from_euler('xyz',[20,-30,17],degrees=True).as_matrix()
        points=origin+frame.T  # rows are world-space basis directions
        mapped=transform(points,origin,frame)
        np.testing.assert_allclose(mapped,[[0,1,0],[0,0,1],[1,0,0]],atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(mapped),1.)
        np.testing.assert_allclose(np.linalg.norm(mapped[:,None]-mapped[None,:],axis=-1),np.linalg.norm(points[:,None]-points[None,:],axis=-1),atol=1e-12)

    def test_known_elevation_arc_in_arbitrary_world_orientation(self):
        r=Rotation.from_euler('xyz',[10,30,40],degrees=True).as_matrix()
        shoulder=np.array([.3,.2,4.])
        angle=np.deg2rad(25)
        elbow=shoulder+r@np.array([np.sin(angle),-np.cos(angle),0.])*.32
        arc,measured=elevation_arc(shoulder,elbow,r[:,1])
        self.assertAlmostEqual(measured,25.)
        np.testing.assert_allclose(arc[0],shoulder-.19*r[:,1],atol=1e-12)
        np.testing.assert_allclose(arc[-1],shoulder+.19*(elbow-shoulder)/np.linalg.norm(elbow-shoulder),atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(arc-shoulder,axis=1),.19,atol=1e-12)

    def test_zero_elevation_does_not_invent_an_arc_plane(self):
        arc,angle=elevation_arc(np.zeros(3),np.array([0.,-1.,0.]),np.array([0.,1.,0.]))
        self.assertEqual(angle,0.)
        np.testing.assert_allclose(arc,np.tile([0,-.19,0],(32,1)))

    def test_antiparallel_directions_are_explicitly_rejected(self):
        with self.assertRaises(ValueError):
            elevation_arc(np.zeros(3),np.array([0.,1.,0.]),np.array([0.,1.,0.]))


if __name__=='__main__':unittest.main()
