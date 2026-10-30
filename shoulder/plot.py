"""Standalone Matplotlib plots; no GEM or MuJoCo imports."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    p=argparse.ArgumentParser(); p.add_argument('directory',type=Path); args=p.parse_args()
    a=np.load(args.directory/'shoulder.npz',allow_pickle=False); t=a['times_s']
    with plt.style.context('dark_background'):
        fig,axes=plt.subplots(3,1,figsize=(6,9.6),dpi=100)
        fig.subplots_adjust(left=.14,right=.97,top=.81,bottom=.09,hspace=.35)
        fig.suptitle('Provisional humerothoracic angles\nUnvalidated anatomical proxy calibration',fontsize=12,y=.985)
        for ax,column,title in zip(axes,(1,0,2),('Elevation','Plane of elevation','Axial rotation')):
            for side,color in [('left','#ffc857'),('right','#55c9ff')]:
                y=a[side+'_angles_deg'][:,1] if column==1 else a[side+('_plane_unwrapped_deg' if column==0 else '_axial_unwrapped_deg')]
                ax.plot(t,y,label=side,color=color,lw=1.8)
            ax.set(title=title,ylabel='degrees',xlim=(t[0],t[-1])); ax.grid(alpha=.25); ax.legend(fontsize=8,loc='best')
        axes[-1].set_xlabel('Clip time (s)')
        fig.text(.07,.025,'ISB-style YXY; left mirrored. Not clinical ROM.\nPlane/axial gaps = numerical conditioning exclusion.',fontsize=9)
        fig.canvas.draw()
        # Pixel coordinates for a moving time cursor in the video panel.
        boxes=[]
        for ax in axes:
            box=ax.get_window_extent(); boxes.append(dict(left=box.x0,right=box.x1,top=960-box.y1,bottom=960-box.y0))
        fig.savefig(args.directory/'angles.png',dpi=100)
        fig.savefig(args.directory/'angles.svg')
        (args.directory/'plot-layout.json').write_text(json.dumps(dict(width=600,height=960,axes=boxes),indent=2))
        plt.close(fig)


if __name__=='__main__': main()
