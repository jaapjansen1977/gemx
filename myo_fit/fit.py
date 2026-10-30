"""Relative-rotation proof of principle on the pinned, unmodified MyoFullBody."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .constraints import CoupledCoordinates

MODEL_COMMIT = '93b0ca8f4ec90c9899ee7f05fee561e9911da91b'
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / 'mujoco_demo/data/motion.npz'


def load_model():
    import myo_sim
    from myo_sim.build.compose import build_spec
    root = Path(myo_sim.__file__).resolve().parents[1]
    # Pin source, not the moving package label 0.2.3. No reset or remote mutation.
    if (root / '.git').exists():
        commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        changes = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], text=True)
        if changes.strip():
            raise ValueError('Tracked MyoSim source differs from pinned version')
    else:
        direct = importlib.metadata.distribution('myo-sim').read_text('direct_url.json')
        provenance = json.loads(direct or '{}')
        commit = provenance.get('vcs_info', {}).get('commit_id')
        if provenance.get('url', '').removesuffix('.git') != 'https://github.com/MyoHub/myo_sim':
            raise ValueError('Install MyoSim from the pinned official Git URL in requirements.txt')
    if commit != MODEL_COMMIT:
        raise ValueError(f'Expected MyoSim commit {MODEL_COMMIT}, got {commit}')
    return build_spec('myofullbody').compile()


class RotationFit:
    def __init__(self, model, motion, mapping):
        self.model = model; self.data = mujoco.MjData(model)
        self.motion = motion; self.mapping = mapping
        self.coupled = CoupledCoordinates(model)
        roots = [j for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE]
        if len(roots) != 1 or model.jnt_qposadr[roots[0]] != 0:
            raise ValueError('Expected one root freejoint at qpos[0:7]')
        names = motion['names'].tolist()
        self.source_ids = np.array([names.index(row['source']) for row in mapping['segments']])
        self.body_ids = np.array([model.body(row['body']).id for row in mapping['segments']])
        self.weights = np.array([row['weight'] for row in mapping['segments']])
        self.hips = names.index('Hips'); self.pelvis = model.body('pelvis').id
        reference = self.coupled.reference.copy()
        self.data.qpos[:] = reference; mujoco.mj_kinematics(model, self.data)
        # Initial yaw alignment from left/right hip joint centers; preserve gravity.
        gem_left = motion['positions_m'][0, names.index('LeftLeg')] - motion['positions_m'][0, names.index('RightLeg')]
        model_left = self.data.xpos[model.body('femur_l').id] - self.data.xpos[model.body('femur_r').id]
        if min(np.linalg.norm(gem_left[:2]), np.linalg.norm(model_left[:2])) < 1e-6:
            raise ValueError('Degenerate pelvis yaw reference')
        yaw = np.arctan2(gem_left[1], gem_left[0]) - np.arctan2(model_left[1], model_left[0])
        self.root_reference = Rotation.from_rotvec([0., 0., yaw]) * Rotation.from_quat(reference[3:7][[1, 2, 3, 0]])
        reference[3:7] = self.root_reference.as_quat()[[3, 0, 1, 2]]
        self.data.qpos[:] = reference; mujoco.mj_kinematics(model, self.data)
        self.pelvis_local = self.root_reference.as_matrix().T @ (self.data.xpos[self.pelvis] - reference[:3])
        reference[:3] = motion['positions_m'][0, self.hips] - self.root_reference.as_matrix() @ self.pelvis_local
        self.reference = reference
        self.data.qpos[:] = reference; mujoco.mj_kinematics(model, self.data)
        source = motion['rotations'][:, self.source_ids]
        source = Rotation.from_matrix(source.reshape(-1, 3, 3)).as_matrix().reshape(source.shape)
        model_reference = self.data.xmat[self.body_ids].reshape(-1, 3, 3).copy()
        self.offsets = source[0].transpose(0, 2, 1) @ model_reference
        self.targets = source @ self.offsets
        major = {'flex_extension', 'lat_bending', 'axial_rotation'}
        for side in ('r', 'l'):
            major.update(base + '_' + side for base in ('elv_angle', 'shoulder_elv', 'shoulder_rot', 'elbow_flexion', 'pro_sup', 'deviation', 'flexion', 'hip_flexion', 'hip_adduction', 'hip_rotation', 'knee_angle', 'ankle_angle', 'subtalar_angle', 'mtp_angle'))
        self.selected = np.array([i for i, j in enumerate(self.coupled.independent) if model.joint(j).name in major])
        selected_names = {model.joint(self.coupled.independent[i]).name for i in self.selected}
        if selected_names != major:
            raise ValueError(f'Missing selected coordinates: {major - selected_names}')
        self.selected_names = [model.joint(self.coupled.independent[i]).name for i in self.selected]
        self.initial = np.r_[np.zeros(3), self.coupled.reference_independent[self.selected]]
        self.lower = np.r_[np.full(3, -np.pi), self.coupled.bounds[self.selected, 0]]
        self.upper = np.r_[np.full(3, np.pi), self.coupled.bounds[self.selected, 1]]

    def pose(self, parameters, frame):
        independent = self.coupled.reference_independent.copy()
        independent[self.selected] = parameters[3:]
        qpos = self.coupled.apply(independent, self.reference.copy())
        root = Rotation.from_rotvec(parameters[:3]) * self.root_reference
        qpos[3:7] = root.as_quat()[[3, 0, 1, 2]]
        qpos[:3] = self.motion['positions_m'][frame, self.hips] - root.as_matrix() @ self.pelvis_local
        self.data.qpos[:] = qpos
        mujoco.mj_kinematics(self.model, self.data)
        return qpos

    def angles(self, frame):
        current = self.data.xmat[self.body_ids].reshape(-1, 3, 3)
        return Rotation.from_matrix(self.targets[frame].transpose(0, 2, 1) @ current).as_rotvec()

    def residual(self, parameters, frame, previous):
        self.pose(parameters, frame)
        orientation = self.angles(frame) * np.sqrt(self.weights[:, None])
        # Weak priors, explicitly separate from the hard bounds/equalities.
        return np.r_[orientation.ravel(), .03 * (parameters - previous), .002 * (parameters - self.initial)]


def run(input_path, output_dir, max_frames=None, max_nfev=60):
    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=False)
    with np.load(input_path, allow_pickle=False) as source:
        motion = {key: source[key].copy() for key in source.files}
    mapping_path = Path(__file__).with_name('mapping.json')
    mapping = json.loads(mapping_path.read_text())
    model = load_model(); fitter = RotationFit(model, motion, mapping)
    count = len(motion['clip_times_s']) if max_frames is None else min(max_frames, len(motion['clip_times_s']))
    parameters = fitter.initial.copy(); qposes = []; fitted = []; errors = []; baseline = []; frames = []
    for frame in range(count):
        fitter.pose(fitter.initial, frame)
        baseline.append(np.linalg.norm(fitter.angles(frame), axis=-1))
        result = least_squares(fitter.residual, parameters, args=(frame, parameters.copy()),
                               bounds=(fitter.lower, fitter.upper), max_nfev=max_nfev,
                               ftol=1e-7, xtol=1e-7, gtol=1e-7, method='trf')
        parameters = result.x
        qpos = fitter.pose(parameters, frame)
        constraint = fitter.coupled.check(qpos)
        mujoco.mj_forward(model, fitter.data)
        mask = fitter.data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
        equality = float(np.max(np.abs(fitter.data.efc_pos[mask]))) if np.any(mask) else 0.
        if equality > 1e-8:
            raise ValueError(f'MuJoCo equality error {equality}')
        error = np.linalg.norm(fitter.angles(frame), axis=-1)
        frames.append({'frame': frame, 'time_s': float(motion['clip_times_s'][frame]),
                       'optimizer_success': bool(result.success), 'status': int(result.status),
                       'message': result.message, 'nfev': result.nfev, 'cost': float(result.cost),
                       'mean_orientation_error_deg': float(np.rad2deg(error).mean()),
                       'max_mujoco_equality_residual': equality, **constraint})
        qposes.append(qpos.copy()); fitted.append(fitter.data.xpos.copy()); errors.append(error)
        print(f'frame {frame + 1}/{count}: mean rotation error {np.rad2deg(error).mean():.2f} deg, feasible, nfev={result.nfev}, success={result.success}', flush=True)
    error = np.array(errors); baseline = np.array(baseline)
    evaluation = slice(1, None) if count > 1 else slice(None)
    report = {'status': 'completed' if all(f['optimizer_success'] for f in frames) else 'completed_with_optimizer_nonconvergence',
              'frames': frames, 'wall_s': time.perf_counter() - started,
              'model_commit': MODEL_COMMIT, 'mujoco': mujoco.__version__,
              'packages': {name: importlib.metadata.version(name) for name in ('myo-sim', 'mujoco', 'numpy', 'scipy')},
              'nq': model.nq, 'nv': model.nv, 'njnt': model.njnt, 'nu': model.nu,
              'active_joint_couplings': len(fitter.coupled.dependencies),
              'optimized_scalar_coordinates': fitter.selected_names,
              'root_translation': 'Prescribed to exported Hips position; not optimized',
              'rotation_reference': 'Frame 0 bootstraps constant segment-local offsets against a feasible stock-model pose; initial yaw aligned using hips. Not anatomical calibration.',
              'mapping': mapping, 'propagated_bound_intervals': fitter.coupled.intervals,
              'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
              'mapping_sha256': hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
              'metrics_exclude_reference_frame': count > 1,
              'mean_orientation_error_deg': float(np.rad2deg(error[evaluation]).mean()),
              'static_reference_mean_error_deg': float(np.rad2deg(baseline[evaluation]).mean()),
              'per_segment_mean_deg': {row['source']: float(np.rad2deg(error[evaluation, i]).mean()) for i, row in enumerate(mapping['segments'])},
              'max_range_violation': max(f['max_range_violation'] for f in frames),
              'max_joint_coupling_error': max(f['max_joint_coupling_error'] for f in frames),
              'max_mujoco_equality_residual': max(f['max_mujoco_equality_residual'] for f in frames),
              'limitations': ['Relative reference-frame alignment, not subject/anatomical calibration', 'Fixed stock body lengths', 'No ISB landmark fit', 'Finger coordinates frozen; no independent neck/head fit', 'No muscle control, dynamics, collision/contact feasibility guarantee', 'No ground-truth accuracy validation; Windows not tested']}
    np.savez_compressed(output_dir / 'fit.npz', qpos=np.array(qposes), times_s=motion['clip_times_s'][:count],
                        body_positions_m=np.array(fitted), body_names=np.array([model.body(i).name for i in range(model.nbody)]),
                        source_positions_m=motion['positions_m'][:count], source_names=motion['names'], source_parents=motion['parents'],
                        mapped_body_ids=fitter.body_ids, mapped_source_ids=fitter.source_ids,
                        target_rotations=fitter.targets[:count], offsets=fitter.offsets,
                        orientation_errors_rad=error, reference_qpos=fitter.reference)
    (output_dir / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: report[key] for key in ('status', 'wall_s', 'mean_orientation_error_deg', 'static_reference_mean_error_deg', 'max_range_violation', 'max_mujoco_equality_residual')}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--max-nfev', type=int, default=60)
    args = parser.parse_args()
    run(args.input, args.output, args.max_frames, args.max_nfev)


if __name__ == '__main__':
    main()
