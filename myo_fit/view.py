"""Display/render the fitted qpos with a cyan GEM-X skeleton overlay.

Playback uses saved frames, not unconstrained qpos interpolation: the latter
would generally violate the polynomial joint couplings between frames.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit', type=Path, default=Path(__file__).parent / 'results/fit.npz')
    parser.add_argument('--render', type=Path)
    args = parser.parse_args()
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        os.environ.setdefault('MUJOCO_GL', 'egl')
    import mujoco
    from .fit import load_model
    from .constraints import CoupledCoordinates
    from mujoco_demo.__main__ import Playback
    with np.load(args.fit, allow_pickle=False) as source:
        fit = {key: source[key].copy() for key in source.files}
    model = load_model(); data = mujoco.MjData(model); constraints = CoupledCoordinates(model)
    for qpos in fit['qpos']:
        constraints.check(qpos)
    points = fit['source_positions_m']; names = fit['source_names'].tolist()
    camera = mujoco.MjvCamera()
    camera.lookat[:] = (points.min(axis=(0, 1)) + points.max(axis=(0, 1))) / 2.
    camera.distance = max(2.5, np.ptp(points.reshape(-1, 3), axis=0).max() * 1.8)
    left = points[0, names.index('LeftLeg')] - points[0, names.index('RightLeg')]
    front = np.cross(left, [0., 0., 1.])
    camera.azimuth = float(np.rad2deg(np.arctan2(front[1], front[0]))) + 180.
    camera.elevation = -10.
    option = mujoco.MjvOption()
    option.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = False
    def set_frame(frame):
        data.qpos[:] = fit['qpos'][frame]
        data.qvel[:] = 0.
        mujoco.mj_forward(model, data)
        data.time = float(fit['times_s'][frame])
    def ghost(scene, frame):
        for child, parent in enumerate(fit['source_parents']):
            if parent < 0:
                continue
            if scene.ngeom >= scene.maxgeom:
                raise RuntimeError('MuJoCo scene has insufficient geometry capacity')
            geom = scene.geoms[scene.ngeom]
            mujoco.mjv_initGeom(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3), np.eye(3).ravel(), np.array([.1, .85, 1., .7]))
            mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, .004, points[frame, parent], points[frame, child])
            scene.ngeom += 1
    if args.render:
        args.render.parent.mkdir(parents=True, exist_ok=True)
        model.vis.global_.offwidth = 720
        model.vis.global_.offheight = 720
        with mujoco.Renderer(model, width=720, height=720) as renderer:
            cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '720x720', '-framerate', '30', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(args.render)]
            with subprocess.Popen(cmd, stdin=subprocess.PIPE) as process:
                for frame in range(len(fit['times_s'])):
                    set_frame(frame); renderer.update_scene(data, camera=camera, scene_option=option)
                    ghost(renderer.scene, frame)
                    process.stdin.write(renderer.render().tobytes())
                process.stdin.close()
                if process.wait():
                    raise RuntimeError('FFmpeg failed')
        print(args.render)
    else:
        if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
            raise RuntimeError('Interactive viewer requires a desktop display; use --render')
        import mujoco.viewer
        playback = Playback(fit['times_s']); lock = threading.Lock()
        def key_callback(key):
            with lock:
                playback.key(key)
        set_frame(0)
        print('SPACE pause/play; arrows frame-step; R restart; S speed; L loop. Cyan = GEM-X input. Saved frames preserve couplings.')
        with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
            with viewer.lock():
                viewer.cam.lookat[:] = camera.lookat; viewer.cam.distance = camera.distance
                viewer.cam.azimuth = camera.azimuth; viewer.cam.elevation = camera.elevation
                viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = False
            previous = time.monotonic()
            while viewer.is_running():
                now = time.monotonic()
                with lock:
                    playback.advance(now - previous)
                    frame = int(np.clip(np.searchsorted(fit['times_s'], playback.time, side='right') - 1, 0, len(fit['times_s']) - 1))
                previous = now
                with viewer.lock():
                    set_frame(frame); viewer.user_scn.ngeom = 0; ghost(viewer.user_scn, frame)
                viewer.sync(); time.sleep(1 / 120.)


if __name__ == '__main__':
    main()
