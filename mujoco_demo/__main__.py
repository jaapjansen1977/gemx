"""Prepare, validate, render or play the saved GEM-X skeleton in MuJoCo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import numpy as np

DEFAULT_MOTION = Path(__file__).parent / 'data' / 'motion.npz'


def load_motion(path):
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def validate(skeleton):
    from .skeleton import sample
    import mujoco
    motion = skeleton.motion
    position_error = rotation_error = bone_error = 0.
    for frame, timestamp in enumerate(motion['clip_times_s']):
        skeleton.apply(*sample(motion, timestamp))
        position_error = max(position_error, float(np.abs(skeleton.data.xpos[skeleton.joint_bodies] - motion['positions_m'][frame]).max()))
        rotation_error = max(rotation_error, float(np.abs(skeleton.data.xmat[skeleton.joint_bodies].reshape(-1, 3, 3) - motion['rotations'][frame]).max()))
        for child, parent, _, geom in skeleton.bones:
            half_axis = skeleton.data.geom_xmat[geom].reshape(3, 3)[:, 2] * skeleton.model.geom_size[geom, 1]
            midpoint = skeleton.data.geom_xpos[geom]
            for actual, expected in [(midpoint - half_axis, motion['positions_m'][frame, parent]), (midpoint + half_axis, motion['positions_m'][frame, child])]:
                bone_error = max(bone_error, float(np.abs(actual - expected).max()))
    assert max(position_error, rotation_error, bone_error) < 1e-5
    assert skeleton.model.nq == 0 and skeleton.model.nv == 0
    return {'status': 'passed', 'mujoco': mujoco.__version__, 'frames': len(motion['clip_times_s']),
            'joints': len(motion['names']), 'bones': len(skeleton.bones),
            'max_position_error_m': position_error, 'max_rotation_matrix_error': rotation_error,
            'max_bone_endpoint_error_m': bone_error, 'qpos_count': skeleton.model.nq,
            'scope': 'kinematic reproduction of GEM-X export, not physical or clinical accuracy'}


def render(skeleton, target, width, height):
    import mujoco
    from OpenGL.GL import glGetString, GL_RENDERER
    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Video export requires ffmpeg on PATH; interactive playback does not')
    target.parent.mkdir(parents=True, exist_ok=True)
    times = skeleton.motion['clip_times_s']
    fps = 1. / float(np.median(np.diff(times)))
    command = [executable, '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format', 'rgb24',
               '-video_size', f'{width}x{height}', '-framerate', str(fps), '-i', 'pipe:0',
               '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '20', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', str(target)]
    option = mujoco.MjvOption(); option.geomgroup[3] = 0
    camera = skeleton.camera()
    with mujoco.Renderer(skeleton.model, width=width, height=height) as renderer:
        renderer_name = glGetString(GL_RENDERER)
        with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
            from .skeleton import sample
            for timestamp in times:
                skeleton.apply(*sample(skeleton.motion, timestamp))
                renderer.update_scene(skeleton.data, camera=camera, scene_option=option)
                image = renderer.render()
                process.stdin.write(image.tobytes())
            process.stdin.close()
            if process.wait():
                raise RuntimeError('FFmpeg video export failed')
    return {'frames': len(times), 'fps': fps, 'renderer': renderer_name.decode() if renderer_name else 'unknown', 'output': str(target)}


class Playback:
    def __init__(self, times):
        self.times = times
        self.start = float(times[0]); self.end = float(times[-1] + np.median(np.diff(times)))
        self.time = self.start; self.paused = False; self.loop = True; self.speed = 1.

    def advance(self, delta):
        if not self.paused:
            self.time += delta * self.speed
            if self.time >= self.end:
                if self.loop:
                    self.time = self.start + (self.time - self.start) % (self.end - self.start)
                else:
                    self.time = float(self.times[-1]); self.paused = True

    def key(self, key):
        import glfw
        if key == glfw.KEY_SPACE:
            self.paused = not self.paused
        elif key == glfw.KEY_R:
            self.time = self.start
        elif key == glfw.KEY_L:
            self.loop = not self.loop
        elif key == glfw.KEY_S:
            speeds = [.25, .5, 1., 2.]
            self.speed = speeds[(speeds.index(self.speed) + 1) % len(speeds)]
        elif key in (glfw.KEY_LEFT, glfw.KEY_RIGHT):
            self.paused = True
            index = int(np.argmin(np.abs(self.times - self.time)))
            index += 1 if key == glfw.KEY_RIGHT else -1
            self.time = float(self.times[np.clip(index, 0, len(self.times) - 1)])


def play(skeleton):
    import mujoco.viewer
    from .skeleton import sample
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        raise RuntimeError('Interactive playback requires a desktop display. Use validate or render on a headless machine.')
    playback = Playback(skeleton.motion['clip_times_s']); lock = threading.Lock()
    def key_callback(key):
        with lock:
            playback.key(key)
            print(f't={playback.time:.3f}s  paused={playback.paused}  speed={playback.speed}x  loop={playback.loop}', flush=True)
    print('SPACE pause/play | LEFT/RIGHT frame | R restart | S speed | L loop | Close window to exit\nBlue = left; orange = right. Group 3 in the viewer toggles local segment axes.')
    with mujoco.viewer.launch_passive(skeleton.model, skeleton.data, key_callback=key_callback) as viewer:
        camera = skeleton.camera()
        viewer.cam.lookat[:] = camera.lookat
        viewer.cam.distance = camera.distance; viewer.cam.azimuth = camera.azimuth; viewer.cam.elevation = camera.elevation
        viewer.opt.geomgroup[3] = 0
        previous = time.monotonic()
        while viewer.is_running():
            now = time.monotonic()
            with lock:
                playback.advance(now - previous)
                positions, quats = sample(skeleton.motion, playback.time)
                timestamp = playback.time
            previous = now
            with viewer.lock():
                skeleton.apply(positions, quats)
                skeleton.data.time = timestamp
            viewer.sync()
            time.sleep(1 / 120.)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='Convert original kinematics.npz, preserving native segment-local axes')
    prepare.add_argument('--input', required=True, type=Path)
    prepare.add_argument('--output-dir', type=Path, default=DEFAULT_MOTION.parent)
    for name in ('play', 'validate', 'render'):
        command = sub.add_parser(name)
        command.add_argument('--motion', type=Path, default=DEFAULT_MOTION)
        if name == 'validate':
            command.add_argument('--output', type=Path)
        if name == 'render':
            command.add_argument('--output', type=Path, default=Path('outputs/mujoco-skeleton.mp4'))
            command.add_argument('--width', type=int, default=720)
            command.add_argument('--height', type=int, default=720)
    args = parser.parse_args()
    # CPU Mesa rendering on this headless Linux environment. No CUDA API used.
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        os.environ.setdefault('MUJOCO_GL', 'egl')
    from .skeleton import Skeleton, convert
    if args.command == 'prepare':
        motion = convert(args.input); args.output_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.output_dir / 'motion.npz', **motion)
        skeleton = Skeleton(motion, args.output_dir / 'skeleton.xml')
        summary = validate(skeleton)
        summary.update(source_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                       conversion='p_mj = C @ p_native + display_offset; R_mj = C @ R_native; SOMA-local axes unchanged',
                       C=motion['world_to_mujoco'].tolist(), display_offset_m=motion['display_offset_m'].tolist(),
                       units={'position': 'meters', 'time': 'seconds', 'quaternion': 'wxyz'},
                       meaning='Mocap bodies, no forces, no joints/qpos, no dynamics or IK retargeting. Constant display lift; raw export unchanged.')
        (args.output_dir / 'metadata.json').write_text(json.dumps(summary, indent=2))
    else:
        skeleton = Skeleton(load_motion(args.motion))
        if args.command == 'play':
            play(skeleton); return
        summary = validate(skeleton) if args.command == 'validate' else render(skeleton, args.output, args.width, args.height)
        if args.command == 'validate' and args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
