"""Music21 score analysis and reference-guided candidate selection (offline).
Uses actual music21 APIs, not synthetic substitutes. Never rewrites source scores.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS = ('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def motif_bank(attacks, digest):
    """Six attacks, pitch intervals and onset gaps in quarter notes."""
    motifs = []
    seen = set()
    for i in range(0, len(attacks)-5, 3):
        seq = attacks[i:i+6]
        ps = [x[1] for x in seq]
        gaps = [round(b[0]-a[0], 6) for a,b in zip(seq,seq[1:])]
        ds = [b-a for a,b in zip(ps,ps[1:])]
        if len(set(ps)) < 3 or any(not 0 < g <= 4 for g in gaps) or any(abs(d)>87 for d in ds):
            continue
        k = (tuple(ds),tuple(gaps))
        if k in seen:
            continue
        seen.add(k)
        motifs.append({'intervals':ds,'gaps':gaps})
        if len(motifs)==32:
            break
    if not motifs:
        raise ValueError('No usable six-note theme in selected part')
    return {'schema':'music-motif-v1','source':'music21-score','sha256':digest,'motifs':motifs}


def analyze(filename, part_index=0):
    import music21 as m21
    source = Path(filename).resolve(strict=True)
    if source.suffix.lower() not in ('.xml','.musicxml','.mid','.midi'):
        raise ValueError('Only local uncompressed MusicXML or MIDI accepted')
    if source.stat().st_size > 8_000_000:
        raise ValueError('Score too large')
    raw = source.read_bytes()
    if not raw or b'<!ENTITY' in raw.upper():
        raise ValueError('Empty or unsafe score')
    digest = hashlib.sha256(raw).hexdigest()
    score = m21.converter.parse(str(source), forceSource=True)
    if not isinstance(score,m21.stream.Score) or not score.parts:
        raise ValueError('Single score with parts required')
    if not 0 <= part_index < len(score.parts):
        raise ValueError('Invalid melody part index')
    part = score.parts[part_index]
    top = {}
    for n in part.flatten().notes:
        if isinstance(n,m21.note.Unpitched) or not getattr(n,'pitches',()):
            continue
        t=float(n.offset); duration=float(n.quarterLength)
        if duration<=0 or not math.isfinite(t) or t<0:
            continue
        if n.tie is not None and n.tie.type in ('stop','continue'):
            continue
        p=max(int(round(x.midi)) for x in n.pitches)
        if 21<=p<=108:
            top[t]=max(p,top.get(t,0))
    attacks=sorted(top.items())
    if not attacks or len(attacks)>20000:
        raise ValueError('Empty/oversized pitched melody')
    length=float(part.highestTime)
    if not math.isfinite(length) or length<=0 or length>10000:
        raise ValueError('Invalid or oversized score duration')
    inferred=score.analyze('key')
    leaps=[abs(b[1]-a[1]) for a,b in zip(attacks,attacks[1:])]
    hist=[0]*12
    for _,p in attacks: hist[p%12]+=1
    # Vertical sonorities are observations, NOT authoritative chord symbols.
    # Ignore dyads and clusters when labeling; preserve ambiguity as null.
    vertical=[]
    for c in score.chordify().flatten().getElementsByClass(m21.chord.Chord):
        if len(vertical)>=4096: raise ValueError('Too many vertical sonorities')
        pcs=sorted(set(int(round(p.midi))%12 for p in c.pitches))
        figure=None
        if 3<=len(pcs)<=4 and (c.isTriad() or c.isSeventh()):
            try: figure=m21.roman.romanNumeralFromChord(c,inferred).figure
            except (ValueError,m21.exceptions21.Music21Exception): pass
        vertical.append({'quarterStart':float(c.offset),'quarterLength':float(c.quarterLength),'pcs':pcs,'romanEstimate':figure})
    pitches=[p for _,p in attacks]
    profile={'schema':'music21-profile-v1','engine':'music21','version':m21.__version__, 'sha256':digest,
             'part':part_index,'partCount':len(score.parts),'quarterLength':length,
             'estimatedKey':{'root':ROOTS[inferred.tonic.pitchClass],'mode':inferred.mode},
             'metrics':{'attacks':len(attacks),'density':len(attacks)/length,'range':max(pitches)-min(pitches),
                        'meanLeap':sum(leaps)/max(1,len(leaps)), 'pitchClassCounts':hist},
             'sonorities':vertical}
    return profile,attacks


def profile_distance(reference,candidate):
    a,b=reference['metrics'],candidate['metrics']
    # Soft texture distance. Different genres legitimately use different densities.
    density=abs(math.log((a['density']+.1)/(b['density']+.1)))
    return .12*density+.08*abs(a['range']-b['range'])/24+.10*abs(a['meanLeap']-b['meanLeap'])/12


def select(args):
    reference,attacks=analyze(args.source,args.part)
    bank=motif_bank(attacks,reference['sha256'])
    if not 1<=args.candidates<=6 or not 0<=args.seed<=0xffffffff:
        raise ValueError('Candidates 1–6, uint32 seed required')
    root=args.root or reference['estimatedKey']['root']; mode=args.mode or reference['estimatedKey']['mode']
    if mode not in ('major','minor'): raise ValueError('Select major or minor explicitly')
    target=Path(args.out).resolve()
    if target.exists(): raise FileExistsError('Choose a new output directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='music21-select-',dir=target.parent) as tmp:
        work=Path(tmp); bpath=work/'motif.json'; write_json(bpath,bank)
        ranked=[]
        for i in range(args.candidates):
            prefix=work/f'candidate-{i}'
            cmd=['node',str(HERE/'compose.mjs'),'--style',args.style,'--root',root,'--mode',mode,
                 '--seed',str((args.seed+17*i)&0xffffffff),'--motif',str(bpath),'--out',str(prefix)]
            if args.tonal: cmd+=['--harmony','tonal']
            subprocess.run(cmd,check=True,timeout=180)
            data=json.loads(Path(str(prefix)+'.json').read_text())
            p,_=analyze(str(prefix)+'.musicxml',0)
            d=data.get('motifDistance')
            if not isinstance(d,(int,float)) or not math.isfinite(d): raise ValueError('Missing motif distance')
            cost=d+profile_distance(reference,p)
            ranked.append((cost,i,prefix,p))
        cost,_,prefix,profile=min(ranked,key=lambda x:(x[0],x[1]))
        result=work/'result';result.mkdir()
        for ext in ('.json','.mid','.musicxml'):
            shutil.copy2(str(prefix)+ext,result/('piece'+ext))
        write_json(result/'motif.json',bank)
        write_json(result/'profile.json',{'reference':reference,'selected':profile,'selectionCost':cost})
        result.rename(target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('analyze');a.add_argument('source');a.add_argument('out');a.add_argument('--part',type=int,default=0);a.add_argument('--motif-out')
    a=sub.add_parser('select');a.add_argument('source');a.add_argument('--out',required=True);a.add_argument('--part',type=int,default=0);a.add_argument('--style',default='nocturne');a.add_argument('--root',choices=ROOTS);a.add_argument('--mode',choices=['major','minor']);a.add_argument('--seed',type=int,default=1);a.add_argument('--candidates',type=int,default=3);a.add_argument('--tonal',action='store_true')
    args=parser.parse_args()
    if args.cmd=='select': select(args)
    else:
        profile,attacks=analyze(args.source,args.part)
        bank=motif_bank(attacks,profile['sha256']) if args.motif_out else None
        targets=[Path(args.out).resolve()]+([Path(args.motif_out).resolve()] if args.motif_out else [])
        if len(set(targets))!=len(targets) or any(p.exists() for p in targets): raise FileExistsError('Use new output paths')
        write_json(args.out,profile)
        if bank is not None:write_json(args.motif_out,bank)

if __name__=='__main__':main()
