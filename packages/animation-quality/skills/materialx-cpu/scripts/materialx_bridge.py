"""CPU-only MaterialX graph exchange from verified, opaque PBR map packs."""
import argparse, hashlib, json, re, shutil, tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image

PIN='1.39.4'
KEYS=('baseColor','normal','orm')
HEX=re.compile(r'[0-9a-f]{64}\Z')
def need(v,msg):
    if not v: raise ValueError(msg)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read_source(root):
    m=json.loads((root/'material.json').read_text())
    need(m['schema'] in ('meta-osl-pbr-v1','meta-material-maker-pbr-v1'),'unsupported material schema')
    n=m['size']; need(n in (256,512,1024,2048),'texture size')
    need(isinstance(m.get('tileable'),bool),'explicit tileability required')
    if m['schema']=='meta-osl-pbr-v1':
        need(m['preset'] in ('cloth','steel') and all(HEX.fullmatch(m[k]) for k in ('source_recipe_sha256','shader_sha256')),'OSL metadata')
    else:
        need(HEX.fullmatch(m['source_recipe_sha256']) and m.get('normal_convention')=='+Y' and m.get('orm_channels')==['occlusion','roughness','metallic'],'Material Maker export contract')
    for key in KEYS:
        e=m['maps'][key]; p=root/(key+'.png')
        need(e['file']==p.name and not p.is_symlink() and e['sha256']==digest(p),'map identity '+key)
        need(e['color_space']==('srgb' if key=='baseColor' else 'linear'),'color space '+key)
        with Image.open(p) as im:
            need(im.size==(n,n) and im.mode=='RGB' and im.format=='PNG','map dimensions or format '+key)
            im.load()
    return m

def graph(tileable):
    root=ET.Element('materialx',version='1.39',colorspace='lin_rec709')
    def node(category,name,typ,**kw): return ET.SubElement(root,category,name=name,type=typ,**kw)
    def inp(parent,name,typ,**kw): return ET.SubElement(parent,'input',name=name,type=typ,**kw)
    for name,typ,file in [('base','color3','baseColor.png'),('nrm','vector3','normal.png'),('ao','float','occlusion.png'),('rough','float','roughness.png'),('metal','float','metallic.png')]:
        a=node('image',name,typ); inp(a,'file','filename',value=file,**({'colorspace':'srgb_texture'} if name=='base' else {}))
        for k in ('uaddressmode','vaddressmode'): inp(a,k,'string',value='periodic' if tileable else 'clamp')
    n=node('normalmap','normal_world','vector3');inp(n,'in','vector3',nodename='nrm')
    s=node('gltf_pbr','surface','surfaceshader')
    for name,typ,source in [('base_color','color3','base'),('normal','vector3','normal_world'),('occlusion','float','ao'),('roughness','float','rough'),('metallic','float','metal')]: inp(s,name,typ,nodename=source)
    inp(s,'alpha_mode','integer',value='0')
    mat=node('surfacematerial','META_Material','material');inp(mat,'surfaceshader','surfaceshader',nodename='surface')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def export(source,out):
    m=read_source(source);need(not out.exists(),'output exists')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        p=Path(tmp)/'pack';p.mkdir()
        for k in KEYS: shutil.copyfile(source/(k+'.png'),p/(k+'.png'))
        with Image.open(p/'orm.png') as im:
            for name,ch in zip(('occlusion','roughness','metallic'),im.split()): ch.save(p/(name+'.png'))
        shutil.copyfile(source/'material.json',p/'source-material.json')
        (p/'material.mtlx').write_bytes(graph(m['tileable']))
        files={f.name:digest(f) for f in sorted(p.iterdir())}
        meta={'schema':'meta-materialx-pbr-v1','materialx_reference_version':PIN,'source_schema':m['schema'],'source_recipe_sha256':m['source_recipe_sha256'],'tileable':m['tileable'],'size':m['size'],'files':files,'approved':False,'native_validation':'not-run','normal_convention':'+Y','alpha_mode':'OPAQUE'}
        (p/'exchange.json').write_text(json.dumps(meta,indent=2)+'\n')
        audit(p)
        p.rename(out)

def audit(root):
    m=json.loads((root/'exchange.json').read_text());need(m['schema']=='meta-materialx-pbr-v1' and m['materialx_reference_version']==PIN and m['approved'] is False and m['alpha_mode']=='OPAQUE' and m['normal_convention']=='+Y','exchange contract')
    expected={'baseColor.png','normal.png','orm.png','occlusion.png','roughness.png','metallic.png','source-material.json','material.mtlx'}
    need(set(m['files'])==expected,'unexpected manifest paths')
    for f,h in m['files'].items(): need(not (root/f).is_symlink() and HEX.fullmatch(h) and digest(root/f)==h,'file hash '+f)
    src=json.loads((root/'source-material.json').read_text());need(src['schema']==m['source_schema'] and src['size']==m['size'] and src['tileable']==m['tileable'] and src['source_recipe_sha256']==m['source_recipe_sha256'],'source identity')
    need(m['size'] in (256,512,1024,2048),'dimensions')
    for key in KEYS:
        need(src['maps'][key]['sha256']==m['files'][key+'.png'] and src['maps'][key]['color_space']==('srgb' if key=='baseColor' else 'linear'),'source map mismatch')
        with Image.open(root/(key+'.png')) as im: need(im.mode=='RGB' and im.size==(m['size'],m['size']),'map format')
    with Image.open(root/'orm.png') as im:
        for name,ch in zip(('occlusion','roughness','metallic'),im.split()):
            with Image.open(root/(name+'.png')) as actual: need(actual.mode=='L' and actual.size==ch.size and actual.tobytes()==ch.tobytes(),'ORM split mismatch '+name)
    need((root/'material.mtlx').read_bytes()==graph(m['tileable']),'graph differs from supported safe subset')
    return m

def validate_native(root):
    audit(root)
    import MaterialX as mx
    need(mx.getVersionString()==PIN,'use reviewed MaterialX '+PIN)
    doc=mx.createDocument(); library=mx.createDocument()
    mx.loadLibraries(mx.getDefaultDataLibraryFolders(),mx.getDefaultDataSearchPath(),library)
    need(library.getNodeDef('ND_gltf_pbr_surfaceshader') is not None,'missing standard library')
    mx.readFromXmlFile(doc,str(root/'material.mtlx'))
    doc.importLibrary(library)
    valid,message=doc.validate();need(valid,'MaterialX validation failed: '+message)
    print('Native graph validation succeeded; not rendering or artistic approval.')

if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('export');a.add_argument('source',type=Path);a.add_argument('out',type=Path)
    for name in ('audit','validate-native'): a=sub.add_parser(name);a.add_argument('pack',type=Path)
    a=p.parse_args()
    if a.command=='export':export(a.source,a.out)
    elif a.command=='audit':audit(a.pack)
    else:validate_native(a.pack)
