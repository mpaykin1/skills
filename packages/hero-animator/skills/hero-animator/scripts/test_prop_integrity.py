"""Regression: actual new props pass; original cropped atlas and padded crop fail."""
import base64,copy,io,json,re,sys,unittest
from pathlib import Path
from PIL import Image
from prop_integrity_gate import validate_image
from repair_environment_props import validate_pack

PACK=Path(sys.argv.pop(1));GAME=Path(sys.argv.pop(1))
class PropGateTests(unittest.TestCase):
    def setUp(self):self.pack=json.loads(PACK.read_text(encoding='utf8'))
    def test_actual_complete_trees(self):
        self.assertTrue(validate_pack(self.pack))
        for a in self.pack['assets'].values():
            with Image.open(io.BytesIO(base64.b64decode(a['url'].split(',',1)[1]))) as im:
                self.assertGreaterEqual(min(validate_image(im,margin_fraction=.05)['margins']),min(im.size)*.05)
    def test_actual_legacy_panorama_atlas_rejected(self):
        src=GAME.read_text(encoding='utf8');assets=json.loads(re.search(r'window.ASSETS=(.*?);</script>',src,re.S)[1])
        for n in ['old_oak','dead_forest','distant_ruins']:
            with Image.open(io.BytesIO(base64.b64decode(assets[n]['url'].split(',',1)[1]))) as im:
                with self.assertRaises(ValueError):validate_image(im)
    def test_padding_is_not_a_fix_for_an_internal_flat_crop(self):
        im=Image.new('RGBA',(320,320),(0,0,0,0));cut=Image.new('RGBA',(150,190),(60,40,25,255));im.paste(cut,(80,60))
        with self.assertRaisesRegex(ValueError,'straight'):validate_image(im)
    def test_fragment_role_and_missing_alpha_rejected(self):
        with self.assertRaises(ValueError):validate_image(Image.new('RGB',(256,256)),role='complete-prop')
        with self.assertRaises(ValueError):validate_image(Image.new('RGBA',(256,256),(1,1,1,255)),role='panorama-fragment')
    def test_missing_review_or_tampered_hash_rejected(self):
        a=next(iter(self.pack['assets'].values()));a['review']['fullSilhouetteObserved']=False
        with self.assertRaises(ValueError):validate_pack(self.pack)
        self.setUp();a=next(iter(self.pack['assets'].values()));a['sha256']='0'*64
        with self.assertRaises(ValueError):validate_pack(self.pack)
if __name__=='__main__':unittest.main()
