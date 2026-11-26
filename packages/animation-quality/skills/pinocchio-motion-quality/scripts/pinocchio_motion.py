"""Native Pinocchio fixed-base scalar-joint QA, with existing OpenSim/SciPy candidate solver."""
import argparse, hashlib, importlib.metadata, json, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np


def require(ok, msg):
    if not ok: raise ValueError(msg)


def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def solver():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'opensim-motion-quality'/'scripts'))
    import opensim_motion
    return opensim_motion


def urdf_joints(path):
    require(path.stat().st_size<=2*1024*1024,'URDF too large')
    raw=path.read_bytes(); require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(),'external declarations unsupported')
    root=ET.fromstring(raw); require(root.tag=='robot','plain URDF required')
    require(not any(e.tag in ('mimic','gazebo','plugin','transmission','include') for e in root.iter()),'unsupported constraints/extensions')
    out={}
    for j in root.findall('joint'):
        name=j.attrib['name']; typ=j.attrib['type']; require(typ in ('fixed','revolute','prismatic'),'scalar bounded joints only')
        if typ=='fixed': continue
        require(name not in out,'duplicate joint name'); lim=j.find('limit'); require(lim is not None,'missing joint limits')
        lo,hi=float(lim.attrib['lower']),float(lim.attrib['upper']); require(np.isfinite([lo,hi]).all() and lo<hi,'finite limits required')
        out[name]=(lo,hi)
    require(0<len(out)<=128,'unsupported DOF count'); return out


def compare_candidate(x,y,col,locked,radius):
    require(x.shape==y.shape and np.isfinite(y).all(),'candidate shape/finite')
    require(np.array_equal(np.delete(x,col,axis=1),np.delete(y,col,axis=1)),'other joint changed')
    require(np.array_equal(x[locked],y[locked]),'authored anchors changed')
    require(0<radius<=.05 and np.max(np.abs(x-y))<=radius+1e-10,'maximum correction exceeded')


def metrics(pos,reference,contacts,tau=None):
    require(pos.shape==reference.shape and pos.ndim==3 and pos.shape[-1]==3 and np.isfinite(pos).all() and np.isfinite(reference).all(),'marker arrays invalid')
    err=np.linalg.norm(pos-reference,axis=-1)
    d={'marker_rms_m':np.sqrt(np.mean(err**2,axis=0)).tolist(),'marker_p95_m':np.percentile(err,95,axis=0).tolist(),'contacts':[]}
    for c in contacts:
        p=pos[c['start']:c['end']+1,c['marker_index']]; d['contacts'].append(float(np.max(np.linalg.norm(p-p[0],axis=-1))))
    if tau is not None:
        require(tau.ndim==2 and len(tau)==len(pos) and np.isfinite(tau).all(),'invalid inverse dynamics')
        d['demand_rms_native']=np.sqrt(np.mean(tau**2,axis=0)).tolist(); d['demand_peak_native']=np.max(np.abs(tau),axis=0).tolist()
    return d


def nonregress(a,b):
    require(a.keys()==b.keys(),'metric contract changed')
    for k in a:
        x,y=np.asarray(a[k]),np.asarray(b[k]); require(x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all(),'invalid metric')
        tol=1e-6 if not k.startswith('demand') else 1e-6+0.01*np.abs(x)
        require(np.all(y<=x+tol),'regression: '+k)


