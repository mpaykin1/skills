"""Read a NotaGen-X exported MusicXML piano score; no third-party dependencies."""
import argparse, hashlib, json, math, xml.etree.ElementTree as ET
from pathlib import Path
from fractions import Fraction

def extract(path):
    data=Path(path).read_bytes()
    if len(data)>8_000_000 or b'<!ENTITY' in data.upper(): raise ValueError('Unsafe or oversized XML')
    tree=ET.fromstring(data)
    for e in tree.iter(): e.tag=e.tag.rsplit('}',1)[-1]
    if tree.tag!='score-partwise': raise ValueError('Expected score-partwise MusicXML')
    parts=tree.findall('part')
    if len(parts)!=1: raise ValueError('Use a single piano part')
    div=1; base=Fraction(0); melody={}
    for measure in parts[0].findall('measure'):
        t=base; end=base; last=base
        for e in measure:
            if e.tag=='attributes':
                div=int(e.findtext('divisions',str(div)))
                if div<1: raise ValueError('Invalid divisions')
            if e.tag in ('backup','forward'):
                delta=Fraction(int(e.findtext('duration','0')),div); t+=delta if e.tag=='forward' else -delta
                end=max(end,t); continue
            if e.tag!='note' or e.find('grace') is not None: continue
            dur=Fraction(int(e.findtext('duration','0')),div)
            chord=e.find('chord') is not None
            if not chord: last=t; t+=dur
            end=max(end,t,last+dur)
            pitch=e.find('pitch')
            if pitch is None or e.findtext('staff','1')!='1' or dur<=0: continue
            if any(x.attrib.get('type')=='stop' for x in e.findall('tie')): continue
            alt=float(pitch.findtext('alter','0'))
            if not alt.is_integer(): continue
            midi=12*(int(pitch.findtext('octave'))+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[pitch.findtext('step')]+int(alt)
            if not 21<=midi<=108: raise ValueError('Note outside piano range')
            melody[last]=max(midi,melody.get(last,0))
        base=end
    seq=sorted(melody.items()); motifs=[]
    for i in range(0,min(len(seq)-5,96),6):
        chunk=seq[i:i+6]; pitches=[p for t,p in chunk]; gaps=[float(chunk[j+1][0]-chunk[j][0]) for j in range(5)]
        if len(set(pitches))>=3 and min(gaps)>0 and max(gaps)<=4:
            motifs.append({'intervals':[pitches[j+1]-pitches[j] for j in range(5)],'gaps':gaps})
    if not motifs: raise ValueError('No usable six-note melodic motif')
    return {'schema':'music-motif-v1','source':'notagen-x-musicxml','sha256':hashlib.sha256(data).hexdigest(),'motifs':motifs}
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('xml'); p.add_argument('out'); a=p.parse_args(); Path(a.out).write_text(json.dumps(extract(a.xml),indent=2))
