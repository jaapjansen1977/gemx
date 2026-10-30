"""Saved Body Motion -> fixed proxy frames -> provisional shoulder angles."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.spatial.transform import Rotation
from .angles import unit,decompose,unwrap_runs,longest_run


def stats(values):
    finite=values[np.isfinite(values)]
    if not len(finite): return None
    return dict(min_deg=float(finite.min()),max_deg=float(finite.max()),excursion_deg=float(np.ptp(finite)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kinematics',type=Path,default=Path('reports/jaap-cpu-pilot-01/kinematics.npz'))
    parser.add_argument('--neutral',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--threshold-deg',type=float,default=10.)
    args=parser.parse_args()
    if not 0<args.threshold_deg<90: raise ValueError('Threshold must be between 0 and 90 degrees')
    args.output.mkdir(parents=True,exist_ok=False); started=time.perf_counter()
    data=np.load(args.kinematics,allow_pickle=False); neutral=np.load(args.neutral,allow_pickle=False)
    names=data['segment_names'].tolist(); neutral_names=neutral['names'].tolist()
    p={name:neutral['joints'][neutral_names.index(name)].astype(np.float64) for name in neutral_names}
    neutral_rotations=Rotation.from_matrix(neutral['rotations']).as_matrix()
    right=unit(p['RightLeg']-p['LeftLeg'])
    up=p['Chest']-p['Hips']; up=unit(up-right*np.dot(up,right))
    front=unit(np.cross(up,right)); right=unit(np.cross(front,up))
    eye_front=(p['LeftEye']+p['RightEye'])/2-p['Head']
    if np.dot(front,eye_front)<=0: raise ValueError('Anatomical anterior sign conflicts with eye/head geometry')
    thorax_ref=np.stack([front,up,right],axis=-1)
    chest=names.index('Chest'); chest_neutral=neutral_rotations[neutral_names.index('Chest')]
    thorax_offset=chest_neutral.T@thorax_ref
    # Projection to SO(3) removes only numerical non-orthogonality in saved FK.
    source=data['segment_rotations_incam'][0]
    source=Rotation.from_matrix(source.reshape(-1,3,3)).as_matrix().reshape(source.shape)
    thorax=source[:,chest]@thorax_offset
    times=data['clip_times_s'].reshape(-1); joints=data['joints_incam_m'][0]
    outputs={}; calibration={}; summaries={}
    for side,source_side in [('left','Left'),('right','Right')]:
        arm=names.index(source_side+'Arm'); elbow=names.index(source_side+'ForeArm')
        y=unit(p[source_side+'Arm']-p[source_side+'ForeArm'])
        x=unit(front-y*np.dot(front,y)); z=unit(np.cross(x,y)); x=unit(np.cross(y,z))
        anatomical_ref=np.stack([x,y,z],axis=-1)
        offset=neutral_rotations[neutral_names.index(source_side+'Arm')].T@anatomical_ref
        humerus=source[:,arm]@offset; relative=thorax.transpose(0,2,1)@humerus
        angle,valid,singular=decompose(relative,side,args.threshold_deg)
        plane=unwrap_runs(angle[:,0],valid); axial=unwrap_runs(angle[:,2],valid)
        true_long=unit(joints[:,arm]-joints[:,elbow])
        longitudinal_error=np.rad2deg(np.arccos(np.clip(np.sum(true_long*humerus[:,:,1],axis=1),-1,1)))
        safe=valid & (longitudinal_error<5.)
        # Recompute contiguous runs if the geometric consistency check excludes a frame.
        plane=unwrap_runs(angle[:,0],safe); axial=unwrap_runs(angle[:,2],safe)
        start,end=longest_run(safe)
        outputs[side]=dict(angles_deg=angle,plane_unwrapped_deg=plane,axial_unwrapped_deg=axial,valid=safe,singular=singular,humerus=humerus,relative=relative,axis_error_deg=longitudinal_error)
        calibration[side]=dict(source_joint=source_side+'Arm',constant_local_offset=offset.tolist(),neutral_anatomical_frame=anatomical_ref.tolist(),long_axis='GH proxy (Arm) minus elbow-center proxy (ForeArm)',transverse_axis='Thorax anterior projected perpendicular to neutral humerus long axis; assumed twist, NOT epicondylar calibration',max_dynamic_long_axis_discrepancy_deg=float(longitudinal_error.max()))
        summaries[side]=dict(elevation_all_frames=stats(angle[:,1]),valid_plane_axial_frames=int(safe.sum()),total_frames=len(times),longest_valid_interval_frames=[int(start),int(end)],longest_valid_interval_times_s=([float(times[start]),float(times[end-1])] if end>start else None),plane_longest_valid_interval=stats(plane[start:end]),axial_longest_valid_interval=stats(axial[start:end]),interpretation='Clip excursion under unvalidated proxy calibration; not clinical maximum ROM. Plane/axial statistics use one contiguous valid interval only.')
    arrays=dict(times_s=times,thorax_frames_incam=thorax,thorax_origins_incam_m=joints[:,chest],source_joint_positions_incam_m=joints,source_names=np.array(names),intrinsics=None)
    arrays.pop('intrinsics')
    for side,row in outputs.items():
        for key,value in row.items(): arrays[side+'_'+key]=value
    np.savez_compressed(args.output/'shoulder.npz',**arrays)
    with (args.output/'angles.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['frame','clip_time_s','side','elevation_deg','plane_wrapped_deg','axial_wrapped_deg','plane_continuous_valid_deg','axial_continuous_valid_deg','plane_axial_valid','mathematical_singularity','long_axis_discrepancy_deg','calibration_status'])
        def number(value): return float(value) if np.isfinite(value) else ''
        for frame,t in enumerate(times):
            for side,row in outputs.items():
                plane,elevation,axial=row['angles_deg'][frame]
                writer.writerow([frame,float(t),side,number(elevation),number(plane),number(axial),number(row['plane_unwrapped_deg'][frame]),number(row['axial_unwrapped_deg'][frame]),bool(row['valid'][frame]),bool(row['singular'][frame]),float(row['axis_error_deg'][frame]),'unvalidated_anatomical_proxy'])
    report=dict(status='provisional_computed_anatomical_calibration_incomplete',frames=len(times),wall_s=time.perf_counter()-started,reference='Wu et al. (2005), ISB recommendation Part II, J Biomech 38:981-992, doi:10.1016/j.jbiomech.2004.05.042',interpretation='ISB-style intrinsic YXY decomposition with explicit proxy axes; NOT validated ISB anatomical calibration',axes='Right-handed columns X anterior, Y superior, Z right',sequence='R_template=Ry(plane) Rx(-elevation) Ry(axial); intrinsic YXY, negative middle branch',sides='Right template; left reflected with S R_left S, S=diag(1,1,-1). Bilateral standardized signs, not an unlabelled native left Euler sequence.',signs='Plane 0=coronal abduction, +90=forward flexion; elevation positive arm raising; axial positive internal rotation in the right-template/left-mirrored construction',threshold_deg=args.threshold_deg,threshold_note='Conditioning threshold chosen for inspection, NOT a statistical confidence bound',thorax=dict(method='Neutral Hips->Chest superior, hip-center right direction orthogonalized; anterior cross product checked against eye/head direction. Missing IJ/C7/PX/T8.',constant_chest_local_offset=thorax_offset.tolist()),humerus=calibration,summary=summaries,limitations=['No verified IJ/C7/PX/T8 thorax landmarks','No verified medial/lateral epicondyles or functional GH center','Humerus axial zero is assumed from neutral model anterior, not measured','No glenohumeral or scapular kinematics','No frame-zero angle subtraction; no smoothing or forced motion fit','Plane and axial unstable near arm down/up, separated from elevation','Proxy calibration and video accuracy unvalidated; axes consistency is not anatomy accuracy'],input_sha256={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.kinematics,args.neutral)})
    (args.output/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(summaries,indent=2))


if __name__=='__main__': main()
