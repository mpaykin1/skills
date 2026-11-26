"""Compare actual OIDN render against matched high-sample raw Cycles frames.
No temporal denoising claim; measure residual changes including the loop seam.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from lpips_guard import Metric, prepare_pair
from webp_cover import load_manifest, sha


def paired(reference, candidate):
    rp, cp = Path(reference).resolve(), Path(candidate).resolve()
    if rp.parent != cp.parent or rp == cp:
        raise ValueError('Use different render manifests in the same scene directory')
    r, rf, rt, rh = load_manifest(rp)
    c, cf, ct, ch = load_manifest(cp, allow_unreviewed_oidn=True)
    for k in ('scene', 'sceneSHA256', 'inputSHA256', 'renderer', 'blenderVersion'):
        if not r.get(k) or r[k] != c.get(k): raise ValueError('Unmatched render: '+k)
    if r['renderer'] != 'Blender Cycles': raise ValueError('Require real Cycles manifests')
    for name, h in r['inputSHA256'].items():
        p=(rp.parent/name).resolve()
        if not p.is_relative_to(rp.parent) or not p.is_file() or sha(p)!=h:
            raise ValueError('Changed scene input: '+name)
    rs, cs = r['renderSettings'], c['renderSettings']
    if rs.get('denoise')!='off' or cs.get('denoise')!='oidn' or cs.get('denoiser')!='OPENIMAGEDENOISE':
        raise ValueError('Require undenoised reference and actual OIDN candidate')
    if cs.get('guides')!='RGB_ALBEDO_NORMAL' or cs.get('prefilter')!='ACCURATE' or cs.get('quality')!='HIGH':
        raise ValueError('Unexpected OIDN settings')
    for k in ('seed','adaptiveSampling','device','viewTransform'):
        if k not in rs or rs[k]!=cs.get(k): raise ValueError('Different sampling/color setup: '+k)
    for k in ('colorManagement','outputEncoding'):
        if rs.get(k)!=cs.get(k): raise ValueError('Different OCIO color setup: '+k)
    if rs['device']!='CPU' or rs['adaptiveSampling'] is not False or not 1<=cs['samples']<=rs['samples']<=512:
        raise ValueError('Require CPU fixed sampling and a reference at least as dense')
    if rt!=ct or len(rf)!=len(cf) or any(x.size!=y.size for x,y in zip(rf,cf)):
        raise ValueError('Unmatched frame timing or dimensions')
    return r,c,rf,cf,rh,ch


def residuals(reference,candidate):
    previous=first=None; worst=0.
    for x,y in zip(reference,candidate):
        a,b=np.asarray(x,dtype=np.float32)/255.,np.asarray(y,dtype=np.float32)/255.
        if not np.array_equal(a[:,:,3],b[:,:,3]): raise ValueError('Alpha changed; retain raw render')
        residual=(b[:,:,:3]-a[:,:,:3])*a[:,:,3:]
        if first is None: first=residual
        if previous is not None: worst=max(worst,float(np.abs(residual-previous).mean()))
        previous=residual
    return max(worst,float(np.abs(previous-first).mean()))


def review(a):
    for value in (a.max_lpips,a.max_temporal_drift):
        if not math.isfinite(value) or value<0: raise ValueError('Use calibrated nonnegative thresholds')
    if not a.calibration_id.strip() or not a.visual_approval_id.strip(): raise ValueError('Calibration and visual approval IDs required')
    rp,cp,out=map(lambda p:Path(p).resolve(),(a.reference,a.candidate,a.out))
    if out.parent!=cp.parent or out.exists(): raise ValueError('Output must be a new manifest in scene directory')
    r,c,rf,cf,rh,ch=paired(rp,cp)
    drift=residuals(rf,cf)
    if drift>a.max_temporal_drift: raise ValueError('Temporal residual drift exceeds calibrated limit; retain raw render')
    metric=Metric('cpu'); peak=0.
    for x,y in zip(rf,cf):
        pairs,_=prepare_pair(x,y);peak=max(peak,metric(pairs))
        if peak>a.max_lpips: raise ValueError('LPIPS drift exceeds calibrated limit; retain raw render')
    c['denoiseGate']={'status':'accepted','sceneSHA256':c['sceneSHA256'],'candidateHashes':ch,'referenceHashes':rh,
        'referenceManifestSHA256':sha(rp),'candidateManifestSHA256':sha(cp),'metric':metric.provenance,
        'peakLPIPS':peak,'maxLPIPS':a.max_lpips,'temporalResidualDrift':drift,'maxTemporalDrift':a.max_temporal_drift,
        'alphaExact':True,'calibrationId':a.calibration_id,'visualApprovalId':a.visual_approval_id}
    c['status']='denoise-reviewed; encoding and mobile review required'
    with out.open('x',encoding='utf-8') as f: json.dump(c,f,indent=2,ensure_ascii=False);f.write('\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('reference','candidate','out','calibration-id','visual-approval-id'):p.add_argument('--'+k,required=True)
    for k in ('max-lpips','max-temporal-drift'):p.add_argument('--'+k,required=True,type=float)
    review(p.parse_args())
if __name__=='__main__':main()
