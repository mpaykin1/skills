"""Real CLI regression. Usage: python test_meshopt_lossless.py --cli /path/to/gltf-transform"""
import argparse,copy,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from gltf_transform_worker import read_glb,describe_asset

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cli',required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent
    source=here/'fixtures/meshopt-skinned-morph.glb'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for mode in ('safe','meshopt'):
            output=root/(mode+'.glb')
            done=subprocess.run([sys.executable,'-B','-S',str(here/'gltf_transform_worker.py'),'--input',str(source),'--output',str(output),'--mode',mode,'--gltf-transform-bin',args.cli],capture_output=True,text=True)
            assert done.returncode==0,done.stdout+done.stderr
            actual=read_glb(output);original=read_glb(source)
            assert describe_asset(original)==describe_asset(actual)
            if mode=='meshopt':assert 'EXT_meshopt_compression' in actual['extensionsRequired']
        for mutation in ('animation','skin','morph'):
            bad=copy.deepcopy(actual)
            if mutation=='animation':bad['animations'][0]['channels'][0]['target']['path']='scale'
            elif mutation=='skin':bad['skins'][0]['joints']=[]
            else:bad['meshes'][0]['primitives'][0]['targets']=[]
            assert describe_asset(original)!=describe_asset(bad)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    print(json.dumps({'actual_cli':'PASS','strict_guards':'PASS','synthetic':True,'browser_render':'UNTESTED'}))
if __name__=='__main__':main()
