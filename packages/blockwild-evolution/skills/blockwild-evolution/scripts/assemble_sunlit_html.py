from pathlib import Path
import json,argparse
a=argparse.ArgumentParser(description='Assemble Sunlit v12 onto an authorized existing BLOCKWILD HTML')
a.add_argument('--source',required=True,type=Path);a.add_argument('--out',required=True,type=Path)
a.add_argument('--runtime',type=Path,default=Path(__file__).resolve().parent.parent/'templates'/'sunlit_courtyard.js')
a.add_argument('--assets',required=True,type=Path)
args=a.parse_args()
src=args.source;out=args.out
s=src.read_text()
art=args.runtime.read_text().replace('__ROYAL_SPRITES__',args.assets.read_text())
assert 'function render(t){' in s
s=s.replace('function render(t){','function render(t){  if(royalActive){renderRoyal(t);return;} ',1)
# CSS styling establishes a faithful portrait isometric UI while retaining original togglable world.
css='''
#royal-canvas{position:absolute;inset:0;display:none;pointer-events:none;z-index:1;touch-action:none;filter:brightness(.95) contrast(1.06)}
#royal-toggle{position:absolute;z-index:6;top:max(14px,env(safe-area-inset-top));left:max(14px,env(safe-area-inset-left));padding:0;display:grid;place-items:center;width:41px;height:41px;border-radius:50%;font-size:20px!important;background:rgba(37,65,68,.47);color:#fff0cc;border:1px solid #efe0b87d;backdrop-filter:blur(8px);box-shadow:0 3px 18px #23251d49;font:600 10px system-ui;letter-spacing:.06em}
#royal-mini{display:none;position:absolute;z-index:3;top:max(14px,env(safe-area-inset-top));right:max(14px,env(safe-area-inset-right));border:1px solid rgba(251,223,161,.64);background:rgba(21,47,49,.48);border-radius:11px;padding:5px;box-shadow:0 4px 21px #15261f33;pointer-events:none}
#royal-mini canvas{display:block;width:106px;height:106px;border-radius:7px}
body.royal-ui #top, body.royal-ui #world-picker,body.royal-ui #bottom,body.royal-ui #map-wrap,body.royal-ui #music,body.royal-ui #vignette,body.royal-ui #grain{display:none!important}
body.royal-ui #stick{display:block!important;opacity:.75;background:rgba(41,70,63,.23);border:1px solid rgba(245,231,177,.8);box-shadow:0 0 0 5px rgba(237,215,165,.08),inset 0 0 30px rgba(254,227,177,.12);width:112px;height:112px;bottom:max(26px,env(safe-area-inset-bottom));left:max(18px,env(safe-area-inset-left))}
body.royal-ui #knob{background:rgba(231,202,124,.55);border:1px solid rgba(250,243,207,.69);box-shadow:0 1px 20px rgba(237,209,158,.2)}
body.royal-ui #touch-actions{display:flex!important;opacity:.80;gap:9px;bottom:max(30px,env(safe-area-inset-bottom))}
body.royal-ui #touch-actions button{background:rgba(32,68,69,.28)!important;border:1px solid rgba(251,222,176,.75)!important;border-radius:50%;height:58px;width:58px;min-width:58px;padding:4px!important;font-size:10px!important;backdrop-filter:blur(6px)}
body.royal-ui #interact{border-color:rgba(255,238,182,.8);background:rgba(39,73,59,.60);left:auto;transform:none;right:18px;bottom:122px;width:47px;height:47px;border-radius:50%;padding:0;font-size:0;display:none}
body.royal-ui #interact:before{content:"☏";font-size:21px;color:#f3ddbd;display:grid;place-items:center;height:100%}
body.royal-ui #royal-canvas{display:block}
@media(max-width:510px){body.royal-ui #stick{width:112px;height:112px}body.royal-ui #touch-actions button{height:54px;width:54px;min-width:54px}#royal-mini canvas{width:94px;height:94px}}
@media(max-height:500px){body.royal-ui #stick{width:82px;height:82px}body.royal-ui #knob{width:38px;height:38px;left:calc(50% - 19px);top:calc(50% - 19px)}body.royal-ui #touch-actions button{height:44px;width:44px;min-width:44px;font-size:8px!important}#royal-mini canvas{width:70px;height:70px}}
'''
assert '</style>' in s
s=s.replace('</style>',css+'</style>',1)
s=s.replace('<canvas id="scene" aria-label="Трёхмерный мир BLOCKWILD"></canvas>',
 '''<canvas id="scene" aria-label="Оригинальный трёхмерный мир BLOCKWILD"></canvas><canvas id="royal-canvas" aria-label="Солнечная изометрическая площадь, объёмный Sprite Stacking"></canvas><button id="royal-toggle" title="Переключить художественную диораму и оригинальный мир">⌂</button><div id="royal-mini"><canvas id="royal-mini-canvas" width="140" height="140"></canvas></div>''',1)
s=s.replace('АРХИВ 0.22.1 · V11 · ФАКТУРЫ + АТМОСФЕРА + СВЕТ','АРХИВ 0.22.1 · V12 · SUNLIT COURTYARD / STACKED DIORAMA',1)
assert s.count('function initialize(){')==1
s=s.replace('function initialize(){',art+'\nfunction initialize(){',1)
assert 'initialize();\n// Load from this file' in s
s=s.replace('initialize();\n// Load from this file', 'initialize();\nroyalSetup();\n// Load from this file',1)
# Ensure initial v11 base palette and player original world remain unchanged.
out.write_text(s)
print('FILE',out,out.stat().st_size,'art length',len(art))
