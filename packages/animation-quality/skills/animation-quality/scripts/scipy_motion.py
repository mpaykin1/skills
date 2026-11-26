"""Constrained CPU retiming of exact, nonorganic, rigid XY cruise motion."""
import argparse, json, tempfile
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import minimize
from PIL import Image
from quality import load, reduced
from opencv_motion import translation_positions, sequence


def metrics(d, t, cyc):
    v=d/(t[:,None]/1000.)
    speed=np.linalg.norm(v,axis=1)
    if cyc:
        dv=np.roll(v,-1,axis=0)-v; dt=(t+np.roll(t,-1))/2000.
    else:
        dv=np.diff(v,axis=0); dt=(t[:-1]+t[1:])/2000.
    a=np.linalg.norm(dv/dt[:,None],axis=1)
    return {'speed_cv':float(speed.std()/speed.mean()), 'acceleration_rms_px_s2':float(np.sqrt(np.mean(a*a))), 'acceleration_p95_px_s2':float(np.percentile(a,95))}


def optimize_times(d,t,cyc,minimum):
    n=len(t); total=int(t.sum()); avg=total/n
    if n<4 or n>256 or total<minimum*n or np.min(t)<10: raise ValueError('unsupported segment count or duration budget')
    norm=np.linalg.norm(d,axis=1)
    if np.any(norm==0): raise ValueError('held poses require authored timing')
    unit=d/norm[:,None]; a=unit if cyc else unit[:-1]; b=np.roll(unit,-1,axis=0) if cyc else unit[1:]
    if np.any(np.sum(a*b,axis=1)<np.cos(np.deg2rad(75))): raise ValueError('sharp turns/reversals require authored motion')
    old=metrics(d,t,cyc)
    if old['speed_cv']<.01 or old['acceleration_rms_px_s2']<1e-6: raise ValueError('no significant uneven cruise speed')
    # Normalize units and optimize both tangential consistency and vector acceleration.
    scale=max(old['acceleration_rms_px_s2'],1.)
    def objective(x):
        m=metrics(d,x*avg,cyc)
        return (m['acceleration_rms_px_s2']/scale)**2 + m['speed_cv']**2
    low=minimum/avg; start=np.ones(n)
    result=minimize(objective,start,method='SLSQP',bounds=[(low,n-(n-1)*low)]*n,
                    constraints=[{'type':'eq','fun':lambda x:x.sum()-n}],options={'maxiter':150,'ftol':1e-9})
    if not result.success or not np.isfinite(result.x).all() or abs(result.x.sum()-n)>1e-5: raise ValueError('SciPy optimization did not converge')
    ideal=result.x*avg
    # Integer milliseconds; retain the total exactly and respect the interpolation budget.
    rounded=np.maximum(minimum,np.floor(ideal+1e-8).astype(int)); rem=total-int(rounded.sum())
    if rem<0 or rem>n: raise ValueError('rounding infeasible')
    rounded[np.argsort(-(ideal-rounded),kind='stable')[:rem]]+=1
    new=metrics(d,rounded,cyc)
    if not (new['acceleration_rms_px_s2']<.99*old['acceleration_rms_px_s2'] and new['speed_cv']<old['speed_cv'] and new['acceleration_p95_px_s2']<=old['acceleration_p95_px_s2']+1e-8):
        raise ValueError('no safe simultaneous speed and acceleration improvement')
    return rounded,old,new


def repair(source,output,mode,factor=1):
    source,output=Path(source),Path(output)
    if factor not in (1,2,3,4) or mode not in ('once','loop'): raise ValueError('invalid mode/factor')
    if output.exists() or output.resolve()==source.resolve() or output.suffix.lower() not in ('.png','.apng'): raise ValueError('new lossless APNG path required')
    fs,t,loop=load(source); cyc=mode=='loop'
    if not np.all(t>=10) or not np.all(t==np.rint(t)): raise ValueError('integer durations >=10ms required')
    with Image.open(source) as im:
        if cyc and loop!=0: raise ValueError('infinite loop required')
        if not cyc and not (loop is None or (im.format=='PNG' and loop==1)): raise ValueError('one-shot required')
    pos=translation_positions(fs); t=t.astype(int)
    d=np.roll(pos,-1,axis=0)-pos if cyc else np.diff(pos,axis=0)
    new,old,m=optimize_times(d,t if cyc else t[:-1],cyc,10*factor)
    times=new if cyc else np.r_[new,t[-1]]
    # Independent LK check on identical full frames, same mode and same timeline length.
    images=[reduced(f) for f in fs]; ob=sequence(images,t,cyc); oa=sequence(images,times,cyc)
    if min(ob['tracked_pair_fraction'] or 0,oa['tracked_pair_fraction'] or 0)<.8: raise ValueError('insufficient OpenCV tracking coverage')
    p,q=ob['acceleration_p95'],oa['acceleration_p95']
    if p is None or q is None or q>p+max(.001,.03*p): raise ValueError('independent optical-flow acceleration regression')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        dst=Path(tmp)/'candidate.png'; ims=[Image.fromarray(f) for f in fs]
        ims[0].save(dst,format='PNG',save_all=True,append_images=ims[1:],duration=times.tolist(),loop=0 if cyc else 1,disposal=0,blend=0)
        got,dt,lp=load(dst)
        if len(got)!=len(fs) or any(not np.array_equal(a,b) for a,b in zip(got,fs)) or not np.array_equal(dt,times) or dt.sum()!=t.sum() or lp!=(0 if cyc else 1): raise ValueError('lossless frame/timeline verification failed')
        dst.replace(output)
    return {'output':str(output),'scipy_version':scipy.__version__,'before':old,'after':m,'acceleration_rms_reduction_percent':100*(1-m['acceleration_rms_px_s2']/old['acceleration_rms_px_s2']),'speed_cv_reduction_percent':100*(1-m['speed_cv']/old['speed_cv']),'opencv_acceleration_p95_before':p,'opencv_acceleration_p95_after':q,'duration_ms':int(t.sum()),'frame_count':len(fs),'bitmapflow_factor_budget':factor,'artistic_quality':None}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('output'); p.add_argument('--mode',choices=['once','loop'],required=True); p.add_argument('--bitmapflow-factor',type=int,choices=[1,2,3,4],default=1); p.add_argument('--confirm-rigid-cruise',action='store_true',required=True)
    a=p.parse_args(); print(json.dumps(repair(a.source,a.output,a.mode,a.bitmapflow_factor),indent=2,allow_nan=False))
