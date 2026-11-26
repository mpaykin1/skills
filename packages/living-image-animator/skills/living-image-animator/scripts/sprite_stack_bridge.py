#!/usr/bin/env python3
"""Approved full-cel 2D actors + genuine author-painted XY/Z slice volumes -> Three.js.

This is a separate additive 3D export, not a replacement for the original GIF,
PNG assets, 2D physics, or source identity/gait/pose validations.
"""
from __future__ import annotations
import argparse, base64, hashlib, io, json, math, re, zipfile
from pathlib import Path
from PIL import Image
from pixijs_bridge import load_scene

class StackError(ValueError): pass

def fail(msg):raise StackError('Authentic sprite stacking blocked: '+str(msg))
def number(v,lo,hi,label):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:fail(label+' invalid')
    return float(v)
def ident(s):
    if not isinstance(s,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,59}',s):fail('Unsafe object ID')
    return s

def within(root,rel):
    if not isinstance(rel,str) or not 1<=len(rel)<=240 or '\\' in rel or ':' in rel or rel.startswith('/') or any(t in ('','.','..') for t in rel.split('/')):fail('Unsafe stack path')
    root=Path(root).resolve();path=(root/rel).resolve()
    if root not in path.parents or not path.is_file():fail('Missing source stack file '+rel)
    return path

def triples(v,lo,hi,label):
    if not isinstance(v,list) or len(v)!=3:fail(label+' requires exactly 3 numbers')
    return [number(q,lo,hi,label) for q in v]

def stack(root,rel,expected_pose_sha=None):
    path=within(root,rel);config=json.loads(path.read_text('utf8'))
    if not isinstance(config,dict):fail('stack.json must be an object')
    if set(config)-{'layers','spacing','pivot','size','source_pose_sha256','source','author','material'}:fail('Unknown slice stack metadata')
    layers=config.get('layers');spacing=triples(config.get('spacing'),.0005,50,'spacing')
    pivot=triples(config.get('pivot',[0,0,0]),-50000,50000,'pivot')
    if not isinstance(layers,list) or not 8<=len(layers)<=160:fail('8..160 actual PNG XY slices needed')
    if expected_pose_sha is not None and config.get('source_pose_sha256')!=expected_pose_sha:
        fail('Stack full-body pose provenance mismatch: independently authored stack must reference approved original pose SHA256')
    frames=[];unique=set();signatures=set();any_pixels=False;first_size=None;bytes_total=0
    source_hash=hashlib.sha256(path.read_bytes())
    for relpng in layers:
        imagepath=within(path.parent,relpng)
        raw=imagepath.read_bytes();bytes_total+=len(raw);source_hash.update(raw)
        if len(raw)>12_000_000:fail('Individual author PNG slice exceeds 12 MB')
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG' or im.mode not in ('RGBA','LA','P'):fail('Slices must be genuine RGBA PNG, no fake still image')
            im=im.convert('RGBA');size=im.size
            if not (16<=size[0]<=512 and 16<=size[1]<=512):fail('Slice grid must be 16..512 px along XY; supply authored low-resolution LOD for mobile if needed')
            if first_size is not None and first_size!=size:fail('Every 3D slice must have identical dimensions')
            first_size=size
            if im.getchannel('A').getextrema()[1]>0:any_pixels=True
            # Changes between actual slices are expected; no cloned flat-card impostors.
            signatures.add(hashlib.sha256(im.tobytes()).hexdigest())
        frames.append('data:image/png;base64,'+base64.b64encode(raw).decode('ascii'))
        unique.add(str(imagepath))
    if len(unique)!=len(layers):fail('Repeated PNG path cannot masquerade as independently authored depth slices')
    if not any_pixels or len(signatures)<min(4,len(layers)):fail('Empty or repeated 2D card extrusion: provide actual 3D sections')
    if type(config.get('size')) is not int or config['size']!=first_size[0] or first_size[0]!=first_size[1]:
        fail('stack.json size must equal the square XY image resolution')
    return ({'size':first_size[0],'depth':len(layers),'spacing':spacing,'pivot':pivot,'slices':frames,
            'author':config.get('author'),'sha256':source_hash.hexdigest(),
            'source_pose_sha256':config.get('source_pose_sha256'), 'source_file':rel},
           first_size[0]*first_size[1]*len(layers)*4)

