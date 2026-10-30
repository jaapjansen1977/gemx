"""Mesh attachments with exact closest-point barycentric coordinates."""
import numpy as np


def attach(point, vertices, faces):
    """Closest point over triangle interiors and edges, including degenerate faces."""
    triangles = vertices[faces]
    a, b, c = triangles.transpose(1, 0, 2)
    u, v = b - a, c - a
    uu = np.sum(u*u, 1); uv = np.sum(u*v, 1); vv = np.sum(v*v, 1)
    w = point - a; wu = np.sum(w*u, 1); wv = np.sum(w*v, 1)
    det = uu*vv - uv*uv
    safe = np.where(det > 1e-20, det, 1.)
    s = (wu*vv - wv*uv)/safe; t = (wv*uu - wu*uv)/safe
    weights = np.stack((1-s-t, s, t), axis=1)
    valid = (det > 1e-20) & (weights >= 0).all(1)
    options = [weights]; distances = [np.where(valid, np.sum((a+s[:,None]*u+t[:,None]*v-point)**2,1), np.inf)]
    for i, j in ((0,1), (1,2), (2,0)):
        start = triangles[:,i]; edge = triangles[:,j]-start
        length = np.sum(edge*edge,1)
        alpha = np.clip(np.sum((point-start)*edge,1)/np.maximum(length,1e-30),0,1)
        bary = np.zeros((len(faces),3)); bary[:,i]=1-alpha; bary[:,j]=alpha
        options.append(bary)
        distances.append(np.sum((start+alpha[:,None]*edge-point)**2,1))
    kind, face = np.unravel_index(np.argmin(distances), (4,len(faces)))
    return int(face), options[kind][face], float(np.sqrt(distances[kind][face]))


def evaluate(vertices, faces, face_ids, barycentric):
    return np.einsum('...lvc,lv->...lc', vertices[..., faces[face_ids], :], barycentric)


def seeds(joints):
    """Heuristic seeds in a neutral pose. Distances in meters, NOT ISB definitions.

    L is anatomical left; U is torso-up; F=L cross U is assumed anterior.
    Surface projection refines attachment, not anatomical correctness.
    """
    left = joints['LeftLeg']-joints['RightLeg']; left /= np.linalg.norm(left)
    up = joints['Chest']-joints['Hips']; up -= left*np.dot(up,left); up /= np.linalg.norm(up)
    forward = np.cross(left,up)
    rows = []
    def add(name,joint,body,offset):
        rows.append(dict(name=name,joint=joint,body=body,seed_m=(joints[joint]+offset).tolist()))
    for side, sign, suffix in [('Left',1,'l'),('Right',-1,'r')]:
        lateral=sign*left
        for tag, depth in [('ASIS',.08),('PSIS',-.07)]:
            add(f'{tag}_{suffix}','Hips','pelvis', .095*lateral+.06*up+depth*forward)
        add(f'acromion_{suffix}',side+'Arm','scapula_'+suffix,.025*lateral+.035*up)
        for tag,direction in [('lateral',1),('medial',-1)]:
            add(f'elbow_epicondyle_{tag}_{suffix}',side+'ForeArm','humerus_'+suffix,direction*.035*lateral)
            add(f'knee_epicondyle_{tag}_{suffix}',side+'Shin','femur_'+suffix,direction*.045*lateral)
            # This MyoFullBody has no separate fibula body: both ankle markers
            # are attached to the rigid tibia/fibula segment represented by tibia.
            add(f'malleolus_{tag}_{suffix}',side+'Foot','tibia_'+suffix,direction*.035*lateral-.015*up)
    return rows
