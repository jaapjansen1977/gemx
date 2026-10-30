"""Independently re-load saved qpos and check the original MuJoCo model."""
import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .constraints import CoupledCoordinates
from .fit import load_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    model = load_model(); data = mujoco.MjData(model); coupled = CoupledCoordinates(model)
    with np.load(args.fit, allow_pickle=False) as source:
        fit = {key: source[key].copy() for key in source.files}
    assert fit['qpos'].shape == (len(fit['times_s']), model.nq)
    assert np.isfinite(fit['qpos']).all()
    assert np.all(np.diff(fit['times_s']) > 0)
    np.testing.assert_allclose(np.linalg.norm(fit['qpos'][:, 3:7], axis=1), 1., atol=1e-10)
    bounds = coupling = equality = rotation_error = 0.
    for frame, qpos in enumerate(fit['qpos']):
        check = coupled.check(qpos)
        bounds = max(bounds, check['max_range_violation']); coupling = max(coupling, check['max_joint_coupling_error'])
        data.qpos[:] = qpos; mujoco.mj_forward(model, data)
        mask = data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
        assert np.count_nonzero(mask) == len(coupled.dependencies)
        equality = max(equality, float(np.abs(data.efc_pos[mask]).max()))
        matrices = data.xmat[fit['mapped_body_ids']].reshape(-1, 3, 3)
        angles = np.linalg.norm(Rotation.from_matrix(fit['target_rotations'][frame].transpose(0, 2, 1) @ matrices).as_rotvec(), axis=1)
        rotation_error = max(rotation_error, float(np.abs(angles - fit['orientation_errors_rad'][frame]).max()))
    assert max(bounds, coupling, equality, rotation_error) < 1e-8
    result = {'status': 'passed', 'frames': len(fit['qpos']), 'joint_ranges_checked': int(model.jnt_limited.sum()),
              'active_joint_couplings_checked': len(coupled.dependencies), 'max_range_violation': bounds,
              'max_coupling_error': coupling, 'max_mujoco_equality_residual': equality,
              'max_recomputed_angle_difference_rad': rotation_error,
              'scope': 'range/coupling feasibility and saved numerical fit; not anatomical/clinical accuracy or contact feasibility'}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
