"""Real GLB bytes, synthetic triangle/translation clip; no network/encoder mock or artistic approval."""
import hashlib,json,struct,tempfile,unittest
from pathlib import Path
import gltf_transform_bridge as bridge

def fixture(path):
    binary=struct.pack('<9f',0,0,0,1,0,0,0,1,0)+struct.pack('<3H',0,1,2)+b'\0\0'+struct.pack('<2f',0,1)+struct.pack('<6f',0,0,0,0,.1,0)
    doc={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'name':'fixture-triangle','mesh':0}],
      'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
      'buffers':[{'byteLength':len(binary)}],
      'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36,'target':34962},{'buffer':0,'byteOffset':36,'byteLength':6,'target':34963},{'buffer':0,'byteOffset':44,'byteLength':8},{'buffer':0,'byteOffset':52,'byteLength':24}],
      'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[0,0,0],'max':[1,1,0]},{'bufferView':1,'componentType':5123,'count':3,'type':'SCALAR'},{'bufferView':2,'componentType':5126,'count':2,'type':'SCALAR','min':[0],'max':[1]},{'bufferView':3,'componentType':5126,'count':2,'type':'VEC3'}],
      'animations':[{'name':'fixture-idle','samplers':[{'input':2,'output':3,'interpolation':'LINEAR'}],'channels':[{'sampler':0,'target':{'node':0,'path':'translation'}}]}]}
    data=json.dumps(doc,separators=(',',':')).encode();data+=b' '*((-len(data))%4)
    path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(data)+len(binary))+struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary)

class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.src=self.root/'fixture.glb';fixture(self.src)
        self.before=hashlib.sha256(self.src.read_bytes()).hexdigest();self.items=[{'id':'fixture','source':self.src}]
        self.missing=self.root/'uninstalled-gltf-transform.mjs'
    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(),self.before);self.tmp.cleanup()
    def test_auto_missing_explicit_cli_retains_original(self):
        selected,results=bridge.optimize(self.items,self.root/'out',policy='auto',executable=self.missing)
        self.assertEqual(selected[0]['source'],self.src);self.assertEqual(results[0]['status'],'unavailable');self.assertFalse((self.root/'out').exists())
    def test_required_missing_explicit_cli_fails(self):
        with self.assertRaises(bridge.OptimizationError):bridge.optimize(self.items,self.root/'out',policy='required',executable=self.missing)
    def test_off_does_not_require_cli_and_real_glb_keeps_clip(self):
        selected,results=bridge.optimize(self.items,self.root/'out',policy='off',executable=self.missing)
        self.assertEqual(results[0]['status'],'disabled');self.assertEqual(bridge.read_glb(selected[0]['source'])['clips'],['fixture-idle'])
        self.assertEqual(len(bridge.glb_json(self.src)['accessors']),4)

if __name__=='__main__':unittest.main(verbosity=2)
