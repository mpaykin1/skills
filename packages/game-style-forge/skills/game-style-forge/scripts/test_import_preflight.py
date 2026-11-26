"""Stdlib regression; fixture is a synthetic GLB triangle with one clip."""
import base64,contextlib,io,json,tempfile,types,unittest
from pathlib import Path
import assets_gltf as module
FIXTURE='Z2xURgIAAAD8AwAAlAMAAEpTT057ImFzc2V0Ijp7InZlcnNpb24iOiIyLjAifSwic2NlbmUiOjAsInNjZW5lcyI6W3sibm9kZXMiOlswXX1dLCJub2RlcyI6W3sibmFtZSI6ImZpeHR1cmUtdHJpYW5nbGUiLCJtZXNoIjowfV0sIm1lc2hlcyI6W3sicHJpbWl0aXZlcyI6W3siYXR0cmlidXRlcyI6eyJQT1NJVElPTiI6MH0sImluZGljZXMiOjF9XX1dLCJidWZmZXJzIjpbeyJieXRlTGVuZ3RoIjo3Nn1dLCJidWZmZXJWaWV3cyI6W3siYnVmZmVyIjowLCJieXRlT2Zmc2V0IjowLCJieXRlTGVuZ3RoIjozNiwidGFyZ2V0IjozNDk2Mn0seyJidWZmZXIiOjAsImJ5dGVPZmZzZXQiOjM2LCJieXRlTGVuZ3RoIjo2LCJ0YXJnZXQiOjM0OTYzfSx7ImJ1ZmZlciI6MCwiYnl0ZU9mZnNldCI6NDQsImJ5dGVMZW5ndGgiOjh9LHsiYnVmZmVyIjowLCJieXRlT2Zmc2V0Ijo1MiwiYnl0ZUxlbmd0aCI6MjR9XSwiYWNjZXNzb3JzIjpbeyJidWZmZXJWaWV3IjowLCJjb21wb25lbnRUeXBlIjo1MTI2LCJjb3VudCI6MywidHlwZSI6IlZFQzMiLCJtaW4iOlswLDAsMF0sIm1heCI6WzEsMSwwXX0seyJidWZmZXJWaWV3IjoxLCJjb21wb25lbnRUeXBlIjo1MTIzLCJjb3VudCI6MywidHlwZSI6IlNDQUxBUiJ9LHsiYnVmZmVyVmlldyI6MiwiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjIsInR5cGUiOiJTQ0FMQVIiLCJtaW4iOlswXSwibWF4IjpbMV19LHsiYnVmZmVyVmlldyI6MywiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjIsInR5cGUiOiJWRUMzIn1dLCJhbmltYXRpb25zIjpbeyJuYW1lIjoiZml4dHVyZS1pZGxlIiwic2FtcGxlcnMiOlt7ImlucHV0IjoyLCJvdXRwdXQiOjMsImludGVycG9sYXRpb24iOiJMSU5FQVIifV0sImNoYW5uZWxzIjpbeyJzYW1wbGVyIjowLCJ0YXJnZXQiOnsibm9kZSI6MCwicGF0aCI6InRyYW5zbGF0aW9uIn19XX1dfSAgTAAAAEJJTgAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAACAPwAAAAAAAAEAAgAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAAAAAM3MzD0AAAAA'
class ImportPreflight(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.workspace=self.root/'workspace';self.workspace.mkdir()
  (self.workspace/'integrations.lock.json').write_text(json.dumps({'integrated':{'gltf-transform':{}}}),encoding='utf-8')
  self.source=self.root/'fixture.glb';self.source.write_bytes(base64.b64decode(FIXTURE));self.before=self.source.read_bytes()
 def tearDown(self):
  self.assertEqual(self.source.read_bytes(),self.before);self.tmp.cleanup()
 def run_import(self,collider):
  args=types.SimpleNamespace(workspace=str(self.workspace),input=str(self.source),name='sample',position=[0,0,0],scale=1,collider=collider)
  with contextlib.redirect_stdout(io.StringIO()):module.add_model(args)
 def test_invalid_dimensions_leave_no_assets(self):
  for collider in [[0,1,1],[-1,1,1],[101,1,1]]:
   with self.subTest(collider=collider):
    with self.assertRaisesRegex(ValueError,'Collider dimensions'):self.run_import(collider)
    self.assertFalse((self.workspace/'assets').exists())
 def test_valid_retry_retains_clip_and_duplicate_guard(self):
  with self.assertRaisesRegex(ValueError,'Collider dimensions'):self.run_import([0,1,1])
  self.run_import([1,1,1])
  model=self.workspace/'assets/models/raw/sample.glb';manifest=self.workspace/'assets/models.json'
  self.assertEqual(model.read_bytes(),self.before);doc=json.loads(manifest.read_text())
  self.assertEqual(doc['models'][0]['source_counts']['animations'],1)
  old=manifest.read_bytes()
  with self.assertRaisesRegex(ValueError,'already registered'):self.run_import([1,1,1])
  self.assertEqual(manifest.read_bytes(),old);self.assertEqual(model.read_bytes(),self.before)
 def test_invalid_preserves_existing_manifest(self):
  path=self.workspace/'assets/models.json';path.parent.mkdir();old=b'{"schema":1,"models":[]}'
  path.write_bytes(old)
  with self.assertRaisesRegex(ValueError,'Collider dimensions'):self.run_import([101,1,1])
  self.assertEqual(path.read_bytes(),old);self.assertFalse((self.workspace/'assets/models').exists())
 def test_valid_no_collider(self):
  self.run_import(None);doc=json.loads((self.workspace/'assets/models.json').read_text());self.assertIsNone(doc['models'][0]['collider'])
if __name__=='__main__':unittest.main(verbosity=2)