def native(path,names,t,x,markers,limits,dynamics):
    # No synthetic fallback. Correct distribution is pin (not pinocchio).
    importlib.metadata.version('pin')
    import pinocchio as pin
    m=pin.buildModelFromUrdf(str(path)); d=m.createData()
    require(m.nq==m.nv==len(names) and set(list(m.names)[1:])==set(names),'fixed-base scalar URDF/CSV mismatch')
    order=[]
    for k in names:
        j=m.joints[m.getJointId(k)]; require(j.nq==j.nv==1 and j.idx_q==j.idx_v,'non-scalar joint'); order.append(j.idx_q)
    q=np.empty_like(x); q[:,order]=x
    for i,k in enumerate(names):
        lo,hi=limits[k]; require(np.all((x[:,i]>=lo)&(x[:,i]<=hi)),'joint outside limits: '+k)
    fids=[m.getFrameId(k) for k in markers]; require(len(set(fids))==len(fids) and all(i<m.nframes for i in fids),'unknown/duplicate marker frame')
    dt=t[1]-t[0]; v=np.gradient(q,dt,axis=0,edge_order=2); a=np.gradient(v,dt,axis=0,edge_order=2)
    pos=[]; tau=[]
    for i,row in enumerate(q):
        pin.forwardKinematics(m,d,row); pin.updateFramePlacements(m,d)
        pos.append([np.array(d.oMf[f].translation).copy() for f in fids])
        if dynamics: tau.append(np.array(pin.rnea(m,d,row,v[i],a[i])).copy()[order])
    return np.asarray(pos),np.asarray(tau) if dynamics else None


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('model',type=Path);p.add_argument('motion',type=Path);p.add_argument('reference',type=Path);p.add_argument('spec',type=Path);p.add_argument('--output',type=Path); z=p.parse_args()
    s=json.loads(z.spec.read_text()); require(s['rights_confirmed'] is True and s['mapping_reviewed'] is True and s['mode']=='once' and s['units']=='native-rad-m','reviewed one-shot source required')
    for key,path in [('model_sha256',z.model),('motion_sha256',z.motion),('reference_sha256',z.reference)]: require(sha(path)==s[key],'hash mismatch: '+key)
    lim=urdf_joints(z.model); qmod=solver(); names,t,x=qmod.read_motion(z.motion); require(set(names)==set(lim),'all native joints required')
    require(z.reference.stat().st_size<=32*1024**2,'reference too large')
    ref=json.loads(z.reference.read_text()); markers=ref['frame_names']; require(len(markers)>=3 and len(set(markers))==len(markers) and ref['units']=='m' and ref['axes']=='urdf-world' and ref['hero_id']==s['hero_id'] and ref['clip']==s['clip'],'calibrated reference mismatch')
    require(np.array_equal(np.asarray(ref['time']),t),'reference timeline mismatch'); target=np.asarray(ref['positions'],float); require(target.shape==(len(t),len(markers),3) and np.isfinite(target).all(),'reference shape')
    contacts=s['contacts']; require(contacts or s.get('no_ground_contact_confirmed') is True,'explicit contact declaration required')
    locks=set(s['anchors'])|{0,1,len(t)-2,len(t)-1}; require(all(type(i)==int and 0<=i<len(t) for i in locks),'invalid anchors')
    for c in contacts:
        lo,hi,j=c['start'],c['end'],c['marker_index']; require(all(type(i)==int for i in (lo,hi,j)) and 0<=lo<hi<len(t) and 0<=j<len(markers),'invalid contact'); locks.update(range(lo,hi+1))
    locked=sorted(locks); dyn=s.get('unloaded_inverse_dynamics_confirmed') is True; require(not dyn or (not contacts and s.get('inertia_and_gravity_reviewed') is True),'inverse dynamics restricted to reviewed unloaded fixed-base motion')
    a,ta=native(z.model,names,t,x,markers,lim,dyn); before=metrics(a,target,contacts,ta); result={'backend':'native-pinocchio','version':importlib.metadata.version('pin'),'status':'diagnostics_only','baseline':before}
    if z.output:
        require(s['confirm_unintended_jitter'] is True,'explicit unwanted jitter confirmation'); j=names.index(s['edited_joint']); radius=float(s['radius_native']); y=x.copy(); y[:,j]=qmod.smooth(x[:,j],t[1]-t[0],locked,radius); compare_candidate(x,y,j,locked,radius)
        b,tb=native(z.model,names,t,y,markers,lim,dyn); after=metrics(b,target,contacts,tb); nonregress(before,after)
        result.update(status='candidate_only',after=after,kinematic_before=qmod.kinematic_metrics(x[:,j],t[1]-t[0]),kinematic_after=qmod.kinematic_metrics(y[:,j],t[1]-t[0]))
        with z.output.open('x') as f: np.savetxt(f,np.column_stack([t,y]),delimiter=',',header=','.join(['time']+names),comments='',fmt='%.17g')
    print(json.dumps(result,allow_nan=False))

if __name__=='__main__': main()
