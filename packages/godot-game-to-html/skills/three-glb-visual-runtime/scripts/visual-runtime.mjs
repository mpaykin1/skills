// Three.js GLB visual runtime: ORIGINAL models, textures, animation and cameras.
// No fabricated gameplay; bundle this module locally with esbuild for offline HTML.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';

const host = document.getElementById('scene');
const status = document.getElementById('status');
const controlsPanel = document.getElementById('controls');
const clipPicker = document.getElementById('clip');
const playButton = document.getElementById('play');
const resetButton = document.getElementById('reset');
const loading = document.getElementById('loading');
let renderer, scene, camera, orbit, mixer, currentAction, clips = [], originalCamera = null;
const clock = new THREE.Clock();
let wasPlaying = true;
let ktx2Loader = null;
let transcoderObjectURLs = [];

function decodeBase64(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing embedded Basis component: ${id}`);
  const raw = node.textContent.trim();
  const chunks = [];
  let length = 0;
  for (let n = 0; n < raw.length; n += 65536) {
    const part = atob(raw.slice(n, n + 65536));
    const bytes = Uint8Array.from(part, c => c.charCodeAt(0));
    chunks.push(bytes); length += bytes.length;
  }
  const result = new Uint8Array(length);
  let pos = 0;
  for (const chunk of chunks) { result.set(chunk, pos); pos += chunk.length; }
  return result;
}
function makeBasisBridge(manager, loader) {
  // Build-time __HAS_BASIS__ eliminates these dependencies for ordinary PNG GLBs.
  const js = decodeBase64('basis-js');
  const wasm = decodeBase64('basis-wasm');
  if (wasm.length < 8 || wasm[0] !== 0 || wasm[1] !== 97 || wasm[2] !== 115 || wasm[3] !== 109)
    throw new Error('Embedded Basis WASM signature invalid');
  const jsUrl = URL.createObjectURL(new Blob([js], {type:'text/javascript'}));
  const wasmUrl = URL.createObjectURL(new Blob([wasm], {type:'application/wasm'}));
  transcoderObjectURLs = [jsUrl, wasmUrl];
  manager.setURLModifier(url => {
    if (url === '__embedded_basis__/basis_transcoder.js') return jsUrl;
    if (url === '__embedded_basis__/basis_transcoder.wasm') return wasmUrl;
    return url;
  });
  ktx2Loader = new KTX2Loader(manager);
  ktx2Loader.setTranscoderPath('__embedded_basis__/');
  ktx2Loader.detectSupport(renderer);
  loader.setKTX2Loader(ktx2Loader);
}
function releaseBasisBridge() {
  if (ktx2Loader) { ktx2Loader.dispose(); ktx2Loader = null; }
  for (const url of transcoderObjectURLs) URL.revokeObjectURL(url);
  transcoderObjectURLs = [];
}


function setStatus(message) { status.textContent = message; }
function getEmbeddedBytes() {
  const raw = document.getElementById('asset-glb').textContent.replace(/\s/g, '');
  const buffer = new Uint8Array(Math.floor(raw.length * 3 / 4));
  let offset = 0;
  const chunkSize = 4 * 16384;
  for (let i = 0; i < raw.length; i += chunkSize) {
    const part = atob(raw.slice(i, i + chunkSize));
    for (let n = 0; n < part.length; n++) buffer[offset++] = part.charCodeAt(n);
  }
  return buffer.buffer.slice(0, offset);
}
function frameCamera(target) {
  const bounds = new THREE.Box3().setFromObject(target);
  if (bounds.isEmpty()) return;
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const radius = Math.max(0.5, size.length() * 0.5);
  camera.position.copy(center).add(new THREE.Vector3(radius * 1.3, radius * 0.65, radius * 1.5));
  camera.near = Math.max(0.001, radius / 1000);
  camera.far = Math.max(400, radius * 500);
  camera.updateProjectionMatrix();
  orbit.target.copy(center);
  orbit.minDistance = Math.max(0.1, radius * 0.05);
  orbit.maxDistance = Math.max(20, radius * 30);
  orbit.update();
}
function useClip(index) {
  if (!mixer) return;
  if (currentAction) currentAction.stop();
  const clip = clips[index];
  currentAction = clip ? mixer.clipAction(clip) : null;
  if (currentAction) { currentAction.reset().play(); currentAction.paused = !wasPlaying; }
  playButton.disabled = !currentAction;
}
function resize() {
  if (!renderer || !camera) return;
  const w = Math.max(1, host.clientWidth), h = Math.max(1, host.clientHeight);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
function onLoad(gltf) {
  releaseBasisBridge();
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x080d13); // Only neutral stage backdrop; no replacement scenery.
  scene.add(gltf.scene);
  const lights = [];
  gltf.scene.traverse(o => { if (o.isLight) lights.push(o); });
  if (lights.length === 0) {
    // Viewer-only fill lighting, needed when source GLB does not include Unity/Godot scene lights.
    scene.add(new THREE.HemisphereLight(0xacc5e3, 0x24202e, 1.35));
    const key = new THREE.DirectionalLight(0xffffff, 2.1);
    key.position.set(6, 11, 8);
    scene.add(key);
  }
  camera = new THREE.PerspectiveCamera(55, 1, 0.01, 1000);
  originalCamera = gltf.cameras?.find(c => c.isPerspectiveCamera) ?? null;
  if (originalCamera) {
    // Use original camera field-of-view, but orbit framing remains under user control.
    camera.fov = originalCamera.fov;
    camera.updateProjectionMatrix();
  }
  orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enableDamping = true;
  orbit.dampingFactor = 0.075;
  orbit.screenSpacePanning = true;
  frameCamera(gltf.scene);
  resize();
  clips = gltf.animations || [];
  if (clips.length > 0) {
    mixer = new THREE.AnimationMixer(gltf.scene);
    clips.forEach((clip, i) => {
      const option = document.createElement('option');
      option.value = String(i);
      option.textContent = clip.name || `Animation ${i + 1}`;
      clipPicker.append(option);
    });
    clipPicker.disabled = false;
    useClip(0);
  } else {
    clipPicker.innerHTML = '<option>Без анимаций</option>';
    clipPicker.disabled = true;
  }
  clipPicker.addEventListener('change', () => useClip(Number(clipPicker.value)));
  playButton.addEventListener('click', () => {
    wasPlaying = !wasPlaying;
    if (currentAction) currentAction.paused = !wasPlaying;
    playButton.textContent = wasPlaying ? 'Пауза' : 'Играть';
  });
  resetButton.addEventListener('click', () => frameCamera(gltf.scene));
  loading.hidden = true;
  controlsPanel.hidden = false;
  let nodes = 0, meshes = 0;
  gltf.scene.traverse(o => { nodes++; if (o.isMesh || o.isSkinnedMesh) meshes++; });
  setStatus(`${meshes} meshes · ${nodes} nodes · ${clips.length} animations · visual scene`);
}
try {
  renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: false});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping; // Default avoids subjective alteration of original materials.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  host.appendChild(renderer.domElement);
  const manager = new THREE.LoadingManager();
  const loader = new GLTFLoader(manager);
  loader.setMeshoptDecoder(MeshoptDecoder);
  if (__HAS_BASIS__) makeBasisBridge(manager, loader);
  loader.parse(getEmbeddedBytes(), '', onLoad, err => {
    releaseBasisBridge();
    setStatus('GLB: ошибка загрузки · ' + String(err?.message || err));
    loading.textContent = 'Не удалось открыть GLB';
  });
  window.addEventListener('resize', resize);
  const obs = new ResizeObserver(resize);
  obs.observe(host);
  let slowFrames = 0;
  function tick() {
    requestAnimationFrame(tick);
    if (!renderer || !scene || !camera) return;
    const dt = Math.min(0.1, clock.getDelta());
    if (!document.hidden) {
      if (mixer) mixer.update(dt);
      if (orbit) orbit.update();
      renderer.render(scene, camera);
      if (dt > 1 / 28) slowFrames++;
      else slowFrames = Math.max(0, slowFrames - 2);
      if (slowFrames > 30 && renderer.getPixelRatio() > 1) {
        renderer.setPixelRatio(1);
        resize();
        slowFrames = 0;
      }
    }
  }
  tick();
} catch (e) {
  releaseBasisBridge();
  setStatus('WebGL недоступен: ' + String(e?.message || e));
  loading.textContent = 'WebGL не поддерживается этим браузером';
}
