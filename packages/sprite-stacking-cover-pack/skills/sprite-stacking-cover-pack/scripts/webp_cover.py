"""Compress actual rendered frames via Pillow's libwebp backend, never source assets."""
import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image, features
from lpips_guard import Metric, prepare_pair


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_manifest(path, *, allow_unreviewed_oidn=False):
    path = Path(path).resolve()
    spec = json.loads(path.read_text(encoding='utf-8'))
    root = path.parent
    scene = (root / spec['scene']).resolve()
    if not scene.is_relative_to(root) or sha(scene) != spec['sceneSHA256']:
        raise ValueError('Missing or changed source scene')
    from ocio_color import read_contract
    expected, color_files = read_contract(json.loads(scene.read_text(encoding='utf-8')), root)
    if expected is not None:
        settings=spec.get('renderSettings',{})
        if settings.get('colorManagement')!=expected or settings.get('outputEncoding')!='sRGB':
            raise ValueError('Missing or changed color-managed render; no double conversion')
        if any(spec.get('inputSHA256',{}).get(k)!=v for k,v in color_files.items()):
            raise ValueError('OCIO config/LUT changed since render')
    frames, durations, hashes = [], [], []
    for item in spec['frames']:
        p = (root / item['path']).resolve()
        if not p.is_relative_to(root) or p.suffix.lower() != '.png':
            raise ValueError('Use original rendered PNG frames within manifest directory')
        h = sha(p)
        if h != item['sha256']:
            raise ValueError('Source frame hash mismatch')
        ms = item['durationMs']
        if type(ms) != int or not 10 <= ms <= 10000:
            raise ValueError('Invalid frame duration in milliseconds')
        with Image.open(p) as im:
            if im.format != 'PNG' or getattr(im, 'n_frames', 1) != 1:
                raise ValueError('Expected one rendered PNG per entry')
            frames.append(im.convert('RGBA'))
        durations.append(ms); hashes.append(h)
    if not 2 <= len(frames) <= 240 or len({f.size for f in frames}) != 1:
        raise ValueError('Expected 2–240 equal-sized frames')
    if not 2000 <= sum(durations) <= 8000:
        raise ValueError('Cover loop must be 2–8 seconds')
    if not 32 <= min(frames[0].size) or max(frames[0].size)>2048:
        raise ValueError('Unsupported cover dimensions')
    if len(set(hashes)) == 1 or all(np.array_equal(np.asarray(f),np.asarray(frames[0])) for f in frames):
        raise ValueError('Static sequence is not an animated cover')
    if spec.get('renderSettings',{}).get('denoise')=='oidn' and not allow_unreviewed_oidn:
        gate=spec.get('denoiseGate',{})
        if (gate.get('status')!='accepted' or gate.get('candidateHashes')!=hashes
            or gate.get('sceneSHA256')!=spec['sceneSHA256'] or not gate.get('calibrationId')
            or not gate.get('visualApprovalId') or gate.get('metric',{}).get('metric')!='LPIPS'):
            raise ValueError('OIDN candidate needs paired LPIPS, alpha, temporal and visual approval before encoding')
    return spec, frames, durations, hashes


def decode(path):
    with Image.open(path) as im:
        if im.format != 'WEBP' or im.info.get('loop') != 0 or im.n_frames < 2:
            raise ValueError('Expected infinitely looping animated WebP')
        frames, times = [], []
        for i in range(im.n_frames):
            im.seek(i); im.load()
            times.append(int(im.info['duration']))
            frames.append(im.convert('RGBA'))
    return frames, times


