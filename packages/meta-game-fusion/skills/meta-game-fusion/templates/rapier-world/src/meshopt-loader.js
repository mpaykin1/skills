/**
 * META GAME FUSION — SHA-256 verified glTF visual loading.
 * Geometry: meshoptimizer/decoder. Textures: Basis Universal KTX2Loader.
 * Rapier owns collisions; Recast owns navigation. Visual meshes never become
 * physics truth merely because they are compressed or decoded.
 */
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'meshoptimizer/decoder';

const MAX_GLB_BYTES = 128 * 1024 * 1024;
const APPROVED_PATH = /^\/assets\/([a-f0-9]{18})\.glb$/;
const HASH = /^[a-f0-9]{64}$/;
const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);
let basisLoader = null;
let supportedRenderer = null;
let validationManifestPromise = null;

async function requireKhronosValidation(assetURL, expectedHash) {
  if (!validationManifestPromise) {
    validationManifestPromise = (async () => {
      const response = await fetch('/gltf-validation-manifest.json', {
        cache: 'no-store', credentials: 'same-origin'
      });
      if (!response.ok || response.type === 'opaque') {
        throw new Error('Khronos glTF validation manifest missing; refusing model load');
      }
      const stamp = await response.json();
      if (stamp?.schema !== 'meta-game-fusion.gltf-validation.v1' ||
          stamp?.validator !== '2.0.0-dev.3.10' || stamp?.status !== 'validator-executed' ||
          !Array.isArray(stamp.assets)) {
        throw new Error('No genuine Khronos GLB validator approval');
      }
      return stamp;
    })();
  }
  const stamp = await validationManifestPromise;
  const record = stamp.assets.find(row => row?.src === assetURL && row?.asset_sha256 === expectedHash);
  if (!record || record.errors !== 0) {
    throw new Error('GLB is not Khronos-validated at its approved SHA-256');
  }
}


function configureBasis(renderer) {
  if (!renderer?.capabilities || typeof renderer.getContext !== 'function') {
    throw new Error('Three.js WebGL renderer required to initialize KTX2 transcoder');
  }
  if (!basisLoader) {
    // Files are copied from the *installed, pinned* Three.js npm package by
    // scripts/stage-ktx2.mjs, never loaded from a CDN or external host.
    basisLoader = new KTX2Loader().setTranscoderPath('/basis/');
  }
  if (supportedRenderer !== renderer) {
    basisLoader.detectSupport(renderer);
    supportedRenderer = renderer;
  }
  loader.setKTX2Loader(basisLoader);
}

function digestHex(bytes) {
  if (!globalThis.crypto?.subtle?.digest) {
    throw new Error('Secure browser SHA-256 unavailable; refusing unverifiable asset');
  }
  return crypto.subtle.digest('SHA-256', bytes).then(result =>
    [...new Uint8Array(result)].map(v => v.toString(16).padStart(2, '0')).join(''));
}

export async function loadVerifiedScenery(asset, renderer) {
  const url = asset?.src;
  const expected = asset?.asset_sha256;
  const matched = typeof url === 'string' && url.match(APPROVED_PATH);
  if (!matched || typeof expected !== 'string' || !HASH.test(expected) || matched[1] !== expected.slice(0, 18)) {
    throw new Error('Approved visual asset path/hash invalid');
  }
  const compression = asset?.compression || 'none';
  const textures = asset?.texture_compression || 'none';
  if (!['none', 'meshopt'].includes(compression) || !['none', 'ktx2'].includes(textures)) {
    throw new Error('Unsupported declared visual compression');
  }
  await requireKhronosValidation(url, expected);
  if (compression === 'meshopt') {
    if (!MeshoptDecoder.supported) throw new Error('meshoptimizer WebAssembly decoder unavailable');
    await MeshoptDecoder.ready;
  }
  // KTX2 uses native GPU texture formats where possible, with Basis fallback
  // managed by the official Three.js transcoder for the detected GPU.
  if (textures === 'ktx2') configureBasis(renderer);
  const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok || response.type === 'opaque') {
    throw new Error(`Could not fetch approved GLB (${response.status})`);
  }
  const announcedSize = Number(response.headers.get('content-length') || 0);
  if (announcedSize > MAX_GLB_BYTES) throw new Error('GLB exceeds browser memory budget');
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength < 20 || bytes.byteLength > MAX_GLB_BYTES) {
    throw new Error('Invalid or oversized GLB payload');
  }
  if (await digestHex(bytes) !== expected) {
    throw new Error('Approved GLB SHA-256 changed after export');
  }
  const view = new DataView(bytes);
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== bytes.byteLength) {
    throw new Error('Not a valid GLB2 file');
  }
  // Decoded render geometry is allowed into MeshBVH only when static; no visual
  // decoding ever changes Rapier collision bodies or Recast navmesh authority.
  return loader.parseAsync(bytes, '/assets/');
}
