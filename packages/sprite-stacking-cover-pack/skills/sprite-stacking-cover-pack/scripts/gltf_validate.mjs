// Official Khronos validator only. No network resources or mock validation.
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const path = process.argv[2];
if (!path || process.argv.length !== 3) throw Error('Usage: node gltf_validate.mjs asset.glb');
const validator = require('gltf-validator');
const bytes = await readFile(path);
if (bytes.length < 20 || bytes.toString('ascii',0,4)!=='glTF' || bytes.readUInt32LE(4)!==2 || bytes.readUInt32LE(8)!==bytes.length) throw Error('Expected self-contained GLB v2');
const jsonLength=bytes.readUInt32LE(12);
if (bytes.toString('ascii',16,20)!=='JSON' || jsonLength>bytes.length-20) throw Error('Invalid GLB JSON chunk');
const gltf=JSON.parse(bytes.toString('utf8',20,20+jsonLength));
const supported=new Set(validator.supportedExtensions());
const unsupported=[...new Set([...(gltf.extensionsUsed??[]),...(gltf.extensionsRequired??[])])].filter(x=>!supported.has(x));
if (unsupported.length) throw Error('Validator does not cover extensions: '+unsupported.join(', '));
const report = await validator.validateBytes(new Uint8Array(bytes), {
  uri:'asset.glb', format:'glb', maxIssues:0,
  externalResourceFunction: async () => { throw Error('External resources forbidden; embed them in GLB'); }
});
const result={schema:'cover-pack-khronos-validation/1',sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,report};
process.stdout.write(JSON.stringify(result));
