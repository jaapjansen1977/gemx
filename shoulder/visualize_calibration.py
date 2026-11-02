"""Auditable saved-pose calibration views; no model inference or zero correction."""
import argparse
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from .angles import unit
from .compare_mesh import mesh_frame

AXIS_COLORS = ['#d62728', '#239b38', '#2466da']
SIDE_COLORS = {'left': '#007ca8', 'right': '#ad5100'}
# Anatomical XYZ (anterior, superior, right) -> display (right, anterior, superior).
DISPLAY = np.eye(3)[[2, 0, 1]]


def transform(points, origin, thorax):
    """One rigid display transform; not a new calibration or gravity estimate."""
    return (np.asarray(points) - origin) @ thorax @ DISPLAY.T


def elevation_arc(shoulder, elbow, superior, radius=.19, samples=32):
    down = -unit(superior)
    arm = unit(elbow - shoulder)
    angle = np.arccos(np.clip(np.dot(down, arm), -1, 1))
    tangent = arm - down * np.dot(down, arm)
    if np.linalg.norm(tangent) < 1e-10:
        # The arc degenerates to one direction for zero elevation.
        if angle > 1e-6:
            raise ValueError('Antiparallel directions do not define a unique arc plane')
        tangent = np.zeros(3)
    else:
        tangent = unit(tangent)
    a = np.linspace(0, angle, samples)
    return shoulder + radius * (np.cos(a)[:, None] * down + np.sin(a)[:, None] * tangent), float(np.rad2deg(angle))


def load_poses(root):
    files = dict(baseline=root/'shoulder/results/shoulder.npz', neutral=root/'shoulder/results/neutral.npz',
                 calibration=root/'shoulder/results/report.json', surface=root/'landmarks/results/surface.npz',
                 topology=root/'mujoco_demo/data/motion.npz', attachments=root/'landmarks/results/attachments.json')
    base = np.load(files['baseline'], allow_pickle=False)
    neutral = np.load(files['neutral'], allow_pickle=False)
    surface = np.load(files['surface'], allow_pickle=False)
    demo = np.load(files['topology'], allow_pickle=False)
    calibration = json.loads(files['calibration'].read_text())
    names = base['source_names'].tolist()
    if names != demo['names'].tolist() or names != neutral['names'].tolist():
        raise ValueError('Joint names/order disagree between inputs')
    np.testing.assert_allclose(base['times_s'], surface['times_s'], atol=1e-8, rtol=0)
    faces = surface['faces']
    refs = surface['reference_vertices_m']
    ref_landmarks = np.einsum('lvc,lv->lc', refs[faces[surface['face_ids']]], surface['barycentric'])
    evaluated = np.einsum('lvc,lv->lc', surface['vertices_incam_m'][0][faces[surface['face_ids']]], surface['barycentric'])
    bary_error = float(np.max(np.abs(evaluated - surface['landmarks_incam_m'][0])))
    if bary_error > 1e-6:
        raise ValueError('Saved landmarks do not match mesh attachments')
    reference_thorax = Rotation.from_matrix(neutral['rotations'][names.index('Chest')]).as_matrix() @ np.array(calibration['thorax']['constant_chest_local_offset'])
    poses = []
    for key, title, vertices, joints, points, thorax in [
        ('start', 'Beginhouding — opgeslagen frame 0, t=0,00 s', surface['vertices_incam_m'][0], base['source_joint_positions_incam_m'][0], surface['landmarks_incam_m'][0], base['thorax_frames_incam'][0]),
        ('reference', 'Modelreferentie — T-pose, geen gemeten nulhouding', refs, neutral['joints'], ref_landmarks, reference_thorax),
    ]:
        origin = joints[names.index('Chest')]
        convert = lambda p: transform(p, origin, thorax)
        basis = DISPLAY @ thorax.T
        np.testing.assert_allclose(basis.T @ basis, np.eye(3), atol=1e-6)
        if np.linalg.det(basis) < 0:
            raise ValueError('Display reflection')
        pose = dict(key=key, title=title, vertices=convert(vertices), joints=convert(joints),
                    landmarks=convert(points), faces=faces, names=names, landmark_names=surface['names'].tolist(),
                    parents=demo['parents'], thorax=basis @ thorax, humerus={}, mesh_fixed={}, mesh_dynamic={}, audit={})
        for side, prefix, suffix in [('left', 'Left', 'l'), ('right', 'Right', 'r')]:
            arm = names.index(prefix+'Arm'); elbow = names.index(prefix+'ForeArm')
            baseline_ref = np.array(calibration['humerus'][side]['neutral_anatomical_frame'])
            baseline_humerus = base[side+'_humerus'][0] if key == 'start' else baseline_ref
            mi = pose['landmark_names'].index('elbow_epicondyle_medial_'+suffix)
            li = pose['landmark_names'].index('elbow_epicondyle_lateral_'+suffix)
            mesh_ref, _, _, _ = mesh_frame(neutral['joints'][arm], ref_landmarks[mi], ref_landmarks[li], side)
            dynamic, ok, line_angle, separation = mesh_frame(joints[arm], points[mi], points[li], side)
            pose['humerus'][side] = basis @ baseline_humerus
            pose['mesh_fixed'][side] = basis @ baseline_humerus @ (baseline_ref.T @ mesh_ref)
            pose['mesh_dynamic'][side] = basis @ dynamic
            arc, direct = elevation_arc(pose['joints'][arm], pose['joints'][elbow], pose['thorax'][:, 1])
            frame_angle = float(np.rad2deg(np.arccos(np.clip(np.dot(thorax[:, 1], baseline_humerus[:, 1]), -1, 1))))
            pose['audit'][side] = dict(direct_elevation_deg=direct, frame_elevation_deg=frame_angle,
                axis_vs_joint_line_difference_deg=abs(direct-frame_angle),
                candidate_epicondylar_line_to_long_axis_deg=float(line_angle), candidate_separation_mm=float(separation*1000),
                candidate_numeric_geometry_pass=bool(ok), anatomical_landmarks_verified=False,
                saved_baseline_elevation_deg=float(base[side+'_angles_deg'][0, 1]) if key == 'start' else None)
            if key == 'start' and abs(direct - base[side+'_angles_deg'][0, 1]) > .05:
                raise ValueError('Direct geometric elevation disagrees with saved result')
        poses.append(pose)
    return poses, files, bary_error


