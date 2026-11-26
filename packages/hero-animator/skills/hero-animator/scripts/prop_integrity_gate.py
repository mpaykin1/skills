#!/usr/bin/env python3
"""Structural gate for complete isolated RGBA world objects, never panorama fragments.
Heuristics supplement a visual silhouette review; they cannot certify missing branches.
"""
import argparse,hashlib,json,math
from pathlib import Path
from PIL import Image

def longest_run(values):
    best=run=0
    for v in values:
        run=run+1 if v else 0;best=max(best,run)
    return best

def validate_image(im,role='complete-prop',margin_fraction=.02):
    if role!='complete-prop':raise ValueError('BLOCKED: panorama/background fragments are not independent world props')
    if im.mode!='RGBA':raise ValueError('BLOCKED: true RGBA required')
    w,h=im.size
    if min(w,h)<64:raise ValueError('BLOCKED: insufficient prop resolution')
    alpha=im.getchannel('A');lo,hi=alpha.getextrema()
    if lo!=0 or hi<240:raise ValueError('BLOCKED: transparent exterior and solid painted interior required')
    mask=alpha.point(lambda a:255 if a>=16 else 0);bbox=mask.getbbox()
    if bbox is None:raise ValueError('BLOCKED: empty silhouette')
    l,t,r,b=bbox;margin=max(4,math.ceil(min(w,h)*margin_fraction))
    pads=[l,t,w-r,h-b]
    if min(pads)<margin:raise ValueError('BLOCKED: silhouette touches/approaches image boundary; do not hide it by padding a clipped source')
    coverage=sum(mask.histogram()[1:])/(w*h)
    if not .005<coverage<.70:raise ValueError('BLOCKED: empty object or opaque background rectangle')
    m=mask.load()
    runs={'top':longest_run(m[x,t]>0 for x in range(l,r)),
          'bottom':longest_run(m[x,b-1]>0 for x in range(l,r)),
          'left':longest_run(m[l,y]>0 for y in range(t,b)),
          'right':longest_run(m[r-1,y]>0 for y in range(t,b))}
    for edge,n in runs.items():
        limit=max(14,math.ceil((w if edge in ['top','bottom'] else h)*.025))
        if n>limit:raise ValueError('BLOCKED: suspicious straight silhouette termination at '+edge+'; inspect/redraw, never blur to conceal')
    return {'status':'PROP STRUCTURE PASS / VISUAL REVIEW REQUIRED','size':[w,h],'bbox':list(bbox),'margins':pads,'coverage':round(coverage,6),'boundaryRuns':runs}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('image',type=Path);p.add_argument('--role',default='complete-prop');p.add_argument('--margin',type=float,default=.02);a=p.parse_args()
    with Image.open(a.image) as im:r=validate_image(im,a.role,a.margin)
    r['sha256']=hashlib.sha256(a.image.read_bytes()).hexdigest();print(json.dumps(r,indent=2))
if __name__=='__main__':main()