def compare(source, durations, decoded, decoded_times, metric=None, threshold=None):
    # Compare every overlapping time interval; identical adjacent frames may be coalesced.
    if sum(durations) != sum(decoded_times) or any(t <= 0 for t in decoded_times):
        return None
    i=j=0; a=durations[0]; b=decoded_times[0]; peak=0.
    while i<len(source) and j<len(decoded):
        if source[i].size != decoded[j].size: return None
        x,y=np.asarray(source[i]),np.asarray(decoded[j])
        if not np.array_equal(x[:,:,3],y[:,:,3]): return None
        if metric is None:
            # Invisible RGB under fully transparent pixels is not a displayed color.
            visible=x[:,:,3]>0
            if not np.array_equal(x[:,:,:3][visible],y[:,:,:3][visible]): return None
        else:
            pair,alpha=prepare_pair(source[i],decoded[j])
            score=metric(pair)
            if not math.isfinite(score) or score>threshold: return None
            peak=max(peak,score)
        t=min(a,b);a-=t;b-=t
        if a==0:
            i+=1
            if i<len(source):a=durations[i]
        if b==0:
            j+=1
            if j<len(decoded):b=decoded_times[j]
    return peak if i==len(source) and j==len(decoded) else None


def optimize(manifest, out, device='cpu', max_lpips=None, calibration_id=None, budget=None):
    if not features.check('webp'): raise RuntimeError('Pillow with libwebp support required')
    if max_lpips is not None and (not math.isfinite(max_lpips) or max_lpips<0 or not calibration_id):
        raise ValueError('Lossy search requires a calibrated LPIPS threshold and calibration ID')
    if budget is not None and budget<=0: raise ValueError('Positive budget required')
    spec,frames,durations,hashes=load_manifest(manifest)
    out=Path(out)
    if out.exists(): raise FileExistsError(out)
    metric=Metric(device) if max_lpips is not None else None
    candidates=[(True,100)]+([(False,q) for q in (95,90,85,80,75,65)] if metric else [])
    best=None
    with tempfile.TemporaryDirectory() as td:
        for lossless,q in candidates:
            p=Path(td)/f'{lossless}-{q}.webp'
            frames[0].save(p,format='WEBP',save_all=True,append_images=frames[1:],duration=durations,
                           loop=0,lossless=lossless,quality=q,alpha_quality=100,method=6,background=(0,0,0,0),allow_mixed=False)
            try:
                dst,times=decode(p)
                score=compare(frames,durations,dst,times,None if lossless else metric,max_lpips)
            except (ValueError,OSError,KeyError):
                continue
            if score is None: continue
            n=p.stat().st_size
            if best is None or n<best['bytes']:
                best={'data':p.read_bytes(),'bytes':n,'lossless':lossless,'quality':q,'peakLPIPS':None if lossless else score,'decodedFrameCount':len(dst)}
    if best is None: raise RuntimeError('No valid encoding; keep source frames and revise encoder settings')
    if budget is not None and best['bytes']>budget:
        raise RuntimeError('No valid candidate within byte budget; do not lower fidelity gate')
    out.mkdir(parents=True)
    (out/'cover.webp').write_bytes(best.pop('data'))
    frames[0].save(out/'cover.png')
    result={'schema':'cover-pack-webp/1','sceneSHA256':spec['sceneSHA256'],'sourceFrameSHA256':hashes,
            'sourceDurationMs':durations,'loop':0,'size':list(frames[0].size),'encoder':'Pillow/libwebp',
            'libwebpVersion':features.version('webp'),'colorManagement':spec.get('renderSettings',{}).get('colorManagement'),'outputEncoding':spec.get('renderSettings',{}).get('outputEncoding','legacy-unverified'),'alphaPreserved':True,'timingPreserved':True,
            'lpipsCalibrationId':calibration_id,'lpipsThreshold':max_lpips,'lpipsModel':metric.provenance if metric else None,
            **best,'cover':'cover.webp','poster':'cover.png','coverSHA256':sha(out/'cover.webp'),
            'posterSHA256':sha(out/'cover.png'),'status':'encoding-verified; visual and browser review required'}
    (out/'encoding.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu');p.add_argument('--max-lpips',type=float);p.add_argument('--calibration-id');p.add_argument('--budget-bytes',type=int)
    a=p.parse_args();optimize(a.manifest,a.out,a.device,a.max_lpips,a.calibration_id,a.budget_bytes)

if __name__=='__main__':main()
