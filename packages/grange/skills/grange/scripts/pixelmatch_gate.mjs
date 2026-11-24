import fs from 'node:fs';
import pixelmatch from 'pixelmatch';
import {PNG} from 'pngjs';
const [a,b,m]=process.argv.slice(2).map(p=>PNG.sync.read(fs.readFileSync(p)));
if ([b,m].some(x=>x.width!==a.width||x.height!==a.height)) throw Error('shape mismatch');
let n=0;
for(let i=0;i<a.data.length;i+=4){if(m.data[i]>=128){n++;continue;} for(let k=0;k<4;k++)a.data[i+k]=b.data[i+k]=k===3?255:0;}
if(!n)throw Error('empty protected mask');
const changed=pixelmatch(a.data,b.data,null,a.width,a.height,{threshold:.1,includeAA:true});
console.log(JSON.stringify({changed,protected_pixels:n,ratio:changed/n}));
