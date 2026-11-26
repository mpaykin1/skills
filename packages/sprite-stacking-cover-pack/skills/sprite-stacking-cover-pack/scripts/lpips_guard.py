"""Perceptual candidate comparison. Never substitutes pixel distance for LPIPS."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_rgba(path, crop=None):
    with Image.open(path) as im:
        img = ImageOps.exif_transpose(im).convert('RGBA')
    if crop is not None:
        if len(crop) != 4 or any(not isinstance(x, int) for x in crop):
            raise ValueError('crop must be four integer pixel coordinates')
        x0,y0,x1,y1 = crop
        if not (0 <= x0 < x1 <= img.width and 0 <= y0 < y1 <= img.height):
            raise ValueError('crop outside image')
        img = img.crop(crop)
    return img


def prepare_pair(a,b,max_side=768):
    # Preserve aspect ratio; unlike catalog comparison, matched views must be aligned.
    if abs(math.log((a.width/a.height)/(b.width/b.height))) > .025:
        raise ValueError('Images have different aspect ratios; supply corresponding crops')
    ratio = min(1.,max_side/max(a.size))
    size = tuple(max(32,round(x*ratio)) for x in a.size)
    if min(a.size)<32 or min(b.size)<32:
        raise ValueError('Image crop too small for perceptual comparison')
    a,b = [x.resize(size,Image.Resampling.LANCZOS) for x in (a,b)]
    aa,bb = [np.asarray(x,dtype=np.float32)/255. for x in (a,b)]
    # Two backgrounds avoid hiding lost opacity or light/dark transparent detail.
    backgrounds = (.08,.85) if min(aa[:,:,3].min(),bb[:,:,3].min())<1 else (.08,)
    pairs=[]
    for bg in backgrounds:
        pair = [(x[:,:,:3]*x[:,:,3:]+bg*(1-x[:,:,3:]))*2-1 for x in (aa,bb)]
        pairs.append(tuple(np.ascontiguousarray(x.transpose(2,0,1)[None]) for x in pair))
    return pairs,float(np.abs(aa[:,:,3]-bb[:,:,3]).mean())


class Metric:
    def __init__(self,device):
        import torch
        if device=='cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable')
        # torchvision's pretrained AlexNet resolves this exact local checkpoint.
        # No surprise model download; reject an absent or invalid file.
        checkpoint=Path(torch.hub.get_dir())/'checkpoints'/'alexnet-owt-7be5be79.pth'
        if not checkpoint.is_file() or not sha(checkpoint).startswith('7be5be79'):
            raise RuntimeError('Install the official AlexNet checkpoint into torch hub cache first; no random weights or fallback metric')
        import lpips
        self.torch=torch; self.device=device
        self.model=lpips.LPIPS(net='alex',version='0.1',pretrained=True,pnet_rand=False,eval_mode=True,verbose=False).to(device).eval()
        self.provenance={'metric':'LPIPS','network':'alex','modelVersion':'0.1','packageVersion':importlib.metadata.version('lpips'),'trunkSHA256':sha(checkpoint)}

    def __call__(self,pairs):
        t=self.torch
        with t.inference_mode():
            scores=[float(self.model(t.from_numpy(a).to(self.device),t.from_numpy(b).to(self.device)).item()) for a,b in pairs]
        if not all(math.isfinite(x) for x in scores): raise ValueError('Non-finite metric')
        return max(scores)


ROUTES={
 'silhouette':'SAM 2.1 mask review, TRELLIS.2 reconstruction and Open3D geometry',
 'geometry':'TRELLIS.2 / Infinigen / Open3D; check O-Voxel alignment and thin detail',
 'material':'Material Maker and O-Voxel material channels; retain geometry and alpha',
 'atmosphere':'OpenVDB density, lighting and scene composition',
 'cover':'Review hero, architecture, palette, camera and scene layout',
 'compression':'Retain uncompressed render; retry encoder settings rather than modifying assets',
}


def evaluate(manifest,root,metric):
    """Manifest contains explicit paired views, reviewed regions and catalog alternatives."""
    root=Path(root).resolve()
    def path(p):
        q=(root/p).resolve()
        if not q.is_relative_to(root) or not q.is_file(): raise ValueError('Missing or out-of-root image: '+str(p))
        return q
    thresholds=manifest.get('thresholds',{})
    for k,v in thresholds.items():
        if k not in ('matchedMax','duplicateMax','alphaMax') or isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0:
            raise ValueError('Invalid calibrated threshold '+k)
    rows=[]; flags=[]
    pairs=manifest.get('pairs',[])
    if not pairs: raise ValueError('At least one comparison pair required')
    for i,p in enumerate(pairs):
        mode=p['mode']; kind=p.get('kind','cover')
        if mode not in ('matched','catalog') or kind not in ROUTES: raise ValueError('Unknown pair type')
        a,b=path(p['candidate']),path(p['reference'])
        if mode=='matched' and p.get('aligned') is not True:
            raise ValueError('Matched mode requires confirmed matching view/composition')
        ai,bi=load_rgba(a,p.get('candidateCrop')),load_rgba(b,p.get('referenceCrop'))
        inputs,alpha=prepare_pair(ai,bi)
        score=float(metric(inputs))
        if not math.isfinite(score): raise ValueError('Non-finite score')
        exact=np.array_equal(np.asarray(ai),np.asarray(bi))
        row={'id':p.get('id',str(i)), 'mode':mode,'kind':kind,'candidate':p['candidate'],'reference':p['reference'],'candidateSHA256':sha(a),'referenceSHA256':sha(b),'lpips':score,'meanAlphaError':alpha,'pixelIdentical':bool(exact),'feedback':ROUTES[kind]}
        t=thresholds.get('matchedMax' if mode=='matched' else 'duplicateMax')
        reasons=[]
        if mode=='catalog' and (exact or (t is not None and score<=t)): reasons.append('possible duplicate')
        if mode=='matched' and t is not None and score>t: reasons.append('perceptual drift')
        if mode=='matched' and 'alphaMax' in thresholds and alpha>thresholds['alphaMax']: reasons.append('alpha drift')
        row['flags']=reasons; rows.append(row)
        if reasons: flags.append(row['id'])
    # Semantic uniqueness is separate from LPIPS, never inferred from pixel distance.
    candidate=manifest.get('identity',{})
    required=('heroId','paletteId','architectureId')
    semantic=[]
    if any(not isinstance(candidate.get(k),str) or not candidate[k].strip() for k in required):
        semantic.append('missing reviewed candidate identity')
    else:
        for other in manifest.get('catalogIdentities',[]):
            for k in required:
                if not isinstance(other.get(k),str) or not other[k].strip():
                    semantic.append(f"{other.get('id','unknown')}: missing {k}")
                elif candidate[k].strip().casefold()==other[k].strip().casefold():
                    semantic.append(f"{other.get('id','unknown')}: repeated {k}")
    return {'schema':'cover-pack-perceptual/1','metric':metric.provenance,'thresholds':thresholds,'calibrationId':manifest.get('calibrationId'),'comparisons':rows,'flaggedPairs':flags,'semanticFlags':semantic,'status':'review-required','note':'LPIPS is a distance, not artistic quality or a percentage; no automatic ready. Catalog thresholds need calibration and manual semantic review.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    a=p.parse_args();m=Path(a.manifest).resolve();o=Path(a.out)
    if o.exists():raise FileExistsError(o)
    result=evaluate(json.loads(m.read_text(encoding='utf-8')),m.parent,Metric(a.device))
    o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
