#!/usr/bin/env python3
"""Verified original PNG full-cel + true four-view slices -> PixiJS8 in-game sprite stacking.

Adds 360-degree independently rotatable layered volumes to the REAL verified
PixiJS + Matter.js + PathFinding + nipplejs (+ YUKA when configured) HTML.
Never renders a substituted full-body character frame or changes existing cels.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,math,os,re,zipfile
from pathlib import Path
from PIL import Image
import io
from sprite_stacking_slicer import _rgba
from sprite_stacking_slicer import carve_views,pack_slices,StackSlicerError
from matter_bridge import validate_scene

class SpriteStackError(ValueError):pass

def bad(m):raise SpriteStackError('Sprite stacking blocked: '+str(m))

def finite(v,lo,hi,key):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:bad(f'{key} must be {lo}..{hi}')
    return float(v)

def safe(root,relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or relative.startswith('/'):
        bad('Unsafe source path '+str(relative))
    parts=relative.split('/')
    if any(p in ('','.','..') for p in parts):bad('Unsafe source path '+relative)
    root=Path(root).resolve();result=(root/relative).resolve()
    if root not in result.parents or not result.is_file():bad('Missing original authored 3D view: '+relative)
    return result.read_bytes()

def strid(v):
    if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',v):bad('All stack IDs must use letters/numbers/_/-')
    return v

def source_viewset(entry,root,original=None,reference=None):
    if not isinstance(entry,dict) or set(entry)-{'top','side','front','back'}:
        bad('Every volume must have four original orthographic views')
    views={}
    for view in ('top','side','front','back'):
        if view==reference and original is not None:
            if entry.get(view) not in (None,'@original'):
                bad('Original approved pose must be used unmodified as '+view+' silhouette')
            views[view]=original
        else:
            views[view]=safe(root,entry.get(view))
    return views

def atlas_from_views(views,n,allow_resample):
    layers,meta=carve_views(views,n,allow_resample)
    binary,cols,w,d=pack_slices(layers)
    return {'atlas':'data:image/png;base64,'+base64.b64encode(binary).decode('ascii'),
            'columns':cols,'width':w,'depth':d,'slices':n,
            'height':meta['height'],'shape_profiles':meta['distinct_profiles'],
            'sha256':hashlib.sha256(binary).hexdigest()},len(binary),cols*w*math.ceil(n/cols)*d*4


def atlas_from_stack_manifest(root,manifest_rel,approved_pose=None):
    """Read the EXACT existing Grunge Horror / Three.js stack.json + original PNG Z slices.

    This does not invent any new view or modify source actor art, and can reuse
    the same 360-degree cross-sections in Three.js GLSL and PixiJS/Matter gameplay.
    """
    raw=safe(root,manifest_rel)
    if len(raw)>200000:bad('Source stack.json too large')
    try:manifest=json.loads(raw)
    except (ValueError,UnicodeDecodeError):bad('Invalid original authored stack.json')
    if not isinstance(manifest,dict):bad('Original source stack.json must be JSON object')
    if approved_pose is not None:
        expected=hashlib.sha256(approved_pose).hexdigest()
        if manifest.get('source_pose_sha256')!=expected:
            bad('Actual approved actor frame SHA256 not matched by original stack.json')
    layers=manifest.get('layers')
    if not isinstance(layers,list) or not 8<=len(layers)<=96:
        bad('Physical mobile PixiJS mode needs 8..96 original stacked PNG layers; retain the real Three.js GLSL mode for up to 160')
    size=manifest.get('size')
    if type(size) is not int or not 16<=size<=512:bad('Stack source XY slice size must be 16..512')
    spacing=manifest.get('spacing')
    if not isinstance(spacing,list) or len(spacing)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in spacing):
        bad('Original stack.json needs physically real positive XYZ voxel spacing')
    path=Path(manifest_rel)
    sheet=[];sha=set();profiles=set()
    for rel in layers:
        p=(path.parent/rel).as_posix()
        content=safe(root,p)
        if p in sha:bad('Duplicate original source PNG layer PATH in stack.json')
        sha.add(p)
        rgba=_rgba(content,'original source stack layer')
        if rgba.shape[:2]!=(size,size):bad('Source stack.json layer dimensions mismatch')
        im=Image.fromarray(rgba,'RGBA');sheet.append(im)
        profiles.add((rgba[:,:,3]>90).tobytes())
    if len(profiles)<4:bad('Original stack.json lacks four distinct alpha cross-sections')
    data,cols,w,d=pack_slices(sheet)
    result={'atlas':'data:image/png;base64,'+base64.b64encode(data).decode('ascii'),
            'columns':cols,'width':w,'depth':d,'slices':len(layers),
            'height':float(spacing[2])*len(layers),'shape_profiles':len(profiles),
            'sha256':hashlib.sha256(data).hexdigest(),
            'source_stack_manifest':manifest_rel}
    return result,len(data),cols*w*math.ceil(len(layers)/cols)*d*4

def config_from_source(approved_zip,scene_path):
    scene_path=Path(scene_path).resolve();root=scene_path.parent
    verified=validate_scene(approved_zip)
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:bad('Original character ZIP corrupt')
        cfg=json.loads(z.read('scene.json'));gate=json.loads(z.read('motion_gate.json'))
        if gate.get('all_actors_pass') is not True:bad('Original full-body actor motion gate not passed')
        original=json.loads(scene_path.read_text('utf8'))
        if original.get('inventory')!=cfg.get('inventory'):
            bad('Original declared actor roster changed in approved ZIP')
        request=original.get('sprite_stacking_game',original.get('sprite_stacking'))
        if not isinstance(request,dict):bad('scene.sprite_stacking configuration required')
        allowed={'mode','minimum_coverage','azimuth_deg','elevation_deg','actors','objects','inventory','max_atlas_memory_mb','clean_plate','sampling'}
        if set(request)-allowed:bad('Unexpected sprite_stacking keys '+str(sorted(set(request)-allowed)))
        if request.get('mode','maximal')!='maximal':bad('Sprite stacking export prioritizes maximal mode only')
        coverage=finite(request.get('minimum_coverage',.90),.75,1,'minimum_coverage')
        azimuth=finite(request.get('azimuth_deg',35),-720,720,'azimuth_deg')
        elevation=finite(request.get('elevation_deg',32),12,72,'elevation_deg')
        max_mem=finite(request.get('max_atlas_memory_mb',110),16,220,'max_atlas_memory_mb')
        sampling=request.get('sampling','linear')
        if sampling not in ('linear','nearest'):bad('Sprite stacking supports original painterly linear or original pixel nearest sampling')
        cast={a['id']:a for a in cfg.get('actors',[])}
        visual_entities=request.get('inventory')
        if not isinstance(visual_entities,list) or not visual_entities:
            bad('Declare all visible volumetric actors/props/buildings/weapons/vehicles as sprite_stacking.inventory')
        declared={};ids=set()
        for item in visual_entities:
            if not isinstance(item,dict) or set(item)-{'id','category'}:bad('Invalid stacking.inventory entry')
            eid=strid(item.get('id'));kind=item.get('category')
            if eid in ids:bad('Duplicate volume ID '+eid)
            if kind not in ('actor','building','architecture','prop','weapon','vehicle','furniture','vegetation','terrain','door','gate','machine','monster'):
                bad('Unknown source volume category for '+eid)
            ids.add(eid);declared[eid]=kind
        if not set(cast).issubset(declared):bad('Every original animated person/monster must appear in stacking inventory')
        # An authored clean environment plate prevents stacking on top of a second
        # flattened copy of the same door/building/vehicle in the original picture.
        clean=None
        if request.get('objects'):
            if not request.get('clean_plate'):
                bad('With stacked props/buildings a real source-painted clean_plate PNG is required (avoid ghost duplicate objects)')
            clean_file=safe(root,request['clean_plate'])
            with Image.open(__import__('io').BytesIO(clean_file)) as image:
                with Image.open(z.open('source.png')) as original_image:
                    source_size=original_image.size
                if image.format!='PNG' or image.size!=source_size:
                    bad('Authored clean_plate must be real source-aligned PNG, no substitute background')
                if image.convert('RGBA').getchannel('A').getextrema()[1]==0:
                    bad('Original clean environmental plate is completely transparent')
            clean='data:image/png;base64,'+base64.b64encode(clean_file).decode('ascii')
        original_actor_ids={x for x in declared if declared[x]=='actor'}
        if original_actor_ids!=set(cast):bad('Actor ID roster differs from source inventory')
        original_actors=request.get('actors',[]);original_objects=request.get('objects',[])
        if not isinstance(original_actors,list) or not isinstance(original_objects,list) or len(original_objects)>200:
            bad('Invalid actor/prop stack lists or more than 200 world volumes')
        result_actors=[];result_objects=[];covered=set();bytes_total=0;mem=0;atlas_count=0
        for entry in original_actors:
            if not isinstance(entry,dict) or set(entry)-{'actor_id','reference_view','views_root','clips','slices','step_px','allow_resample','yaw_deg'}:
                bad('Unsupported actor stack authoring fields')
            actor_id=strid(entry.get('actor_id'))
            if actor_id not in cast or actor_id in covered:bad('Unknown or duplicate character stack '+actor_id)
            sourceview=entry.get('reference_view','front')
            if sourceview not in ('front','side','back'):bad('Character reference_view must be original front, side or back')
            views_root=entry.get('views_root')
            clips=entry.get('clips')
            if clips is not None and (not isinstance(clips,dict) or set(clips)!={c['action'] for c in cast[actor_id]['clips']}):
                bad('Actor source stack.json clips must list each approved original action exactly once')
            if clips is None and (not isinstance(views_root,str) or not views_root or any(x in ('','..','.') for x in views_root.split('/'))):
                bad('Each character needs either original Grunge Horror stack.json clips or a 4-view art root')
            count=entry.get('slices',32)
            if type(count) is not int or not 8<=count<=96:bad('Actor needs 8..96 real stack layers')
            step=finite(entry.get('step_px',cast[actor_id]['box'][3]/count),.1,12,'step_px')
            yaw=finite(entry.get('yaw_deg',0),-720,720,'yaw_deg')
            allow=entry.get('allow_resample',False)
            if type(allow) is not bool:bad('allow_resample must be explicit boolean')
            sequence=[];dims=None
            for clip in cast[actor_id]['clips']:
                action=strid(clip['action'])
                for frame in clip['frames']:
                    rel=frame.get('png')
                    if not isinstance(rel,str) or rel.startswith('/') or '..' in rel.split('/') or '\\' in rel:
                        bad('Unsafe original full body frame member')
                    basename=Path(rel).stem
                    src=z.read('project/inputs/'+rel)
                    if clips is not None:
                        index=len(sequence)-sum(len(c['frames']) for c in cast[actor_id]['clips'][:cast[actor_id]['clips'].index(clip)])
                        members=clips.get(action)
                        if not isinstance(members,list) or len(members)!=len(clip['frames']):
                            bad('Existing Three.js actor source stack.json list must match actual clip frame count')
                        atl,size,rgba_bytes=atlas_from_stack_manifest(root,members[index],src)
                        if atl['slices']!=count:bad('All 3D actor poses must use the same source slice count')
                    else:
                        # Original full body source art IS one of four views: three real extras only.
                        extras={k:f'{views_root}/{action}/{basename}_{k}.png' for k in ('top','side','front','back') if k!=sourceview}
                        extras[sourceview]='@original'
                        payload=source_viewset(extras,root,original=src,reference=sourceview)
                        atl,size,rgba_bytes=atlas_from_views(payload,count,allow)
                    if dims is None:dims=(atl['width'],atl['depth'],atl['height'])
                    if dims!=(atl['width'],atl['depth'],atl['height']):bad('Animated character volume geometry jumps size between poses')
                    sequence.append({'source_frame':rel,**atl})
                    bytes_total+=size;mem+=rgba_bytes;atlas_count+=1
            if len(sequence)<24:bad('Character lacks original independently painted frame stacks')
            result_actors.append({'id':actor_id,'reference_view':sourceview,'step_px':step,
                                  'yaw_deg':yaw,'box':cast[actor_id]['box'],'frames':sequence})
            covered.add(actor_id)
        for entry in original_objects:
            if not isinstance(entry,dict) or set(entry)-{'id','position','yaw_deg','scale','slices','step_px','z','views','stack','states','open_trigger','collider','allow_resample'}:
                bad('Unsupported object stack schema')
            eid=strid(entry.get('id'))
            if eid not in declared or declared[eid]=='actor' or eid in covered:bad('Duplicate/undeclared non-actor volume '+eid)
            p=entry.get('position')
            if not isinstance(p,list) or len(p)!=2:bad('Object position must be source-world [x,y]')
            x,y=[finite(v,0,verified['width'] if k==0 else verified['height'],'source world position') for k,v in enumerate(p)]
            count=entry.get('slices',32)
            if type(count) is not int or not 8<=count<=96:bad('Object needs 8..96 real stack layers')
            yaw=finite(entry.get('yaw_deg',0),-720,720,'yaw_deg')
            step=finite(entry.get('step_px',1),.10,12,'step_px');scale=finite(entry.get('scale',1),.2,4,'scale')
            zvalue=finite(entry.get('z',20),-10000,10000,'z')
            allow=entry.get('allow_resample',False)
            if type(allow) is not bool:bad('Object allow_resample must be boolean')
            states=entry.get('states')
            if states is None:
                if 'stack' in entry:states={'default':{'stack':entry['stack']}}
                elif 'views' in entry:states={'default':entry['views']}
                else:bad('Every object needs original four-view art or genuine existing stack.json')
            if not isinstance(states,dict) or not states or len(states)>4:
                bad('Object states must be 1..4 actual separately authored full-view volumes')
            if 'open_trigger' in entry and set(states)!={'closed','open'}:
                bad('Doors with open_trigger require both original closed/open 3D view packs')
            finished={};dims=None
            for label,views in states.items():
                strid(label)
                if isinstance(views,str):views={'stack':views}
                if isinstance(views,dict) and set(views)=={'stack'}:
                    atl,size,rgba_bytes=atlas_from_stack_manifest(root,views['stack'])
                    if atl['slices']!=count:bad('Original object 3D stack count differs from requested PixiJS layering')
                else:
                    payload=source_viewset(views,root)
                    atl,size,rgba_bytes=atlas_from_views(payload,count,allow)
                if dims is None:dims=(atl['width'],atl['depth'],atl['height'])
                if dims!=(atl['width'],atl['depth'],atl['height']):bad('Original closed/open door dimensions differ')
                finished[label]=atl
                bytes_total+=size;mem+=rgba_bytes;atlas_count+=1
            trigger=entry.get('open_trigger')
            obstacle=entry.get('collider')
            if trigger is not None:
                if not isinstance(trigger,str) or trigger not in {s.get('id') for s in cfg.get('matter',{}).get('sensors',[])}:
                    bad('Stacked door opener must reference a real Matter.js sensor from source scene')
                if not isinstance(obstacle,list) or len(obstacle)!=4:
                    bad('Openable source door must reference a real Matter.js/Godot rectangular obstacle')
                if list(obstacle) not in cfg.get('godot',{}).get('obstacles',[]):
                    bad('Door collider must match a real authored obstacle [x,y,w,h]')
            result_objects.append({'id':eid,'category':declared[eid],'position':[x,y], 'z':zvalue,
                                   'step_px':step,'scale':scale,'yaw_deg':yaw,
                                   'states':finished,'open_trigger':trigger,'collider':obstacle})
            covered.add(eid)
    if not covered:bad('No actual original multi-layer volumes could be compiled')
    share=len(covered)/len(declared)
    if share+1e-10<coverage:
        bad(f'Only {share:.0%} of declared 3D volumes source-authored as full sprite stacks, requires {coverage:.0%}; missing '+str(sorted(set(declared)-covered)))
    if mem>max_mem*1024*1024:bad(f'GPU atlas memory {mem/1048576:.1f} MB exceeds declared budget {max_mem:.1f} MB')
    if bytes_total>65_000_000:bad('Stack textures exceed 65MB compressed; reduce source atlas dimensions')
    return {'actors':result_actors,'objects':result_objects,'clean_plate':clean,'azimuth_deg':azimuth,
            'elevation_deg':elevation,'coverage':share,'layer_count':sum(x['frames'][0]['slices'] for x in result_actors)+sum(next(iter(x['states'].values()))['slices'] for x in result_objects),
            'original_source_gate':True,'source_pixels_replaced':0,'genuine_four_view_projection':True,'sampling':sampling,
            'compressed_atlas_bytes':bytes_total,'estimated_texture_bytes':mem,'atlas_count':atlas_count,
            'source_object_inventory':len(declared),'stacked_objects':len(covered)}


def archive_original_views(approved_zip,scene_path):
    """Preserve all real four-view original PNGs and clean plate in source ZIP.

    Never modify already-verified character pose PNG or gate certification.
    """
    scene_path=Path(scene_path).resolve();root=scene_path.parent
    cfg=json.loads(scene_path.read_text('utf8'));stack=cfg.get('sprite_stacking_game',cfg.get('sprite_stacking'))
    with zipfile.ZipFile(approved_zip) as z:
        original=json.loads(z.read('scene.json'))
        if z.testzip() is not None:bad('Approved source art archive is damaged before 3D source preservation')
    files={}
    def add(path):
        if path is None or path=='@original':return
        content=safe(root,path)
        if len(content)>16_000_000:bad('Source orthographic art exceeds file budget')
        files[path]=content
    add(stack.get('clean_plate'))
    def add_manifest(path):
        add(path)
        manifest=json.loads(safe(root,path))
        if not isinstance(manifest,dict) or not isinstance(manifest.get('layers'),list):
            bad('Stack source file is not original layered stack.json')
        for rel in manifest['layers']:add((Path(path).parent/rel).as_posix())
    for actor in stack.get('actors',[]):
        aid=actor['actor_id'];reference=actor.get('reference_view','front')
        cliplist=next((a['clips'] for a in original.get('actors',[]) if a['id']==aid),None)
        if cliplist is None:bad('Original approved character source missing')
        if actor.get('clips') is not None:
            for manifests in actor['clips'].values():
                for path in manifests:add_manifest(path)
        else:
            for clip in cliplist:
                for frame in clip['frames']:
                    stem=Path(frame['png']).stem
                    for view in ('top','side','front','back'):
                        if view!=reference:add(f"{actor['views_root']}/{clip['action']}/{stem}_{view}.png")
    for item in stack.get('objects',[]):
        states=item.get('states',{'default':{'stack':item['stack']} if 'stack' in item else item.get('views')})
        for views in states.values():
            if isinstance(views,str):add_manifest(views)
            elif isinstance(views,dict):
                if set(views)=={'stack'}:add_manifest(views['stack'])
                else:
                    for source in views.values():add(source)
    existing_hashes={}
    with zipfile.ZipFile(approved_zip,'r') as z:
        names=set(z.namelist())
        for path in files:
            target='project/sprite_stacking/original_views/'+path
            if target in names:bad('Original 360 source asset would overwrite an existing ZIP member: '+path)
    entries={}
    with zipfile.ZipFile(approved_zip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path,raw in sorted(files.items()):
            target='project/sprite_stacking/original_views/'+path
            z.writestr(target,raw)
            entries[path]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'archive_member':target}
        m='project/sprite_stacking/original_views_manifest.json'
        if m in names:bad('Original stack view manifest already exists')
        z.writestr(m,json.dumps(entries,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:bad('Source ZIP broken while archiving original 360 views')
    return {'archived_original_views':len(files),'archive_members':entries}


def patch_html(approved_zip,scene_path,upstream_html,out_html):
    data=config_from_source(approved_zip,scene_path)
    html=Path(upstream_html).resolve().read_text('utf8')
    if 'Matter.Engine.create' not in html or 'PF.AStarFinder' not in html or 'window.nipplejs' not in html:
        bad('The source must be a real verified original PixiJS8/Matter.js/A*/nipplejs game HTML')
    if 'YUKA' in html and 'window.YUKA' not in html:bad('YUKA marker present but real NPC AI absent')
    pattern=r'<script id="lia-scene" type="application/json">(.*?)</script>'
    scene_match=re.search(pattern,html,re.S)
    if not scene_match:bad('Original full-body actor JSON missing')
    digest=hashlib.sha256(scene_match.group(1).encode('utf8')).hexdigest()
    if html.count(' let frameTime=0;let accumulator=0;let paused=false;')!=1:
        bad('Original engine frame initialization changed; no unsound patch')
    if html.count('if(frame!==a.last){a.visual.texture=a.frames[frame];a.last=frame;}')!=1:
        bad('Original frame-by-frame actor update changed; cannot bypass source pose timeline')
    js=Path(__file__).with_name('sprite_stacking_runtime.js').read_text('utf8')
    html=html.replace(' let frameTime=0;let accumulator=0;let paused=false;',
        js+'\n let frameTime=0;let accumulator=0;let paused=false;',1)
    html=html.replace('if(frame!==a.last){a.visual.texture=a.frames[frame];a.last=frame;}',
        'if(frame!==a.last){a.visual.texture=a.frames[frame];a.last=frame;'+
        'if(a.spriteStack)setStackPose(a,frame);}',1)
    meta=json.dumps(data,separators=(',',':'),ensure_ascii=False).replace('<','\\u003c')
    if html.count('<script id="lia-scene"')!=1:bad('Unexpected source scene anchor')
    html=html.replace('<script id="lia-scene"',
        '<script id="lia-stacks" type="application/json">'+meta+'</script><script id="lia-scene"',1)
    css='''\n#lia-stack-tools{position:fixed;right:max(12px,env(safe-area-inset-right));top:max(12px,env(safe-area-inset-top));display:flex;gap:7px;z-index:9;touch-action:manipulation}
#lia-stack-tools button{background:#142028e8;border:1px solid #6e8290;border-radius:8px;color:#dde8ee;padding:9px 12px;font:600 14px system-ui;cursor:pointer;touch-action:manipulation}
@media (pointer:fine){#lia-stack-tools button{opacity:.7}}\n'''
    if html.count('</style></head>')!=1:bad('Approved HTML style anchor changed')
    html=html.replace('</style></head>',css+'</style></head>',1)
    if html.count('<div id="error" role="alert"></div>')!=1:bad('Approved HTML controls anchor changed')
    html=html.replace('<div id="error" role="alert"></div>',
        '<div id="error" role="alert"></div><div id="lia-stack-tools" aria-label="Поворот объёмной сцены"><button id="lia-stack-left" aria-label="Повернуть влево">⟲</button><button id="lia-stack-right" aria-label="Повернуть вправо">⟳</button><button id="lia-stack-up" aria-label="Поднять камеру">＋</button><button id="lia-stack-down" aria-label="Опустить камеру">−</button></div>',1)
    checked=re.search(pattern,html,re.S)
    if not checked or hashlib.sha256(checked.group(1).encode('utf8')).hexdigest()!=digest:
        bad('Source artist-approved full-body actor PNG scene changed during 3D export')
    if len(html.encode('utf8'))>150*1024*1024:bad('Offline HTML exceeds 150 MiB')
    dest=Path(out_html).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():bad('Refuse to overwrite previous game; choose a fresh output directory')
    temporary=dest.with_suffix('.tmp');temporary.write_text(html,'utf8');os.replace(temporary,dest)
    stats={k:v for k,v in data.items() if k not in ('actors','objects','clean_plate')}
    stats.update({'game_html':str(dest),'source_scene_sha256':digest,
                  'render':'true horizontal source-3D sprite stacking in existing physical PixiJS game',
                  'npc_ai_retained':'window.YUKA' in html,'matter_physics_retained':True,
                  'mobile_controls_retained':True,'all_cast_art_unchanged':True,
                  'offline':True,'bytes':dest.stat().st_size,
                  'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    return dest,stats

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--approved-zip',required=True,type=Path)
    a.add_argument('--scene',required=True,type=Path);a.add_argument('--game-html',required=True,type=Path)
    a.add_argument('--out',required=True,type=Path);s=a.parse_args()
    print(json.dumps(patch_html(s.approved_zip,s.scene,s.game_html,s.out)[1],ensure_ascii=False))
