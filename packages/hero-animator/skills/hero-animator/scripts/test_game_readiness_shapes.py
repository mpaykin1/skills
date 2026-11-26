import json, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT=Path(sys.argv.pop(1)).resolve()
class MalformedMetadata(unittest.TestCase):
    def run_case(self,project,atlas):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/'project.json';a=root/'atlas.json';out=root/'report.json'
            p.write_text(json.dumps(project),encoding='utf8')
            a.write_text(json.dumps(atlas),encoding='utf8')
            original=p.read_bytes()+a.read_bytes()
            run=subprocess.run([sys.executable,'-B','-S',str(SCRIPT),str(p),'--output',str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertNotIn('Traceback',run.stderr)
            report=json.loads(out.read_text('utf8'))
            self.assertEqual(report,json.loads(run.stdout))
            self.assertEqual(report['status'],'BLOCKED')
            self.assertTrue(report['blockers'])
            self.assertEqual(original,p.read_bytes()+a.read_bytes())
            return report
    def test_shapes_fail_closed(self):
        standard={'atlas':'atlas.json','directions':4}
        cases=[([],{}),(standard,[]),(standard,{'identity':None}),
               (standard,{'identity':{'actions':[]}}),(standard,{'anims':[]}),
               (standard,{'anims':{'idle_front':None}}),
               (standard,{'identity':{'actions':{'idle_front':None}}}),
               ({**standard,'checks':None},{}),({**standard,'checks':{'offline':None}},{}),
               ({**standard,'artReview':None},{})]
        for project,atlas in cases:
            with self.subTest(project=project,atlas=atlas):self.run_case(project,atlas)
    def test_regular_incomplete_preserved(self):
        result=self.run_case({'atlas':'atlas.json','directions':4},{'anims':{}})
        self.assertEqual(result['requiredClips'],44)
        self.assertEqual(len(result['missingClips']),44)
        self.assertEqual(len(result['checks']),15)
        self.assertIn('artistic review/approval not supplied',result['blockers'])
if __name__=='__main__':unittest.main()
