"""Generator regression; production Vite build is a separate integration check."""
import subprocess,sys,tempfile,unittest
from pathlib import Path

class BuildNoiseFallback(unittest.TestCase):
    def test_base_scene_resolves_both_noise_imports(self):
        script=Path(__file__).resolve().with_name('styleforge.py')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);workspace=root/'workspace';workspace.mkdir();game=root/'game'
            custom=game/'src/custom/owner.txt';custom.parent.mkdir(parents=True);custom.write_bytes(b'owner content')
            run=subprocess.run([sys.executable,'-B','-S',str(script),'build','--workspace',str(workspace),'--out',str(game)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            for name in ('noise.js','noise3D.js'):
                self.assertEqual((game/'src'/name).read_text('utf8').strip(),'export default "";')
            self.assertEqual(custom.read_bytes(),b'owner content')
            self.assertTrue((game/'package.json').is_file())
            self.assertTrue((game/'src/main.js').is_file())
if __name__=='__main__':unittest.main()
