"""Reproduce neutral model geometry for the explicit proxy calibration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path,required=True); p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    os.environ.setdefault('WARP_CACHE_PATH',str(args.output.resolve().parent/'warp-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    import torch
    from gem.common.soma import SomaFixedGs1BodyAdapter,SomaRuntimeConfig
    torch.set_num_threads(2)
    # Trusted local pilot output only; pickle can execute code.
    raw=torch.load(args.raw,weights_only=False,map_location='cpu')
    params={k:v[:,0].clone() for k,v in raw['pred_soma_params_incam'].items() if k in ('body_pose','global_orient','transl','identity_coeffs','scale_params')}
    for k in ('body_pose','global_orient','transl'): params[k].zero_()
    body=SomaFixedGs1BodyAdapter(SomaRuntimeConfig(data_root=str(args.assets),lod='mid',device='cpu',apply_correctives=False,enable_procedural_transforms=True,procedural_reference='runtime'))
    with torch.inference_mode(): out=body(**params,return_joints_only=True,repose_to_bind_pose=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output,names=np.array(list(body.runtime.public_joint_names)[1:]),joints=out['joints'][0].numpy(),rotations=out['transforms'][0,1:,:3,:3].numpy())
    record=dict(status='model_neutral_proxy_not_anatomical_calibration',shape='Saved frame-0 identity and scales, zero pose/global orientation/translation. NOT a subject neutral-pose observation.',soma_lod='mid',soma_version='0.3.3',raw_sha256=hashlib.sha256(args.raw.read_bytes()).hexdigest(),asset_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in args.assets.iterdir() if f.name in ('SOMA_neutral.npz','SOMA_template_rig.usda','SOMA_procedural_transforms.json')})
    args.output.with_suffix('.json').write_text(json.dumps(record,indent=2))


if __name__=='__main__': main()
