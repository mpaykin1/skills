"""Pack canonical RGBA layers into block-aligned runtime pages; optionally encode real Basis UASTC KTX2."""
import argparse, hashlib, json, math, struct, subprocess, shutil
from pathlib import Path
from PIL import Image


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def local(root, name):
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file(): raise ValueError('Missing/outside source: '+str(name))
    return p


def inspect_ktx2(p, size):
    with Path(p).open('rb') as f: b=f.read(80)
    if len(b)!=80 or b[:12]!=b'\xabKTX 20\xbb\r\n\x1a\n': raise ValueError('Invalid KTX2 identifier')
    vk,ts,w,h,d,layers,faces,levels,superc=struct.unpack_from('<9I',b,12)
    if (w,h)!=tuple(size) or (vk,ts,d,layers,faces,levels)!=(0,1,0,0,1,1) or superc not in (0,2):
        raise ValueError('Expected single-level 2D UASTC KTX2, no arrays or mipmaps')
    return {'width':w,'height':h,'supercompression':superc}


def pack(meta_path, out, max_page=2048, basis=None):
    meta_path=Path(meta_path).resolve();root=meta_path.parent;m=json.loads(meta_path.read_text());out=Path(out).resolve()
    w,h=m['tileSize'];d=m['layerCount'];sp=m['spacing']
    if any(type(x)!=int or x<1 for x in (w,h,d)) or d>2048 or m['layerOrder']!='bottom-to-top' or len(sp)!=3 or any(not math.isfinite(x) or x<=0 for x in sp): raise ValueError('Invalid source stack')
    if m.get('axes','+X right, +Y top of PNG, +Z up')!='+X right, +Y top of PNG, +Z up': raise ValueError('Unsupported axis convention')
    if max_page not in (512,1024,2048,4096): raise ValueError('Invalid page limit')
    cw,ch=4*math.ceil((w+8)/4),4*math.ceil((h+8)/4);cols,rows=max_page//cw,max_page//ch
    if not cols or not rows: raise ValueError('Tile exceeds page budget; no downsampling')
    sources={str(meta_path.relative_to(root)):sha(meta_path)}
    def rgba(p):
        sources[str(p.relative_to(root))]=sha(p)
        with Image.open(p) as im:
            if im.mode!='RGBA' or im.format!='PNG':raise ValueError('Require canonical RGBA PNG')
            return im.copy()
    if 'layers' in m:
        if len(m['layers'])!=d:raise ValueError('Layer count mismatch')
        def tile(i):return rgba(local(root,m['layers'][i]))
    else:
        atlas=rgba(local(root,m['atlas']));c,r=m['columns'],m['rows']
        if type(c)!=int or type(r)!=int or c<1 or r<1 or c*r<d or atlas.size!=(c*w,r*h):raise ValueError('Invalid source atlas')
        def tile(i):
            x,y=(i%c)*w,(i//c)*h;return atlas.crop((x,y,x+w,y+h))
    if basis:
        exe=shutil.which(basis)
        if not exe: raise RuntimeError('basisu unavailable: run PNG-only first; never fake KTX2')
        exe=str(Path(exe).resolve())
    out.mkdir(parents=True,exist_ok=False);pages=[];layers=[];capacity=cols*rows
    for start in range(0,d,capacity):
        count=min(capacity,d-start);pc=min(cols,count);pr=math.ceil(count/pc);pw,ph=pc*cw,pr*ch
        im=Image.new('RGBA',(pw,ph));page=len(pages)
        for j in range(count):
            t=tile(start+j)
            if t.size!=(w,h):raise ValueError('Source layer size mismatch')
            x,y=j%pc*cw+4,j//pc*ch+4;im.paste(t,(x,y))
            layers.append({'layer':start+j,'page':page,'rectXYWH':[x,y,w,h], 'uvTopLeft':[(x+.5)/pw,(y+.5)/ph,(x+w-.5)/pw,(y+h-.5)/ph]})
        png=out/f'page-{page:03d}.png';im.save(png)
        # Check exact repacking including hidden RGB and alpha.
        with Image.open(png) as check:
            for entry in layers[start:start+count]:
                x,y,tw,th=entry['rectXYWH'];assert check.crop((x,y,x+tw,y+th)).tobytes()==tile(entry['layer']).tobytes()
        row={'png':png.name,'pngSHA256':sha(png),'size':[pw,ph],'pngBytes':png.stat().st_size}
        if basis:
            k=png.with_suffix('.ktx2');subprocess.run([exe,'-ktx2','-uastc','-force_alpha','-file',str(png),'-output_file',str(k)],check=True,cwd=out)
            info=inspect_ktx2(k,[pw,ph]);subprocess.run([exe,'-validate',str(k)],check=True,cwd=out)
            row.update(ktx2=k.name,ktx2SHA256=sha(k),ktx2Bytes=k.stat().st_size,header=info,codec='UASTC',status='candidate; decoded alpha and visual review required')
        pages.append(row)
    if any(sha(root/p)!=hsh for p,hsh in sources.items()):raise RuntimeError('Source changed')
    result={'schema':'cover-pack-runtime-atlas/1','sourceSHA256':sources,'tileSize':[w,h],'layerCount':d,'layerOrder':m['layerOrder'],'spacing':sp,'pivot':m.get('pivot'),'pivotConvention':m.get('pivotConvention'),'gridOrigin':m.get('gridOrigin'),'bounds':m.get('bounds'),'axes':m.get('axes','+X right, +Y top of PNG, +Z up'),'pages':pages,'layers':layers,'uvConvention':'top-left; v=0 at top; texel centers','mipmaps':False,'filter':'nearest','colorSpace':'srgb','status':'candidate; canonical PNG preserved; compressed pages not approved'}
    p=out/'runtime-atlas.json';p.write_text(json.dumps(result,indent=2)+'\n');return p


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stack',required=True);p.add_argument('--out',required=True);p.add_argument('--max-page',type=int,default=2048);p.add_argument('--basisu',help='path to installed upstream basisu; omit for exact PNG pages only');a=p.parse_args();print(pack(a.stack,a.out,a.max_page,a.basisu))
if __name__=='__main__':main()
