#!/usr/bin/env python3
"""Optional real rembg + RIFE preprocessing; never publishes or edits original art."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path
from PIL import Image
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rife_mid(a,b,model,torch):
    h,w=a.shape[:2];dev='cuda' if torch.cuda.is_available() else 'cpu';pad=(0,(-w)%32,0,(-h)%32)
    def matte(x,white):
        f=x.astype('float32')/255;alpha=f[...,3:4];rgb=f[...,:3]*alpha+(1-alpha)*white
        return torch.nn.functional.pad(torch.from_numpy(rgb.transpose(2,0,1)[None]).to(dev),pad)
    with torch.inference_mode():
        black=model.inference(matte(a,0),matte(b,0))[...,:h,:w].clamp(0,1)
        white=model.inference(matte(a,1),matte(b,1))[...,:h,:w].clamp(0,1)
        alpha=(1-(white-black).mean(1,keepdim=True)).clamp(0,1);rgb=(black/alpha.clamp(min=.02)).clamp(0,1)
        rgba=torch.cat([rgb,alpha],1)[0].permute(1,2,0)
        if not torch.isfinite(rgba).all():raise ValueError('nonfinite RIFE result')
        out=(rgba.cpu().numpy()*255+.5).astype('uint8');out[out[...,3]==0,:3]=0
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--rembg',action='store_true');p.add_argument('--rife-repo',type=Path);p.add_argument('--rife-weights',type=Path);p.add_argument('--kind',choices=['rigid-transport','effect','actor','other'],required=True);p.add_argument('--single-action-view',action='store_true');p.add_argument('--loop',action='store_true');a=p.parse_args();src=a.source.resolve();dst=a.output.resolve()
    if dst.exists() or dst in src.parents or src in dst.parents:raise ValueError('fresh independent candidate directory required')
    paths=sorted(src.glob('*.png'))
    if not paths:raise ValueError('no PNG source frames')
    if a.rife_repo and (a.kind not in ('rigid-transport','effect') or not a.single_action_view or len(paths)<2):raise ValueError('RIFE forbidden for actors, mixed views/actions or <2 frames')
    session=None;model=None
    if a.rembg:
        from rembg import remove,new_session
        # rembg model cache must already be available; no provider substitution.
        session=new_session('u2net')
    if a.rife_repo:
        import torch
        commit=subprocess.check_output(['git','-C',str(a.rife_repo),'rev-parse','HEAD'],text=True).strip()
        if commit!='5d8adbdd40e12c2c8f91930eff838aebe561c086':raise ValueError('wrong official RIFE revision')
        if not a.rife_weights or not (a.rife_weights/'flownet.pkl').is_file():raise ValueError('official local RIFE weights required')
        sys.path.insert(0,str(a.rife_repo.resolve()));from model.RIFE import Model
        model=Model();model.load_model(str(a.rife_weights.resolve()),-1);model.eval();model.device()
    images=[];removed=[]
    for path in paths:
        im=Image.open(path).convert('RGBA');arr=np.array(im);changed=False
        if a.rembg and np.all(arr[...,3]==255):
            mask=np.array(remove(im.convert('RGB'),session=session,only_mask=True).convert('L'))
            if mask.shape!=arr.shape[:2] or not np.any(mask<128) or not np.any(mask>=128):raise ValueError('invalid rembg mask')
            arr[...,3]=mask;changed=True
        if np.all(arr[...,3]==255):raise ValueError('opaque frame; real transparency required')
        images.append(arr);removed.append(changed)
    if any(x.shape!=images[0].shape for x in images):raise ValueError('canvas mismatch')
    dst.mkdir(parents=True);records=[]
    def save(arr,original=None):
        path=dst/f'{len(records):04}.png'
        if original is not None:shutil.copyfile(original,path)
        else:Image.fromarray(arr).save(path)
        records.append({'name':path.name,'sha256':sha(path),'original_keyframe':original is not None})
    for i,im in enumerate(images):
        save(im,paths[i] if not removed[i] and Image.open(paths[i]).mode=='RGBA' else None)
        if model and (i+1<len(images) or a.loop):save(rife_mid(im,images[(i+1)%len(images)],model,torch))
    (dst/'candidate.json').write_text(json.dumps({'approved':False,'source_files':[{'name':p.name,'sha256':sha(p)} for p in paths],'rembg_changed':removed,'rife_used':model is not None,'frames':records},indent=2))
    print('UNAPPROVED_CANDIDATE',dst)
if __name__=='__main__':main()
