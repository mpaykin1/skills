import json,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(sys.argv.pop(1)).resolve()
class OutlinerVisibility(unittest.TestCase):
    def test_hidden_and_regular(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);src=root/'model.bbmodel';out=root/'result.glb'
            cubes=[{'uuid':key,'name':key,'from':[0,0,0],'to':[16,16,16]} for key in ('hidden','shown')]
            def run(model):
                src.write_text(json.dumps(model),encoding='utf8');before=src.read_bytes()
                proc=subprocess.run([sys.executable,'-B','-S',str(SCRIPT),'--src',str(src),'--out',str(out)],capture_output=True,text=True)
                self.assertEqual(src.read_bytes(),before)
                return proc
            model={'meta':{},'elements':cubes,'outliner':[{'visibility':False,'children':['hidden','shown']}]}
            old=b'previous artifact';out.write_bytes(old)
            bad=run(model)
            self.assertNotEqual(bad.returncode,0,bad.stdout)
            self.assertIn('no visible cubes',bad.stderr)
            self.assertEqual(out.read_bytes(),old)
            out.unlink()
            bad=run(model)
            self.assertNotEqual(bad.returncode,0)
            self.assertFalse(out.exists())
            model['outliner']=[{'visibility':False,'children':['hidden']},'shown']
            good=run(model);self.assertEqual(good.returncode,0,good.stderr)
            raw=out.read_bytes();size,kind=struct.unpack_from('<II',raw,12)
            gltf=json.loads(raw[20:20+size])
            self.assertEqual([m['name'] for m in gltf['meshes']],['shown'])
            self.assertEqual(gltf['accessors'][0]['count'],24)
            del model['outliner']
            good=run(model);self.assertEqual(good.returncode,0,good.stderr)
            raw=out.read_bytes();size=struct.unpack_from('<I',raw,12)[0]
            self.assertEqual(len(json.loads(raw[20:20+size])['meshes']),2)
if __name__=='__main__':unittest.main()
