"""CPU OpenSim 4.6 kinematic quality gate; optional anchored SciPy candidate.
Native model required. CSV columns: time + exact coordinate names, rad/metres.
No model editing, force estimation, or automatic game publication.
"""
import argparse, csv, hashlib, importlib.metadata, json, math
from pathlib import Path
import numpy as np
from scipy.sparse import diags, vstack, eye
from scipy.optimize import lsq_linear


def require(ok,msg):
    if not ok: raise ValueError(msg)


def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def read_motion(p):
    require(Path(p).stat().st_size <= 32*1024**2,'motion too large')
    with Path(p).open(newline='',encoding='utf-8-sig') as f:
        r=csv.reader(f); h=next(r); require(h and h[0]=='time' and len(h)>1 and len(set(h))==len(h),'exact unique coordinate columns required')
        rows=[]
        for line in r:
            require(len(line)==len(h) and len(rows)<1800,'invalid shape or frame budget')
            rows.append([float(x) for x in line])
    a=np.array(rows,float); require(len(a)>=8 and np.isfinite(a).all(),'finite clip >=8 frames required')
    dt=np.diff(a[:,0]); require(np.all(dt>0) and np.allclose(dt,dt[0],rtol=1e-5,atol=1e-8) and 1/120-1e-8<=dt[0]<=.1+1e-8,'CFR 10–120 fps required')
    return h[1:],a[:,0],a[:,1:]


def kinematic_metrics(x,dt):
    a=np.diff(x,n=2,axis=0)/dt**2; j=np.diff(x,n=3,axis=0)/dt**3
    return {'accel_rms':float(np.sqrt(np.mean(a*a))), 'jerk_rms':float(np.sqrt(np.mean(j*j)))}


def smooth(x,dt,locked,radius):
    """One scalar native coordinate, bounded least squares, exact anchors."""
    n=len(x); require(n>=8 and np.isfinite(x).all() and 0<radius<=.05,'invalid trajectory/radius (max .05 native units)')
    lock=np.array(sorted(set(locked)|{0,1,n-2,n-1}),int)
    require(np.all((lock>=0)&(lock<n)),'invalid anchors')
    free=np.setdiff1d(np.arange(n),lock); require(len(free)>0,'no free samples')
    d2=diags([1.,-2.,1.],[0,1,2],shape=(n-2,n),format='csr')
    d3=diags([-1.,3.,-3.,1.],[0,1,2,3],shape=(n-3,n),format='csr')
    A=vstack([eye(n,format='csr'),5*d2,8*d3],format='csr'); b=np.r_[x,np.zeros(2*n-5)]
    b=b-A[:,lock]@x[lock]; fit=lsq_linear(A[:,free],b,bounds=(x[free]-radius,x[free]+radius),tol=1e-10,max_iter=200)
    require(fit.success,'solver failed'); y=x.copy(); y[free]=fit.x
    require(np.array_equal(x[lock],y[lock]) and np.max(abs(x-y))<=radius+1e-10,'anchor/radius failed')
    a,c=kinematic_metrics(x,dt),kinematic_metrics(y,dt)
    require(a['jerk_rms']>1e-10 and c['jerk_rms']<.99*a['jerk_rms'] and c['accel_rms']<=a['accel_rms']+1e-10,'no improvement')
    return y


def reference_targets(path,spec,t):
    require(sha(path)==spec['capture_file_sha256'],'capture hash mismatch')
    d=json.loads(Path(path).read_text()); require(d['schema']=='freemocap-control-targets-v1' and d['axes']=='blender-z-up-metres','expected existing FreeMoCap bridge output')
    require(d['hero_id']==spec['hero_id'] and d['clip']==spec['clip'] and d['interpolated_marker_frames']==0,'identity/clip mismatch or filled capture gaps')
    frames=d['frames']; require(len(frames)==len(t) and np.allclose([f['time'] for f in frames],t,rtol=0,atol=1e-7) and [f['frame'] for f in frames]==list(range(len(t))),'capture timeline mismatch')
    R=np.asarray(spec['blender_to_opensim'],float); b=np.asarray(spec['origin_offset_m'],float)
    require(R.shape==(3,3) and b.shape==(3,) and np.isfinite(b).all() and np.allclose(R@R.T,np.eye(3),atol=1e-6) and abs(np.linalg.det(R)-1)<1e-6,'proper calibrated rotation + translation required')
    mapping=spec['marker_map']; require(len(mapping)>=3 and len(set(mapping.values()))==len(mapping),'at least 3 explicit one-to-one corresponding markers')
    a=np.array([[f['targets'][mapping[m]] for m in mapping] for f in frames],float)
    require(a.shape==(len(t),len(mapping),3) and np.isfinite(a).all(),'invalid calibrated capture')
    return list(mapping),a@R.T+b


