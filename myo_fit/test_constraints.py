import unittest

import mujoco
import numpy as np

from .constraints import CoupledCoordinates


class ConstraintTests(unittest.TestCase):
    def test_polynomial_coupling_restricts_parent_and_respects_mujoco(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><compiler angle="radian"/><worldbody>
          <body><joint name="a" range="-2 2"/><geom size=".1"/></body>
          <body><joint name="b" range="-.1 .25"/><geom size=".1"/></body>
          </worldbody><equality><joint joint1="b" joint2="a" polycoef="0 0 1 0 0"/></equality></mujoco>''')
        coupled = CoupledCoordinates(model)
        # The child b=a^2 restricts a to [-.5,.5], within its own [-2,2].
        bound = np.sqrt(model.jnt_range[1, 1])
        expected = min(model.jnt_range[0, 1], bound)
        self.assertAlmostEqual(coupled.bounds[0, 1], expected)
        data = mujoco.MjData(model)
        for x in np.linspace(*coupled.bounds[0], 7):
            coupled.apply(np.array([x]), data.qpos); coupled.check(data.qpos)
            mujoco.mj_forward(model, data)
            mask = data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
            self.assertLess(np.max(np.abs(data.efc_pos[mask])), 1e-10)
        data.qpos[1] += .1
        with self.assertRaises(ValueError):
            coupled.check(data.qpos)

    def test_cycles_fail_instead_of_omitting_couplings(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <body><joint name="a" range="-1 1"/><geom size=".1"/></body>
          <body><joint name="b" range="-1 1"/><geom size=".1"/></body>
          </worldbody><equality><joint joint1="a" joint2="b"/><joint joint1="b" joint2="a"/></equality></mujoco>''')
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            CoupledCoordinates(model)


if __name__ == '__main__':
    unittest.main()
