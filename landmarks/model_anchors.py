"""Provisional bone-fixed counterparts, seeded independently on the stock model.

These offsets are NOT projected to a skin mesh and require anatomical review.
They are exported with zero fit weight so they cannot silently bias the solver.
"""
import argparse
import json
from pathlib import Path
import mujoco
import numpy as np
from myo_fit.fit import load_model
from myo_fit.constraints import CoupledCoordinates
from .geometry import seeds


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surface',type=Path,required=True)
    parser.add_argument('--fit',type=Path,default=Path('myo_fit/results/fit.npz'))
    args=parser.parse_args()
    model=load_model(); data=mujoco.MjData(model); coordinates=CoupledCoordinates(model)
    data.qpos[:]=coordinates.reference; mujoco.mj_forward(model,data)
    positions={name:data.xpos[model.body(body).id].copy() for name,body in [('Hips','pelvis'),('Chest','torso')]}
    for side,suffix in [('Left','l'),('Right','r')]:
        for source,body in [('Leg','femur'),('Arm','humerus'),('ForeArm','ulna'),('Shin','tibia'),('Foot','talus')]:
            positions[side+source]=data.xpos[model.body(body+'_'+suffix).id].copy()
    records=seeds(positions)
    source=json.loads((args.surface/'attachments.json').read_text())['landmarks']
    if [r['name'] for r in source]!=[r['name'] for r in records]: raise ValueError('Landmark order mismatch')
    local=[]; ids=[]
    for row in records:
        body=model.body(row['body']).id; rotation=data.xmat[body].reshape(3,3)
        offset=rotation.T@(np.array(row['seed_m'])-data.xpos[body])
        row.update(local_position_m=offset.tolist(),status='unreviewed_bone_fixed_heuristic',fit_weight=0.)
        local.append(offset); ids.append(body)
    local=np.array(local); ids=np.array(ids); fit=np.load(args.fit,allow_pickle=False)
    world=[]
    for qpos in fit['qpos']:
        coordinates.check(qpos); data.qpos[:]=qpos; mujoco.mj_forward(model,data)
        world.append(np.einsum('lij,lj->li',data.xmat[ids].reshape(-1,3,3),local)+data.xpos[ids])
    surface=np.load(args.surface/'surface.npz',allow_pickle=False)
    if not np.array_equal(fit['times_s'],surface['times_s']): raise ValueError('Fit/source timestamps mismatch')
    world=np.array(world); error=np.linalg.norm(world-surface['landmarks_mujoco_m'],axis=-1)
    np.savez_compressed(args.surface/'model-anchors.npz',names=surface['names'],body_ids=ids,local_positions_m=local,model_positions_m=world,source_positions_m=surface['landmarks_mujoco_m'],times_s=fit['times_s'],distance_m=error)
    report=dict(status='unreviewed_not_used_in_fit',method='Independent neutral-pose heuristic seeds converted to fixed bone-local coordinates; no skin projection, no subject calibration, not ISB verified',landmarks=records,mean_candidate_distance_m=float(error.mean()),max_candidate_distance_m=float(error.max()),interpretation='Candidate correspondence diagnostic only, NOT anatomical accuracy',model_commit='93b0ca8f4ec90c9899ee7f05fee561e9911da91b')
    (args.surface/'model-anchors.json').write_text(json.dumps(report,indent=2)); print(json.dumps({k:v for k,v in report.items() if k!='landmarks'},indent=2))


if __name__=='__main__': main()
