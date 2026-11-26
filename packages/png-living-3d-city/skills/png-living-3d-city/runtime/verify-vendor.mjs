import fs from 'node:fs';
import path from 'node:path';
const base=path.resolve(import.meta.dirname,'vendor');
const entries=[['three-bvh-csg','src/index.js','LICENSE'],['three.quarks','dist/index.js','LICENSE'],['quarks.core','dist/index.js','LICENSE'],['postprocessing','src/index.js','LICENSE.md']];
let failures=0;
for(const [name,entry,license] of entries){const root=path.join(base,name);for(const rel of [entry,license,'package.json']){if(!fs.existsSync(path.join(root,rel))){console.error('Missing '+name+'/'+rel);failures++;}} if(!failures)console.log('Source vendored: '+name);}
if(failures) process.exitCode=1;
