"""Small regression checks for axes, parent IDs, interpolation and playback."""
import tempfile
import unittest
from pathlib import Path

import glfw
import mujoco
import numpy as np

from .__main__ import Playback, validate
from .skeleton import WORLD_TO_MUJOCO, Skeleton, bone_quat, convert, sample, slerp


class DemoTests(unittest.TestCase):
    def fixture(self, directory):
        path = Path(directory) / 'native.npz'
        joints = np.array([[[[0., 0., 0.], [0., 1., 0.], [1., 1., 0.]],
                            [[0., .3, 0.], [0., 1.3, 0.], [1., 1.3, 0.]]]])
        rotations = np.broadcast_to(np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]), (1, 2, 3, 3, 3))
        np.savez(path, segment_names=np.array(['Hips', 'Head', 'LeftHand']),
                 parent_ids_with_root=np.array([0, 0, 1, 2]), joints_global_m=joints,
                 segment_rotations_global=rotations, clip_times_s=np.array([[0., .1]]),
                 source_times_s=np.array([[2., 2.1]]))
        return path

    def test_axis_mapping_is_right_handed(self):
        np.testing.assert_array_equal(WORLD_TO_MUJOCO @ [0., 1., 0.], [0., 0., 1.])
        np.testing.assert_array_equal(WORLD_TO_MUJOCO @ [0., 0., 1.], [0., -1., 0.])
        self.assertAlmostEqual(np.linalg.det(WORLD_TO_MUJOCO), 1.)

    def test_parent_mapping_rotation_basis_and_constant_display_lift(self):
        with tempfile.TemporaryDirectory() as directory:
            motion = convert(self.fixture(directory))
        np.testing.assert_array_equal(motion['parents'], [-1, 0, 1])
        # Native Rz(90) sends local X to native Y, which becomes world Z.
        np.testing.assert_allclose(motion['rotations'][0, 0] @ [1., 0., 0.], [0., 0., 1.])
        np.testing.assert_allclose(motion['positions_m'][1] - motion['positions_m'][0], [[0., 0., .3]] * 3)
        np.testing.assert_array_equal(motion['source_times_s'], [2., 2.1])
        positions, _ = sample(motion, .05)
        np.testing.assert_allclose(positions, (motion['positions_m'][0] + motion['positions_m'][1]) / 2.)
        report = validate(Skeleton(motion))
        self.assertEqual(report['frames'], 2)
        self.assertEqual(report['bones'], 2)
        self.assertEqual(report['qpos_count'], 0)

    def test_slerp_and_quaternion_sign(self):
        first = np.array([[1., 0., 0., 0.]])
        second = np.array([[0., 0., 0., 1.]])
        np.testing.assert_allclose(slerp(first, second, .5), [[2 ** -.5, 0., 0., 2 ** -.5]])
        np.testing.assert_allclose(slerp(first, -first, .5), first)

    def test_capsule_alignment_including_antiparallel(self):
        for vector in ([0., 0., -1.], [.0001, 0., -1.], [1., 2., 3.], [0., 0., 0.]):
            quat, length = bone_quat(np.array(vector))
            matrix = np.empty(9); mujoco.mju_quat2Mat(matrix, quat)
            np.testing.assert_allclose(matrix.reshape(3, 3)[:, 2] * length, vector, atol=1e-9)

    def test_pause_frame_step_speed_restart_and_loop(self):
        playback = Playback(np.arange(60) / 30.)
        playback.advance(.5); self.assertAlmostEqual(playback.time, .5)
        playback.key(glfw.KEY_SPACE); playback.advance(10.)
        self.assertAlmostEqual(playback.time, .5)
        playback.key(glfw.KEY_RIGHT); self.assertAlmostEqual(playback.time, 16 / 30.)
        playback.key(glfw.KEY_LEFT); self.assertAlmostEqual(playback.time, .5)
        playback.key(glfw.KEY_R); self.assertEqual(playback.time, 0.)
        playback.key(glfw.KEY_S); self.assertEqual(playback.speed, 2.)
        playback.key(glfw.KEY_SPACE); playback.advance(1.1)
        self.assertAlmostEqual(playback.time, .2)
        playback.key(glfw.KEY_L); playback.advance(10.)
        self.assertTrue(playback.paused)
        self.assertAlmostEqual(playback.time, 59 / 30.)


if __name__ == '__main__':
    unittest.main()
