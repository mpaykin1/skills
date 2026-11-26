import { createRequire } from 'node:module';
import fs from 'node:fs';
const require=createRequire(import.meta.url);
const pkg=JSON.parse(fs.readFileSync(new URL('./package.json',import.meta.url),'utf8'));
let missing=[];
for (const [name,ver] of Object.entries(pkg.dependencies)){try {const p=require.resolve(name);console.log(name, 'resolved',p);}catch(e){missing.push(name+': '+ver);}}
if(missing.length){console.error('Runtime dependencies not yet resolved: '+missing.join(', '));process.exitCode=1;}
