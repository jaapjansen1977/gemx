"""Pinned official model downloads; resumable transfers with exact hash checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.request import Request,urlopen
from zipfile import ZipFile

MANIFEST=Path(__file__).with_name('model-manifest.json')
DETECTOR_URL='https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_x_8xb8-300e_humanart-a39d44ed.zip'
DETECTOR_SHA256='8e9ea96a176bd48501eaaa77216e49ee30794d2f8ba80c7b9862beca4ea972da'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def verified(path,digest,size=None):
    path=Path(path)
    return path.is_file() and (size is None or path.stat().st_size==size) and sha256(path)==digest


def download(url,target,digest,size=None,opener=urlopen):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if verified(target,digest,size):print('Al gecontroleerd:',target.name,flush=True);return
        raise ValueError('Bestaand bestand heeft niet de vastgelegde checksum: '+str(target))
    partial=target.with_suffix(target.suffix+'.part')
    offset=partial.stat().st_size if partial.exists() else 0
    if size is not None and offset>=size:
        if offset==size and verified(partial,digest,size):partial.replace(target);return
        partial.unlink();offset=0
    headers={'User-Agent':'GEMX-local-setup/1'}
    if offset:headers['Range']=f'bytes={offset}-'
    with opener(Request(url,headers=headers),timeout=90) as response:
        status=getattr(response,'status',200)
        if status==206:
            content_range=response.headers.get('Content-Range','')
            if not content_range.startswith(f'bytes {offset}-'):raise ValueError('Ongeldig hervatbereik van downloadserver')
        elif status==200:offset=0
        else:raise ValueError(f'Onverwachte downloadstatus {status}')
        count=offset;last=count
        with partial.open('ab' if offset else 'wb') as output:
            while True:
                block=response.read(4*1024*1024)
                if not block:break
                output.write(block);count+=len(block)
                if count-last>=64*1024*1024:
                    print(f'{target.name}: {count/1e6:.0f} MB'+(f' / {size/1e6:.0f} MB' if size else ''),flush=True);last=count
    if not verified(partial,digest,size):
        partial.unlink(missing_ok=True)
        raise ValueError('SHA256 of bestandsgrootte klopt niet: '+target.name)
    partial.replace(target)
    print('Checksum akkoord:',target.name,flush=True)


def detector(weights):
    weights=Path(weights);target=weights/'yolox_humanart.onnx'
    if target.exists():
        if verified(target,DETECTOR_SHA256):return
        raise ValueError('Detectorchecksum klopt niet: '+str(target))
    # Only the verified ONNX member is retained; no untrusted paths are extracted.
    archive=weights/'detector-download.zip.part'
    with urlopen(Request(DETECTOR_URL,headers={'User-Agent':'GEMX-local-setup/1'}),timeout=90) as response,archive.open('wb') as stream:
        shutil.copyfileobj(response,stream,4*1024*1024)
    temporary=weights/'yolox_humanart.onnx.part'
    try:
        with ZipFile(archive) as source:
            matches=[name for name in source.namelist() if name.endswith('/end2end.onnx')]
            if len(matches)!=1:raise ValueError('Officieel detectorarchief bevat geen unieke ONNX-detector')
            with source.open(matches[0]) as member,temporary.open('wb') as output:shutil.copyfileobj(member,output,4*1024*1024)
        if not verified(temporary,DETECTOR_SHA256):raise ValueError('Uitgepakte detector heeft een andere SHA256 dan de vastgelegde proef')
        temporary.replace(target)
    finally:
        archive.unlink(missing_ok=True);temporary.unlink(missing_ok=True)


def make_config(weights):
    import yaml
    weights=Path(weights).resolve()
    original=weights/'body_video_native77.yaml'
    config=yaml.safe_load(original.read_text(encoding='utf-8'))
    expected={'pose':{'checkpoint':'body_s240000.ckpt'},'observations':{'checkpoint':'vitpose.pth'},
              'detector':{'checkpoint':'yolox_humanart.onnx'},'motion':{'checkpoint':'motion_native77_e774_s292175.ckpt','stats':'motion_stats_raw.npz'}}
    for section,keys in expected.items():
        for key,filename in keys.items():
            if Path(config[section][key]).name!=filename:raise ValueError('Onverwachte releaseconfiguratie: '+section+'.'+key)
            config[section][key]=str(weights/filename)
    target=weights/'windows_body_video_native77.yaml'
    target.write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    return target


def install_models(root):
    root=Path(root).resolve();records=json.loads(MANIFEST.read_text())
    for record in records:
        directory=root/('weights' if record['repository']=='nvidia/GEM-X' else 'soma')
        url=f"https://huggingface.co/{record['repository']}/resolve/{record['revision']}/{record['filename']}"
        print('Download/controleren:',record['repository'],record['filename'],flush=True)
        download(url,directory/record['filename'],record['sha256'],record['bytes'])
    detector(root/'weights');config=make_config(root/'weights')
    (root/'verified-models.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    return config


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    try:print('Runtimeconfiguratie:',install_models(args.root))
    except Exception as error:raise SystemExit('Modelinstallatie niet voltooid: '+str(error))


if __name__=='__main__':main()
