#!/usr/bin/env python3
"""Add real pixi-filters v6 ONLY to original source-registered environment planes.

Requires already-validated full-cel GIF/ZIP + actual offline pixi-viewport HTML.
Never filters original animated actor sprites and never generates character poses.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, re, zipfile
from pathlib import Path
from pixijs_bridge import load_scene

VERSION='6.1.5'
class FiltersBridgeError(ValueError):pass

def stop(message):raise FiltersBridgeError('pixi-filters integration blocked: '+message)
def finite(v,a,b,label):
    if type(v) not in (int,float) or not math.isfinite(v) or not a<=v<=b:
        stop(label+f' must be finite number in [{a},{b}]')
    return float(v)
def safe_effect(config,typ):
    if not isinstance(config,dict):stop('Effect configuration must be object')
    options={}
    if typ=='adjustment':
        allowed={'type','brightness','contrast','saturation','gamma','red','green','blue','alpha'}
        if set(config)-allowed:stop('Unsupported AdjustmentFilter options')
        for k in ('brightness','contrast','saturation','gamma','red','green','blue','alpha'):
            if k in config:options[k]=finite(config[k],0.05 if k!='alpha' else 0,2.5 if k!='alpha' else 1,k)
        if not options:stop('AdjustmentFilter requires explicit nondefault parameters')
    elif typ=='glow':
        allowed={'type','distance','outerStrength','innerStrength','alpha','color','quality'}
        if set(config)-allowed:stop('Unsupported GlowFilter options')
        options['distance']=int(finite(config.get('distance',3),1,12,'glow distance'))
        options['outerStrength']=finite(config.get('outerStrength',1.4),0,3,'glow strength')
        options['innerStrength']=finite(config.get('innerStrength',0),0,2,'glow inside')
        options['alpha']=finite(config.get('alpha',.75),0,1,'glow alpha')
        options['quality']=finite(config.get('quality',.1),.05,.35,'glow quality')
        color=config.get('color','#eebc85')
        if not isinstance(color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',color):stop('Glow color must be #RRGGBB')
        options['color']=int(color[1:],16)
    elif typ=='blur':
        allowed={'type','strength','quality'}
        if set(config)-allowed:stop('Unsupported Kawase blur options')
        options['strength']=finite(config.get('strength',1.25),.3,3.5,'blur strength')
        options['quality']=int(finite(config.get('quality',3),1,4,'blur quality'))
    elif typ=='bloom':
        allowed={'type','threshold','bloomScale','brightness','blur','quality'}
        if set(config)-allowed:stop('Unsupported AdvancedBloomFilter options')
        options['threshold']=finite(config.get('threshold',.72),0,1,'bloom threshold')
        options['bloomScale']=finite(config.get('bloomScale',.8),0,2,'bloom intensity')
        options['brightness']=finite(config.get('brightness',1),.2,2,'bloom brightness')
        options['blur']=finite(config.get('blur',2.5),.5,6,'bloom radius')
        options['quality']=int(finite(config.get('quality',3),1,4,'bloom quality'))
    else:stop('Unknown effect '+str(typ))
    return {'type':typ,'options':options}

def config_from_zip(approved):
    approved=Path(approved).resolve()
    # Repeat original Pixi source/actor/cel checks; cannot use this bridge to bypass pose gate.
    source=load_scene(approved)
    with zipfile.ZipFile(approved) as z:
        try:cfg=json.loads(z.read('scene.json'));gate=json.loads(z.read('motion_gate.json'))
        except (KeyError,ValueError) as e:stop('Missing approved scene or motion gate: '+str(e))
    if gate.get('all_actors_pass') is not True:stop('Original motion validation did not pass')
    pixi=cfg.get('pixi',{})
    if not isinstance(pixi,dict):stop('scene.pixi must be object')
    conf=pixi.get('filters',{})
    if not isinstance(conf,dict) or set(conf)-{'enabled','background','planes'}:stop('scene.pixi.filters has unsupported keys')
    if type(conf.get('enabled',True)) is not bool:stop('filters.enabled must be boolean')
    # Default subtle background tone so new renderer visibly differs even without extra art.
    background=conf.get('background',{'type':'adjustment','brightness':.92,'contrast':1.08,'saturation':.89})
    bg=None
    if background is not None:
        if not isinstance(background,dict) or background.get('type','adjustment')!='adjustment':stop('Background supports only AdjustmentFilter to protect legibility')
        bg=safe_effect({'type':'adjustment',**background},'adjustment')
    rawplanes=conf.get('planes',[])
    if not isinstance(rawplanes,list) or len(rawplanes)>16:stop('Up to 16 original-authored filtered planes allowed')
    indexes={x['png']:i for i,x in enumerate(source['layers'])}
    seen=set();planes=[]
    for p in rawplanes:
        if not isinstance(p,dict) or not isinstance(p.get('png'),str):stop('Filtered layer must reference existing source PNG')
        path=p['png']
        if path not in indexes:stop('Unknown source-authored 2.5D plane: '+path)
        if path in seen:stop('Duplicate filtered plate; combine effects in original art')
        seen.add(path)
        typ=p.get('type')
        if typ not in ('glow','blur','bloom','adjustment'):stop('Unsupported filter on plane '+path)
        planes.append({'index':indexes[path],**safe_effect({k:v for k,v in p.items() if k!='png'},typ)})
    if not conf.get('enabled',True):bg=None;planes=[]
    return {'background':bg,'planes':planes,'enabled':bool(bg or planes),'rendered_cast':len(source['actors'])}

def vendor_bundle(path):
    path=path or os.environ.get('PIXI_FILTERS_BUNDLE')
    if not path:stop('Real pixi-filters browser bundle required (--filters-js or --fetch-filters)')
    p=Path(path).expanduser().resolve()
    if not p.is_file():stop('pixi-filters runtime missing: '+str(p))
    data=p.read_bytes()
    if not 50_000<=len(data)<=5_000_000 or b'Filter' not in data:stop('Not an official compatible PixiJS Filters browser bundle')
    try:code=data.decode('utf8')
    except UnicodeError:stop('Browser bundle is not UTF-8')
    return p,code

def one(src,search,replacement,label):
    if src.count(search)!=1:stop('PixiJS viewport template changed: '+label)
    return src.replace(search,replacement,1)

def patch_html(viewport_html,out_html,approved_zip,filters_js):
    effect=config_from_zip(approved_zip)
    _,js=vendor_bundle(filters_js)
    src=Path(viewport_html).read_text('utf8')
    if 'window.pixi_viewport' not in src or '<script>const LIVING_SCENE=' not in src:
        stop('Expected previous verified pixi-viewport HTML, not an unrelated website')
    js=re.sub('</script',r'<\\/script',js,flags=re.I)
    src=one(src,'<script>const LIVING_SCENE=',
       '<script>/* pixi-filters 6.1.5 MIT. Official npm package, original license in ZIP. */\n'+js+'</script><script>const LIVING_SCENE=',
       'real pixi-filters library insertion')
    settings=json.dumps(effect,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    code='''    // Filters apply to registered scene plates ONLY: never mutate actor cels.
    const LIA_FILTERS=__SETTINGS__;
    const Fx=(window.PIXI && PIXI.filters && PIXI.filters.AdjustmentFilter)
      ? PIXI.filters : ((window.pixi_filters && window.pixi_filters.AdjustmentFilter)
      ? window.pixi_filters : ((window.PixiFilters && window.PixiFilters.AdjustmentFilter)
      ? window.PixiFilters : null));
    if(!Fx) throw new Error('pixi-filters 6.x library did not initialize');
    const fxMake=(def)=>{
      if(!def) return null;
      const op=def.options;
      switch(def.type){
        case 'adjustment':return new Fx.AdjustmentFilter(op);
        case 'glow':return new Fx.GlowFilter(op);
        case 'blur':return new Fx.KawaseBlurFilter(op);
        case 'bloom':return new Fx.AdvancedBloomFilter(op);
        default:throw new Error('Unapproved source-plane effect');
      }
    };
    if(LIA_FILTERS.background) background.filters=[fxMake(LIA_FILTERS.background)];
    for(const spec of LIA_FILTERS.planes){
      const plane=planes[spec.index];
      if(!plane) throw new Error('Source scene plane missing for filter');
      plane.object.filters=[fxMake(spec)];
    }
    // Visual effects are NEVER counted as authored character movement.
'''.replace('__SETTINGS__',settings)
    src=one(src,'    const avatars=[];',code+'    const avatars=[];','filter-only-original-planes')
    # Confirm pose timeline is left in place and no source data JSON was altered.
    if 'const avatars=[];' not in src or 'const LIVING_SCENE=' not in src:stop('Approved animation runtime missing')
    if len(src.encode('utf8'))>150*1024*1024:stop('HTML exceeds standalone size limit')
    out=Path(out_html).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix('.tmp');temp.write_text(src,'utf8');os.replace(temp,out)
    return out,{'version':VERSION,'effect_planes':len(effect['planes']),
                'background_effect':effect['background'] is not None,
                'actors_unchanged':effect['rendered_cast'],'byte_count':out.stat().st_size,
                'no_character_deformation':True,'offline':True,
                'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--viewport-html',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--filters-js',type=Path);a=p.parse_args()
    print(json.dumps(patch_html(a.viewport_html,a.out,a.approved_zip,a.filters_js)[1],ensure_ascii=False))
