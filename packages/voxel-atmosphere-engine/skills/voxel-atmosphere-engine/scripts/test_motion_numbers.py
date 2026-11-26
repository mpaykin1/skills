"""Portable stdlib regression. Synthetic technical GLB, no art/runtime claim."""
import base64,hashlib,math,struct,tempfile,unittest
from pathlib import Path
import glb_motion as motion
FIXTURE = 'Z2xURgIAAAD8AwAAlAMAAEpTT057ImFzc2V0Ijp7InZlcnNpb24iOiIyLjAifSwic2NlbmUiOjAsInNjZW5lcyI6W3sibm9kZXMiOlswXX1dLCJub2RlcyI6W3sibmFtZSI6ImZpeHR1cmUtdHJpYW5nbGUiLCJtZXNoIjowfV0sIm1lc2hlcyI6W3sicHJpbWl0aXZlcyI6W3siYXR0cmlidXRlcyI6eyJQT1NJVElPTiI6MH0sImluZGljZXMiOjF9XX1dLCJidWZmZXJzIjpbeyJieXRlTGVuZ3RoIjo3Nn1dLCJidWZmZXJWaWV3cyI6W3siYnVmZmVyIjowLCJieXRlT2Zmc2V0IjowLCJieXRlTGVuZ3RoIjozNiwidGFyZ2V0IjozNDk2Mn0seyJidWZmZXIiOjAsImJ5dGVPZmZzZXQiOjM2LCJieXRlTGVuZ3RoIjo2LCJ0YXJnZXQiOjM0OTYzfSx7ImJ1ZmZlciI6MCwiYnl0ZU9mZnNldCI6NDQsImJ5dGVMZW5ndGgiOjh9LHsiYnVmZmVyIjowLCJieXRlT2Zmc2V0Ijo1MiwiYnl0ZUxlbmd0aCI6MjR9XSwiYWNjZXNzb3JzIjpbeyJidWZmZXJWaWV3IjowLCJjb21wb25lbnRUeXBlIjo1MTI2LCJjb3VudCI6MywidHlwZSI6IlZFQzMiLCJtaW4iOlswLDAsMF0sIm1heCI6WzEsMSwwXX0seyJidWZmZXJWaWV3IjoxLCJjb21wb25lbnRUeXBlIjo1MTIzLCJjb3VudCI6MywidHlwZSI6IlNDQUxBUiJ9LHsiYnVmZmVyVmlldyI6MiwiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjIsInR5cGUiOiJTQ0FMQVIiLCJtaW4iOlswXSwibWF4IjpbMV19LHsiYnVmZmVyVmlldyI6MywiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjIsInR5cGUiOiJWRUMzIn1dLCJhbmltYXRpb25zIjpbeyJuYW1lIjoiZml4dHVyZS1pZGxlIiwic2FtcGxlcnMiOlt7ImlucHV0IjoyLCJvdXRwdXQiOjMsImludGVycG9sYXRpb24iOiJMSU5FQVIifV0sImNoYW5uZWxzIjpbeyJzYW1wbGVyIjowLCJ0YXJnZXQiOnsibm9kZSI6MCwicGF0aCI6InRyYW5zbGF0aW9uIn19XX1dfSAgTAAAAEJJTgAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAACAPwAAAAAAAAEAAgAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAAAAAM3MzD0AAAAA'
class MotionNumbers(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'input.glb'
  self.source.write_bytes(base64.b64decode(FIXTURE));self.original=self.source.read_bytes()
 def tearDown(self):
  self.assertEqual(self.source.read_bytes(),self.original);self.tmp.cleanup()
 def test_invalid_api_preserves_existing_target(self):
  target=self.root/'existing.glb';target.write_bytes(b'preserve-existing-output')
  for key,value in [('duration',float('nan')),('duration',float('inf')),('duration',0),('duration',-1),('amplitude',float('nan')),('amplitude',float('inf')),('amplitude',-1)]:
   with self.subTest(key=key,value=value):
    with self.assertRaises(ValueError):motion.build_motion(self.source,target,**{key:value})
    self.assertEqual(target.read_bytes(),b'preserve-existing-output')
 def test_invalid_api_creates_no_target(self):
  target=self.root/'not-created'/'out.glb'
  with self.assertRaises(ValueError):motion.build_motion(self.source,target,duration=float('nan'))
  self.assertFalse(target.parent.exists())
 def test_positive_finite_tracks_and_original_clip(self):
  for action in ['hover','breathe']:
   target=self.root/(action+'.glb');motion.build_motion(self.source,target,motion=action,duration=4,amplitude=0.19)
   old,oldbin=motion.parse_glb(self.original);doc,buf=motion.parse_glb(target.read_bytes())
   self.assertEqual(doc['meshes'],old['meshes']);self.assertEqual(doc['nodes'],old['nodes'])
   self.assertEqual(doc['animations'][:-1],old['animations']);self.assertEqual(buf[:len(oldbin)],oldbin)
   clip=doc['animations'][-1];self.assertEqual(len(clip['channels']),3)
   for sampler in clip['samplers']:
    for key in ['input','output']:
     acc=doc['accessors'][sampler[key]];view=doc['bufferViews'][acc['bufferView']]
     count=acc['count']*{'SCALAR':1,'VEC3':3,'VEC4':4}[acc['type']]
     offset=view.get('byteOffset',0)+acc.get('byteOffset',0)
     values=struct.unpack_from('<'+'f'*count,buf,offset)
     self.assertTrue(all(math.isfinite(v) for v in values))
     if key=='input':self.assertEqual(values[0],0);self.assertEqual(values[-1],4);self.assertTrue(all(a<b for a,b in zip(values,values[1:])))
 def test_original_guards(self):
  with self.assertRaisesRegex(ValueError,'overwrite'):motion.build_motion(self.source,self.source)
  with self.assertRaisesRegex(ValueError,'Unsupported'):motion.build_motion(self.source,self.root/'bad.glb',motion='not-supported')
if __name__=='__main__':unittest.main(verbosity=2)
