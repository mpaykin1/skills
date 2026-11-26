/**
 * Official Khronos glTF-Validator gate for approved GLBs in a generated game.
 * Runs before Vite dev/build. Never validates by hash alone, and never fetches
 * remote resources, executes game scripts, or changes original game files.
 * A private, hash-bound approval manifest is written only after real validator
 * execution. This is internal data, not a substitute for visual QA.
 *
 * Runtime dependency: gltf-validator@2.0.0-dev.3.10 (Apache-2.0).
 */
import { readFile, writeFile, rm, lstat, realpath } from 'node:fs/promises';
import { resolve, join, sep } from 'node:path';
import { createHash } from 'node:crypto';

const PROJECT = resolve(process.cwd());
const PUBLIC = resolve(PROJECT, 'public');
const STAMP = join(PUBLIC, 'gltf-validation-manifest.json');
const HASH_RE = /^[a-f0-9]{64}$/;
const ASSET_RE = /^\/assets\/([a-f0-9]{18})\.glb$/;
const SCHEMA = 'meta-game-fusion.gltf-validation.v1';
const VERSION = '2.0.0-dev.3.10';
const MAX_GLB_BYTES = 128 * 1024 * 1024;
const MAX_ASSETS = 256;

function check(test, message) {
  if (!test) throw new Error(`glTF Validator gate: ${message}`);
}
function object(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}
async function json(path) {
  const contents = await readFile(path, 'utf8');
  check(contents.length < 8 * 1024 * 1024, 'world manifest exceeds size budget');
  return JSON.parse(contents);
}
async function assertSafeRegularFile(filename) {
  const st = await lstat(filename);
  check(st.isFile() && !st.isSymbolicLink(), `unsafe or absent file: ${filename}`);
  const full = await realpath(filename);
  check(full.startsWith(PUBLIC + sep), 'path escaped game public directory');
  check(st.size >= 20 && st.size <= MAX_GLB_BYTES, 'GLB exceeds size budget');
}
function failDetails(report) {
  const messages = report?.issues?.messages;
  if (!Array.isArray(messages)) return '';
  return messages.filter(x => x && x.severity === 0).slice(0, 5)
    .map(x => String(x.code || 'INVALID') + ': ' + String(x.message || '').slice(0, 180)).join(' | ');
}

async function run() {
  // Invalidate any stamp from a previous (possibly modified) build.
  await rm(STAMP, { force: true });
  const world = await json(join(PUBLIC, 'world.json'));
  check(object(world) && Array.isArray(world.assets), 'world.assets must be an array');
  check(world.assets.length <= MAX_ASSETS, 'too many assets');
  const seen = new Set();
  const assets = [];
  // No GLBs: no validator invocation and no misleading "validated model" claims.
  if (world.assets.length === 0) {
    await writeFile(STAMP, JSON.stringify({ schema: SCHEMA, validator: VERSION, assets: [],
      status: 'no-GLB-assets-to-validate' }, null, 2) + '\n', { flag: 'wx' });
    process.stdout.write('glTF Validator: no imported GLB assets; gate not applicable\n');
    return;
  }
  let validator;
  try {
    const mod = await import('gltf-validator');
    validator = typeof mod.validateBytes === 'function' ? mod : mod.default;
    check(typeof validator?.validateBytes === 'function', 'official npm API missing validateBytes');
    check(typeof validator.version === 'function', 'official validator.version() missing');
    check(String(validator.version()) === VERSION, 'installed glTF-Validator version mismatch');
  } catch (e) {
    throw new Error(`glTF-Validator ${VERSION} is required: ${e.message}`);
  }
  for (const entry of world.assets) {
    check(object(entry), 'malformed world asset');
    const src = entry.src;
    const expected = entry.asset_sha256;
    const match = typeof src === 'string' ? ASSET_RE.exec(src) : null;
    check(match && HASH_RE.test(expected) && match[1] === expected.slice(0, 18), 'asset path/hash mismatch');
    check(!seen.has(src), `duplicate approved asset ${src}`);
    seen.add(src);
    const file = join(PUBLIC, src.slice(1));
    await assertSafeRegularFile(file);
    const bytes = await readFile(file);
    const digest = createHash('sha256').update(bytes).digest('hex');
    check(digest === expected, `approved GLB changed: ${src}`);
    const header = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    check(header.getUint32(0, true) === 0x46546c67 &&
      header.getUint32(4, true) === 2 &&
      header.getUint32(8, true) === bytes.byteLength, `invalid GLB2 header: ${src}`);
    // No remote/file:// resources: imported GLBs must be fully self-contained.
    const report = await validator.validateBytes(new Uint8Array(bytes), {
      uri: src, format: 'glb', maxIssues: 100, writeTimestamp: false,
      externalResourceFunction: async () => {
        throw new Error('external GLB dependencies are prohibited');
      }
    });
    const errors = report?.issues?.numErrors;
    const warnings = report?.issues?.numWarnings;
    check(Number.isInteger(errors) && errors === 0,
      `invalid glTF ${src} (${errors ?? 'unknown'} errors): ${failDetails(report)}`);
    check(Number.isInteger(warnings) && warnings >= 0, `invalid validation result for ${src}`);
    assets.push({ src, asset_sha256: digest, errors: 0, warnings });
  }
  const stamp = { schema: SCHEMA, validator: VERSION, status: 'validator-executed', assets };
  await writeFile(STAMP, JSON.stringify(stamp, null, 2) + '\n', { flag: 'wx' });
  process.stdout.write(`glTF Validator: validated ${assets.length} approved GLB(s); no errors\n`);
}

run().catch(async error => {
  await rm(STAMP, { force: true }).catch(() => {});
  process.stderr.write(String(error?.message || error) + '\n');
  process.exitCode = 2;
});
