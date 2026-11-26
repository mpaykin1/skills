import json, subprocess, sys, tempfile, unittest
from pathlib import Path
SCRIPT=Path(sys.argv.pop(1)).resolve()
class StoryCapacity(unittest.TestCase):
    def test_capacity_and_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);work=root/'workbench';store=work/'stories-src';store.mkdir(parents=True)
            source=root/'original.ink';source.write_text('Synthetic story.\n-> END\n',encoding='utf8')
            registry=store/'story-list.json'
            entries=[{'id':'story'+str(i)} for i in range(100)]
            registry.write_text(json.dumps({'schema':'meta-game-fusion.ink-source-list.v1','stories':entries}),encoding='utf8')
            original=source.read_bytes();before=registry.read_bytes()
            def run(ident,replace=False):
                cmd=[sys.executable,'-B','-S',str(SCRIPT),'add','--workbench',str(work),'--source',str(source),'--id',ident,'--title','Synthetic','--game','fixture']
                if replace:cmd.append('--replace')
                return subprocess.run(cmd,capture_output=True,text=True)
            bad=run('newstory',True)
            self.assertEqual(bad.returncode,2,bad.stdout+bad.stderr)
            self.assertIn('100 stories',bad.stderr)
            self.assertEqual(registry.read_bytes(),before)
            self.assertFalse((store/'newstory.ink').exists())
            self.assertFalse(list(store.glob('*.tmp')))
            (store/'story0.ink').write_text('Old',encoding='utf8')
            duplicate=run('story0')
            self.assertEqual(duplicate.returncode,2)
            replacement=run('story0',True)
            self.assertEqual(replacement.returncode,0,replacement.stderr)
            updated=json.loads(registry.read_text('utf8'))['stories']
            self.assertEqual(len(updated),100)
            self.assertEqual(sum(x['id']=='story0' for x in updated),1)
            self.assertEqual((store/'story0.ink').read_bytes(),original)
            updated=[x for x in updated if x['id']!='story99']
            registry.write_text(json.dumps({'schema':'meta-game-fusion.ink-source-list.v1','stories':updated}),encoding='utf8')
            added=run('newstory')
            self.assertEqual(added.returncode,0,added.stderr)
            self.assertEqual(len(json.loads(registry.read_text('utf8'))['stories']),100)
            self.assertEqual(source.read_bytes(),original)
if __name__=='__main__':unittest.main()