def native_positions(model_path,names,t,x,markers):
    # Deliberately no fallback/mock. The official model evaluates each pose.
    require(importlib.metadata.version('opensim')=='4.6','use official isolated OpenSim 4.6 environment')
    import opensim as osim
    model=osim.Model(str(model_path)); state=model.initSystem(); cs=model.getCoordinateSet(); ms=model.getMarkerSet()
    require(cs.getSize()==len(names) and set(names)=={cs.get(i).getName() for i in range(cs.getSize())},'all exact model coordinates required')
    coords=[cs.get(n) for n in names]; mk=[ms.get(n) for n in markers]; out=[]
    for i,row in enumerate(x):
        state.setTime(float(t[i]))
        for c,v in zip(coords,row):
            require(c.getRangeMin()-1e-8<=v<=c.getRangeMax()+1e-8,'model coordinate outside authored range: '+c.getName())
            c.setValue(state,float(v),False)
        model.assemble(state); model.realizePosition(state)
        actual=np.array([c.getValue(state) for c in coords]); require(np.isfinite(actual).all() and np.allclose(actual,row,rtol=0,atol=1e-6),'assembly changed submitted coordinates; constrained model needs native review')
        out.append([[float(m.getLocationInGround(state).get(k)) for k in range(3)] for m in mk])
    a=np.array(out);require(np.isfinite(a).all(),'invalid model evaluation'); return a


def marker_metrics(a,ref,markers,contacts):
    err=np.linalg.norm(a-ref,axis=-1)
    results={'rms_m':float(np.sqrt(np.mean(err**2))), 'p95_m':float(np.percentile(err,95)), 'per_marker_rms_m':{k:float(np.sqrt(np.mean(err[:,j]**2))) for j,k in enumerate(markers)},'contacts':{}}
    for i,c in enumerate(contacts):
        lo,hi=c['start'],c['end']; require(type(lo)==type(hi)==int and 0<=lo<hi<len(a),'invalid contact interval')
        j=markers.index(c['marker']); p=a[lo:hi+1,j]; target=ref[lo:hi+1,j]; slip=np.linalg.norm(p-p[0],axis=1); residual=np.linalg.norm(p-target,axis=1)
        results['contacts'][str(i)]={'max_displacement_m':float(slip.max()),'max_error_m':float(residual.max())}
    return results


def nonregress(b,a):
    # Tiny tolerance for numerical assembly only; not a fit-quality pass.
    for k in ('rms_m','p95_m'): require(a[k]<=b[k]+1e-6,'marker fit worsened: '+k)
    for k,v in b['per_marker_rms_m'].items(): require(a['per_marker_rms_m'][k]<=v+1e-6,'marker fit worsened: '+k)
    for k,v in b['contacts'].items():
        for m,z in v.items(): require(a['contacts'][k][m]<=z+1e-6,'support contact worsened')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path);p.add_argument('motion',type=Path);p.add_argument('capture',type=Path);p.add_argument('spec',type=Path);p.add_argument('--output',type=Path);p.add_argument('--confirm-trusted-calibrated-model-and-mapping',action='store_true',required=True);args=p.parse_args()
    spec=json.loads(args.spec.read_text()); require(spec['rights_confirmed'] is True and spec['coordinate_units']=='native-rad-m' and spec['mode']=='once','approved one-shot native rad/m clip only')
    model_hash, motion_hash=sha(args.model),sha(args.motion);require(model_hash==spec['model_sha256'] and motion_hash==spec['motion_sha256'],'source SHA mismatch')
    names,t,x=read_motion(args.motion); markers,ref=reference_targets(args.capture,spec,t); contacts=spec['contacts']; require(contacts or spec.get('no_ground_contact_confirmed') is True,'explicit contacts required')
    before=marker_metrics(native_positions(args.model,names,t,x,markers),ref,markers,contacts)
    result={'backend':'OpenSim-4.6-native','before':before,'status':'kinematic_diagnostics_only'}
    if args.output:
        require(spec['confirm_unintended_jitter'] is True,'author confirmation of unintended jitter required'); locks=list(spec['anchors']);require(all(type(i)==int and 0<=i<len(t) for i in locks),'invalid event anchors')
        for c in contacts:locks.extend(range(c['start'],c['end']+1))
        targets=spec['coordinate_radii']; require(targets and set(targets)<=set(names),'explicit editable coordinates required');y=x.copy(); m={};dt=t[1]-t[0]
        for name,r in targets.items():
            j=names.index(name);y[:,j]=smooth(x[:,j],dt,locks,float(r));m[name]={'before':kinematic_metrics(x[:,j],dt),'after':kinematic_metrics(y[:,j],dt)}
        after=marker_metrics(native_positions(args.model,names,t,y,markers),ref,markers,contacts);nonregress(before,after)
        require(sha(args.model)==model_hash and sha(args.motion)==motion_hash and sha(args.capture)==spec['capture_file_sha256'],'source changed')
        with args.output.open('x',newline='') as f:
            w=csv.writer(f);w.writerow(['time']+names);w.writerows(np.column_stack([t,y]))
        result.update(status='candidate_requires_visual_retarget_review',after=after,coordinate_metrics=m)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__': main()
