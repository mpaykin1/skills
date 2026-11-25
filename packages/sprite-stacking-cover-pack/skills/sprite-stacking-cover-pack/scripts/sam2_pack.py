"""Segment an approved scene with SAM 2.1, export lossless masked crops, then hand selected objects to TRELLIS.2."""
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def export_mask(image, mask, out, oid, padding=16):
    """Never modify approved RGB within mask. Keep original alpha, no invented soft matte."""
    if not ID.fullmatch(oid): raise ValueError('Invalid object ID: '+oid)
    a = np.asarray(image.convert('RGBA')).copy()
    mask = np.asarray(mask)
    if mask.shape != a.shape[:2]: raise ValueError('Mask dimensions must match original image')
    if mask.dtype == np.bool_: mask = mask.astype(np.uint8)*255
    elif mask.dtype != np.uint8: raise ValueError('Mask must be bool or uint8')
    a[:,:,3] = ((a[:,:,3].astype(np.uint16)*mask.astype(np.uint16)+127)//255).astype(np.uint8)
    yy,xx = np.where(a[:,:,3]>0)
    if not len(xx): raise ValueError('Empty mask: '+oid)
    if not (a[:,:,3]==0).any(): raise ValueError('Mask covers whole image; isolate an object')
    x0,y0=max(0,int(xx.min())-padding),max(0,int(yy.min())-padding)
    x1,y1=min(a.shape[1],int(xx.max())+1+padding),min(a.shape[0],int(yy.max())+1+padding)
    dst=Path(out)/oid;dst.mkdir(parents=True,exist_ok=False)
    Image.fromarray(mask).save(dst/'mask.png')
    # Padding outside the crop preserves aspect ratio and ensures a transparent border even for edge objects.
    crop=Image.fromarray(a[y0:y1,x0:x1]); canvas=Image.new('RGBA',(crop.width+2,crop.height+2));canvas.paste(crop,(1,1))
    canvas.save(dst/'reference.png')
    return {'id':oid,'mask':f'{oid}/mask.png','reference':f'{oid}/reference.png','cropXYXY':[x0,y0,x1,y1], 'extraBorder':1,'visiblePixels':len(xx),'status':'candidate','referenceSHA256':digest(dst/'reference.png')}

def segment(args):
    image=Image.open(args.image).convert('RGBA');out=Path(args.out)
    if out.exists(): raise FileExistsError(out)
    if args.padding<0: raise ValueError('Padding must be nonnegative')
    specs=read_json(args.objects) if args.objects else None
    if specs is not None and (not isinstance(specs,list) or not specs): raise ValueError('objects JSON must be a nonempty list')
    if args.mode=='import' and specs is None: raise ValueError('Import requires object definitions')
    if args.mode=='sam2' and (not args.checkpoint or not Path(args.checkpoint).is_file()): raise FileNotFoundError('Provide official local SAM 2.1 checkpoint')
    if specs is not None:
        ids=[s['id'] for s in specs]
        if len(set(ids))!=len(ids) or not all(ID.fullmatch(i) for i in ids): raise ValueError('Object IDs must be unique kebab-case')
    # No upstream model is imported or executed in external-mask mode.
    candidates=[]; provenance={'mode':args.mode,'sourceSHA256':digest(args.image),'sourceSize':list(image.size)}
    if args.mode=='sam2':
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
        device=args.device
        if device=='cuda' and not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable; use supported CPU mode or real GPU')
        model=build_sam2(args.config,args.checkpoint,device=device)
        rgb=np.asarray(image.convert('RGB'))
        provenance.update(upstream='https://github.com/facebookresearch/sam2',config=args.config,checkpointSHA256=digest(args.checkpoint),device=device)
        with torch.inference_mode():
            if specs is None:
                gen=SAM2AutomaticMaskGenerator(model,points_per_side=args.points_per_side)
                proposals=sorted(gen.generate(rgb),key=lambda m:float(m['predicted_iou']),reverse=True)[:args.max_candidates]
                for k,p in enumerate(proposals):
                    candidates.append(({'id':f'candidate-{k+1:03d}','score':float(p['predicted_iou']),'stability':float(p['stability_score'])},p['segmentation']))
            else:
                predictor=SAM2ImagePredictor(model);predictor.set_image(rgb)
                for spec in specs:
                    points=np.asarray(spec['points'],np.float32) if 'points' in spec else None
                    labels=np.asarray(spec['labels'],np.int32) if 'labels' in spec else None
                    box=np.asarray(spec['box'],np.float32) if 'box' in spec else None
                    if points is None and box is None: raise ValueError('Need points or box for '+spec['id'])
                    if points is not None and (points.ndim!=2 or points.shape[1]!=2 or labels is None or labels.shape!=(len(points),) or not np.isin(labels,[0,1]).all()): raise ValueError('Invalid positive/negative points')
                    if box is not None and (box.shape!=(4,) or box[0]>=box[2] or box[1]>=box[3]): raise ValueError('Invalid XYXY box')
                    masks,scores,_=predictor.predict(point_coords=points,point_labels=labels,box=box,multimask_output=True)
                    i=int(spec.get('mask_index',np.argmax(scores)))
                    if i<0 or i>=len(masks): raise ValueError('Invalid mask index')
                    candidates.append(({**spec,'score':float(scores[i]),'maskIndex':i},masks[i]))
    else:
        root=Path(args.objects).resolve().parent
        for spec in specs:
            p=(root/spec['mask']).resolve()
            mask=np.asarray(Image.open(p).convert('L'))
            candidates.append(({**spec,'externalMaskSHA256':digest(p)},mask))
    if not candidates: raise ValueError('No segmentation candidates')
    out.mkdir(parents=True)
    image.save(out/'approved-source.png')
    records=[]; masks=[]
    for spec,mask in candidates:
        try: record=export_mask(image,mask,out,spec['id'],args.padding)
        except ValueError:
            if specs is not None: raise
            continue
        record['prompt']=spec;records.append(record);masks.append(np.asarray(mask)>0)
    if not records: raise ValueError('No usable object mask')
    overlaps=[]
    for i,m in enumerate(masks):
        for j in range(i):
            n=masks[j]; intersection=int((m&n).sum()); smaller=min(int(m.sum()),int(n.sum()))
            if smaller and intersection/smaller>.2: overlaps.append({'ids':[records[j]['id'],records[i]['id']],'fractionOfSmaller':intersection/smaller})
    write_json(out/'segments.json',{'schema':'cover-pack-segments/1','provenance':provenance,'objects':records,'overlaps':overlaps,'status':'review-required'})

def generate(args):
    root=Path(args.segments).resolve(); manifest=read_json(root/'segments.json'); selection=read_json(args.selection)
    if not isinstance(selection,list) or not selection or len(set(selection))!=len(selection): raise ValueError('Selection must be reviewed unique object IDs')
    records={r['id']:r for r in manifest['objects']};out=Path(args.out)
    if out.exists(): raise FileExistsError(out)
    if not all(i in records and ID.fullmatch(i) for i in selection): raise ValueError('Unknown object ID')
    for i in selection:
        r=records[i]; p=root/r['reference']
        if digest(p)!=r['referenceSHA256']: raise ValueError('Reference changed since segmentation: '+i)
    out.mkdir(parents=True)
    script=Path(__file__).with_name('trellis_stack.py')
    for i in selection:
        r=records[i]; cmd=[args.python,str(script),'generate','--image',str(root/r['reference']),'--out',str(out/i),'--up',args.up,'--size',str(args.size),'--seed',str(args.seed)]
        if args.glb:cmd.append('--glb')
        subprocess.run(cmd,check=True)
    write_json(out/'generation.json',{'segmentsSHA256':digest(root/'segments.json'),'assets':selection,'status':'prototype; visual fidelity and animation unverified'})

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for mode in ('sam2','import'):
        s=sub.add_parser(mode);s.set_defaults(mode=mode);s.add_argument('--image',required=True);s.add_argument('--out',required=True);s.add_argument('--objects',required=mode=='import');s.add_argument('--padding',type=int,default=16)
        if mode=='sam2':
            s.add_argument('--checkpoint',required=True);s.add_argument('--config',default='configs/sam2.1/sam2.1_hiera_t.yaml');s.add_argument('--device',choices=['cpu','cuda'],default='cpu');s.add_argument('--points-per-side',type=int,default=24);s.add_argument('--max-candidates',type=int,default=40)
    s=sub.add_parser('generate');s.add_argument('--segments',required=True);s.add_argument('--selection',required=True);s.add_argument('--out',required=True);s.add_argument('--python',default=sys.executable);s.add_argument('--size',type=int,choices=[128,256,512,1024],default=256);s.add_argument('--up',choices=['y','z'],required=True);s.add_argument('--seed',type=int,default=42);s.add_argument('--glb',action='store_true')
    a=p.parse_args();generate(a) if a.command=='generate' else segment(a)
if __name__=='__main__':main()
