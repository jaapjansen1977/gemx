"""Check the real local Python, native runtimes, codecs and optional model assets."""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from .models import MANIFEST,DETECTOR_SHA256,verified
from .paths import profile_path



def codec_smoke(ffmpeg,ffprobe,environment):
    with tempfile.TemporaryDirectory(prefix='gemx-codec-') as temporary:
        target=Path(temporary)/'test.mp4'
        subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=black:s=32x32:r=30','-t','0.1','-an','-c:v','libx264','-pix_fmt','yuv420p','-y',str(target)],env=environment,capture_output=True,text=True,timeout=30,check=True)
        result=subprocess.run([ffprobe,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=codec_name,nb_read_frames','-of','json',str(target)],env=environment,capture_output=True,text=True,timeout=30,check=True)
        stream=json.loads(result.stdout)['streams'][0]
        if stream['codec_name']!='h264' or int(stream['nb_read_frames'])<1:raise RuntimeError('FFmpeg encode-/decodetest mislukt')
        return stream


def check_engine(root,ffmpeg_bin=None,dependencies_only=False):
    root=Path(root).resolve();checks=[]
    def check(name,action):
        try:
            details=action();checks.append(dict(name=name,status='passed',details=details));print('[OK]',name,flush=True)
        except Exception as error:
            checks.append(dict(name=name,status='failed',error=str(error)));print('[FOUT]',name,str(error),flush=True)
    def python_check():
        if sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8:raise RuntimeError('Python 3.12 (64-bit) vereist')
        return platform.python_version()
    check('Python 3.12 64-bit',python_check)
    def cpu():
        import torch
        if torch.__version__.split('+')[0]!='2.10.0' or torch.version.cuda is not None:raise RuntimeError('Verwacht CPU-only PyTorch 2.10.0')
        value=torch.eye(3)@torch.ones(3,1)
        if value.sum().item()!=3:raise RuntimeError('Torch CPU-controle mislukt')
        return torch.__version__
    check('PyTorch CPU-berekening',cpu)
    for name in ('onnxruntime','cv2','warp','pxr.Usd','cholespy','rtree','soma'):
        check('Import '+name,lambda name=name:bool(importlib.import_module(name)))
    def upstream():
        meta=json.loads(importlib.metadata.distribution('gem').read_text('direct_url.json') or '{}')
        if meta.get('vcs_info',{}).get('commit_id')!='20555befe2fbbe5b2015e1fff7ff214dc18ea9d6':raise RuntimeError('Andere GEM-X-bronversie')
        from gem.inference.body_video import run_body_video
        return bool(run_body_video)
    check('Vastgelegde GEM-X-videopipeline',upstream)
    def model():
        import mujoco
        from myo_sim.build.compose import build_spec
        meta=json.loads(importlib.metadata.distribution('myo-sim').read_text('direct_url.json') or '{}')
        if meta.get('vcs_info',{}).get('commit_id')!='93b0ca8f4ec90c9899ee7f05fee561e9911da91b':raise RuntimeError('Andere MyoSim-bronversie')
        if mujoco.__version__!='3.4.0':raise RuntimeError('MuJoCo 3.4.0 vereist')
        m=build_spec('myofullbody').compile();d=mujoco.MjData(m);mujoco.mj_forward(m,d)
        if (m.nq,m.njnt)!=(129,123):raise RuntimeError('Onverwacht MyoFullBody-model')
        return dict(nq=m.nq,joints=m.njnt)
    check('MyoFullBody compileren en doorrekenen',model)
    environment=os.environ.copy()
    if ffmpeg_bin:environment['PATH']=str(ffmpeg_bin)+os.pathsep+environment.get('PATH','')
    for executable in ('ffmpeg','ffprobe'):
        def codec(executable=executable):
            path=shutil.which(executable,path=environment.get('PATH'))
            if not path:raise RuntimeError(executable+' ontbreekt; stel -FFmpegDirectory in')
            result=subprocess.run([path,'-version'],capture_output=True,text=True,timeout=30,check=True)
            return result.stdout.splitlines()[0]
        check('Uitvoeren '+executable,codec)
    def encoder():
        binary=shutil.which('ffmpeg',path=environment.get('PATH'))
        if not binary:raise RuntimeError('FFmpeg ontbreekt')
        result=subprocess.run([binary,'-hide_banner','-encoders'],capture_output=True,text=True,timeout=30,check=True)
        if 'libx264' not in result.stdout:raise RuntimeError('Deze FFmpeg-build bevat geen libx264')
        return True
    check('H.264-encoder beschikbaar',encoder)
    check('Echte H.264-codecproef',lambda:codec_smoke(shutil.which('ffmpeg',path=environment.get('PATH')),shutil.which('ffprobe',path=environment.get('PATH')),environment))
    if not dependencies_only:
        records=json.loads(MANIFEST.read_text())
        for record in records:
            target=root/('weights' if record['repository']=='nvidia/GEM-X' else 'soma')/record['filename']
            def asset(target=target,record=record):
                if not verified(target,record['sha256'],record['bytes']):raise RuntimeError('Ontbrekend of checksum onjuist: '+str(target))
                return True
            check('Model '+str(target.relative_to(root)),asset)
        def detector_check():
            if not verified(root/'weights/yolox_humanart.onnx',DETECTOR_SHA256):raise RuntimeError('Detector ontbreekt of heeft andere SHA256')
            return True
        check('YOLOX-detector',detector_check)
        def config():
            from gem.inference.body_video import load_body_video_config
            c=load_body_video_config(root/'weights/windows_body_video_native77.yaml')
            for section in ('pose','observations','detector','motion'):
                if not Path(c[section]['checkpoint']).is_file():raise RuntimeError('Onjuist configuratiepad: '+section)
            return True
        check('Lokale runtimeconfiguratie',config)
        def soma_forward():
            os.environ.setdefault('WARP_CACHE_PATH',str(root/'warp-cache'))
            os.environ.setdefault('HF_HUB_OFFLINE','1')
            import torch
            from gem.common.soma import SomaFixedGs1BodyAdapter,SomaRuntimeConfig
            body=SomaFixedGs1BodyAdapter(SomaRuntimeConfig(data_root=str(root/'soma'),device='cpu',apply_correctives=False))
            with torch.inference_mode():
                output=body(global_orient=torch.zeros(1,3),body_pose=torch.zeros(1,76,3),identity_coeffs=torch.zeros(1,128),scale_params=torch.ones(1,57),return_joints_only=True,repose_to_bind_pose=True)
            joints=output['joints']
            if joints.shape!=(1,77,3) or not torch.isfinite(joints).all():raise RuntimeError('SOMA CPU-geometriecontrole mislukt')
            return dict(joints=77,device=str(joints.device))
        check('SOMA CPU-geometrie met echte assets',soma_forward)
    try:
        import psutil
        resources=dict(ram_gib=round(psutil.virtual_memory().total/1024**3,1),logical_cpus=os.cpu_count())
    except ImportError:resources=dict(ram_gib=None,logical_cpus=os.cpu_count())
    print('Systeem:',resources,flush=True)
    passed=all(c['status']=='passed' for c in checks)
    return dict(status=('dependencies_checked_models_not_checked' if dependencies_only else 'ready_for_video_test') if passed else 'incomplete',
                python=str(Path(sys.executable).resolve()),config=str(root/'weights/windows_body_video_native77.yaml'),assets=str(root/'soma'),
                ffmpeg_bin=str(Path(ffmpeg_bin).resolve()) if ffmpeg_bin else '',platform=platform.platform(),resources=resources,checks=checks,
                windows_video_end_to_end_tested=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ffmpeg-bin',type=Path);parser.add_argument('--dependencies-only',action='store_true');parser.add_argument('--register',action='store_true')
    args=parser.parse_args()
    report=check_engine(args.root,args.ffmpeg_bin,args.dependencies_only)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    if args.register and report['status']=='ready_for_video_test':
        target=profile_path();target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Apps automatisch ingesteld:',target)
    if report['status']=='incomplete':raise SystemExit(1)


if __name__=='__main__':main()
