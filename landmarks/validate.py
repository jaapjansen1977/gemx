"""Independent attachment checks and CSV export; no anatomical accuracy claim."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from .geometry import evaluate


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('directory',type=Path); args=p.parse_args()
    a=np.load(args.directory/'surface.npz',allow_pickle=False)
    bary=a['barycentric']; faces=a['faces']; ids=a['face_ids']; points=a['landmarks_incam_m']
    assert np.isfinite(bary).all() and (bary>=0).all()
    np.testing.assert_allclose(bary.sum(1),1.,atol=1e-10)
    assert ids.min()>=0 and ids.max()<len(faces)
    assert len(set(a['names'].tolist()))==len(ids)
    for k in a.files: assert a[k].dtype.kind=='U' or np.isfinite(a[k]).all(),k
    times=a['times_s']; assert (np.diff(times)>0).all()
    predicted=evaluate(a['vertices_incam_m'],faces,ids,bary)
    error=float(np.abs(predicted-points).max()); assert error<1e-9
    assert (points[:,:,2]>.05).all()
    demo=np.load(Path(__file__).resolve().parents[1]/'mujoco_demo/data/motion.npz',allow_pickle=False)
    expected=a['landmarks_global_m']@demo['world_to_mujoco'].T+demo['display_offset_m']
    np.testing.assert_allclose(expected,a['landmarks_mujoco_m'],atol=1e-9)
    np.testing.assert_array_equal(times,demo['clip_times_s'])
    anchors=np.load(args.directory/'model-anchors.npz',allow_pickle=False)
    np.testing.assert_array_equal(anchors['names'],a['names'])
    np.testing.assert_array_equal(anchors['times_s'],times)
    np.testing.assert_allclose(anchors['source_positions_m'],a['landmarks_mujoco_m'])
    with (args.directory/'landmarks.csv').open('w',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['frame','clip_time_s','landmark','space','x_m','y_m','z_m','status'])
        for frame,t in enumerate(times):
            for space,key in [('camera','landmarks_incam_m'),('gem_world_y_up','landmarks_global_m'),('mujoco_z_up_display_lift','landmarks_mujoco_m')]:
                for name,point in zip(a['names'],a[key][frame]): writer.writerow([frame,float(t),name,space,*point.tolist(),'unreviewed_heuristic'])
    report=dict(status='technical_checks_passed_anatomy_unvalidated',frames=len(times),landmarks=len(ids),max_attachment_reconstruction_error_m=error,barycentric_valid=True,finite_arrays=True,world_to_mujoco_basis_and_lift_verified=True,time_alignment_verified=True,model_anchor_names_and_times_verified=True,landmark_fit_enabled=False)
    (args.directory/'validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))


if __name__=='__main__': main()
