// Independent bridge: use NotaGen contour/rhythm to select complete upstream pieces.
// Never rewrite pitches under existing chord, notation or ornament metadata.
export function validateMotifs(bank){
 if(bank?.schema!=='music-motif-v1'||!Array.isArray(bank.motifs)||!bank.motifs.length||bank.motifs.length>32) throw new Error('Invalid motif bank');
 for(const m of bank.motifs) if(m.intervals?.length!==5||m.gaps?.length!==5||!m.intervals.every(x=>Number.isInteger(x)&&Math.abs(x)<=87)||!m.gaps.every(x=>Number.isFinite(x)&&x>0&&x<=4)) throw new Error('Invalid motif');
 return bank;
}
export function motifDistance(piece,bank){
 validateMotifs(bank); const top=new Map();
 for(const n of piece.notes) if(n.hand==='right'&&!n.ornament) top.set(n.time,Math.max(n.pitch,top.get(n.time)??0));
 const notes=[...top].sort((a,b)=>a[0]-b[0]).slice(0,96); let best=Infinity;
 for(let k=0;k+5<notes.length;k++) for(const motif of bank.motifs){
  const gaps=[], intervals=[];
  for(let j=0;j<5;j++){gaps.push(notes[k+j+1][0]-notes[k+j][0]);intervals.push(notes[k+j+1][1]-notes[k+j][1]);}
  const sum=gaps.reduce((a,b)=>a+b,0), target=motif.gaps.reduce((a,b)=>a+b,0); if(sum<=0)continue;
  let cost=0; for(let j=0;j<5;j++){cost+=Math.abs(intervals[j]-motif.intervals[j])/12+0.35*(Math.sign(intervals[j])!==Math.sign(motif.intervals[j]))+Math.abs(gaps[j]/sum-motif.gaps[j]/target);}
  best=Math.min(best,cost/5);
 }
 return best;
}
export function chooseVariation(compose,options,bank,count=8){
 validateMotifs(bank); if(!Number.isInteger(count)||count<1||count>16)throw new Error('Candidate count 1..16');
 let best=null; const seed=options.seed??1;
 for(let i=0;i<count;i++){
  const piece=compose({...options,seed:(seed+i)>>>0}); const distance=motifDistance(piece,bank);
  if(!best||distance<best.distance)best={piece,distance};
 }
 if(!Number.isFinite(best.distance))throw new Error('No comparable melody');
 return {...best, candidates:count, motifSource:bank.sha256??null};
}
