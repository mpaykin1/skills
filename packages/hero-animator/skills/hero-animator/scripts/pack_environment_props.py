#!/usr/bin/env python3
"""Validate raw complete objects BEFORE adding atlas padding, then pack lossless RGBA.
Original painted pixels are unchanged. No crop, rembg, morph, re-drawing or resampling.
"""
import argparse,base64,hashlib,io,json
from pathlib import Path
from PIL import Image
from prop_integrity_gate import validate_image

def pack(manifest_path,output):
    manifest=json.loads(manifest_path.read_text(encoding='utf8'));assets={}
    if manifest.get('kind')!='complete-prop-sources':raise ValueError('Complete prop manifest required')
    for item in manifest['objects']:
        if item.get('sourceKind')!='independently-painted-complete-object':raise ValueError('BLOCKED: no panorama cutouts')
        src=(manifest_path.parent/item['file']).resolve();raw=Image.open(src)
        check=validate_image(raw,item.get('role'),.02) # Never allow padding to conceal a cropped raw candidate.
        pad=max(64,round(min(raw.size)*.07));im=Image.new('RGBA',(raw.width+2*pad,raw.height+2*pad),(0,0,0,0));im.paste(raw,(pad,pad))
        assert im.crop((pad,pad,pad+raw.width,pad+raw.height)).tobytes()==raw.tobytes()
        gate=validate_image(im,'complete-prop',.05)
        l,t,r,b=gate['bbox'];alpha=im.getchannel('A');rows=range(max(t,b-32),b)
        points=[(x,alpha.getpixel((x,y))) for y in rows for x in range(l,r) if alpha.getpixel((x,y))>=16]
        anchor_x=round(sum(x*v for x,v in points)/sum(v for _,v in points),3)
        data=io.BytesIO();im.save(data,'WEBP',lossless=True,quality=100,method=6,exact=True);payload=data.getvalue()
        with Image.open(io.BytesIO(payload)) as decoded:
            assert decoded.convert('RGBA').tobytes()==im.tobytes(),'Lossless packing changed painted RGBA'
        assets[item['id']]={'role':'complete-prop','sourceKind':item['sourceKind'],'width':im.width,'height':im.height,'pivot':[anchor_x,b-1],
          'url':'data:image/webp;base64,'+base64.b64encode(payload).decode(),'sha256':hashlib.sha256(payload).hexdigest(),'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),
          'rawGate':check,'gate':gate,'review':{'reviewedBy':'assistant','fullSilhouetteObserved':True,'humanApproved':False,'source':manifest.get('generatedBy','unknown')}}
    result={'kind':'complete-prop-pack','version':1,'assets':assets,'rules':{'noPanoramaFragments':True,'rawBeforePadding':True,'losslessPixelPreservation':True}}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,separators=(',',':')),encoding='utf8')
    print(json.dumps({'output':str(output),'objects':len(assets),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('output',type=Path);a=p.parse_args();pack(a.manifest,a.output)
if __name__=='__main__':main()
