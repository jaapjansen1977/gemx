"""Reconstruct saved temporal SOMA meshes and make editable candidate attachments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
from .geometry import attach, evaluate, seeds


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--attachments',type=Path,help='Reuse reviewed MID triangle/barycentric attachments instead of generating seeds')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    os.environ.setdefault('WARP_CACHE_PATH',str(args.output.resolve()/'warp-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    import torch
    from gem.common.soma import SomaFixedGs1BodyAdapter,SomaRuntimeConfig
    started=time.perf_counter(); torch.set_num_threads(2)
    # Only open the trusted output of our own pilot; torch pickle is executable.
    raw_path=args.results/'raw_motion.pt'
    raw=torch.load(raw_path,map_location='cpu',weights_only=False)
    body=SomaFixedGs1BodyAdapter(SomaRuntimeConfig(data_root=str(args.assets),lod='mid',device='cpu',apply_correctives=False,enable_procedural_transforms=True,procedural_reference='runtime'))
    allowed=('global_orient','body_pose','transl','identity_coeffs','scale_params')
    parameters=raw['pred_soma_params_incam']; count=parameters['body_pose'].shape[1]
    def values(params,frame):
        return {k:(v[:,frame] if v.ndim>=3 else v) for k,v in params.items() if k in allowed}
    neutral=values(parameters,0)
    neutral={k:(torch.zeros_like(v) if k in ('global_orient','body_pose','transl') else v) for k,v in neutral.items()}
    with torch.inference_mode(): reference=body(**neutral,return_joints_only=False,repose_to_bind_pose=True)
    vertices_ref=reference['vertices'][0].numpy(); faces=body.runtime.faces.cpu().numpy().astype(np.int32)
    names=list(body.runtime.public_joint_names)[1:]
    joint_ref={k:v.copy() for k,v in zip(names,reference['joints'][0].numpy())}
    records=seeds(joint_ref)
    for index,row in enumerate(records):
        face,bary,distance=attach(np.array(row['seed_m']),vertices_ref,faces)
        row.update(id=index+1,face_id=face,barycentric=bary.tolist(),seed_to_surface_m=distance,status='unreviewed_heuristic',fit_weight=0.,review_note='No anatomical validation; anterior sign and placement require inspection')
    if args.attachments:
        reviewed=json.loads(args.attachments.read_text())
        if reviewed['lod']!='mid' or [r['name'] for r in reviewed['landmarks']] != [r['name'] for r in records]:
            raise ValueError('Expected matching MID landmark names/order')
        records=reviewed['landmarks']
    face_ids=np.array([r['face_id'] for r in records]); bary=np.array([r['barycentric'] for r in records])
    if (face_ids<0).any() or (face_ids>=len(faces)).any() or bary.shape!=(len(records),3) or not np.isfinite(bary).all() or (bary<0).any() or not np.allclose(bary.sum(1),1.,atol=1e-8):
        raise ValueError('Invalid mesh attachment')
    vertices=[]; joint_error=[]; same_lod_error=[]
    fk=np.load(args.results/'kinematics.npz')
    for frame in range(count):
        with torch.inference_mode():
            out=body(**values(parameters,frame),return_joints_only=False,repose_to_bind_pose=True)
            fk_same=body(**values(parameters,frame),return_joints_only=True,repose_to_bind_pose=True)
        vertices.append(out['vertices'][0].numpy().copy())
        joint_error.append(float(np.max(np.abs(out['joints'][0].numpy()-fk['joints_incam_m'][0,frame]))))
        same_lod_error.append(float(torch.max(torch.abs(out['joints']-fk_same['joints']))))
    vertices=np.array(vertices); points=evaluate(vertices,faces,face_ids,bary)
    if not np.isfinite(vertices).all() or max(same_lod_error)>1e-6: raise ValueError('Mesh/FK consistency failed at same LOD')
    if len(set(face_ids.tolist())) != len(records): raise ValueError('Candidate landmarks collapsed onto the same face; review seeds')
    with torch.inference_mode():
        params_global=raw['pred_soma_params_global']; world=[]
        for frame in range(count):
            out=body(**values(params_global,frame),return_joints_only=False,repose_to_bind_pose=True)
            world.append(evaluate(out['vertices'][0].numpy(),faces,face_ids,bary))
    world=np.array(world); basis=np.array([[1,0,0],[0,0,-1],[0,1,0.]])
    demo=np.load(Path(__file__).resolve().parents[1]/'mujoco_demo/data/motion.npz')
    world_mj=world@basis.T+demo['display_offset_m']
    np.savez_compressed(args.output/'surface.npz',vertices_incam_m=vertices,faces=faces,reference_vertices_m=vertices_ref,landmarks_incam_m=points,landmarks_global_m=world,landmarks_mujoco_m=world_mj,face_ids=face_ids,barycentric=bary,names=np.array([r['name'] for r in records]),times_s=fk['clip_times_s'].reshape(-1),intrinsics=raw['conditions']['K_fullimg'][0].numpy())
    document=dict(status='candidate_placement_requires_review',lod='mid',correctives=False,units='meters, seconds',camera_axes='right-handed X right Y down Z forward',mujoco_axes='right-handed Z up; same basis and constant display lift as mujoco_demo',method='Heuristic neutral-pose seeds projected to closest mesh triangle; fixed topology and barycentric attachment over the entire clip. Shape parameters remain the saved Motion prediction per frame.',landmarks=records)
    (args.output/'attachments.json').write_text(json.dumps(document,indent=2))
    import resource
    report=dict(frames=count,vertices=len(vertices_ref),triangles=len(faces),landmarks=len(records),wall_s=time.perf_counter()-started,peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,max_mid_mesh_vs_mid_fk_difference_m=max(same_lod_error),max_mid_vs_previous_xlo_joint_difference_m=max(joint_error),raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),soma_revision='d281db2d01553f7230c56e764cec00fe27ef23f7',gem_commit='20555befe2fbbe5b2015e1fff7ff214dc18ea9d6',source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},limitations=['Unreviewed anatomical candidates, not ISB validated','No fit objective enabled; weights zero','No person-specific landmark calibration','No photometric or silhouette optimization; mesh comes from saved temporal Body Motion','CPU Linux only; no new video inference or network downloads'])
    (args.output/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))


if __name__=='__main__': main()
