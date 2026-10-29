"""Coordinate conversion and mocap skeleton, without GEM-X model inference."""
from pathlib import Path
from xml.sax.saxutils import quoteattr

import mujoco
import numpy as np

# Right-handed change of WORLD basis only. SOMA segment-local axes stay intact.
# Native (x,y,z) -> MuJoCo (x,-z,y). Thus R_mj = C @ R_native, not C R C.T.
WORLD_TO_MUJOCO = np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])


def convert(native_path):
    with np.load(native_path, allow_pickle=False) as source:
        names = source['segment_names'].copy()
        native = source['joints_global_m']
        rotations = source['segment_rotations_global']
        if native.ndim != 4 or native.shape[0] != 1 or native.shape[2:] != (len(names), 3):
            raise ValueError('Expected one subject: joints_global_m [1,T,J,3]')
        times = source['clip_times_s'][0].copy()
        source_times = source['source_times_s'][0].copy()
        raw_parents = source['parent_ids_with_root'].copy()
        if len(raw_parents) != len(names) + 1:
            raise ValueError('Expected Root-inclusive parent IDs')
        # Source transform list: [Root,Hips,...]; exported joints omit Root.
        parents = raw_parents[1:].astype(np.int64) - 1
        positions = native[0].astype(np.float64) @ WORLD_TO_MUJOCO.T
        matrices = WORLD_TO_MUJOCO @ rotations[0].astype(np.float64)
    if len(times) < 2 or positions.shape[0] != len(times) or not np.all(np.diff(times) > 0):
        raise ValueError('At least two frames with increasing timestamps required')
    if matrices.shape != (*positions.shape[:2], 3, 3):
        raise ValueError('Rotation dimensions differ from joint dimensions')
    if not np.isfinite(positions).all() or not np.isfinite(matrices).all():
        raise ValueError('Non-finite motion')
    if not np.isfinite(times).all() or not np.isfinite(source_times).all():
        raise ValueError('Non-finite timestamps')
    if any(parent >= child or parent < -1 for child, parent in enumerate(parents)):
        raise ValueError('Invalid parent mapping; expected parent before child')
    if len(set(names.tolist())) != len(names):
        raise ValueError('Duplicate joint names')
    if not np.allclose(matrices.swapaxes(-1, -2) @ matrices, np.eye(3), atol=1e-4):
        raise ValueError('Non-orthogonal rotations')
    if not np.allclose(np.linalg.det(matrices), 1., atol=1e-4):
        raise ValueError('Improper rotation matrices')
    # One constant DISPLAY translation for the whole clip. No per-frame foot fix.
    offset = np.array([0., 0., .025 - positions[..., 2].min()])
    positions += offset
    quaternions = np.empty((*positions.shape[:2], 4))
    for frame in range(len(times)):
        for joint in range(len(names)):
            mujoco.mju_mat2Quat(quaternions[frame, joint], matrices[frame, joint].reshape(9))
    return dict(names=names, parents=parents, positions_m=positions,
                rotations=matrices, quaternions_wxyz=quaternions,
                clip_times_s=times, source_times_s=source_times,
                world_to_mujoco=WORLD_TO_MUJOCO, display_offset_m=offset)


def slerp(first, second, alpha):
    second = np.where((first * second).sum(-1, keepdims=True) < 0., -second, second)
    dot = np.clip((first * second).sum(-1, keepdims=True), -1., 1.)
    angle = np.arccos(dot)
    denominator = np.maximum(np.sin(angle), 1e-12)
    spherical = (np.sin((1. - alpha) * angle) * first + np.sin(alpha * angle) * second) / denominator
    linear = (1. - alpha) * first + alpha * second
    value = np.where(dot > .9995, linear, spherical)
    return value / np.linalg.norm(value, axis=-1, keepdims=True)


def sample(motion, timestamp):
    times = motion['clip_times_s']
    timestamp = np.clip(timestamp, times[0], times[-1])
    left = int(np.clip(np.searchsorted(times, timestamp, side='right') - 1, 0, len(times) - 2))
    fraction = (timestamp - times[left]) / (times[left + 1] - times[left])
    positions = (1. - fraction) * motion['positions_m'][left] + fraction * motion['positions_m'][left + 1]
    quats = slerp(motion['quaternions_wxyz'][left], motion['quaternions_wxyz'][left + 1], fraction)
    return positions, quats


def bone_quat(vector):
    length = np.linalg.norm(vector)
    if length < 1e-10:
        return np.array([1., 0., 0., 0.]), 0.
    direction = vector / length
    if direction[2] < 0. and np.linalg.norm(direction[:2]) < 1e-12:
        return np.array([0., 1., 0., 0.]), length
    quat = np.array([1. + direction[2], -direction[1], direction[0], 0.])
    return quat / np.linalg.norm(quat), length


