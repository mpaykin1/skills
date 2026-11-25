"""Use an independently installed GPL-2.0-or-later MMA executable.
Translate the real Piano Music Generator harmony to MMA and align its bass/drums
with the original MIDI tempo map. No replacement melody, no paid service.
"""
import argparse
from collections import defaultdict, deque
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

GROOVES = {'jazz': ('SwingWalk', 4), 'blues': ('Blues', 4),
           'rock': ('8Beat', 4), 'bossa': ('BossaNova', 4), 'waltz': ('Waltz', 3)}
NAMES = ('C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B')
SUFFIX = {(0,4,7):'', (0,3,7):'m', (0,3,6):'mb5',
          (0,4,7,10):'7', (0,3,7,10):'m7'}


def chart(piece, genre):
    groove, meter = GROOVES[genre]
    if piece['beats'] != meter or piece.get('beatUnit',1) != 1:
        raise ValueError(f'{genre} requires {meter}/4; choose a matching piano style, do not distort meter')
    bars, bpm = piece['totalBars'], piece['tempo']
    if type(bars) is not int or not 1<=bars<=256 or not isinstance(bpm,(int,float)) or not 30<=bpm<=220:
        raise ValueError('Invalid length or tempo')
    seed = piece['seed']
    if type(seed) is not int or not 0<=seed<=0xffffffff:
        raise ValueError('Invalid seed')
    rows = defaultdict(list)
    for event in piece['chords']:
        bar, start, pcs = event['bar'],event.get('start',0),event['pcs']
        if type(bar) is not int or not 0<=bar<bars or not isinstance(start,(float,int)) or not 0<=start<meter:
            raise ValueError('Invalid chord position')
        if not pcs or any(type(p) is not int or not 0<=p<12 for p in pcs):
            raise ValueError('Invalid chord pitch classes')
        # Upstream QUALITY lists root first, followed by chord members.
        intervals = tuple(sorted((p-pcs[0])%12 for p in pcs))
        if intervals not in SUFFIX:
            raise ValueError(f'Unsupported chord {event}: no silent substitution')
        rows[bar].append((start,NAMES[pcs[0]]+SUFFIX[intervals]))
    lines = [f'RndSeed {seed}',f'Groove {groove}',f'Tempo {round(bpm)}']
    last=None
    for bar in range(bars):
        items=sorted(rows[bar]); tokens=[]
        if not items or items[0][0]>1e-6:
            if last is None: raise ValueError('No opening chord')
            tokens.append(last+'@1')
        prev=-1
        for start,symbol in items:
            if start<=prev: raise ValueError('Duplicate chord onset')
            tokens.append(f'{symbol}@{1+start:.6f}'); last=symbol; prev=start
        lines.append(f'{bar+1} '+ ' '.join(tokens))
    return '\n'.join(lines)+'\n'


