"""Visual check: anatomical proxy axes, shoulder values and time-aligned curves."""
import argparse
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True); p.add_argument('--video',type=Path,required=True)
    p.add_argument('--surface',type=Path,default=Path('landmarks/results/surface.npz'))
    args=p.parse_args(); a=np.load(args.directory/'shoulder.npz',allow_pickle=False)
    surface=np.load(args.surface,allow_pickle=False); K=surface['intrinsics']; times=a['times_s']
    np.testing.assert_array_equal(times,surface['times_s'])
    chart=cv2.imread(str(args.directory/'angles.png')); layout=json.loads((args.directory/'plot-layout.json').read_text())
    if chart is None or chart.shape[:2]!=(960,600): raise ValueError('Run shoulder.plot first')
    capture=cv2.VideoCapture(str(args.video)); names=a['source_names'].tolist()
    cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','bgr24','-video_size','1140x960','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-threads','2','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(args.directory/'shoulder-check.mp4')]
    def project(points,k):
        h=points@k.T
        if (h[:,2]<=.05).any(): raise ValueError('Axis behind camera')
        return np.rint(h[:,:2]/h[:,2:3]*.5).astype(int)
    def text(image,label,xy,color=(255,255,255),size=.43):
        cv2.putText(image,label,xy,cv2.FONT_HERSHEY_SIMPLEX,size,(0,0,0),3,cv2.LINE_AA)
        cv2.putText(image,label,xy,cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
        for f,t in enumerate(times):
            ok,image=capture.read()
            if not ok: raise ValueError(f'Missing aligned frame {f}')
            if image.shape[:2]!=(1920,1080): raise ValueError('Expected normalized 1080x1920 portrait clip')
            image=cv2.resize(image,(540,960)); canvas=np.concatenate([image,chart.copy()],axis=1)
            def axes(origin,rotation,label):
                coordinates=np.vstack([origin,origin+rotation.T*.14]); uv=project(coordinates,K[f])
                for i,(axis,color) in enumerate(zip('XYZ',[(0,0,255),(0,255,0),(255,150,30)])):
                    cv2.arrowedLine(canvas,tuple(uv[0]),tuple(uv[i+1]),color,2,cv2.LINE_AA,tipLength=.15)
                    text(canvas,label+axis,tuple(uv[i+1]),color,.36)
            axes(a['thorax_origins_incam_m'][f],a['thorax_frames_incam'][f],'T')
            for side,source_side,color,y in [('left','Left',(70,200,255),88),('right','Right',(255,200,70),116)]:
                origin=a['source_joint_positions_incam_m'][f,names.index(source_side+'Arm')]
                axes(origin,a[side+'_humerus'][f],source_side[0])
                plane,elevation,axial=a[side+'_angles_deg'][f]
                valid=bool(a[side+'_valid'][f])
                values=f'{side}: elev {elevation:.1f}  plane {plane:.1f}  axial {axial:.1f}' if valid else f'{side}: elev {elevation:.1f}; plane/axial UNSTABLE'
                text(canvas,values,(555,y),color,.43)
            text(canvas,f't={t:.2f}s  PROXY AXES - anatomy unvalidated',(8,25),size=.42)
            text(canvas,'X anterior (red), Y superior (green), Z right (blue)',(8,49),size=.37)
            for box in layout['axes']:
                x=int(540+box['left']+(box['right']-box['left'])*(t-times[0])/(times[-1]-times[0]))
                cv2.line(canvas,(x,int(box['top'])),(x,int(box['bottom'])),(210,210,210),1)
            if f in (0,30,59): cv2.imwrite(str(args.directory/f'check-{f:03d}.jpg'),canvas)
            process.stdin.write(canvas.tobytes())
        process.stdin.close()
        if process.wait(): raise RuntimeError('FFmpeg failed')
    capture.release()


if __name__=='__main__': main()
