import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from anti_jerk_gate import validate_game_replay,validate

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.manifest=self.root/'manifest.json';self.scene=self.root/'scene.json';self.replay=self.root/'replay.json'
        paths=[];hashes=[]
        for n in range(8):
            p=self.root/f'{n}.png';Image.new('RGBA',(64,64),(n*20,60,30,255)).save(p);paths.append(p.name);hashes.append(hashlib.sha256(p.read_bytes()).hexdigest())
        self.manifest.write_text(json.dumps({'approved':False,'characters':[{'id':'TEST_ONLY','poseFrames':paths,'poseSHA256':hashes}]}))
        self.scene.write_text(json.dumps({'kind':'interactive-game','motionProfile':'ash-adventure-v1','heroId':'TEST_ONLY','viewport':{'width':240,'height':160}}))
        self.data={'kind':'hero-game-replay','viewport':{'width':240,'height':160},'samples':[{'heroId':'TEST_ONLY','gameTime':n/30,'wallTimeMs':n*1000/30,'position':{'x':0,'y':0,'z':-n*3.7/30},'camera':{'x':0,'y':2,'z':8},'action':'walk','frame':n%8,'held':['KeyW'],'glError':0} for n in range(90)]}
    def tearDown(self):self.tmp.cleanup()
    def run_gate(self):
        self.replay.write_text(json.dumps(self.data));return validate_game_replay(self.replay,self.manifest,self.scene)
    def test_recorded_walk_structure(self):self.assertIn('PASS',self.run_gate()['status'])
    def test_unknown_profile_rejected(self):
        s=json.loads(self.scene.read_text());s['motionProfile']='unknown';self.scene.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError,'unsupported motion profile'):self.run_gate()
    def test_teleport_rejected(self):
        self.data['samples'][20]['position']['x']=10
        with self.assertRaisesRegex(ValueError,'teleport'):self.run_gate()
    def test_wrong_run_clip_rejected(self):
        for r in self.data['samples']:r['action']='run'
        with self.assertRaisesRegex(ValueError,'walking speed'):self.run_gate()
    def test_camera_teleport_rejected(self):
        self.data['samples'][20]['camera']['x']=100
        with self.assertRaisesRegex(ValueError,'camera teleport'):self.run_gate()
    def test_unsolicited_motion_rejected(self):
        for r in self.data['samples']:r['held']=[]
        with self.assertRaisesRegex(ValueError,'unsolicited'):self.run_gate()
    def test_old_gif_restrictions_remain(self):
        p=self.root/'small.gif';Image.new('RGB',(90,160)).save(p,'GIF',loop=0,duration=40)
        with self.assertRaisesRegex(ValueError,'1000'):validate(p,self.manifest,self.scene)
    def test_sprite_hash_rejected(self):
        (self.root/'0.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash changed'):self.run_gate()
if __name__=='__main__':unittest.main(verbosity=2)