def make_xml(motion):
    rows = ['<mujoco model="GEM-X kinematic skeleton">',
            '<compiler angle="radian"/>', '<option gravity="0 0 0"/>',
            '<visual><global offwidth="960" offheight="960"/><quality shadowsize="2048"/><headlight ambient=".4 .4 .4" diffuse=".8 .8 .8" specular=".1 .1 .1"/></visual>',
            '<default><geom contype="0" conaffinity="0"/></default>',
            '<asset><texture type="skybox" builtin="gradient" width="512" height="3072" rgb1=".12 .17 .23" rgb2=".3 .35 .4"/><texture name="grid" type="2d" builtin="checker" width="512" height="512" rgb1=".22 .25 .29" rgb2=".29 .32 .36"/><material name="floor" texture="grid" texrepeat="8 8"/></asset>',
            '<worldbody><light pos="0 -2 4" dir="0 0 -1" diffuse=".9 .9 .9"/>',
            '<geom name="floor" type="plane" size="5 5 .1" material="floor"/>']
    for joint, name in enumerate(motion['names']):
        pos = ' '.join(map(str, motion['positions_m'][0, joint]))
        quat = ' '.join(map(str, motion['quaternions_wxyz'][0, joint]))
        color = '.15 .65 1 1' if str(name).startswith('Left') else ('1 .45 .2 1' if str(name).startswith('Right') else '.9 .9 .85 1')
        finger = any(word in str(name) for word in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'))
        radius = .003 if finger else .01
        rows.append(f'<body name={quoteattr("joint_" + str(name))} mocap="true" pos="{pos}" quat="{quat}"><geom type="sphere" size="{.005 if finger else .017}" rgba="{color}"/>')
        for axis, rgba in [(' .045 0 0', '1 0 0 1'), ('0 .045 0', '0 1 0 1'), ('0 0 .045', '0 0 1 1')]:
            rows.append(f'<geom type="capsule" fromto="0 0 0 {axis}" size=".002" rgba="{rgba}" group="3"/>')
        rows.append('</body>')
        parent = motion['parents'][joint]
        if parent >= 0:
            vector = motion['positions_m'][0, joint] - motion['positions_m'][0, parent]
            rotation, length = bone_quat(vector)
            midpoint = (motion['positions_m'][0, joint] + motion['positions_m'][0, parent]) / 2.
            pos = ' '.join(map(str, midpoint)); quat = ' '.join(map(str, rotation))
            rows.append(f'<body name="bone_{joint}" mocap="true" pos="{pos}" quat="{quat}"><geom name="bone_geom_{joint}" type="capsule" size="{radius} {max(length / 2., 1e-8)}" rgba="{color}"/></body>')
    rows.append('</worldbody></mujoco>')
    return '\n'.join(rows)


class Skeleton:
    def __init__(self, motion, xml_path=None):
        self.motion = motion
        xml = make_xml(motion)
        if xml_path is not None:
            Path(xml_path).write_text(xml)
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.joint_bodies = np.array([self.model.body('joint_' + str(n)).id for n in motion['names']])
        self.joint_mocap = self.model.body_mocapid[self.joint_bodies]
        self.bones = [(int(child), int(parent), self.model.body(f'bone_{child}').mocapid[0], self.model.geom(f'bone_geom_{child}').id)
                      for child, parent in enumerate(motion['parents']) if parent >= 0]
        self.apply(*sample(motion, motion['clip_times_s'][0]))

    def apply(self, positions, quaternions):
        self.data.mocap_pos[self.joint_mocap] = positions
        self.data.mocap_quat[self.joint_mocap] = quaternions
        for child, parent, mocap, geom in self.bones:
            quat, length = bone_quat(positions[child] - positions[parent])
            self.data.mocap_pos[mocap] = (positions[child] + positions[parent]) / 2.
            self.data.mocap_quat[mocap] = quat
            self.model.geom_size[geom, 1] = max(length / 2., 1e-8)
            self.model.geom_rbound[geom] = self.model.geom_size[geom, 0] + length / 2.
        mujoco.mj_forward(self.model, self.data)

    def camera(self):
        positions = self.motion['positions_m']
        lower = positions.min(axis=(0, 1)); upper = positions.max(axis=(0, 1))
        camera = mujoco.MjvCamera()
        camera.lookat[:] = (lower + upper) / 2.
        camera.distance = max(2., (upper - lower).max() * 1.65)
        names = self.motion['names'].tolist()
        if 'LeftShoulder' in names and 'RightShoulder' in names:
            left = positions[0, names.index('LeftShoulder')] - positions[0, names.index('RightShoulder')]
            left[2] = 0.
            front = np.cross(left, [0., 0., 1.])
            camera.azimuth = float(np.degrees(np.arctan2(front[1], front[0])))
        else:
            camera.azimuth = 90.
        camera.elevation = -12.
        return camera
