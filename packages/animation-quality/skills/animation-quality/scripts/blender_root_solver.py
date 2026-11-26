"""CPU constrained smoothing of authored root translations; no pose synthesis."""
import json, sys
import numpy as np
from scipy.optimize import lsq_linear
from scipy.sparse import eye, diags, vstack

def metrics(p,dt):
    a=np.diff(p,n=2,axis=0)/dt**2; j=np.diff(p,n=3,axis=0)/dt**3
    return {'acceleration_rms':float(np.sqrt(np.mean(np.sum(a*a,axis=1)))), 'jerk_rms':float(np.sqrt(np.mean(np.sum(j*j,axis=1))))}

def solve(p, fps, radius, anchors=()):
    p=np.asarray(p,dtype=float); n=len(p)
    if p.shape!=(n,3) or not 6<=n<=2000 or not np.isfinite(p).all() or not np.isfinite([fps,radius]).all() or not 0<fps<=240 or radius<=0: raise ValueError('invalid input')
    fixed=np.unique([0,1,n-2,n-1,*anchors]).astype(int)
    if fixed.min()<0 or fixed.max()>=n: raise ValueError('bad anchor')
    free=np.setdiff1d(np.arange(n),fixed)
    if not len(free): raise ValueError('all samples anchored')
    # Penalize discrete acceleration and jerk, and retain original path.
    d2=diags([1,-2,1],[0,1,2],shape=(n-2,n),dtype=float); d3=diags([-1,3,-3,1],[0,1,2,3],shape=(n-3,n),dtype=float)
    A=vstack([eye(n),2*d2,4*d3],format='csr'); q=p.copy(); bound=radius/np.sqrt(3)
    for k in range(3):
        rhs=np.r_[p[:,k],np.zeros(2*n-5)]-A[:,fixed]@p[fixed,k]
        r=lsq_linear(A[:,free],rhs,bounds=(p[free,k]-bound,p[free,k]+bound),tol=1e-10,lsmr_tol='auto')
        if not r.success: raise ValueError('optimization failed')
        q[free,k]=r.x
    old,new=metrics(p,1/fps),metrics(q,1/fps)
    dev=float(np.linalg.norm(q-p,axis=1).max())
    if dev>radius+1e-9 or not np.array_equal(q[fixed],p[fixed]) or old['jerk_rms']<1e-9 or new['jerk_rms']>=.99*old['jerk_rms'] or new['acceleration_rms']>old['acceleration_rms']+1e-9: raise ValueError('no safe simultaneous improvement')
    return {'positions':q.tolist(),'before':old,'after':new,'max_deviation':dev,'anchors':fixed.tolist()}

if __name__=='__main__':
    data=json.load(sys.stdin); print(json.dumps(solve(**data),allow_nan=False))
