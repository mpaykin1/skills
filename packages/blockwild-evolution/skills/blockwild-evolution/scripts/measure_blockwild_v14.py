"""Bounded raster detail + optional reference-palette metric, not artistic score.
Requires OpenCV. Compare matched art-probe screenshots only.
"""
import argparse,json
from pathlib import Path
import cv2
p=argparse.ArgumentParser()
p.add_argument('--before-portrait',type=Path,required=True)
p.add_argument('--after-portrait',type=Path,required=True)
p.add_argument('--before-landscape',type=Path,required=True)
p.add_argument('--after-landscape',type=Path,required=True)
p.add_argument('--reference',type=Path)
a=p.parse_args()
ref=cv2.imread(str(a.reference)) if a.reference else None

def detail(before,after):
 a0=cv2.imread(str(before));a1=cv2.imread(str(after))
 if a0 is None or a1 is None or a0.shape!=a1.shape:raise SystemExit('Missing/mismatched aligned frame '+str(before))
 g0=cv2.cvtColor(a0,cv2.COLOR_BGR2GRAY);g1=cv2.cvtColor(a1,cv2.COLOR_BGR2GRAY)
 v0=float(cv2.Laplacian(g0,cv2.CV_64F).var());v1=float(cv2.Laplacian(g1,cv2.CV_64F).var())
 r={'before':round(v0,4),'after':round(v1,4),'detail_change_pct':round((v1/v0-1)*100,3) if v0 else None}
 if ref is not None:
  rr=cv2.resize(ref,(a0.shape[1],a0.shape[0]),interpolation=cv2.INTER_AREA)
  def histdist(img):
   a=cv2.cvtColor(img,cv2.COLOR_BGR2LAB);b=cv2.cvtColor(rr,cv2.COLOR_BGR2LAB)
   hist=lambda x: cv2.normalize(cv2.calcHist([x],[0,1,2],None,[12,12,12],[0,256,0,256,0,256]),None,alpha=1,norm_type=cv2.NORM_L1)
   return float(cv2.compareHist(hist(a),hist(b),cv2.HISTCMP_BHATTACHARYYA))
  d0,d1=histdist(a0),histdist(a1)
  r.update(reference_distance_before=round(d0,4),reference_distance_after=round(d1,4),reference_distance_change_pct=round((d0-d1)/d0*100,3) if d0 else None)
 return r
m={'portrait':detail(a.before_portrait,a.after_portrait),'landscape':detail(a.before_landscape,a.after_landscape)}
vals=[m[k]['detail_change_pct'] for k in m if m[k]['detail_change_pct'] is not None]
m['mean_detail_change_pct']=round(sum(vals)/len(vals),3) if vals else None
print(json.dumps(m,ensure_ascii=False,indent=2))
