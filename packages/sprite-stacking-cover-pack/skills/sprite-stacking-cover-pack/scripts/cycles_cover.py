"""Render actual Sprite Stacking slices with Blender Cycles; validate using ordinary Python."""
import argparse, hashlib, json, math, struct, sys, time
from pathlib import Path


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def load(scene_path):
    source=Path(scene_path).resolve(); root=source.parent; inputs={}
    def file(base, rel):
        if not isinstance(rel,str):raise ValueError('Expected relative input path')
        p=(base/rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():raise ValueError('Missing or external input '+str(p))
        inputs[str(p.relative_to(root))]=sha(p);return p
    def vec(x,n):
        if not isinstance(x,list) or len(x)!=n or not all(type(v) in (int,float) and math.isfinite(v) for v in x):raise ValueError('Invalid vector')
        return x
    def scalar(x,lo,hi):
        if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Invalid scalar')
        return x
    def png(p):
        with p.open('rb') as f:b=f.read(33)
        if len(b)!=33 or b[:8]!=b'\x89PNG\r\n\x1a\n' or b[12:16]!=b'IHDR' or b[24:26]!=bytes([8,6]):raise ValueError('Expected 8-bit RGBA PNG: '+str(p))
        return struct.unpack('>II',b[16:24])
    def stack(path):
        m=json.loads(path.read_text());w,h=vec(m['tileSize'],2);d=m['layerCount'];sp=vec(m['spacing'],3)
        if any(type(v)!=int or not 1<=v<=2048 for v in (w,h,d)) or min(sp)<=0:raise ValueError('Invalid stack size or spacing')
        if m.get('layerOrder')!='bottom-to-top':raise ValueError('Require bottom-to-top slices')
        # All planes are relative to bottom-center; retain exact input metadata and spacing.
        # Nonstandard pivots require explicit author alignment; this renderer does not guess conventions.
        if m.get('axes','+X right, +Y top of PNG, +Z up')!='+X right, +Y top of PNG, +Z up':raise ValueError('Unsupported axis convention')
        if 'layers' in m:
            if len(m['layers'])!=d:raise ValueError('Layer count mismatch')
            layers=[file(path.parent,p) for p in m['layers']]
            if any(png(p)!=(w,h) for p in layers):raise ValueError('Layer dimensions mismatch')
            return dict(w=w,h=h,d=d,spacing=sp,entries=[(p,(0,0,1,1)) for p in layers],source=m)
        p=file(path.parent,m['atlas']);cols,rows=m['columns'],m['rows']
        if any(type(v)!=int or v<1 for v in (cols,rows)) or cols*rows<d or png(p)!=(w*cols,h*rows):raise ValueError('Invalid atlas')
        return dict(w=w,h=h,d=d,spacing=sp,entries=[(p,((i%cols)/cols,1-(i//cols+1)/rows,(i%cols+1)/cols,1-(i//cols)/rows)) for i in range(d)],source=m)
    s=json.loads(source.read_text());file(root,source.name)
    if s.get('schema')!='cover-pack-cycles/1':raise ValueError('Unsupported scene schema')
    fps=s['fps'];n=s['frameCount'];w,h=vec(s['resolution'],2)
    if type(fps)!=int or type(n)!=int or not 8<=fps<=30 or not 2<=n<=240 or not 2<=n/fps<=8 or any(type(v)!=int or not 32<=v<=2048 for v in (w,h)) or w*9!=h*16:raise ValueError('Need 16:9, 2–8 second cover, 8–30 fps')
    cam=s['camera'];pos=vec(cam['location'],3);target=vec(cam['target'],3)
    if math.dist(pos,target)<1e-6 or abs(pos[2]-target[2])/math.dist(pos,target)<.15:raise ValueError('Horizontal slice renderer requires elevated camera; avoid edge-on views')
    scalar(cam.get('orthoScale',8),.01,100000);vec(s.get('worldColor',[.04,.04,.06]),3);scalar(s.get('worldStrength',.25),0,100);scalar(s.get('samples',32),1,512)
    if len(s.get('lights',[]))>4:raise ValueError('Maximum four active lights')
    for l in s.get('lights',[]):
        vec(l['location'],3);vec(l['target'],3);vec(l.get('color',[1,1,1]),3);scalar(l['power'],0,1000000);scalar(l.get('size',3),.001,10000)
        if l['location']==l['target']:raise ValueError('Light direction undefined')
    assets=[];ids=set();animated=False;planes=0
    for obj in s['objects']:
        oid=obj['id']
        if not isinstance(oid,str) or not oid or oid in ids:raise ValueError('Duplicate/invalid instance ID')
        ids.add(oid);vec(obj['location'],3);vec(obj.get('anchorOffset',[0,0,0]),3);scalar(obj.get('scale',1),.0001,100000);scalar(obj.get('rotationZ',0),-36000,36000);scalar(obj.get('roughness',.6),0,1);scalar(obj.get('metallic',0),0,1);scalar(obj.get('emission',0),0,100)
        if obj.get('kind','stack')=='density':
            if 'poses' in obj:raise ValueError('Use separate frame VDB sequence for deforming smoke; unsupported here')
            p=file(root,obj['vdb']);
            if p.suffix.lower()!='.vdb':raise ValueError('Expected actual VDB')
            scalar(obj.get('densityScale',1),0,1000);vec(obj.get('tint',[.8,.8,.8]),3)
            assets.append((obj,p,[]));continue
        if obj.get('kind','stack')!='stack':raise ValueError('Unknown asset kind')
        st=stack(file(root,obj['stack']));poses=[]
        if st['source'].get('kind')=='atmosphere-density':raise ValueError('Use real density VDB instead of double-integrating alpha slices')
        for item in obj.get('poses',[]):
            a=stack(file(root,item['stack']));start=item['frame']
            if type(start)!=int or not 0<=start<n or any(a[k]!=st[k] for k in ('w','h','d','spacing')) or a['source'].get('pivot')!=st['source'].get('pivot') or a['source'].get('gridOrigin')!=st['source'].get('gridOrigin'):raise ValueError('Pose stacks must share fixed grid and pivot')
            poses.append((start,a))
        if poses and (poses[0][0]!=0 or [x[0] for x in poses]!=sorted(set(x[0] for x in poses))):raise ValueError('Pose timeline must start at zero and be sorted')
        if len(poses)>1 and len({tuple(inputs[str(p.relative_to(root))] for p,_ in a['entries']) for _,a in poses})>1:animated=True
        motion=obj.get('motion',{}); amp=vec(motion.get('translateAmplitude',[0,0,0]),3);ang=scalar(motion.get('rotationAmplitude',0),-360,360);cycles=motion.get('cycles',1)
        if type(cycles)!=int or not 1<=cycles<=8:raise ValueError('Motion must have integer cycles')
        if any(amp) or ang:animated=True
        planes+=sum(a['d'] for _,a in poses) if poses else st['d'];assets.append((obj,st,poses))
    if not assets or not animated:raise ValueError('Require actual object movement or different full pose stacks; camera-only/static rejected')
    if planes>8192:raise ValueError('Offline render slice budget exceeded; reduce verified LOD or split scene')
    return source,s,assets,inputs


def render(source,s,assets,inputs,out,denoise="off",samples=None):
    import bpy
    from mathutils import Vector
    if bpy.app.version<(4,5,0):raise RuntimeError('Blender 4.5+ required')
    root=source.parent;out=Path(out).resolve();manifest=root/(out.name+'-frames.json')
    if out.parent!=root or out.exists() or manifest.exists():raise ValueError('Output must be a new direct child of scene directory')
    out.mkdir();bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene
    sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=int(samples if samples is not None else s.get('samples',32));sc.cycles.use_denoising=(denoise=='oidn');sc.cycles.transparent_max_bounces=64
    sc.cycles.seed=42;sc.cycles.use_animated_seed=False;sc.cycles.use_adaptive_sampling=False
    if denoise=='oidn':
        # Fail if this Blender build lacks OIDN or its guided quality settings.
        sc.cycles.denoiser='OPENIMAGEDENOISE';sc.cycles.denoising_use_gpu=False
        sc.cycles.denoising_input_passes='RGB_ALBEDO_NORMAL';sc.cycles.denoising_prefilter='ACCURATE';sc.cycles.denoising_quality='HIGH'
    render_settings={'denoise':denoise,'samples':sc.cycles.samples,'seed':42,'adaptiveSampling':False,'device':'CPU','viewTransform':'AgX','denoiser':'OPENIMAGEDENOISE' if denoise=='oidn' else None,'guides':'RGB_ALBEDO_NORMAL' if denoise=='oidn' else None,'prefilter':'ACCURATE' if denoise=='oidn' else None,'quality':'HIGH' if denoise=='oidn' else None}
    started=time.perf_counter()
    sc.render.resolution_x,sc.render.resolution_y=s['resolution'];sc.render.resolution_percentage=100;sc.render.fps=s['fps'];sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.render.image_settings.color_depth='8';sc.render.film_transparent=bool(s.get('transparent',False));sc.view_settings.view_transform='AgX'
    world=bpy.data.worlds.new('Cover world');sc.world=world;world.use_nodes=True;bg=world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(*s.get('worldColor',[.04,.04,.06]),1);bg.inputs['Strength'].default_value=s.get('worldStrength',.25)
    def aim(o,t):o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
    def link(name,data):o=bpy.data.objects.new(name,data);sc.collection.objects.link(o);return o
    cam=link('Cover camera',bpy.data.cameras.new('Cover camera'));cam.location=s['camera']['location'];aim(cam,s['camera']['target']);cam.data.type='ORTHO';cam.data.ortho_scale=s['camera'].get('orthoScale',8);sc.camera=cam
    for i,l in enumerate(s.get('lights',[])):
        data=bpy.data.lights.new('Light '+str(i),'AREA');data.energy=l['power'];data.color=l.get('color',[1,1,1]);data.shape='DISK';data.size=l.get('size',3);o=link(data.name,data);o.location=l['location'];aim(o,l['target'])
    cache={}
    def mat(p,obj):
        key=(str(p),obj.get('roughness',.6),obj.get('metallic',0),obj.get('emission',0))
        if key in cache:return cache[key]
        m=bpy.data.materials.new(p.stem);m.use_nodes=True;n=m.node_tree.nodes;ls=m.node_tree.links;n.clear();o=n.new('ShaderNodeOutputMaterial');bs=n.new('ShaderNodeBsdfPrincipled');tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(p),check_existing=True);tex.image.alpha_mode='STRAIGHT';tex.interpolation='Closest';tex.extension='CLIP';bs.inputs['Roughness'].default_value=key[1];bs.inputs['Metallic'].default_value=key[2];bs.inputs['Emission Strength'].default_value=key[3];ls.new(tex.outputs['Color'],bs.inputs['Base Color']);ls.new(tex.outputs['Color'],bs.inputs['Emission Color']);ls.new(tex.outputs['Alpha'],bs.inputs['Alpha']);ls.new(bs.outputs['BSDF'],o.inputs['Surface']);cache[key]=m;return m
    def group(st,parent,obj,label):
        w,h,d=st['w'],st['h'],st['d'];sx,sy,sz=st['spacing'];a=w*sx/2;b=h*sy/2;result=[]
        for i,(p,uv) in enumerate(st['entries']):
            z=(i+.5)*sz;me=bpy.data.meshes.new(label+str(i));me.from_pydata([(-a,-b,z),(a,-b,z),(a,b,z),(-a,b,z)],[],[(0,1,2,3)]);me.update();layer=me.uv_layers.new();x0,y0,x1,y1=uv
            for j,v in enumerate(((x0,y0),(x1,y0),(x1,y1),(x0,y1))):layer.data[j].uv=v
            o=link(me.name,me);o.parent=parent;o.location=obj.get('anchorOffset',[0,0,0]);o.data.materials.append(mat(p,obj));result.append(o)
        return result
    states=[]
    for obj,st,poses in assets:
        parent=link(obj['id'],None);parent.location=obj['location'];parent.scale=[obj.get('scale',1)]*3
        if obj.get('kind')=='density':
            vol=bpy.data.volumes.new(obj['id']);vol.filepath=str(st);vol.grids.load()
            if not any(g.name=='density' for g in vol.grids):raise ValueError('VDB must have actual density grid')
            o=link(obj['id']+' volume',vol);o.parent=parent;m=bpy.data.materials.new(obj['id']+' fog');m.use_nodes=True;nodes=m.node_tree.nodes;nodes.clear();output=nodes.new('ShaderNodeOutputMaterial');bs=nodes.new('ShaderNodeVolumePrincipled');bs.inputs['Color'].default_value=(*obj.get('tint',[.8,.8,.8]),1);bs.inputs['Density'].default_value=obj.get('densityScale',1);bs.inputs['Density Attribute'].default_value='density';m.node_tree.links.new(bs.outputs['Volume'],output.inputs['Volume']);vol.materials.append(m);groups=[]
        else:groups=[(f,group(a,parent,obj,obj['id']+f'-{f}-')) for f,a in (poses or [(0,st)])]
        states.append((obj,parent,groups))
    frames=[];fps=s['fps'];count=s['frameCount']
    for i in range(count):
        sc.frame_set(i+1)
        for obj,parent,groups in states:
            m=obj.get('motion',{});v=math.sin(2*math.pi*i/count*m.get('cycles',1));parent.location=[a+b*v for a,b in zip(obj['location'],m.get('translateAmplitude',[0,0,0]))];parent.rotation_euler[2]=math.radians(obj.get('rotationZ',0)+v*m.get('rotationAmplitude',0))
            if groups:
                active=max(f for f,_ in groups if f<=i)
                for f,g in groups:
                    for o in g:o.hide_render=(f!=active)
        p=out/f'{i:04d}.png';sc.render.filepath=str(p);bpy.ops.render.render(write_still=True);frames.append({'path':str(p.relative_to(root)),'sha256':sha(p),'durationMs':round((i+1)*1000/fps)-round(i*1000/fps)})
    if len({f['sha256'] for f in frames})<2:raise RuntimeError('Rendered frames are identical')
    if any(sha(root/p)!=h for p,h in inputs.items()):raise RuntimeError('Source changed during render')
    manifest.write_text(json.dumps({'scene':source.name,'sceneSHA256':inputs[source.name],'frames':frames,'inputSHA256':inputs,'renderer':'Blender Cycles','blenderVersion':bpy.app.version_string,'renderSettings':render_settings,'wallSeconds':time.perf_counter()-started,'status':'rendered; visual and browser review required'},indent=2)+'\n');return manifest


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',required=True);p.add_argument('--out');p.add_argument('--validate-only',action='store_true');p.add_argument('--denoise',choices=['off','oidn'],default='off');p.add_argument('--samples',type=int,choices=range(1,513),metavar='1..512');a=p.parse_args(argv);source,s,assets,inputs=load(a.scene)
    if a.validate_only:print(f'Validated {len(assets)} scene instances and {len(inputs)} input files; no render performed');return
    if not a.out:p.error('--out required for rendering')
    print(render(source,s,assets,inputs,a.out,a.denoise,a.samples))
if __name__=='__main__':main()
