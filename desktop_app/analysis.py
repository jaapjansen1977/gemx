"""Neutral-reference shoulder review with explicit YXY conditioning."""
import csv
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from shoulder.angles import decompose, unwrap_runs


def analyze(shoulder_path, output, neutral_seconds=.5):
    with np.load(shoulder_path,allow_pickle=False) as source:
        data={name:source[name].copy() for name in source.files}
    times=data['times_s']; initial=times<=times[0]+neutral_seconds
    if len(times)<2 or not np.isfinite(times).all() or not np.all(np.diff(times)>0):raise ValueError('Expected increasing frame times')
    if not np.isfinite(neutral_seconds) or not 0<neutral_seconds<times[-1]-times[0]:raise ValueError('Neutral interval must be positive and shorter than the motion')
    report=dict(status='experimental_reference_calibration_not_validated_ISB',
        calibration='Mean orientation in selected initial interval assumed anatomical neutral; no gravity measurement.',
        neutral_seconds=neutral_seconds,reference_frames=int(initial.sum()),
        axial_method='Swing-twist about calibrated humerus Y; auxiliary measure, not ISB YXY axial rotation.',
        limitations=['Initial neutral pose assumed, not independently measured.','No verified anatomical landmarks or gravity.','Swing-twist differs from ISB YXY axial angles.','No scapular/glenohumeral separation.'],sides={})
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    arrays=dict(times_s=times); rows=[]
    for side in ('left','right'):
        relative=data[side+'_relative']
        if relative.shape!=(len(times),3,3) or not np.isfinite(relative).all():raise ValueError('Invalid segment rotations')
        reference=Rotation.from_matrix(relative[initial]).mean().as_matrix()
        # Constant local-frame correction; retain torso-relative segment motion.
        calibrated=relative@reference.T
        values,valid,singular=decompose(calibrated,side,20.)
        q=Rotation.from_matrix(calibrated).as_quat() # xyzw
        # Unique twist except for 180-degree swing with zero projected quaternion.
        magnitude=np.hypot(q[:,1],q[:,3]); twist_valid=magnitude>1e-7
        twist=2*np.arctan2(q[:,1],q[:,3]);twist=(twist+np.pi)%(2*np.pi)-np.pi
        twist=np.rad2deg(twist)*(1 if side=='right' else -1)
        twist=unwrap_runs(twist,twist_valid)
        arrays[side+'_angles_deg']=values;arrays[side+'_valid']=valid
        arrays[side+'_twist_deg']=twist; arrays[side+'_relative']=calibrated
        report['sides'][side]=dict(reference_rotation=reference.tolist(),
            raw_frame0_elevation_deg=float(data[side+'_angles_deg'][0,1]),
            calibrated_frame0_elevation_deg=float(values[0,1]),yxy_valid_frames=int(valid.sum()))
        for i,t in enumerate(times):
            number=lambda x:float(x) if np.isfinite(x) else ''
            rows.append([i,float(t),side,*[number(v) for v in values[i]],bool(valid[i]),number(twist[i]),bool(twist_valid[i])])
    np.savez_compressed(output/'shoulder-review.npz',**arrays)
    with (output/'angles.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['frame','time_s','side','yxy_plane_deg','elevation_deg','yxy_axial_deg','yxy_plane_axial_valid','auxiliary_swing_twist_deg','twist_valid']);writer.writerows(rows)
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
    for side in ('left','right'):
        axes[0].plot(times,arrays[side+'_angles_deg'][:,1],label=side)
        axes[1].plot(times,np.where(arrays[side+'_valid'],arrays[side+'_angles_deg'][:,2],np.nan),label=side)
        axes[2].plot(times,arrays[side+'_twist_deg'],label=side)
    for ax,title in zip(axes,['Arm elevation — assumed neutral reference','ISB-style YXY axial — gaps near singularity','Auxiliary swing-twist — a different definition']):
        ax.set(title=title,ylabel='degrees');ax.legend();ax.grid(alpha=.2)
    axes[-1].set_xlabel('Time (s)');fig.suptitle('Experimental shoulder review — anatomical accuracy unvalidated')
    fig.tight_layout();fig.savefig(output/'angles.png',dpi=140);plt.close(fig)
    return report
