"""CPU painter-rendered mesh/video overlay for candidate placement inspection."""
import argparse
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--surface',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    data=np.load(args.surface/'surface.npz',allow_pickle=False)
    records=json.loads((args.surface/'attachments.json').read_text())['landmarks']
    vertices=data['vertices_incam_m']; faces=data['faces']; points=data['landmarks_incam_m']; K=data['intrinsics']
    capture=cv2.VideoCapture(str(args.video))
    if not capture.isOpened(): raise RuntimeError('Cannot open normalized video')
    width,height=540,960; panel=350
    cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','bgr24','-video_size',f'{width+panel}x{height}','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-threads','2','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(args.output/'mesh-landmarks.mp4')]
    def project(x,k):
        homogeneous=x@k.T
        return homogeneous[:,:2]/homogeneous[:,2:3]*.5
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
        for index in range(len(vertices)):
            ok,frame=capture.read()
            if not ok: raise ValueError(f'Missing video frame {index}')
            if frame.shape[:2]!=(1920,1080): raise ValueError('Use original aligned portrait 1080x1920 normalized clip')
            image=cv2.resize(frame,(width,height)); painted=image.copy()
            xyz=vertices[index]; uv=project(xyz,K[index]); tri=xyz[faces]
            normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); norms=np.linalg.norm(normals,axis=1)
            shade=.35+.65*np.abs(normals[:,2])/np.maximum(norms,1e-10)
            for face in np.argsort(-tri[:,:,2].mean(1)):
                if (tri[face,:,2]<=.05).any(): continue
                polygon=uv[faces[face]]
                if not np.isfinite(polygon).all() or np.abs(polygon).max()>10000: continue
                color=(np.array([210,160,70])*shade[face]).astype(int).tolist()
                cv2.fillConvexPoly(painted,np.rint(polygon).astype(np.int32),color)
            image=cv2.addWeighted(image,.55,painted,.45,0)
            coordinates=project(points[index],K[index]); canvas=np.zeros((height,width+panel,3),np.uint8); canvas[:,:width]=image
            for row,point in zip(records,coordinates):
                if not np.isfinite(point).all() or np.abs(point).max()>10000: continue
                xy=tuple(np.rint(point).astype(int))
                cv2.circle(canvas,xy,4,(0,220,255),-1,cv2.LINE_AA)
                cv2.putText(canvas,str(row['id']),(xy[0]+5,xy[1]-4),cv2.FONT_HERSHEY_SIMPLEX,.36,(0,0,0),3,cv2.LINE_AA)
                cv2.putText(canvas,str(row['id']),(xy[0]+5,xy[1]-4),cv2.FONT_HERSHEY_SIMPLEX,.36,(255,255,255),1,cv2.LINE_AA)
            def label(text,y,color=(230,230,230),scale=.42):
                cv2.putText(canvas,text,(width+10,y),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)
            label('SOMA MID mesh + candidates',25); label(f'Body Motion   t={index/30:.2f}s',48)
            label('UNREVIEWED - not ISB validated',80,(0,220,255)); label('All points shown, including back side',103)
            for row in records: label(f"{row['id']:02d} {row['name']}",145+row['id']*27)
            label('Fixed triangle + barycentric attachment',805)
            label('No new video inference; CPU rendering',832)
            label('No landmark fit enabled yet',859,(0,220,255))
            if index in (0,30,59): cv2.imwrite(str(args.output/f'frame-{index:03d}.jpg'),canvas)
            process.stdin.write(canvas.tobytes())
        process.stdin.close()
        if process.wait(): raise RuntimeError('FFmpeg failed')
    capture.release(); print(args.output/'mesh-landmarks.mp4')


if __name__=='__main__': main()
