"""Independent numerical reconstruction and calibration-consistency checks."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from .angles import unit


def main():
    p=argparse.ArgumentParser(); p.add_argument('directory',type=Path); args=p.parse_args()
    a=np.load(args.directory/'shoulder.npz',allow_pickle=False)
    report=json.loads((args.directory/'report.json').read_text()); checks={}
    assert (np.diff(a['times_s'])>0).all()
    for side in ('left','right'):
        angles=a[side+'_angles_deg']; nonsingular=~a[side+'_singular']
        assert np.isfinite(angles[nonsingular]).all()
        euler=angles[nonsingular].copy(); euler[:,1]*=-1
        rebuilt=Rotation.from_euler('YXY',euler,degrees=True).as_matrix()
        if side=='left':
            mirror=np.diag([1.,1.,-1.]); rebuilt=mirror@rebuilt@mirror
        error=float(np.abs(rebuilt-a[side+'_relative'][nonsingular]).max())
        assert error<1e-6
        frames=a[side+'_humerus']; determinant=float(np.max(np.abs(np.linalg.det(frames)-1)))
        orthogonality=float(np.max(np.abs(frames.transpose(0,2,1)@frames-np.eye(3))))
        assert determinant<1e-6 and orthogonality<1e-6
        names=a['source_names'].tolist(); prefix=side.capitalize()
        joints=a['source_joint_positions_incam_m']
        long=unit(joints[:,names.index(prefix+'Arm')]-joints[:,names.index(prefix+'ForeArm')])
        geometric=np.rad2deg(np.arccos(np.clip(np.sum(long*a['thorax_frames_incam'][:,:,1],axis=1),-1,1)))
        geometric_error=float(np.max(np.abs(geometric-angles[:,1])))
        assert geometric_error<.1
        valid=a[side+'_valid']; threshold=report['threshold_deg']
        assert ((angles[valid,1]>threshold)&(angles[valid,1]<180-threshold)).all()
        assert np.isnan(a[side+'_plane_unwrapped_deg'][~valid]).all()
        assert np.isnan(a[side+'_axial_unwrapped_deg'][~valid]).all()
        checks[side]=dict(max_matrix_reconstruction_error=error,max_humerus_determinant_error=determinant,max_humerus_orthogonality_error=orthogonality,max_elevation_vs_joint_line_difference_deg=geometric_error,threshold_sensitivity_valid_frames={str(t):int(((angles[:,1]>t)&(angles[:,1]<180-t)&(a[side+'_axis_error_deg']<5)).sum()) for t in (10,20,30)})
    result=dict(status='numerical_checks_passed_anatomical_calibration_unvalidated',checks=checks,reference_offset_removed=False,clinical_accuracy_validated=False)
    (args.directory/'validation.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))


if __name__=='__main__': main()
