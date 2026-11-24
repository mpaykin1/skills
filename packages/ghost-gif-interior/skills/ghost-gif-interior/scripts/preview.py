import argparse, base64, io, json, zipfile, hashlib
from pathlib import Path
from PIL import Image, ImageSequence

p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('output',type=Path); p.add_argument('--tiles',nargs='*',default=['pol','potolok','stena_gladkaya','lepnina']); a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
items=[]; errors=[]; outputs=[]
for path in sorted(a.source.glob('*.gif')):
    with Image.open(path) as im:
        frames=[]; durations=[]; hashes=set(); transparent=False
        for frame in ImageSequence.Iterator(im):
            rgba=frame.convert('RGBA'); hashes.add(hashlib.sha256(rgba.tobytes()).digest()); transparent |= rgba.getchannel('A').getextrema()[0]==0
            buf=io.BytesIO(); rgba.save(buf,format='PNG'); frames.append('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()); durations.append(max(20,frame.info.get('duration',180)))
        n=len(frames); base=path.stem.rsplit('_',1)[0]; tiled=base in a.tiles
        if im.format!='GIF' or not 4<=n<=8 or len(hashes)!=n or im.info.get('loop')!=0: errors.append(path.name+': invalid frame count, duplicates or loop')
        if not tiled and not transparent: errors.append(path.name+': missing transparency')
        if tiled:
            im.seek(0); f=im.convert('RGBA'); w,h=f.size; tile=Image.new('RGBA',(2*w,2*h));
            for y in range(2):
                for x in range(2): tile.paste(f,(x*w,y*h))
            out=a.output/(path.stem+'_2x2.png'); tile.save(out); outputs.append(out)
        items.append(dict(name=path.name,w=im.width,h=im.height,frames=frames,ms=durations))
    outputs.append(path)
if not items: raise SystemExit('No GIFs found')
if errors: raise SystemExit('\n'.join(errors))
for item in items:
    base=item['name'].rsplit('_',1)[0]; other=base+('_light.gif' if item['name'].endswith('_dark.gif') else '_dark.gif')
    match=next((x for x in items if x['name']==other),None)
    if not match or (match['w'],match['h'])!=(item['w'],item['h']): raise SystemExit('Missing or mismatched palette: '+item['name'])
html='''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>GIF — просмотр</title><style>body{background:#171819;color:#e9e3d4;font:16px system-ui;margin:16px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}article{border:1px solid #696457;padding:8px;min-width:0}img{width:100%;height:260px;object-fit:contain;background:#303136}button{padding:9px;margin:4px;color:inherit;background:#343536;border:1px solid #777}</style><button id=p>Пауза</button><button id=s>Следующий кадр</button><main id=m></main><script>const data=DATA;let play=true;const states=data.map(d=>{const a=document.createElement('article'),img=document.createElement('img'),t=document.createElement('div');t.textContent=d.name+' · '+d.w+' × '+d.h+' · '+d.frames.length+' кадров';a.append(img,t);m.append(a);const q={d,img,i:0,t:0};img.src=d.frames[0];return q});function step(q){q.i=(q.i+1)%q.d.frames.length;q.img.src=q.d.frames[q.i]}p.onclick=()=>{play=!play;p.textContent=play?'Пауза':'Воспроизвести'};s.onclick=()=>{play=false;p.textContent='Воспроизвести';states.forEach(step)};let last=performance.now();function tick(now){let dt=now-last;last=now;if(play)for(const q of states){q.t+=dt;while(q.t>=q.d.ms[q.i]){q.t-=q.d.ms[q.i];step(q)}}requestAnimationFrame(tick)}requestAnimationFrame(tick);</script>'''.replace('DATA',json.dumps(items,ensure_ascii=True).replace('</','<\\/'),1)
viewer=a.output/'preview.html';viewer.write_text(html,encoding='utf-8');outputs.append(viewer)
with zipfile.ZipFile(a.output/'ghost_interior_assets.zip','w',zipfile.ZIP_DEFLATED) as z:
    for x in outputs:z.write(x,x.name)