def add_backing(piano, accompaniment, piece):
    import mido
    if piano.type not in (0,1) or accompaniment.type not in (0,1):
        raise ValueError('Only synchronous MIDI files supported')
    # The source score owns all tempo and meter events. Never copy MMA tempo.
    channels={msg.channel for tr in piano.tracks for msg in tr if not msg.is_meta and hasattr(msg,'channel')}
    if channels-{0}: raise ValueError('Expected original single-channel piano MIDI')
    ratio=piano.ticks_per_beat/accompaniment.ticks_per_beat
    limit=round(piece['totalBars']*piece['beats']*piano.ticks_per_beat)
    prog=defaultdict(int); active=defaultdict(deque); intervals=[]
    tick=0
    for msg in mido.merge_tracks(accompaniment.tracks):
        tick+=msg.time
        if msg.is_meta or not hasattr(msg,'channel'): continue
        ch=msg.channel
        if msg.type=='program_change': prog[ch]=msg.program
        if msg.type=='note_on' and msg.velocity:
            if ch==9 or 32<=prog[ch]<=39:
                active[(ch,msg.note)].append((round(tick*ratio),msg.velocity,prog[ch]))
        elif msg.type in ('note_off','note_on') and active[(ch,msg.note)]:
            start,vel,program=active[(ch,msg.note)].popleft()
            end=min(limit,round(tick*ratio))
            if start<end: intervals.append((start,end,ch,msg.note,vel,program))
    if any(active.values()): raise ValueError('MMA produced unterminated backing notes')
    if not intervals: raise ValueError('No MMA bass/drum events found')
    out=mido.MidiFile(type=1,ticks_per_beat=piano.ticks_per_beat)
    out.tracks.extend(piano.tracks)
    # Separate channels for each bass program, plus GM percussion channel 9.
    programs=sorted({program for _,_,ch,_,_,program in intervals if ch!=9})
    mapping=dict(zip(programs,[1,2,3,4,5,6,7,8,10,11,12,13,14,15]))
    events=[]
    for program,ch in mapping.items():
        events.append((0,0,mido.Message('program_change',channel=ch,program=program)))
    for start,end,ch,note,vel,program in intervals:
        target=9 if ch==9 else mapping[program]
        events.append((start,2,mido.Message('note_on',channel=target,note=note,velocity=vel)))
        events.append((end,1,mido.Message('note_off',channel=target,note=note,velocity=0)))
    track=mido.MidiTrack(); track.append(mido.MetaMessage('track_name',name='MMA bass and percussion'))
    prev=0
    for t,_,msg in sorted(events,key=lambda x:(x[0],x[1])):
        track.append(msg.copy(time=t-prev)); prev=t
    track.append(mido.MetaMessage('end_of_track')); out.tracks.append(track)
    # Build seconds on the same MIDI conductor map, not MMA's independent clock.
    tempo=500000; now=0.; on=defaultdict(deque); backing=[]
    for msg in mido.merge_tracks(out.tracks):
        now+=mido.tick2second(msg.time,out.ticks_per_beat,tempo)
        if msg.type=='set_tempo': tempo=msg.tempo
        if msg.is_meta or not hasattr(msg,'channel') or msg.channel==0: continue
        if msg.type=='note_on' and msg.velocity: on[(msg.channel,msg.note)].append((now,msg.velocity))
        elif msg.type in ('note_off','note_on') and on[(msg.channel,msg.note)]:
            start,v=on[(msg.channel,msg.note)].popleft()
            if now>start: backing.append(dict(kind='drum' if msg.channel==9 else 'bass',pitch=msg.note,start=start,end=now,velocity=v/127))
    if any(on.values()): raise ValueError('Unpaired merged notes')
    return out, sorted(backing,key=lambda n:n['start'])


def main():
    import mido
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path,help='Original compose.mjs JSON with adjacent .mid')
    p.add_argument('--genre',choices=GROOVES,required=True)
    p.add_argument('--out',type=Path,required=True,help='New output prefix')
    p.add_argument('--mma',default='mma',help='Installed MMA executable or upstream mma.py')
    p.add_argument('--chart-only',action='store_true')
    a=p.parse_args(); source=json.loads(a.input.read_text()); piece=source['piece']; text=chart(piece,a.genre)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    chartpath=Path(str(a.out)+'.mma'); midpath=Path(str(a.out)+'.mid'); jsonpath=Path(str(a.out)+'.json')
    if any(x.exists() for x in (chartpath,midpath,jsonpath)): raise FileExistsError('Output prefix already exists')
    if a.chart_only: chartpath.write_text(text); return
    exe=shutil.which(a.mma)
    if exe is None and Path(a.mma).is_file(): exe=str(Path(a.mma).resolve())
    if exe is None: raise RuntimeError('MMA not installed; obtain pinned upstream separately')
    exe=str(Path(exe).resolve()); cmd=[sys.executable,exe] if exe.endswith('.py') else [exe]
    piano=mido.MidiFile(a.input.with_suffix('.mid'))
    with tempfile.TemporaryDirectory(prefix='music-mma-') as d:
        score=Path(d)/'chart.mma'; midi=Path(d)/'backing.mid'; score.write_text(text)
        subprocess.run([*cmd,'-f',str(midi),str(score)],check=True,timeout=180)
        if not midi.is_file(): raise RuntimeError('MMA produced no MIDI')
        merged,backing=add_backing(piano,mido.MidiFile(midi),piece)
        # Original notes remain unchanged; a separate layer contains only real MMA output.
        result={**source,'backing':{'engine':'MMA','groove':GROOVES[a.genre][0],'genre':a.genre,'notes':backing}}
        merged.save(str(midpath)); jsonpath.write_text(json.dumps(result,ensure_ascii=False,indent=2)); chartpath.write_text(text)

if __name__=='__main__': main()
