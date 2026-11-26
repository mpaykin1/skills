"""Create a derived static AO candidate; original material and channels stay intact."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image
import numpy as np
from audit_ao import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def merge(orm,pack,out,orm_sha,source_sha):
    if out.exists() or sha(orm)!=orm_sha:raise ValueError('output exists or original hash mismatch')
    m=audit(pack)
    if m['source_sha256']!=source_sha:raise ValueError('UV sample source mismatch')
    with Image.open(orm) as im:
        if im.mode!='RGB' or list(im.size)!=m['size']:raise ValueError('ORM dimensions/mode; no resize')
        rgb=np.array(im)
    with Image.open(pack/'ao.png') as im:ao=np.asarray(im)
    # Replace only neutral AO; preserve existing AO rather than double-shading.
    if not np.all(rgb[...,0]==255):raise ValueError('existing AO must remain unchanged')
    rgb[...,0]=ao
    out.mkdir(parents=True);p=out/'orm.png';Image.fromarray(rgb).save(p)
    (out/'derived.json').write_text(json.dumps({'schema':'meta-embree-orm-candidate-v1','original_orm_sha256':orm_sha,'uv_sample_sha256':source_sha,'ao_manifest_sha256':sha(pack/'ao.json'),'orm_sha256':sha(p),'approved':False},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('orm',type=Path);p.add_argument('ao_pack',type=Path);p.add_argument('out',type=Path);p.add_argument('--orm-sha',required=True);p.add_argument('--source-sha',required=True);a=p.parse_args();merge(a.orm,a.ao_pack,a.out,a.orm_sha,a.source_sha)