def segments(pose):
    joints = pose['joints']
    return [(joints[parent], joints[child]) for child, parent in enumerate(pose['parents']) if parent >= 0]


def interactive(poses, target):
    import plotly.graph_objects as go
    from plotly.offline import get_plotlyjs
    traces = []
    pose_ranges = []
    for pi, pose in enumerate(poses):
        start = len(traces)
        def add(trace):
            trace.visible = True if pi == 0 else False
            traces.append(trace)
        def line(points, name, color, group, dash='solid', width=5, showlegend=True, labels=None):
            points = np.asarray(points)
            add(go.Scatter3d(x=points[:, 0], y=points[:, 1], z=points[:, 2], mode='lines',
                name=name, legendgroup=group, showlegend=showlegend, line=dict(color=color, width=width, dash=dash),
                text=labels, hovertemplate=(name+'<br>%{x:.3f}, %{y:.3f}, %{z:.3f} m<extra></extra>')))
        v = pose['vertices']; f = pose['faces']; joints = pose['joints']
        add(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color='#a3abb4', opacity=.13, name='Mesh (zelfde GEM-X-bron)', legendgroup=f'mesh{pi}', showlegend=True, hoverinfo='skip'))
        bones = []
        for a,b in segments(pose): bones.extend([a,b,[np.nan]*3])
        line(bones, 'Skelet — voorspelde gewrichtscentra', '#596574', f'skeleton{pi}', width=3)
        important = ['Hips','Chest','LeftArm','LeftForeArm','RightArm','RightForeArm']
        indices = [pose['names'].index(n) for n in important]; q=joints[indices]
        add(go.Scatter3d(x=q[:,0], y=q[:,1], z=q[:,2], mode='markers+text', text=['Bekken','Borstkas','S links','E links','S rechts','E rechts'],
            textposition='top center', marker=dict(size=5,color='#111827'), name='S/E = geschat schouder-/elleboogcentrum', legendgroup=f'centers{pi}', hovertext=important, hoverinfo='text'))
        q=pose['landmarks']
        add(go.Scatter3d(x=q[:,0], y=q[:,1], z=q[:,2], mode='markers', marker=dict(size=5,color='#be8500',symbol='diamond'),
            name='Mesh-landmarks — anatomisch ongecontroleerd', legendgroup=f'landmarks{pi}', text=pose['landmark_names'], hovertemplate='%{text}<extra></extra>'))
        for axis, color in enumerate(AXIS_COLORS):
            origin = np.zeros(3)
            line([origin,origin+.24*pose['thorax'][:,axis]], 'Borstkasassen: X rood, Y groen, Z blauw',color,f'thorax{pi}',showlegend=axis==0)
        for side,prefix,suffix in [('left','Left','l'),('right','Right','r')]:
            shoulder=joints[pose['names'].index(prefix+'Arm')]; elbow=joints[pose['names'].index(prefix+'ForeArm')]
            line([shoulder,elbow], 'Bovenarmlijn '+side, SIDE_COLORS[side],f'arm{pi}{side}',width=8)
            line([shoulder,shoulder-.37*pose['thorax'][:,1]], 'Borstkas-neerwaarts (0°-richting)', '#239b38',f'down{pi}',dash='dash',showlegend=side=='left')
            arc,angle=elevation_arc(shoulder,elbow,pose['thorax'][:,1])
            line(arc,f'Elevatie {side}: {angle:.2f}°','#a024b5',f'angle{pi}',width=5,showlegend=side=='left')
            mi=pose['landmark_names'].index('elbow_epicondyle_medial_'+suffix); li=pose['landmark_names'].index('elbow_epicondyle_lateral_'+suffix)
            line([q[mi],q[li]],'Kandidaat-epicondylaire lijn','#be8500',f'epicondyles{pi}',width=7,showlegend=side=='left')
            for method,label,dash in [('humerus','Bestaande bovenarmassen','solid'),('mesh_fixed','Vaste mesh-kalibratie','dash'),('mesh_dynamic','Mesh-assen per houding','dot')]:
                for axis,color in enumerate(AXIS_COLORS):
                    line([shoulder,shoulder+.14*pose[method][side][:,axis]],label+' (X/Y/Z)',color,f'{method}{pi}',dash=dash,width=4,showlegend=side=='left' and axis==0)
                    traces[-1].meta = {'default_hidden': method != 'humerus'}
                    if pi == 0 and method != 'humerus': traces[-1].visible = 'legendonly'
        pose_ranges.append((start,len(traces)))
    all_points=np.concatenate([p['vertices'] for p in poses])
    lower=all_points.min(axis=0)-.08; upper=all_points.max(axis=0)+.08
    fig=go.Figure(traces)
    fig.update_layout(height=760, margin=dict(l=0,r=0,b=0,t=45), title=poses[0]['title'],
        scene=dict(aspectmode='manual', aspectratio=dict(x=1.1,y=.6,z=.7), xaxis=dict(title='Rechts (m)',range=[-.55,.55]), yaxis=dict(title='Voorwaarts (m)',range=[-.30,.30]),
                   zaxis=dict(title='Borstkas-opwaarts (m)',range=[-.25,.45]), camera=dict(eye=dict(x=1.4,y=2.2,z=.6)),
                   dragmode='orbit'), legend=dict(groupclick='togglegroup', font=dict(size=11)), uirevision='calibration')
    payload=fig.to_json()
    cards=[]
    for pose in poses:
        cards.append('<section><h3>'+html.escape(pose['title'])+'</h3><table><tr><th>Kant</th><th>Elevatie uit gewrichtslijn</th><th>Hoek ellebooglijn / lengteas</th></tr>'+''.join(
            f'<tr><td>{side}</td><td>{pose["audit"][side]["direct_elevation_deg"]:.2f}°</td><td>{pose["audit"][side]["candidate_epicondylar_line_to_long_axis_deg"]:.2f}°</td></tr>' for side in ('left','right'))+'</table></section>')
    page='''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>3D-kalibratiecontrole GEM-X</title>
<style>body{font:16px system-ui;margin:24px auto;max-width:1400px;padding:0 20px;color:#172433}h1{font-size:26px}button,select{font:inherit;padding:8px;margin:4px}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}.note{background:#fff3d9;padding:14px}.cards{display:flex;flex-wrap:wrap;gap:32px}#plot{min-height:760px}</style>
<h1>3D-kalibratiecontrole</h1><p>Draai met de muis, zoom met het scrollwiel. Klik in de legenda om lagen aan/uit te zetten. S = geschat schoudercentrum; E = geschat elleboogcentrum. Mesh-punten zijn geel; ze zijn nog niet anatomisch gecontroleerd.</p>
<p class="note">Dit zijn voorspellingen, geen onafhankelijke metingen. De groene stippellijn is de neerwaartse borstkasas: de 0°-richting voor elevatie. Deze as is geen gemeten zwaartekracht. De model-T-pose is geen waargenomen anatomische nulhouding. IJ/C7/PX/T8 ontbreken. Alle gegevens en scripts zitten in dit bestand; er zijn geen externe netwerkverzoeken nodig.</p>
<label>Houding: <select id="pose"><option value="0">Beginhouding, frame 0</option><option value="1">Modelreferentie, T-pose</option></select></label>
<button id="shoulders">Schouders in beeld</button><button id="whole">Hele lichaam</button><button data-camera="front">Voor</button><button data-camera="right">Rechts</button><button data-camera="top">Boven</button><button data-camera="oblique">Schuin</button><div id="plot"></div><div class="cards">CARDS</div>
<p>Volle SOMA MID-mesh: 18.056 vertices en 36.108 driehoeken per houding. De gewrichtscentra in de beginhouding komen uit de eerdere XLO-export (bestaand gerapporteerd verschil met MID tot circa 1,02 mm). Geen punten verschoven, geen beginhoek afgetrokken.</p>
<script>PLOTLYJS</script><script>
const spec=PAYLOAD; const ranges=RANGES; const fullBounds=FULLBOUNDS;
window.calibrationReady=false;
Plotly.newPlot('plot',spec.data,spec.layout,{responsive:true,displaylogo:false}).then(()=>{window.calibrationReady=true;});
document.getElementById('pose').addEventListener('change', e=>{
 const idx=Number(e.target.value), r=ranges[idx];
 Plotly.update('plot',{visible:spec.data.map((t,i)=>i>=r[0]&&i<r[1]?(t.meta?.default_hidden?'legendonly':true):false)},{title:{text:idx===0?'Beginhouding — opgeslagen frame 0, t=0,00 s':'Modelreferentie — T-pose, geen gemeten nulhouding'}});
});
document.getElementById('shoulders').addEventListener('click',()=>Plotly.relayout('plot',{'scene.xaxis.range':[-.55,.55],'scene.yaxis.range':[-.30,.30],'scene.zaxis.range':[-.25,.45],'scene.aspectratio':{x:1.1,y:.6,z:.7}}));
document.getElementById('whole').addEventListener('click',()=>Plotly.relayout('plot',{'scene.xaxis.range':[fullBounds[0][0],fullBounds[1][0]],'scene.yaxis.range':[fullBounds[0][1],fullBounds[1][1]],'scene.zaxis.range':[fullBounds[0][2],fullBounds[1][2]],'scene.aspectratio':{x:fullBounds[1][0]-fullBounds[0][0],y:fullBounds[1][1]-fullBounds[0][1],z:fullBounds[1][2]-fullBounds[0][2]}}));
const cameras={front:{x:0,y:2.6,z:.15},right:{x:2.6,y:0,z:.15},top:{x:0,y:0,z:2.8},oblique:{x:1.4,y:2.2,z:.6}};
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>{
 const view=b.dataset.camera; Plotly.relayout('plot',{'scene.camera':{eye:cameras[view],up:view==='top'?{x:0,y:1,z:0}:{x:0,y:0,z:1}}});
}));
</script></html>'''
    target.write_text(page.replace('CARDS',''.join(cards)).replace('PAYLOAD',payload).replace('RANGES',json.dumps(pose_ranges)).replace('FULLBOUNDS',json.dumps([lower.tolist(),upper.tolist()])).replace('PLOTLYJS',get_plotlyjs()))
    return len(traces), pose_ranges


