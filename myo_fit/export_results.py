"""Export actual fitted MuJoCo qpos, with replayed model geometry and provenance."""
import csv
import hashlib
import json
from pathlib import Path
import mujoco
import numpy as np
from .fit import load_model, MODEL_COMMIT
from .constraints import CoupledCoordinates


def coordinate_group(name):
    for key,group in [('shoulder','Schouder'),('elv_angle','Schouder'),('elbow','Elleboog'),('pro_sup','Onderarm'),('hip_','Heup'),('knee','Knie'),('ankle','Enkel / voet'),('subtalar','Enkel / voet'),('mtp_','Enkel / voet')]:
        if key in name:return group
    if name in ('flex_extension','lat_bending','axial_rotation'):return 'Romp'
    if name.startswith(('deviation_','flexion_')):return 'Pols'
    return 'Overige modelcoördinaten'


def export(fit_path, output, fit_report=None):
    fit_path=Path(fit_path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with np.load(fit_path,allow_pickle=False) as source:
        fit={k:source[k].copy() for k in source.files}
    model=load_model();data=mujoco.MjData(model);coupled=CoupledCoordinates(model)
    qpos=fit['qpos'];times=fit['times_s']
    if qpos.shape!=(len(times),model.nq) or not np.isfinite(qpos).all() or len(times)<2 or not np.all(np.diff(times)>0):
        raise ValueError('Invalid saved MuJoCo fit')
    provenance=json.loads(Path(fit_report).read_text()) if fit_report else {}
    if not np.allclose(np.linalg.norm(qpos[:,3:7],axis=1),1.,atol=1e-10,rtol=0):raise ValueError('Invalid root quaternion')
    if fit['body_names'].tolist()!=[model.body(i).name for i in range(model.nbody)]:raise ValueError('Model body identity mismatch')
    if provenance.get('model_commit',MODEL_COMMIT)!=MODEL_COMMIT:raise ValueError('Model commit mismatch')
    selected=set(provenance.get('optimized_scalar_coordinates',[]))
    if not selected:raise ValueError('Fit report with optimized coordinate inventory required')
    coordinates=[];values=[]
    for joint in coupled.scalar:
        name=model.joint(joint).name;address=int(model.jnt_qposadr[joint]);hinge=model.jnt_type[joint]==mujoco.mjtJoint.mjJNT_HINGE
        role='coupled' if joint in coupled.dependencies else ('optimized' if name in selected else 'fixed_reference')
        coordinates.append(dict(name=name,qpos_address=address,unit='deg' if hinge else 'm',role=role,group=coordinate_group(name),
            limited=bool(model.jnt_limited[joint]),model_range=(np.rad2deg(model.jnt_range[joint]) if hinge else model.jnt_range[joint]).tolist()))
        values.append(np.rad2deg(qpos[:,address]) if hinge else qpos[:,address].copy())
    values=np.stack(values,axis=1)
    positions=[];rotations=[];equality=position_error=0.;ranges=couplings=0.
    for frame,pose in enumerate(qpos):
        check=coupled.check(pose);ranges=max(ranges,check['max_range_violation']);couplings=max(couplings,check['max_joint_coupling_error'])
        data.qpos[:]=pose;mujoco.mj_forward(model,data)
        mask=data.efc_type==mujoco.mjtConstraint.mjCNSTR_EQUALITY
        equality=max(equality,float(np.max(np.abs(data.efc_pos[mask]))) if np.any(mask) else 0.)
        positions.append(data.xpos.copy());rotations.append(data.xmat.reshape(-1,3,3).copy())
        position_error=max(position_error,float(np.max(np.abs(data.xpos-fit['body_positions_m'][frame]))))
    if max(ranges,couplings,equality,position_error)>1e-8:raise ValueError('Saved qpos does not reproduce the fitted model')
    np.savez_compressed(output/'model-coordinates.npz',times_s=times,qpos=qpos,values=values,
        coordinate_names=np.array([c['name'] for c in coordinates]),units=np.array([c['unit'] for c in coordinates]),
        body_positions_m=np.array(positions),body_rotations=np.array(rotations),body_names=fit['body_names'],body_parents=model.body_parentid,
        reference_qpos=fit['reference_qpos'])
    with (output/'angles.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['frame','time_s',*[c['name']+' ['+c['unit']+']' for c in coordinates]])
        for frame,t in enumerate(times):writer.writerow([frame,float(t),*values[frame].tolist()])
    with (output/'qpos.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['frame','time_s',*[f'qpos_{i}' for i in range(model.nq)]])
        for frame,t in enumerate(times):writer.writerow([frame,float(t),*qpos[frame].tolist()])
    validation=dict(status='passed',source='mujoco_myofullbody_fit',frames=len(times),joints=model.njnt,scalar_coordinates=len(coordinates),
        max_saved_body_position_error_m=position_error,max_range_violation=ranges,max_coupling_error=couplings,max_mujoco_equality_residual=equality)
    report=dict(source='mujoco_myofullbody_fit',model_commit=MODEL_COMMIT,mujoco=mujoco.__version__,nq=model.nq,
        fit_status=provenance.get('status'),optimizer_success_all=all(f.get('optimizer_success',False) for f in provenance.get('frames',[])),
        mean_orientation_error_deg=provenance.get('mean_orientation_error_deg'),fit_sha256=hashlib.sha256(fit_path.read_bytes()).hexdigest(),frames=len(times),coordinates=coordinates,
        zero_correction_applied=False,rotation_reference=provenance.get('rotation_reference'),
        coordinate_definition='Absolute model qpos; hinge coordinates converted radians to degrees. Free root translation/quaternion retained in qpos.csv and NPZ, not treated as joint angles.',
        limitations=['Model coordinates, not independently ISB-calibrated anatomical angles.','Initial model reference imposed by the existing fit.','Fixed-reference coordinates are not independently tracked motion.','Knee feasible intervals remain approximately 1.09 to 42.07 degrees.','No muscle dynamics or optimized foot contact.'],validation=validation)
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    plot(times,values,coordinates,output/'angles.png')
    return report


def plot(times,values,coordinates,target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=[c['name'] for c in coordinates]
    fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
    for ax,key,title in zip(axes,['shoulder_elv','shoulder_rot','elbow_flexion'],['Shoulder elevation','Shoulder rotation','Elbow flexion']):
        for suffix,side in [('l','left'),('r','right')]:
            name=key+'_'+suffix
            if name in names:ax.plot(times,values[:,names.index(name)],label=side)
        ax.set(title=title+' — model coordinate',ylabel='degrees');ax.legend();ax.grid(alpha=.2)
    axes[-1].set_xlabel('Time (s)');fig.suptitle('MyoFullBody fitted qpos — no extra zero correction; not validated ISB')
    fig.tight_layout();fig.savefig(target,dpi=140);plt.close(fig)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit',type=Path,required=True)
    parser.add_argument('--fit-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.fit,args.output,args.fit_report)['validation'],indent=2))


if __name__=='__main__':main()
