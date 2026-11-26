/** Stage official Basis Universal transcoder bytes from pinned Three.js npm.
 * No CDN, silent download or unverified artifact. Runs only for KTX2 models.
 * Must run from a generated game's project root after npm dependencies install.
 */
import { existsSync, mkdirSync, readFileSync, copyFileSync, realpathSync, lstatSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const root = resolve(import.meta.dirname, '..');
const data = JSON.parse(readFileSync(join(root, 'public', 'world.json'), 'utf8'));
const ktx2Needed = (data.assets || []).some(a => a.texture_compression === 'ktx2');
if (!ktx2Needed) {
  console.log('Basis transcoder skipped: this game has no KTX2 textures');
  process.exit(0);
}
const threeEntry = require.resolve('three');
const threeRoot = resolve(threeEntry, '..', '..');
const threePkg = join(threeRoot, 'package.json');
const actualVersion = JSON.parse(readFileSync(threePkg, 'utf8')).version;
if (actualVersion !== '0.186.1') throw new Error('Unexpected Three.js version: ' + actualVersion);
const source = join(threeRoot, 'examples', 'jsm', 'libs', 'basis');
const target = join(root, 'public', 'basis');
const binary = ['basis_transcoder.js', 'basis_transcoder.wasm'];
for (const filename of binary) {
  const path = join(source, filename);
  if (!existsSync(path) || lstatSync(path).isSymbolicLink()) {
    throw new Error('Pinned Three.js Basis transcoder unavailable: ' + filename);
  }
  if (!realpathSync(path).startsWith(realpathSync(threeRoot) + '/')) {
    throw new Error('Transcoder escaped approved npm package');
  }
}
if (existsSync(target) && lstatSync(target).isSymbolicLink()) {
  throw new Error('Unsafe Basis output path');
}
mkdirSync(target, { recursive: true });
for (const filename of binary) {
  const dest = join(target, filename);
  if (existsSync(dest) && lstatSync(dest).isSymbolicLink()) {
    throw new Error('Refusing symlink transcoder destination: ' + filename);
  }
  copyFileSync(join(source, filename), dest);
}
console.log('Staged local Basis transcoder from three@0.186.1');
