"""MUSIC integration with the genuine HarmoniaTextor 2.5 symbolic core.
Run in the pinned upstream Python 3.14 environment. No LLM or paid API is used.
"""
import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENRES = ('sonata', 'concerto', 'symphony')
ROOTS = ('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')


def bank_read(path):
    bank = json.loads(Path(path).read_text())
    motifs = bank.get('motifs')
    if bank.get('schema') != 'music-motif-v1' or not isinstance(motifs,list) or not 1 <= len(motifs) <= 32:
        raise ValueError('Invalid motif bank')
    for m in motifs:
        intervals, gaps = m['intervals'], m['gaps']
        if len(intervals)!=5 or len(gaps)!=5 or not all(type(x) is int and abs(x)<=87 for x in intervals) or not all(type(x) in (int,float) and math.isfinite(x) and 0<x<=4 for x in gaps):
            raise ValueError('Invalid motif')
    return bank


def develop(bank, technique='inversion'):
    from harmoniatextor.domain.models import ThemeNote
    from harmoniatextor.techniques.helpers import (invert_notes, average_axis_midi,
        midi_to_name, name_to_midi)
    out = []
    for m in bank['motifs']:
        pitches = [0]
        for d in m['intervals']:
            pitches.append(pitches[-1]+d)
        # Recover a valid relative pitch register; absolute source pitch is not in bank.
        if max(pitches)-min(pitches)>87:
            raise ValueError('Motif exceeds piano range')
        shift = min(max(60,21-min(pitches)),108-max(pitches))
        lengths = [*m['gaps'], m['gaps'][-1]]
        notes = [ThemeNote(midi_to_name(shift+p), float(d)) for p,d in zip(pitches,lengths)]
        if technique == 'inversion':
            # Use actual upstream implementation, not a reimplementation.
            transformed = invert_notes(notes, average_axis_midi(notes))
        elif technique in ('augmentation','diminution'):
            # Same duration transformation as upstream, applied to onset intervals.
            factor = 2 if technique=='augmentation' else .5
            transformed = [ThemeNote(n.pitch,n.quarter_length*factor) for n in notes]
        else:
            raise ValueError('Unknown technique')
        ps = [name_to_midi(n.pitch) for n in transformed]
        gs = [n.quarter_length for n in transformed[:-1]]
        if any(not 0<g<=4 for g in gs):
            continue
        out.append({'intervals':[b-a for a,b in zip(ps,ps[1:])],'gaps':gs})
    if not out:
        raise ValueError('Transformation cannot fit shared motif schema')
    return {**bank,'motifs':out,'development':{'engine':'HarmoniaTextor','technique':technique},
            'parentSha256':bank.get('sha256')}


def plan(genre):
    from harmoniatextor.genres import build_default_registry
    g = build_default_registry().get(genre)
    return [asdict(spec) for spec in g.movement_specs]


def audit(xml, genre, tonic):
    from music21 import converter, stream
    from harmoniatextor.checker import CheckEngine
    from harmoniatextor.genres import build_default_registry
    from harmoniatextor.domain.key import parse_key
    path = Path(xml)
    raw = path.read_bytes()
    if len(raw)>8_000_000 or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsafe or oversized MusicXML')
    parse_key(tonic)
    score = converter.parse(str(path), forceSource=True)
    if not isinstance(score,stream.Score) or not score.parts:
        raise ValueError('No score parts')
    n = max(len(list(p.getElementsByClass(stream.Measure))) for p in score.parts)
    if not n:
        raise ValueError('No measures')
    context = build_default_registry().get(genre).checker_context(tonic,n,complete=True)
    return CheckEngine().run(score,context)


