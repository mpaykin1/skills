"""Build a browser-ready subset of Alexander Holm's Salamander Grand Piano V3.
Original recordings CC BY 3.0. No normalization between velocity layers.
"""
import argparse, concurrent.futures, json, pathlib, shutil, subprocess, tempfile, urllib.request, urllib.parse

REPO = 'https://github.com/sfzinstruments/SalamanderGrandPiano'
COMMIT = '3382bf9496bba2486f5ab0de55a264d1dfc38404'
RAW = f'https://raw.githubusercontent.com/sfzinstruments/SalamanderGrandPiano/{COMMIT}/'
CREDIT = 'Salamander Grand Piano V3 — Alexander Holm; SFZ remapping by kinwie. CC BY 3.0 Unported. Adaptation: selected velocity layers, mono conversion, shortened tails and MP3 encoding.'
NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
# Original SFZ velocity upper bounds, from Data/notes.txt.
UPPER = [26,34,36,43,46,50,56,64,72,80,88,96,104,112,120,127]
PRESETS = {'mobile': ([5,13],6,22050), 'standard': ([3,8,12,16],10,32000), 'full': (list(range(1,17)),18,44100)}

def name(midi):
    return NAMES[midi % 12] + str(midi // 12 - 1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,help='Local checkout of original SFZ repo; omit to download selected samples from pinned commit');p.add_argument('--out',type=pathlib.Path,default=pathlib.Path(__file__).parent/'salamander');p.add_argument('--preset',choices=PRESETS,default='mobile');p.add_argument('--jobs',type=int,default=3);a=p.parse_args()
    if not shutil.which('ffmpeg'): p.error('ffmpeg is required')
    if not 1 <= a.jobs <= 4: p.error('jobs must be 1–4')
    layers,seconds,rate=PRESETS[a.preset];out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=out/'manifest.json';manifest.unlink(missing_ok=True)
    def convert(item):
        layer,midi=item;fn=f'{name(midi)}v{layer}.flac';target=out/f'{midi}-v{layer}.mp3'
        with tempfile.TemporaryDirectory() as td:
            if a.source: source=a.source/'Samples'/fn
            else:
                source=pathlib.Path(td)/fn
                url=RAW+'Samples/'+urllib.parse.quote(fn,safe='')
                with urllib.request.urlopen(url,timeout=90) as response, source.open('wb') as f: shutil.copyfileobj(response,f)
            if not source.is_file(): raise FileNotFoundError(source)
            temp=pathlib.Path(td)/'out.mp3'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source),'-t',str(seconds),'-ac','1','-ar',str(rate),'-codec:a','libmp3lame','-b:a','96k',str(temp)],check=True)
            shutil.copyfile(temp,target)
        return {'midi':midi,'layer':layer,'file':target.name}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        samples=list(ex.map(convert,[(l,m) for l in layers for m in range(21,109,3)]))
    (out/'ATTRIBUTION.txt').write_text(CREDIT+'\n'+REPO+'\nhttps://creativecommons.org/licenses/by/3.0/\n',encoding='utf8')
    data={'schema':'salamander-bank-v1','source':REPO,'commit':COMMIT,'license':'CC-BY-3.0','credit':CREDIT,'preset':a.preset,'layers':layers,'upperVelocity':UPPER,'samples':samples,'maxSampleSeconds':seconds,'sampleRate':rate}
    manifest.write_text(json.dumps(data,indent=2),encoding='utf8');print(manifest)
if __name__=='__main__': main()