def package(approved_zip,scene_path,three_js,output_html):
    approved_zip=Path(approved_zip).resolve();scene_path=Path(scene_path).resolve()
    if not approved_zip.is_file() or not scene_path.is_file():fail('Previously approved source art and original scene are required')
    approved=load_scene(approved_zip)
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:fail('Approved original animation ZIP corrupted')
        try:
            source=json.loads(z.read('scene.json'));gate=json.loads(z.read('motion_gate.json'))
        except (ValueError,KeyError) as e:fail('Source full-body motion gate required: '+str(e))
        if gate.get('all_actors_pass') is not True:fail('2D actor art gate did not pass')
        original_cfg=json.loads(scene_path.read_text('utf8'))
        if original_cfg.get('inventory')!=source.get('inventory'):fail('Original actor roster changed')
        if original_cfg.get('sprite_stacking')!=source.get('sprite_stacking'):
            fail('Sprite stacking declarations differ from already-approved source scene')
        cfg=source.get('sprite_stacking')
        if not isinstance(cfg,dict) or set(cfg)-{'enabled','objects','actors','camera','coverage_min','background','fog','quality','eligible_object_ids','environment_only'}:
            fail('Scene sprite_stacking configuration absent/invalid')
        if cfg.get('enabled',True) is not True:fail('Stacking explicitly disabled')
        static=cfg.get('objects',[]);dynamic=cfg.get('actors',[])
        if not isinstance(static,list) or not isinstance(dynamic,list) or not static and not dynamic:fail('No authored sprite stacks supplied')
        if len(static)+len(dynamic)>100:fail('Maximum 100 individually authored stack objects')
        records=[];included=set();bytes_total=0;stack_count=0
        root=scene_path.parent
        def add(rel,ref_sha=None):
            nonlocal bytes_total,stack_count
            out,memory=stack(root,rel,ref_sha);bytes_total+=memory;stack_count+=1
            if bytes_total>256_000_000:fail('GPU volume budget exceeded: 256 MB. Supply genuine lower-resolution source LOD')
            if stack_count>250:fail('Animated volume sequences exceed 250 unique source-author stacks')
            return out
        for item in static:
            if not isinstance(item,dict) or set(item)-{'id','stack','position','yaw','kind','motion','parent'}:fail('Malformed authored world object')
            oid=ident(item.get('id'))
            if oid in included:fail('Duplicate source object id')
            included.add(oid)
            pos=triples(item.get('position'),-100000,100000,'object position')
            yaw=number(item.get('yaw',0),-360,360,'object yaw')
            kind=item.get('kind','prop')
            if kind not in ('architecture','terrain','tree','vegetation','vehicle','machine','gate','weapon','prop','water','creature','effect'):
                fail('Unknown source object category')
            motion=item.get('motion')
            if motion is not None:
                if not isinstance(motion,dict) or set(motion)-{'type','axis','degrees','duration','trigger','auto'}:fail('Invalid rigid hinge/spin motion')
                if motion.get('type') not in ('hinge','spin'):fail('Only rigid whole-stack hinge or spin is supported')
                if motion.get('axis','z') not in ('x','y','z'):fail('Invalid rigid mechanical hinge axis')
                number(motion.get('degrees',90),-360,360,'rigid part arc')
                number(motion.get('duration',1.5),.2,30,'rigid part duration')
                if motion.get('trigger','click') not in ('click','auto'):fail('Explicit click or auto trigger required')
            # Separate independent authored stacks for every moving rigid component.
            parent=item.get('parent')
            if parent is not None and parent not in included:fail('Parent rigid stack must be declared before child')
            records.append({'id':oid,'kind':kind,'position':pos,'yaw':yaw,'parent':parent,'motion':motion,
                            'stack':add(item.get('stack'))})
        approved_map={a['id']:a for a in approved['actors']}
        bound=set();actor_records=[]
        for actor in dynamic:
            if not isinstance(actor,dict) or set(actor)-{'actor_id','clips','position','yaw','fps'}:fail('Invalid source actor stack declaration')
            aid=ident(actor.get('actor_id'))
            if aid in bound or aid not in approved_map:fail('3D actor must correspond to one approved original 2D character')
            bound.add(aid)
            approved_actor=approved_map[aid]
            source_actor=next(a for a in source['actors'] if a['id']==aid)
            clips=actor.get('clips')
            if not isinstance(clips,dict) or len(clips)!=len(source_actor['clips']):fail('Every approved original action must have independent full-volume pose stacks')
            frames=[];actions=[]
            for clip in source_actor['clips']:
                action=clip['action'];paths=clips.get(action)
                if not isinstance(paths,list) or len(paths)!=len(clip['frames']):fail(aid+': stack count must equal actual original full-body PNG pose count for '+action)
                for rel,frame in zip(paths,clip['frames']):
                    relpng=frame['png']
                    original_png=z.read('project/inputs/'+relpng)
                    frames.append(add(rel,hashlib.sha256(original_png).hexdigest()))
                    actions.append(action)
            res={(s['size'],s['depth'],tuple(s['spacing']),tuple(s['pivot'])) for s in frames}
            if len(res)!=1:fail(aid+': all full-body stack poses must share dimensions, height, spacing and pivot')
            actor_records.append({'id':aid,'position':triples(actor.get('position',[0,0,0]),-100000,100000,'actor world position'),
                                  'yaw':number(actor.get('yaw',0),-360,360,'actor yaw'),'clips':list(clips.keys()),
                                  'frames':frames,'actions':actions,'phase':source_actor.get('phase_frames',0),
                                  'fps':number(actor.get('fps',24),24,120,'pose FPS'),
                                  'path':(source_actor.get('locomotion') or {}).get('path')})
        # No arbitrary 3D replacement character. Any missing source actor must continue in old 2D output.
        environment_only=cfg.get('environment_only',False)
        if type(environment_only) is not bool:fail('environment_only must be explicitly boolean')
        if not environment_only and len(bound)!=len(approved_map):
            fail('Full 3D scene requires authentic complete authored stack sequences for ALL certified original characters; or explicitly request environment_only preview')
        if environment_only and dynamic:fail('environment_only preview must not declare source 3D actors')
        coverage=number(cfg.get('coverage_min',.9),.75,1,'source 3D coverage minimum')
        eligible=cfg.get('eligible_object_ids')
        if not isinstance(eligible,list) or not 1<=len(eligible)<=500:
            fail('Explicit eligible_object_ids inventory is mandatory: never inflate sprite stacking coverage')
        eligible_ids=[ident(s) for s in eligible]
        if not environment_only and not set(approved_map).issubset(set(eligible_ids)):
            fail('3D scene eligibility inventory must include every original approved actor')
        if len(set(eligible_ids))!=len(eligible_ids):fail('Duplicate eligible source scene object IDs')
        assembled={x['id'] for x in records}|{a['id'] for a in actor_records}
        if not assembled.issubset(set(eligible_ids)):
            fail('3D sprite-stack objects must be on the complete original scene object inventory')
        actual_coverage=len(assembled)/len(eligible_ids)
        if actual_coverage<coverage:
            fail('Only %.1f%% of authored 3D-eligible objects stacked: need %.1f%% or more'
                 %(actual_coverage*100,coverage*100))
        camera=cfg.get('camera',{})
        if not isinstance(camera,dict) or set(camera)-{'azimuth','elevation','distance','target'}:fail('Invalid original 3D camera setup')
        view={'azimuth':number(camera.get('azimuth',40),-360,360,'azimuth'),
              'elevation':number(camera.get('elevation',30),-89,89,'elevation'),
              'distance':number(camera.get('distance',120),1,100000,'distance'),
              'target':triples(camera.get('target',[0,0,0]),-100000,100000,'camera target')}
        # Require real Three.js release JS; no fake stub or CDN fallback.
        three_js=Path(three_js).resolve()
        if not three_js.is_file():fail('Genuine locally supplied official three.module.js is required')
        code=three_js.read_bytes()
        if not 200_000<len(code)<5_000_000 or b'Data3DTexture' not in code or b'export {' not in code:
            fail('Expected complete official Three.js ESM module with 3D textures')
        html_js=code.decode('utf8')
        if re.search(r'^\s*import\s',html_js,re.M):fail('Three.js build has unresolved external imports; use official standalone three.module.js')
        with Image.open(io.BytesIO(z.read('background_clean.png'))) as bg:
            import io as _io
            stream=_io.BytesIO();bg.convert('RGB').save(stream,format='PNG',optimize=True)
            fallback_background='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')
    js=Path(__file__).with_name('sprite_stack_runtime.js').read_text('utf8')
    payload={'engine':'Three.js WebGL2 Data3DTexture sprite stacking','version':'0.187.0',
             'objects':records,'actors':actor_records,'camera':view,'coverage_min':coverage,'coverage_actual':actual_coverage,
             'background':fallback_background,'fog':cfg.get('fog',True),'source_actor_count':len(approved_map),
             'original_source_unchanged':True,'raymarch_3d':True,'environment_only_preview':environment_only}
    engine=html_js.replace('</script','<\\/script');runtime=js.replace('</script','<\\/script')
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    page=("<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
          "<title>Living Image Animator — Authentic Sprite Stacking 3D</title>"
          "<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#080c12;touch-action:none;font-family:system-ui}canvas{display:block}"
          "#hint{position:fixed;top:10px;left:12px;color:#cfd8d9;background:#0c1018af;padding:8px 10px;border-radius:7px;font-size:12px;pointer-events:none}"
          "#err{display:none;position:fixed;inset:0;background:#140c12;color:#f1e8d6;padding:20px;align-items:center;justify-content:center;z-index:8}"
          "</style></head><body><div id='hint'>Sprite Stacking 3D · вращение: перетаскивание · масштаб: колесо/щипок · механизм: нажать</div><div id='err'></div>"
          "<script type='module'>"+engine+"\nconst LIA_STACK="+data+";\n"+runtime+"</script></body></html>")
    out=Path(output_html).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():fail('Output already exists; use a clean destination')
    if len(page.encode('utf8'))>170*1024*1024:fail('Standalone HTML size exceeds offline mobile budget')
    out.write_text(page,'utf8')
    info={'stack_objects':len(records),'stack_actors':len(actor_records),'unique_stacks':stack_count,'stack_coverage':actual_coverage,
          'decoded_gpu_bytes':bytes_total,'html_bytes':out.stat().st_size,'three_module_sha256':hashlib.sha256(code).hexdigest(),
          'html_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_character_pngs_unchanged':True,
          'offline':True,'360_volume_not_flat_cards':True,'actor_cast_total':len(approved_map),
          'environment_only_preview':environment_only}
    return out,info

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',required=True,type=Path);p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--three-js',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(package(a.approved_zip,a.scene,a.three_js,a.out)[1],ensure_ascii=False))