def suite(args):
    # An optional original NotaGen score supplies the shared theme bank.
    bank = bank_read(args.motif)
    specs = plan(args.genre)
    if not 1<=args.attempts<=8 or not 0<=args.seed<=0xffffffff:
        raise ValueError('Invalid attempts/seed')
    target=Path(args.out).resolve()
    if target.exists():
        raise FileExistsError('Output directory must be new')
    target.parent.mkdir(parents=True,exist_ok=True)
    tonic=args.root if args.mode=='major' else args.root[0].lower()+args.root[1:]
    with tempfile.TemporaryDirectory(prefix='music-suite-',dir=target.parent) as tmp:
        work=Path(tmp); result=work/'result'; result.mkdir(); movements=[]
        for i,spec in enumerate(specs):
            # 3/4 uses actual upstream waltz/minuet meters; 4/4 uses sonatina/nocturne/etude.
            meter=spec['time_signature']
            style=('minuet' if spec['tempo']>=90 else 'waltz') if meter=='3/4' else ('nocturne' if spec['tempo']<90 else 'sonatina' if i==0 else 'etude')
            active=develop(bank) if i==1 else bank
            bpath=work/'bank.json'; bpath.write_text(json.dumps(active))
            prefix=work/'candidate'
            chosen=None
            for attempt in range(args.attempts):
                seed=(args.seed+1009*i+17*attempt)&0xffffffff
                subprocess.run(['node',str(HERE/'compose.mjs'),'--style',style,'--root',args.root,'--mode',args.mode,'--tempo',str(spec['tempo']),'--seed',str(seed),'--motif',str(bpath),'--out',str(prefix)],check=True,timeout=180)
                score=Path(str(prefix)+'.musicxml')
                report=audit(score,args.genre,tonic)
                if report.ok:
                    chosen=seed; break
            if chosen is None:
                raise RuntimeError(f'Movement {i+1}: no candidate passed HarmoniaTextor. Original score is unchanged; no unvalidated suite published.')
            out=result/f'movement-{i+1:02d}'
            for ext in ('.mid','.musicxml','.json'):
                Path(str(prefix)+ext).replace(Path(str(out)+ext))
            subprocess.run(['node',str(HERE/'render_open_music.mjs'),str(out)+'.json',str(out)+'.wav',*(['--orchestra'] if args.genre in ('symphony','concerto') else [])],check=True,timeout=600)
            movements.append({'name':spec['name'],'meter':meter,'tempo':spec['tempo'],'style':style,'seed':chosen,'file':out.name+'.wav'})
        (result/'suite.json').write_text(json.dumps({'schema':'music-suite-v1','genre':args.genre,'root':args.root,'mode':args.mode,'motifSource':bank.get('sha256'),'movements':movements},ensure_ascii=False,indent=2))
        result.rename(target)


def main():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('plan'); a.add_argument('genre',choices=GENRES)
    a=s.add_parser('develop'); a.add_argument('bank'); a.add_argument('out'); a.add_argument('--technique',choices=['inversion','augmentation','diminution'],default='inversion')
    a=s.add_parser('check'); a.add_argument('xml'); a.add_argument('--genre',choices=GENRES,default='sonata'); a.add_argument('--tonic',required=True)
    a=s.add_parser('suite'); a.add_argument('--genre',choices=GENRES,required=True); a.add_argument('--motif',required=True); a.add_argument('--out',required=True); a.add_argument('--root',choices=ROOTS,default='C'); a.add_argument('--mode',choices=['major','minor'],default='minor'); a.add_argument('--seed',type=int,default=1); a.add_argument('--attempts',type=int,default=4)
    a=p.parse_args()
    if a.cmd=='plan': print(json.dumps(plan(a.genre),ensure_ascii=False,indent=2))
    elif a.cmd=='develop': Path(a.out).write_text(json.dumps(develop(bank_read(a.bank),a.technique),indent=2))
    elif a.cmd=='check':
        r=audit(a.xml,a.genre,a.tonic); print(json.dumps(r.to_dict(),ensure_ascii=False)); raise SystemExit(0 if r.ok else 2)
    else: suite(a)

if __name__=='__main__': main()
