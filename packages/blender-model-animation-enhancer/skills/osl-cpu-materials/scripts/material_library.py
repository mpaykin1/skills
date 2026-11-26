"""Create an independent Blender material library from a checked PBR candidate."""
import argparse,sys,json,hashlib
from pathlib import Path
import bpy

def main():
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);p.add_argument('output',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=a.pack.resolve();out=a.output.resolve();assert not out.exists() and out.suffix=='.blend','must create new library';m=json.loads((root/'material.json').read_text());assert m['schema']=='meta-osl-pbr-v1' and m['preset'] in ('steel','cloth');
    bpy.ops.wm.read_factory_settings(use_empty=True);mat=bpy.data.materials.new('META_'+m['preset']+'_CANDIDATE');mat.use_nodes=True;mat.use_fake_user=True;mat['material_recipe_sha256']=hashlib.sha256((root/'material.json').read_bytes()).hexdigest();mat['approved']=False;nt=mat.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');uv=nt.nodes.new('ShaderNodeTexCoord');maps={}
    for key in ['baseColor','normal','orm']:
        f=root/(key+'.png');assert m['maps'][key]['file']==f.name and hashlib.sha256(f.read_bytes()).hexdigest()==m['maps'][key]['sha256'];im=bpy.data.images.load(str(f),check_existing=False);assert tuple(im.size)==(m['size'],m['size']);im.colorspace_settings.name='sRGB' if key=='baseColor' else 'Non-Color';im.pack();node=nt.nodes.new('ShaderNodeTexImage');node.image=im;node.extension='EXTEND';nt.links.new(uv.outputs['UV'],node.inputs['Vector']);maps[key]=node
    nt.links.new(maps['baseColor'].outputs['Color'],bs.inputs['Base Color']);sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(maps['orm'].outputs['Color'],sep.inputs['Color']);nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic']);normal=nt.nodes.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.inputs['Strength'].default_value=1;nt.links.new(maps['normal'].outputs['Color'],normal.inputs['Color']);nt.links.new(normal.outputs['Normal'],bs.inputs['Normal']);bpy.ops.wm.save_as_mainfile(filepath=str(out));assert out.is_file()
if __name__=='__main__':main()
