import fs from 'node:fs';import path from 'node:path';import {loadTonal,analyzePiece,analyzeLiveBars} from './tonal_bridge.mjs';
const [input,output]=process.argv.slice(2);if(!input||!output||path.resolve(input)===path.resolve(output))throw Error('Usage: node tonal_cli.mjs input.json output.json');
const source=JSON.parse(fs.readFileSync(input,'utf8')),T=await loadTonal();
const harmony=source.piece?analyzePiece(T,source.piece):{schema:'music-harmony-v1',engine:'tonal',timeline:analyzeLiveBars(T,source.bars)};
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify({...source,harmony},null,2));
