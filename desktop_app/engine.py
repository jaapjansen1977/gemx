"""External Python worker: existing pinned GEM-X environment, local models only."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import sys


def module(name,args):
    sys.argv=[name,*map(str,args)]
    runpy.run_module(name,run_name='__main__')


def main():
    p=argparse.ArgumentParser();p.add_argument('request',type=Path);a=p.parse_args()
    req=json.loads(a.request.read_text(encoding='utf-8')); output=Path(req['output'])
    try:
        if req.get('ffmpeg_bin'):os.environ['PATH']=req['ffmpeg_bin']+os.pathsep+os.environ.get('PATH','')
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',WARP_CACHE_PATH=str(output/'warp-cache'))
        if not all(shutil.which(x) for x in ('ffmpeg','ffprobe')):
            raise RuntimeError('De videomotor vraagt ffmpeg en ffprobe op PATH.')
        import torch
        import onnxruntime
        from gem.inference.body_video import load_body_video_config,run_body_video
        from probe.cpu_probe import export_fk
        from myo_fit.fit import run as fit_model, load_model
        from myo_fit.export_results import export
        load_model()  # Fail before costly inference if the exact model is unavailable.
        torch.set_num_threads(req.get('threads',2));onnxruntime.disable_telemetry_events()
        config=load_body_video_config(req['config'])
        config['detector']['device']='cpu';config['pose']['batch_size']=1;config['observations']['batch_size']=1
        for section in ('pose','observations','detector','motion'):
            path=Path(config[section]['checkpoint'])
            if not path.is_file():raise FileNotFoundError(f'Ontbrekend modelbestand: {path}')
        print('Video analyseren met temporele GEM-X Body Motion',flush=True)
        result=run_body_video(Path(req['video']),config,device='cpu',start=req['start'],duration=req['duration'],progress=lambda x:print(x,flush=True))
        raw=output/'raw';raw.mkdir();torch.save(result,raw/'raw_motion.pt');export_fk(result,Path(req['assets']),raw)
        module('mujoco_demo',['prepare','--input',raw/'kinematics.npz','--output-dir',output/'motion'])
        print('MyoFullBody-model fitten aan segmentrotaties',flush=True)
        fit_model(output/'motion/motion.npz',output/'fit')
        print('Gefitte MuJoCo-modelcoordinaten exporteren',flush=True)
        export(output/'fit/fit.npz',output/'review',output/'fit/report.json')
        print('Wit MyoFullBody-model renderen',flush=True)
        module('myo_fit.view',['--fit',output/'fit/fit.npz','--render',output/'fit/preview.mp4'])
        (output/'completed.json').write_text(json.dumps({'status':'completed','experimental':True,'source':'mujoco_myofullbody_fit'}),encoding='utf-8')
        print('Analyse voltooid',flush=True)
    except Exception:
        import traceback
        traceback.print_exc();raise


if __name__=='__main__':main()
