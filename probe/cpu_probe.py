"""Experimental CPU-only GEM-X Body Motion benchmark; no Pose fallback.

Run in the prepared Python environment. Official weights/assets are required.
Each invocation creates a new output directory and preserves raw predictions.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
import traceback

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_fk(result, assets, target):
    """Use SOMA's reference FK, including joint orientation and shape.

    Do not multiply network-local axis angles as if they were absolute rotations.
    SOMA transforms include the extra Root; the 77 joints exclude that Root.
    """
    import numpy as np
    import torch
    from gem.common.soma import SomaFixedGs1BodyAdapter, SomaRuntimeConfig

    body = SomaFixedGs1BodyAdapter(SomaRuntimeConfig(
        data_root=str(assets), device="cpu", apply_correctives=False,
        enable_procedural_transforms=True, procedural_reference="runtime",
    ))
    runtime = body.runtime
    all_names = [str(name) for name in runtime.public_joint_names]
    names = all_names[1:]
    if len(names) != 77:
        raise ValueError("Expected SOMA 0.3.3 public Root + 77 body joints")
    arrays = {"segment_names": np.array(names),
              "parent_ids_with_root": runtime.output_joint_parent_ids.cpu().numpy()}
    for space in ("incam", "global"):
        params = result[f"pred_soma_params_{space}"]
        length = params["global_orient"].shape[1]
        joints, rotations = [], []
        for frame in range(length):
            values = {}
            for key, value in params.items():
                if key not in ("global_orient", "body_pose", "transl", "identity_coeffs", "scale_params"):
                    continue
                values[key] = value[:, frame] if value.ndim >= 3 else value
            with torch.inference_mode():
                output = body(**values, return_joints_only=True, repose_to_bind_pose=True)
            transforms = output["transforms"][:, 1:]
            torch.testing.assert_close(transforms[..., :3, 3], output["joints"])
            rotation = transforms[..., :3, :3]
            if not torch.isfinite(rotation).all() or not torch.isfinite(output["joints"]).all():
                raise ValueError("Non-finite SOMA geometry")
            identity = torch.eye(3).expand_as(rotation)
            torch.testing.assert_close(rotation.mT @ rotation, identity, atol=1e-4, rtol=1e-4)
            torch.testing.assert_close(torch.linalg.det(rotation), torch.ones(rotation.shape[:-2]), atol=1e-4, rtol=1e-4)
            joints.append(output["joints"].cpu().numpy())
            rotations.append(rotation.cpu().numpy())
        arrays[f"joints_{space}_m"] = np.stack(joints, axis=1)
        arrays[f"segment_rotations_{space}"] = np.stack(rotations, axis=1)
    times = result["conditions"]["frame_times"].cpu().numpy()
    arrays["clip_times_s"] = times
    arrays["source_times_s"] = times + result["video"]["source"]["requested_start"]
    np.savez_compressed(target / "kinematics.npz", **arrays)
    (target / "kinematics.json").write_text(json.dumps({
        "status": "SOMA FK export validated with real assets and synthetic rigid transforms; video accuracy requires assessment",
        "segment_names": names, "transform_names_with_root": all_names,
        "units": {"position": "meters", "time": "seconds", "raw_axis_angle": "radians"},
        "rotation": "3x3 active local-segment-to-selected-space matrix; column vectors; p_space = R @ p_segment + joint_position",
        "array_shape": "batch, time, joint, xyz or matrix row, matrix column",
        "incam": "Right-handed OpenCV camera axes: X right, Y down, Z forward; meters",
        "global": "Right-handed GEM Y-up raw_world_rollout_meters; X/Z horizontal; gravity-view rollout with upstream pi rotation around Z; no absolute heading or origin calibration",
        "axes_validation": "SOMA neutral pose and active Rz/translation checked with real assets; upstream renderer confirms camera and Y-up conventions. Native axes retained. Not MuJoCo Z-up or calibrated MuJoCo qpos.",
        "parent_ids": "SOMA public parent IDs reference the Root-inclusive transform list; retained verbatim",
        "fk": "SOMA 0.3.3 MID, procedural runtime convention, no mesh correctives; raw parameters unchanged",
        "postprocess": "none; raw temporal Body Motion",
        "sampling": "normalized 30Hz, not original source frame IDs",
    }, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--soma-assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float, default=2)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--offline-check", action="store_true", help="Reject Python socket network attempts and disable ONNX telemetry; not OS-level isolation")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("WARP_CACHE_PATH", str(args.output.resolve() / ".warp-cache"))
    if hasattr(os, "sched_getaffinity") and args.threads > 0:
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:args.threads])
    report = {"status": "started", "platform": platform.platform(), "python": platform.python_version(),
              "device": "cpu", "pipeline": "motion-video native77", "postprocess": False,
              "threads": args.threads, "requested_duration_s": args.duration,
              "memory_method": "sampled sum RSS of Python and live child processes every 50ms; shared pages may be double-counted; short peaks may be missed",
              "stages": [], "models": []}
    report["cpu_affinity"] = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    report["cpu_description"] = platform.processor()
    if Path("/proc/cpuinfo").is_file():
        report["cpu_description"] = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "unknown")
    if args.offline_check:
        import sys
        report["offline_check"] = {"scope": "Python socket audit hook; ONNX telemetry disabled; local video and weights", "blocked_socket_attempts": 0}
        def deny_network(event, values):
            if event == "socket.connect":
                import socket
                if values[0].family in (socket.AF_INET, socket.AF_INET6):
                    report["offline_check"]["blocked_socket_attempts"] += 1
                    raise RuntimeError("Network disabled for offline inference check")
        sys.addaudithook(deny_network)
    stop = threading.Event()
    peak = [0]
    started = time.perf_counter()
    def sample():
        import psutil
        process = psutil.Process()
        while not stop.is_set():
            total = 0
            for item in [process, *process.children(recursive=True)]:
                try:
                    total += item.memory_info().rss
                except psutil.Error:
                    pass
            peak[0] = max(peak[0], total)
            stop.wait(0.05)
    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    try:
        import torch
        import gem
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        from gem.inference.body_video import load_body_video_config, run_body_video
        if args.threads < 1 or not 0 < args.duration <= 10:
            raise ValueError("Use positive threads and a short (0,10] second pilot")
        if torch.version.cuda is not None:
            raise RuntimeError("Install CPU-only PyTorch; this pilot rejects CUDA builds")
        torch.set_num_threads(args.threads)
        torch.manual_seed(0)
        report["packages"] = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
        upstream = Path(gem.__file__).resolve().parents[1]
        report["upstream_commit"] = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        report["upstream_changes"] = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True)
        config = load_body_video_config(args.config)
        config["detector"]["device"] = "cpu"
        config["pose"]["batch_size"] = 1
        config["observations"]["batch_size"] = 1
        required = [Path(config[s]["checkpoint"]) for s in ("pose", "observations", "detector", "motion")]
        if config["motion"].get("stats"):
            required.append(Path(config["motion"]["stats"]))
        required.extend(args.soma_assets / name for name in ("SOMA_neutral.npz", "SOMA_template_rig.usda", "SOMA_procedural_transforms.json"))
        missing = [str(path) for path in required if not path.is_file()]
        report["missing_files"] = missing
        if missing:
            raise FileNotFoundError("Official model/assets missing; see missing_files. No fallback executed.")
        report["models"] = [{"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in required]
        report["video_sha256"] = sha256(args.video)
        report["config_sha256"] = sha256(args.config)
        report["resolved_config"] = config
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required on PATH")
        def progress(message):
            report["stages"].append({"stage": message, "elapsed_s": time.perf_counter() - started})
            report["sampled_peak_process_tree_rss_bytes"] = peak[0]
            (args.output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(message, flush=True)
        infer_started = time.perf_counter()
        result = run_body_video(args.video.resolve(), config, device="cpu", start=args.start, duration=args.duration, progress=progress)
        report["inference_wall_s"] = time.perf_counter() - infer_started
        torch.save(result, args.output / "raw_motion.pt")
        report["raw_motion_sha256"] = sha256(args.output / "raw_motion.pt")
        progress("Exporting SOMA FK joints and segment rotations")
        export_fk(result, args.soma_assets, args.output)
        report["status"] = "completed_experimental_requires_windows_and_axes_validation"
        return 0
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        print(report["error"], flush=True)
        return 1
    finally:
        stop.set()
        monitor.join()
        report["total_wall_s"] = time.perf_counter() - started
        report["sampled_peak_process_tree_rss_bytes"] = peak[0]
        (args.output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
