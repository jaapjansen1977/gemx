"""Audit saved MyoFullBody and GEM-X arm directions without rerunning the fit."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation


def angle(a,b):
    a=a/np.linalg.norm(a,axis=-1,keepdims=True)
    b=b/np.linalg.norm(b,axis=-1,keepdims=True)
    return np.rad2deg(np.arccos(np.clip(np.sum(a*b,axis=-1),-1,1)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    paths=[Path('myo_fit/results/fit.npz'),Path('mujoco_demo/data/motion.npz'),Path('shoulder/results/report.json')]
    fit=np.load(paths[0],allow_pickle=False); motion=np.load(paths[1],allow_pickle=False)
    calibration=json.loads(paths[2].read_text())
    names=fit['source_names'].tolist(); bodies=fit['body_names'].tolist()
    if names!=motion['names'].tolist(): raise ValueError('Joint order mismatch')
    np.testing.assert_allclose(fit['times_s'],motion['clip_times_s'],atol=1e-8,rtol=0)
    np.testing.assert_allclose(fit['source_positions_m'],motion['positions_m'],atol=1e-8,rtol=0)
    thorax=Rotation.from_matrix(motion['rotations'][:,names.index('Chest')]).as_matrix()@np.array(calibration['thorax']['constant_chest_local_offset'])
    up=thorax[:,:,1]
    results={}; arrays=dict(times_s=fit['times_s']); vectors={}
    for side,prefix,suffix in [('left','Left','l'),('right','Right','r')]:
        gem=fit['source_positions_m'][:,names.index(prefix+'ForeArm')]-fit['source_positions_m'][:,names.index(prefix+'Arm')]
        myo=fit['body_positions_m'][:,bodies.index('ulna_'+suffix)]-fit['body_positions_m'][:,bodies.index('humerus_'+suffix)]
        gap=angle(gem,myo); gem_elevation=angle(gem,-up); myo_elevation=angle(myo,-up)
        results[side]=dict(frame0_direction_gap_deg=float(gap[0]),mean_direction_gap_deg=float(gap.mean()),direction_gap_range_deg=[float(gap.min()),float(gap.max())],frame0_gem_elevation_in_shared_gem_thorax_deg=float(gem_elevation[0]),frame0_myo_body_origin_line_elevation_in_shared_gem_thorax_deg=float(myo_elevation[0]))
        for key,data in [('gap_deg',gap),('gem_elevation_deg',gem_elevation),('myo_elevation_deg',myo_elevation)]: arrays[side+'_'+key]=data
        # Align origins only for visual comparison; preserve directions, use unit rays.
        vectors[side]=[(thorax[0].T@v[0]/np.linalg.norm(v[0]))[[2,0,1]] for v in (gem,myo)]
    report=dict(status='diagnostic_direction_comparison_not_accuracy_validation',frames=len(fit['times_s']),sides=results,
        max_frame0_qpos_difference_from_chosen_reference=float(np.max(np.abs(fit['qpos'][0]-fit['reference_qpos']))),
        definitions=dict(gem='Arm to ForeArm predicted centers',myo='humerus body origin to ulna body origin; model-origin proxy, not independently validated anatomical landmarks',shared_elevation_reference='Negative superior axis of the SAME GEM-X proxy thorax for both lines; not MyoSim shoulder coordinates or validated ISB angles'),
        explanation='The existing rotation fit maps source frame 0 to a chosen feasible stock-model reference using constant segment offsets. Its initial near-neutral appearance is imposed, not independently recovered. Absolute body/joint positions were not fit objectives.',
        limitations=['No ground truth; neither appearance nor this direction gap establishes better accuracy.','Stock body lengths and unequal body-origin/joint-center definitions.','Fit follows reference-aligned segment rotations, not absolute source orientation.'],input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    np.savez_compressed(args.output/'directions.npz',**arrays)
    plot(vectors,arrays,results,args.output/'comparison.png')
    print(json.dumps(report,indent=2))


def plot(vectors,arrays,results,target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(12,9))
    for col,side in enumerate(('left','right')):
        ax=fig.add_subplot(2,2,col+1,projection='3d')
        for v,color,label in zip(vectors[side],['#00a9cb','#50555c'],['GEM-X predicted joint line','MyoFullBody model-origin line']):
            ax.plot(*np.array([np.zeros(3),v]).T,lw=4,color=color,label=label)
            ax.scatter(*v,color=color,s=35)
        ax.plot([0,0],[0,0],[0,-1],'--',color='#279c3e',label='Shared thorax-down direction')
        ax.set(xlim=(-.45,.45),ylim=(-.45,.45),zlim=(-1.05,.1),xlabel='Right',ylabel='Anterior',zlabel='Superior')
        ax.set_box_aspect((.9,.9,1.15));ax.view_init(elev=8,azim=65)
        ax.set_title(side.title()+f': start direction gap {results[side]["frame0_direction_gap_deg"]:.1f}°')
        if col==0:ax.legend(fontsize=8,loc='upper left')
        ax=fig.add_subplot(2,2,col+3)
        ax.plot(arrays['times_s'],arrays[side+'_gap_deg'],color='#643a9c')
        ax.set(xlabel='Clip time (s)',ylabel='3D direction gap (degrees)',ylim=(0,30),title=side.title()+': direction gap across all 60 frames');ax.grid(alpha=.2)
    fig.suptitle('White model vs cyan source: initial neutral pose was imposed by reference alignment',fontsize=13)
    fig.text(.5,.02,'Unit rays share one origin for direction inspection. Body origins and source centers are proxies. No accuracy or ISB validation.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.045,1,.95));fig.savefig(target,dpi=160);plt.close(fig)


if __name__=='__main__':main()
