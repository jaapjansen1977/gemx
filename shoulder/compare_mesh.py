"""Compare saved humerothoracic angles with unreviewed mesh calibration.

No new inference or anatomical accuracy claim. The thorax stays identical.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .angles import decompose, unit, longest_run, unwrap_runs


def mesh_frame(shoulder, medial, lateral, side, min_transverse_deg=20.):
    """Y: elbow midpoint -> GH proxy; Z: projected epicondylar rightward axis.

    GH is a saved joint proxy, not acromion. Reject axes within 20 degrees
    of the long axis; this is a numerical inspection rule, not ISB validation.
    """
    if side not in ('left', 'right'):
        raise ValueError(side)
    y = unit(shoulder - (medial + lateral) / 2)
    transverse = lateral - medial if side == 'right' else medial - lateral
    separation = np.linalg.norm(transverse, axis=-1)
    direction = transverse / np.maximum(separation[..., None], 1e-15)
    projected = direction - y * np.sum(direction * y, axis=-1, keepdims=True)
    ratio = np.linalg.norm(projected, axis=-1)
    axis_angle = np.rad2deg(np.arcsin(np.clip(ratio, 0, 1)))
    valid = (separation > 1e-6) & (axis_angle >= min_transverse_deg)
    # Keep a diagnostic frame where defined; never invent a fallback axis.
    z = projected / np.where(ratio > 1e-10, ratio, np.nan)[..., None]
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=-1), valid, axis_angle, separation


def wrapped_difference(a, b):
    return (a - b + 180.) % 360. - 180.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=Path('shoulder/results/shoulder.npz'))
    parser.add_argument('--calibration', type=Path, default=Path('shoulder/results/report.json'))
    parser.add_argument('--neutral', type=Path, default=Path('shoulder/results/neutral.npz'))
    parser.add_argument('--surface', type=Path, default=Path('landmarks/results/surface.npz'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threshold-deg', type=float, default=20.)
    args = parser.parse_args()
    if not 0 < args.threshold_deg < 90:
        parser.error('threshold must be between 0 and 90 degrees')
    base = np.load(args.baseline, allow_pickle=False)
    neutral = np.load(args.neutral, allow_pickle=False)
    surface = np.load(args.surface, allow_pickle=False)
    calibration = json.loads(args.calibration.read_text())
    times = base['times_s']
    if times.shape != surface['times_s'].shape or not np.allclose(times, surface['times_s'], atol=1e-8, rtol=0):
        raise ValueError('Baseline and mesh timestamps do not match')
    snames = surface['names'].tolist()
    jnames = base['source_names'].tolist()
    nnames = neutral['names'].tolist()
    reference_points = np.einsum('lvc,lv->lc', surface['reference_vertices_m'][surface['faces'][surface['face_ids']]], surface['barycentric'])
    output = dict(times_s=times)
    report = dict(status='diagnostic_only_unreviewed_mesh_landmarks',
        interpretation='Differences between model-derived definitions, NOT accuracy improvement or clinical ROM.',
        methods=['baseline_saved_segment_frames', 'mesh_neutral_calibration_with_saved_segment_motion', 'mesh_frame_by_frame'],
        thorax='Identical saved proxy thorax for all methods; IJ/C7/PX/T8 unavailable.',
        humerus='Saved Arm joint GH proxy to epicondyle midpoint; rightward epicondylar axis projected perpendicular to long axis. Acromion is not substituted for GH.',
        sequence='Existing bilateral YXY convention: Ry(plane) Rx(-elevation) Ry(axial); left mirrored.',
        threshold_deg=args.threshold_deg,
        quality_rule='Epicondylar line must be at least 20 degrees from long axis; geometry screen only. No anatomical validation.',
        limitations=['All mesh landmarks unreviewed; anatomical placement must be checked.', 'Shared GEM-X source, no independent ground truth.', 'Saved joint positions use XLO and mesh uses MID; existing report documents up to ~1.02 mm difference.', 'No glenohumeral/scapular kinematics.', 'No frame-zero subtraction, smoothing, or fit.'], sides={})
    rows = []
    for side, prefix, suffix in [('left', 'Left', 'l'), ('right', 'Right', 'r')]:
        medial = snames.index('elbow_epicondyle_medial_' + suffix)
        lateral = snames.index('elbow_epicondyle_lateral_' + suffix)
        arm = jnames.index(prefix + 'Arm')
        ref, ref_ok, ref_angle, ref_sep = mesh_frame(neutral['joints'][nnames.index(prefix + 'Arm')], reference_points[medial], reference_points[lateral], side)
        baseline_ref = np.array(calibration['humerus'][side]['neutral_anatomical_frame'])
        fixed = base[side + '_humerus'] @ (baseline_ref.T @ ref)
        points = surface['landmarks_incam_m']
        dynamic, dynamic_ok, axis_angle, separation = mesh_frame(base['source_joint_positions_incam_m'][:, arm], points[:, medial], points[:, lateral], side)
        _, baseline_ok, _ = decompose(base[side + '_relative'], side, args.threshold_deg)
        baseline_ok &= base[side + '_valid']
        side_report = dict(neutral_epicondylar_axis_to_long_axis_deg=float(ref_angle), neutral_marker_separation_mm=float(ref_sep * 1000), neutral_geometry_accepted=bool(ref_ok), dynamic_geometry_accepted_frames=int(dynamic_ok.sum()), total_frames=len(times), dynamic_axis_angle_range_deg=[float(axis_angle.min()), float(axis_angle.max())], comparisons={})
        for method, frames, geometry_ok in [('mesh_fixed', fixed, np.full(len(times), ref_ok)), ('mesh_dynamic', dynamic, dynamic_ok)]:
            relative = base['thorax_frames_incam'].transpose(0, 2, 1) @ frames
            angles, conditioned, singular = decompose(relative, side, args.threshold_deg)
            finite = np.isfinite(angles).all(axis=1)
            valid = baseline_ok & conditioned & geometry_ok & finite
            difference = wrapped_difference(angles, base[side + '_angles_deg'])
            # Elevation itself is not circular.
            difference[:, 1] = angles[:, 1] - base[side + '_angles_deg'][:, 1]
            output[side + '_' + method + '_angles_deg'] = angles
            output[side + '_' + method + '_comparison_valid'] = valid
            output[side + '_' + method + '_delta_deg'] = difference
            side_report['comparisons'][method] = dict(common_accepted_frames=int(valid.sum()), mean_absolute_difference_deg=(np.mean(np.abs(difference[valid]), axis=0).tolist() if valid.any() else None), angle_order=['plane', 'elevation', 'axial'], note='No accepted comparison means no interpretable ROM comparison from these candidates.')
            for i, t in enumerate(times):
                rows.append([i, float(t), side, method, *angles[i], *difference[i], bool(geometry_ok[i]), bool(conditioned[i]), bool(valid[i]), float(axis_angle[i]) if method == 'mesh_dynamic' else float(ref_angle)])
        output[side + '_dynamic_axis_angle_deg'] = axis_angle
        common = output[side + '_mesh_fixed_comparison_valid'] & output[side + '_mesh_dynamic_comparison_valid']
        start, end = longest_run(common)
        excursions = {}
        for method in ('baseline', 'mesh_fixed', 'mesh_dynamic'):
            angles = base[side + '_angles_deg'] if method == 'baseline' else output[side + '_' + method + '_angles_deg']
            continuous = angles.copy()
            for col in (0, 2):
                continuous[:, col] = unwrap_runs(angles[:, col], common)
            excursions[method] = np.ptp(continuous[start:end], axis=0).tolist() if end > start else None
        side_report['shared_contiguous_interval'] = dict(
            frames_start_end_exclusive=[int(start), int(end)],
            times_s=[float(times[start]), float(times[end - 1])] if end > start else None,
            excursions_deg=excursions, angle_order=['plane', 'elevation', 'axial'],
            interpretation='Same contiguous interval for all three methods; numerical geometry screens only. Not anatomically validated ROM.')
        elbow = jnames.index(prefix + 'ForeArm')
        downward_arm = unit(base['source_joint_positions_incam_m'][:, elbow] - base['source_joint_positions_incam_m'][:, arm])
        local_downward_arm = np.einsum('tji,tj->ti', base['thorax_frames_incam'], downward_arm)
        geometric_elevation = np.rad2deg(np.arccos(np.clip(-local_downward_arm[:, 1], -1, 1)))
        initial = (times - times[0]) <= .5
        side_report['starting_posture_audit'] = dict(
            baseline_frame0_elevation_deg=float(base[side + '_angles_deg'][0, 1]),
            direct_joint_line_frame0_elevation_deg=float(geometric_elevation[0]),
            frame0_downward_arm_unit_vector_in_thorax_xyz=local_downward_arm[0].tolist(),
            first_half_second_baseline_elevation_mean_deg=float(base[side + '_angles_deg'][initial, 1].mean()),
            first_half_second_baseline_elevation_std_deg=float(base[side + '_angles_deg'][initial, 1].std()),
            max_direct_joint_line_vs_baseline_elevation_difference_deg=float(np.max(np.abs(geometric_elevation - base[side + '_angles_deg'][:, 1]))),
            interpretation='Nonzero elevation exists in predicted shoulder-elbow geometry relative to the proxy thorax, not just Euler decomposition. Stationarity does not impose anatomical zero; no first-frame subtraction was applied. This does not establish the true anatomical angle.')
        report['sides'][side] = side_report
    report['code_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.baseline, args.calibration, args.neutral, args.surface]}
    args.output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(args.output / 'comparison.npz', **output)
    with (args.output / 'comparison.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'time_s', 'side', 'method', 'plane_deg', 'elevation_deg', 'axial_deg', 'delta_plane_deg', 'delta_elevation_deg', 'delta_axial_deg', 'geometry_accepted', 'yxy_conditioned', 'comparison_accepted', 'epicondylar_axis_to_long_axis_deg'])
        writer.writerows(rows)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    plot(base, output, args.output)
    print(json.dumps(report['sides'], indent=2))


def plot(base, data, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharex=True)
    for row, side in enumerate(('left', 'right')):
        for col, label in enumerate(('Elevation plane', 'Elevation', 'Axial rotation')):
            ax = axes[row, col]
            ax.plot(data['times_s'], base[side + '_angles_deg'][:, col], color='black', label='Existing segment frames')
            for method, color in [('mesh_fixed', 'tab:blue'), ('mesh_dynamic', 'tab:orange')]:
                values = data[side + '_' + method + '_angles_deg'][:, col]
                # Break branch cuts rather than drawing a false 360-degree jump.
                values = values.copy()
                if col != 1:
                    values[1:][np.abs(np.diff(values)) > 180] = np.nan
                ax.plot(data['times_s'], values, '--', color=color, label=method + ' (diagnostic)')
                accepted = data[side + '_' + method + '_comparison_valid']
                ax.scatter(data['times_s'][accepted], values[accepted], color=color, s=8)
            ax.set_title(side.title() + ': ' + label)
            ax.set_ylabel('Degrees'); ax.grid(alpha=.2)
            if row == 1: ax.set_xlabel('Clip time (s)')
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Shared thorax; unreviewed mesh candidates. Dashed curves are diagnostic, dots pass geometry + YXY screens.\nDifferences do not establish anatomical accuracy or ISB validation.', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .92))
    fig.savefig(directory / 'comparison.png', dpi=160)
    fig.savefig(directory / 'comparison.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
