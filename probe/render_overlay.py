"""Reproduce the pilot overlay from saved temporal Motion/FK output.

The drawing/projection logic is the same as the executed pilot postprocessing;
input/output paths are CLI arguments instead of the original cloud paths.
"""
import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
import torch
from gem.inference.video import VideoFrames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--normalized-video", required=True, type=Path)
    args = parser.parse_args()
    out = args.results
    data = np.load(out / "kinematics.npz", allow_pickle=False)
    # Only load our own trusted pilot result: PyTorch pickle can execute code.
    raw = torch.load(out / "raw_motion.pt", map_location="cpu", weights_only=False)
    assert raw["format"] == "gem_body_video_predictions_v1"
    assert raw["conditions"]["condition_spec"]["observation_joint_set"] == "soma77_native_v1"
    joints = data["joints_incam_m"][0]
    count = len(joints)
    for key in ("joints_global_m", "joints_incam_m", "segment_rotations_global", "segment_rotations_incam"):
        assert np.isfinite(data[key]).all(), key
    intrinsics = raw["conditions"]["K_fullimg"][0].numpy()
    parents = data["parent_ids_with_root"][1:] - 1
    command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "bgr24",
               "-video_size", "540x960", "-framerate", "30", "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "jaap-motion-overlay.mp4")]
    with VideoFrames(args.normalized_video) as frames:
        if (frames.width, frames.height) != (1080, 1920) or len(frames) != count:
            raise ValueError("This pilot overlay expects its aligned 1080x1920 normalized clip")
        with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
            for index in range(count):
                frame = cv2.resize(cv2.cvtColor(frames[index], cv2.COLOR_RGB2BGR), (540, 960))
                projected = joints[index] @ intrinsics[index].T
                uv = projected[:, :2] / projected[:, 2:3] * .5
                valid = (joints[index, :, 2] > .05) & np.isfinite(uv).all(1) & (np.abs(uv) < 10000).all(1)
                for child, parent in enumerate(parents):
                    if parent >= 0 and valid[child] and valid[parent]:
                        cv2.line(frame, tuple(np.rint(uv[parent]).astype(int)), tuple(np.rint(uv[child]).astype(int)), (0, 255, 255), 2, cv2.LINE_AA)
                for joint in range(77):
                    if valid[joint]:
                        cv2.circle(frame, tuple(np.rint(uv[joint]).astype(int)), 3, (0, 180, 0), -1, cv2.LINE_AA)
                label = f"GEM-X temporal Body Motion  t={index / 30:.2f}s"
                cv2.putText(frame, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .48, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1, cv2.LINE_AA)
                if index == 30:
                    cv2.imwrite(str(out / "overlay-frame.jpg"), frame)
                process.stdin.write(frame.tobytes())
            process.stdin.close()
            assert process.wait() == 0
    print(json.dumps({"status": "completed", "frames": count, "output": str(out / "jaap-motion-overlay.mp4")}))


if __name__ == "__main__":
    main()
