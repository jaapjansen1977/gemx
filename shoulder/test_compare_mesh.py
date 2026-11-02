import unittest
import numpy as np
from .compare_mesh import mesh_frame, wrapped_difference


class MeshComparisonTests(unittest.TestCase):
    def test_bilateral_right_handed_frames(self):
        for side, sign in [('right', 1), ('left', -1)]:
            frame, valid, angle, separation = mesh_frame(
                np.array([0., 1., 0.]), np.array([0., 0., -.04 * sign]),
                np.array([0., 0., .04 * sign]), side)
            np.testing.assert_allclose(frame, np.eye(3), atol=1e-12)
            self.assertTrue(valid)
            self.assertAlmostEqual(angle, 90.)
            self.assertAlmostEqual(separation, .08)

    def test_rigid_motion_equivariance(self):
        rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        points = np.array([[0., 1., 0.], [0., 0., -.04], [0., 0., .04]])
        reference, _, _, _ = mesh_frame(*points, 'right')
        moved = points @ rotation.T + [3., 2., -7.]
        actual, valid, _, _ = mesh_frame(*moved, 'right')
        np.testing.assert_allclose(actual, rotation @ reference, atol=1e-12)
        self.assertTrue(valid)

    def test_nearly_longitudinal_epicondyles_are_rejected(self):
        frame, valid, angle, _ = mesh_frame(
            np.array([0., 1., 0.]), np.array([0., -.04, -.001]),
            np.array([0., .04, .001]), 'right')
        self.assertFalse(valid)
        self.assertLess(angle, 2.)
        np.testing.assert_allclose(frame.T @ frame, np.eye(3), atol=1e-12)

    def test_coincident_points_have_no_invented_axis(self):
        frame, valid, _, _ = mesh_frame(
            np.array([0., 1., 0.]), np.zeros(3), np.zeros(3), 'right')
        self.assertFalse(valid)
        self.assertTrue(np.isnan(frame).any())

    def test_branch_cut_difference(self):
        np.testing.assert_allclose(wrapped_difference(np.array([-179., 179.]), np.array([179., -179.])), [2., -2.])


if __name__ == '__main__':
    unittest.main()
