"""Explicit intrinsic Y-X-Y branch for a right-shoulder template.

R = Ry(plane) Rx(-elevation) Ry(axial). Axes X anterior, Y superior,
Z right. Left is mirrored with S=diag(1,1,-1) on both sides of R.
At zero/pi elevation, plane and axial are mathematically non-identifiable.
"""
import numpy as np


def unit(vector):
    length=np.linalg.norm(vector,axis=-1,keepdims=True)
    if (length<1e-8).any(): raise ValueError('Degenerate anatomical proxy axis')
    return vector/length


def decompose(relative, side, threshold_deg=10.):
    if side not in ('left','right'): raise ValueError(side)
    r=np.array(relative,copy=True)
    if side=='left':
        mirror=np.diag([1.,1.,-1.]); r=mirror@r@mirror
    elevation=np.arccos(np.clip(r[...,1,1],-1.,1.))
    sine=np.sin(elevation)
    plane=np.arctan2(-r[...,0,1],-r[...,2,1])
    axial=np.arctan2(-r[...,1,0],r[...,1,2])
    singular=np.abs(sine)<1e-7
    valid=(elevation>np.deg2rad(threshold_deg)) & (elevation<np.pi-np.deg2rad(threshold_deg)) & ~singular
    plane=np.where(singular,np.nan,plane); axial=np.where(singular,np.nan,axial)
    return np.rad2deg(np.stack([plane,elevation,axial],axis=-1)),valid,singular


def unwrap_runs(degrees,valid):
    """Never bridge an unidentifiable interval or fabricate a value within it."""
    result=np.full_like(degrees,np.nan)
    edges=np.diff(np.r_[False,valid,False].astype(int))
    for start,end in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
        result[start:end]=np.rad2deg(np.unwrap(np.deg2rad(degrees[start:end])))
    return result


def longest_run(valid):
    edges=np.diff(np.r_[False,valid,False].astype(int))
    runs=list(zip(np.where(edges==1)[0],np.where(edges==-1)[0]))
    return max(runs,key=lambda x:x[1]-x[0]) if runs else (0,0)