def static_views(pose, target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig=plt.figure(figsize=(15,11))
    views=[(0,2,'Voor — kijk langs borstkas-voorwaarts'),(1,2,'Rechts — kijk langs borstkas-rechts'),(0,1,'Boven — kijk langs borstkas-opwaarts')]
    joints=pose['joints']; vertices=pose['vertices']; faces=pose['faces']
    lower=vertices.min(axis=0)-.08; upper=vertices.max(axis=0)+.08
    for panel,(horizontal,vertical,title) in enumerate(views):
        ax=fig.add_subplot(2,2,panel+1)
        ax.add_collection(PolyCollection(vertices[faces][:,:,[horizontal,vertical]],facecolor='#8293a1',edgecolor='none',alpha=.018,rasterized=True))
        for a,b in segments(pose): ax.plot([a[horizontal],b[horizontal]],[a[vertical],b[vertical]],color='#7b8790',linewidth=1)
        q=pose['landmarks']; ax.scatter(q[:,horizontal],q[:,vertical],c='#bb8600',s=17,zorder=5,marker='D')
        for axis,color in enumerate(AXIS_COLORS):
            end=.23*pose['thorax'][:,axis]
            ax.annotate('',xy=end[[horizontal,vertical]],xytext=(0,0),arrowprops=dict(arrowstyle='->',color=color,lw=2))
        for side,prefix,suffix in [('left','Left','l'),('right','Right','r')]:
            shoulder=joints[pose['names'].index(prefix+'Arm')]; elbow=joints[pose['names'].index(prefix+'ForeArm')]
            ax.plot([shoulder[horizontal],elbow[horizontal]],[shoulder[vertical],elbow[vertical]],color=SIDE_COLORS[side],lw=3,label='Bovenarm '+side)
            for label,p in [('S',shoulder),('E',elbow)]:
                ax.scatter(p[horizontal],p[vertical],c=SIDE_COLORS[side],s=28,zorder=6)
                ax.annotate(label+' '+side,(p[horizontal],p[vertical]),xytext=(5,5),textcoords='offset points',fontsize=8)
            end=shoulder-.37*pose['thorax'][:,1]
            ax.plot([shoulder[horizontal],end[horizontal]],[shoulder[vertical],end[vertical]],'--',color=AXIS_COLORS[1],lw=1.8)
            arc,angle=elevation_arc(shoulder,elbow,pose['thorax'][:,1]); ax.plot(arc[:,horizontal],arc[:,vertical],color='#a024b5',lw=2)
            mi=pose['landmark_names'].index('elbow_epicondyle_medial_'+suffix); li=pose['landmark_names'].index('elbow_epicondyle_lateral_'+suffix)
            ax.plot(q[[mi,li],horizontal],q[[mi,li],vertical],color='#bb8600',lw=3)
        ax.set_aspect('equal'); ax.autoscale_view(); ax.grid(alpha=.2); ax.set_title(title,fontsize=11)
        coords=['Rechts (m)','Voorwaarts (m)','Borstkas-opwaarts (m)'];ax.set_xlabel(coords[horizontal]);ax.set_ylabel(coords[vertical])
        ax.set_xlim(lower[horizontal],upper[horizontal]);ax.set_ylim(lower[vertical],upper[vertical])
        if panel==0: ax.invert_xaxis()  # View from anterior, matching the interactive front camera.
    ax=fig.add_subplot(2,2,4,projection='3d')
    # Exact full mesh, rendered with translucent faces; no decimation.
    ax.add_collection3d(Poly3DCollection(vertices[faces],facecolor='#a5afbb',edgecolor='none',alpha=.025,rasterized=True))
    for a,b in segments(pose): ax.plot(*np.array([a,b]).T,color='#7b8790',lw=1)
    for side,prefix in [('left','Left'),('right','Right')]:
        shoulder=joints[pose['names'].index(prefix+'Arm')];elbow=joints[pose['names'].index(prefix+'ForeArm')]
        ax.plot(*np.array([shoulder,elbow]).T,color=SIDE_COLORS[side],lw=3)
        arc,angle=elevation_arc(shoulder,elbow,pose['thorax'][:,1]);ax.plot(*arc.T,color='#a024b5',lw=2)
        ax.plot(*np.array([shoulder,shoulder-.37*pose['thorax'][:,1]]).T,'--',color=AXIS_COLORS[1])
        for axis,color in enumerate(AXIS_COLORS):
            ax.quiver(*shoulder,*(.15*pose['humerus'][side][:,axis]),color=color,arrow_length_ratio=.15)
    for axis,color in enumerate(AXIS_COLORS): ax.quiver(0,0,0,*(.24*pose['thorax'][:,axis]),color=color)
    ax.scatter(*pose['landmarks'].T,color='#bb8600',s=14)
    ax.set(xlim=(lower[0],upper[0]),ylim=(lower[1],upper[1]),zlim=(lower[2],upper[2]),xlabel='Rechts (m)',ylabel='Voorwaarts (m)',zlabel='Opwaarts (m)')
    ax.set_box_aspect(upper-lower);ax.view_init(elev=15,azim=65);ax.set_title('Schuin — bovenarm- en borstkasassen',fontsize=11)
    values=' | '.join(f'{s}: {pose["audit"][s]["direct_elevation_deg"]:.2f}°' for s in ('left','right'))
    fig.suptitle(pose['title']+'\nElevatie uit schouder–ellebooglijn: '+values,fontsize=15)
    fig.text(.5,.025,'S/E: geschatte schouder-/elleboogcentra • Geel: ongecontroleerde mesh-punten • Groene stippellijn: borstkas-neerwaarts\nAssen: X rood (voor), Y groen (op), Z blauw (rechts). Display volgt de proxy-borstkas, geen gemeten zwaartekracht. Geen ISB-validatie.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.065,1,.93));fig.savefig(target,dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    poses,files,error=load_poses(args.root)
    args.output.mkdir(parents=True,exist_ok=False)
    count,ranges=interactive(poses,args.output/'calibration.html')
    for pose in poses: static_views(pose,args.output/(pose['key']+'-views.png'))
    report=dict(status='visualization_of_unvalidated_calibration',landmarks_recomputed_from_exact_triangles=True,
        max_frame0_landmark_barycentric_error_m=error,coordinate_transform='(p - Chest) @ thorax @ DISPLAY.T, DISPLAY maps [anterior,superior,right] to [right,anterior,superior]. Separate thorax basis per pose; full mesh unmodified.',
        units='meters and degrees',interactive_traces=count,pose_trace_ranges=ranges,
        vertices_per_pose=len(poses[0]['vertices']),triangles_per_pose=len(poses[0]['faces']),
        poses={p['key']:p['audit'] for p in poses},
        limitations=['No measured anatomical zero pose or gravity alignment.','No IJ/C7/PX/T8 landmarks.','Mesh candidates anatomically unverified.','XLO predicted joint centers and MID mesh; existing discrepancy up to ~1.02 mm.','Shared GEM-X source; no independent ground truth.','No glenohumeral/scapular measurement.'],
        input_sha256={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in files.items()},
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.output/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
