<template>
  <div ref="container" class="ply-viewer">
    <!-- Loading Overlay -->
    <div v-if="loading" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-neutral-900/85">
      <span class="w-12 h-12 rounded-full border-4 border-neutral-700 border-b-blue-400 inline-block animate-spin mb-4" />
      <span class="text-sm font-medium text-neutral-200 mb-1">{{ loadingPhase }}</span>
      <span v-if="loadingDetail" class="text-xs text-neutral-400">{{ loadingDetail }}</span>
      <div v-if="loadingProgress > 0" class="w-48 h-1.5 bg-neutral-700 rounded-full mt-3 overflow-hidden">
        <div class="h-full bg-blue-400 rounded-full transition-all duration-200" :style="{ width: loadingProgress + '%' }" />
      </div>
    </div>

    <!-- Settings Panel (top-right) -->
    <div v-if="!loading && modelLoaded" class="absolute top-3 right-3 z-20">
      <button
        class="w-8 h-8 flex items-center justify-center rounded-md bg-neutral-800/80 hover:bg-neutral-700/90 border border-neutral-600/50 text-neutral-300 hover:text-white transition-colors backdrop-blur-sm cursor-pointer"
        title="Settings"
        @click="showSettings = !showSettings"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
      </button>
      <Transition name="panel">
        <div
          v-if="showSettings"
          class="absolute top-10 right-0 w-56 bg-neutral-800/95 backdrop-blur-md border border-neutral-600/50 rounded-lg shadow-xl overflow-hidden"
        >
          <div class="px-3 py-2 border-b border-neutral-700/50">
            <span class="text-xs font-semibold text-neutral-300 uppercase tracking-wide">Display</span>
          </div>
          <div class="px-3 py-2 flex flex-col gap-2">
            <label class="flex items-center justify-between cursor-pointer group">
              <span class="text-xs text-neutral-400 group-hover:text-neutral-200 transition-colors">Grid</span>
              <input type="checkbox" v-model="showGrid" class="accent-blue-500 w-3.5 h-3.5 cursor-pointer" />
            </label>
            <label class="flex items-center justify-between cursor-pointer group">
              <span class="text-xs text-neutral-400 group-hover:text-neutral-200 transition-colors">Axes Gizmo</span>
              <input type="checkbox" v-model="showGizmo" class="accent-blue-500 w-3.5 h-3.5 cursor-pointer" />
            </label>
            <label class="flex items-center justify-between cursor-pointer group">
              <span class="text-xs text-neutral-400 group-hover:text-neutral-200 transition-colors">Info Bar</span>
              <input type="checkbox" v-model="showInfoBar" class="accent-blue-500 w-3.5 h-3.5 cursor-pointer" />
            </label>
          </div>
          <div class="px-3 py-2 border-t border-neutral-700/50">
            <span class="text-xs font-semibold text-neutral-300 uppercase tracking-wide">Point Size</span>
            <input
              v-if="renderMode === 'POINTS'"
              type="range" min="1" max="30" step="1" v-model.number="pointSizeSlider"
              class="w-full mt-1.5 accent-blue-500 h-1 cursor-pointer"
              @input="onPointSizeChange"
            />
            <span v-else class="text-xs text-neutral-500 mt-1 block">N/A (mesh mode)</span>
          </div>
          <div class="px-3 py-2 border-t border-neutral-700/50">
            <span class="text-xs font-semibold text-neutral-300 uppercase tracking-wide">Background</span>
            <div class="flex gap-1.5 mt-1.5">
              <button
                v-for="bg in bgOptions" :key="bg.name"
                class="w-6 h-6 rounded-md border-2 transition-all cursor-pointer"
                :class="activeBg === bg.name ? 'border-blue-400 scale-110' : 'border-neutral-600 hover:border-neutral-400'"
                :style="{ background: bg.preview }"
                :title="bg.name"
                @click="setBg(bg.name)"
              />
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Info Bar (bottom) -->
    <div v-if="!loading && modelLoaded && showInfoBar" class="absolute bottom-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-2 bg-neutral-900/75 backdrop-blur-sm border-t border-neutral-700/50">
      <div class="flex items-center gap-4 text-xs text-neutral-400 font-mono">
        <span>FOV: {{ fov }}°</span>
        <span>FPS: {{ fps }}</span>
        <span>{{ renderMode }}</span>
      </div>
      <div class="flex items-center gap-4 text-xs text-neutral-400 font-mono">
        <span>{{ modelName }}</span>
        <span>Vertices: {{ vertexCount }}</span>
        <span>Faces: {{ faceCount }}</span>
        <span v-if="hasVertexColors">VC</span>
      </div>
    </div>

    <!-- Axes Gizmo (bottom-left) -->
    <div v-show="showGizmo" ref="gizmoContainer" class="absolute bottom-12 left-3 z-10 w-[100px] h-[100px] pointer-events-none" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader";

const props = defineProps<{
  src: string;
}>();

const container = ref<HTMLDivElement | null>(null);
const gizmoContainer = ref<HTMLDivElement | null>(null);

const loading = ref(true);
const loadingPhase = ref("Parsing geometry…");
const loadingDetail = ref("");
const loadingProgress = ref(0);
const modelLoaded = ref(false);

const fov = ref(60);
const fps = ref("—");
const renderMode = ref("POINTS");
const modelName = ref("Model");
const vertexCount = ref("0");
const faceCount = ref("0");
const hasVertexColors = ref(false);

const showSettings = ref(false);
const showGrid = ref(false);
const showGizmo = ref(true);
const showInfoBar = ref(true);
const pointSizeSlider = ref(8);
const activeBg = ref("Dark");

const bgOptions = [
  { name: "Dark", preview: "linear-gradient(180deg, #0a0a12, #14142b)", stops: ["#0a0a12", "#14142b"] },
  { name: "Black", preview: "#000000", stops: ["#000000", "#000000"] },
  { name: "Slate", preview: "linear-gradient(180deg, #1e293b, #0f172a)", stops: ["#1e293b", "#0f172a"] },
  { name: "Light", preview: "linear-gradient(180deg, #e2e8f0, #cbd5e1)", stops: ["#e2e8f0", "#cbd5e1"] },
];

let gridHelper: THREE.GridHelper | null = null;
let pointsMaterial: THREE.PointsMaterial | null = null;

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let frameId = 0;

let gizmoScene: THREE.Scene;
let gizmoCamera: THREE.PerspectiveCamera;
let gizmoRenderer: THREE.WebGLRenderer;

let lastTime = performance.now();
let frameCount = 0;

// ---------- Scene ----------
function initScene() {
  scene = new THREE.Scene();

  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
  gradient.addColorStop(0, "#0a0a12");
  gradient.addColorStop(1, "#14142b");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  scene.background = new THREE.CanvasTexture(canvas);

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const directional = new THREE.DirectionalLight(0xffffff, 1.2);
  directional.position.set(10, 20, 10);
  scene.add(directional);
}

function applyBackground(name: string) {
  const opt = bgOptions.find((b) => b.name === name) ?? bgOptions[0];
  const cvs = document.createElement("canvas");
  cvs.width = 256;
  cvs.height = 256;
  const c = cvs.getContext("2d")!;
  const g = c.createLinearGradient(0, 0, 0, cvs.height);
  g.addColorStop(0, opt.stops[0]);
  g.addColorStop(1, opt.stops[1]);
  c.fillStyle = g;
  c.fillRect(0, 0, cvs.width, cvs.height);
  if (scene) scene.background = new THREE.CanvasTexture(cvs);
}

function setBg(name: string) {
  activeBg.value = name;
  applyBackground(name);
}

function onPointSizeChange() {
  if (pointsMaterial) pointsMaterial.size = pointSizeSlider.value / 1000;
}

watch(showGrid, (val) => {
  if (gridHelper) gridHelper.visible = val;
});

// ---------- Camera ----------
function initCamera(width: number, height: number) {
  camera = new THREE.PerspectiveCamera(fov.value, width / height, 0.01, 2000);
  camera.position.set(4.5, 3, -9);
  camera.lookAt(0, 0, 0);
}

// ---------- Renderer ----------
function initRenderer(width: number, height: number) {
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  container.value!.appendChild(renderer.domElement);
}

// ---------- Controls ----------
function initControls() {
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.8;
  controls.zoomSpeed = 1.2;
  controls.panSpeed = 0.6;
}

// ---------- Gizmo (Axes Sphere Widget) ----------
function initGizmo() {
  if (!gizmoContainer.value) return;

  gizmoScene = new THREE.Scene();
  gizmoCamera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  gizmoCamera.position.set(0, 0, 3);

  gizmoRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  gizmoRenderer.setSize(100, 100);
  gizmoRenderer.setPixelRatio(window.devicePixelRatio);
  gizmoRenderer.setClearColor(0x000000, 0);
  gizmoContainer.value.appendChild(gizmoRenderer.domElement);

  const sphereGeo = new THREE.SphereGeometry(0.85, 32, 32);
  const sphereMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.06,
    wireframe: false,
  });
  gizmoScene.add(new THREE.Mesh(sphereGeo, sphereMat));

  const ringGeo = new THREE.RingGeometry(0.84, 0.87, 64);

  const ringXY = new THREE.Mesh(ringGeo.clone(), new THREE.MeshBasicMaterial({ color: 0x4488ff, transparent: true, opacity: 0.2, side: THREE.DoubleSide }));
  gizmoScene.add(ringXY);

  const ringXZ = new THREE.Mesh(ringGeo.clone(), new THREE.MeshBasicMaterial({ color: 0x44ff88, transparent: true, opacity: 0.2, side: THREE.DoubleSide }));
  ringXZ.rotation.x = Math.PI / 2;
  gizmoScene.add(ringXZ);

  const ringYZ = new THREE.Mesh(ringGeo.clone(), new THREE.MeshBasicMaterial({ color: 0xff4444, transparent: true, opacity: 0.2, side: THREE.DoubleSide }));
  ringYZ.rotation.y = Math.PI / 2;
  gizmoScene.add(ringYZ);

  const axisLength = 1.1;
  const createAxis = (dir: THREE.Vector3, color: number, label: string) => {
    const points = [new THREE.Vector3(0, 0, 0), dir.clone().multiplyScalar(axisLength)];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({ color, linewidth: 2 });
    gizmoScene.add(new THREE.Line(geo, mat));

    const tipGeo = new THREE.ConeGeometry(0.06, 0.2, 8);
    const tipMat = new THREE.MeshBasicMaterial({ color });
    const tip = new THREE.Mesh(tipGeo, tipMat);
    tip.position.copy(dir.clone().multiplyScalar(axisLength));
    tip.lookAt(dir.clone().multiplyScalar(axisLength + 1));
    if (dir.y !== 0) tip.rotation.x = dir.y > 0 ? 0 : Math.PI;
    else if (dir.x !== 0) tip.rotation.z = dir.x > 0 ? -Math.PI / 2 : Math.PI / 2;
    gizmoScene.add(tip);

    const cvs = document.createElement("canvas");
    cvs.width = 64;
    cvs.height = 64;
    const c = cvs.getContext("2d")!;
    c.fillStyle = `#${color.toString(16).padStart(6, "0")}`;
    c.font = "bold 48px sans-serif";
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.fillText(label, 32, 32);
    const tex = new THREE.CanvasTexture(cvs);
    const spriteMat = new THREE.SpriteMaterial({ map: tex, transparent: true });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.position.copy(dir.clone().multiplyScalar(axisLength + 0.25));
    sprite.scale.set(0.3, 0.3, 0.3);
    gizmoScene.add(sprite);
  };

  createAxis(new THREE.Vector3(1, 0, 0), 0xff4444, "X");
  createAxis(new THREE.Vector3(0, 1, 0), 0x44ff44, "Y");
  createAxis(new THREE.Vector3(0, 0, 1), 0x4488ff, "Z");
}

function updateGizmo() {
  if (!gizmoCamera || !camera) return;
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  gizmoCamera.position.copy(dir.multiplyScalar(-3));
  gizmoCamera.lookAt(0, 0, 0);
  gizmoRenderer.render(gizmoScene, gizmoCamera);
}

// ---------- Load PLY ----------
function loadPLY(url: string) {
  loading.value = true;
  loadingPhase.value = "Parsing geometry…";
  loadingDetail.value = "Reading PLY data from cache";
  loadingProgress.value = 0;

  const loader = new PLYLoader();
  loader.load(
    url,
    (geometry: any) => {
      loadingPhase.value = "Building scene…";
      loadingDetail.value = "Computing normals and bounding box";
      loadingProgress.value = 80;

      geometry.computeVertexNormals();
      geometry.computeBoundingBox();
      const bbox = geometry.boundingBox!;
      const size = new THREE.Vector3();
      bbox.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      const scale = 5 / maxDim;
      geometry.scale(scale, scale, scale);
      geometry.center();

      const hasFaces = geometry.index !== null && geometry.index.count > 0;
      const vCount = geometry.attributes.position.count;
      const fCount = hasFaces ? geometry.index!.count / 3 : 0;
      const vc = geometry.hasAttribute("color");

      vertexCount.value = vCount.toLocaleString();
      faceCount.value = fCount.toLocaleString();
      hasVertexColors.value = vc;

      let object: THREE.Object3D;

      if (hasFaces) {
        renderMode.value = "MESH";
        const material = new THREE.MeshStandardMaterial({
          vertexColors: vc,
          color: vc ? undefined : 0x888888,
          roughness: 0.4,
          metalness: 0.1,
        });
        object = new THREE.Mesh(geometry, material);
      } else {
        renderMode.value = "POINTS";
        const material = new THREE.PointsMaterial({
          size: pointSizeSlider.value / 1000,
          vertexColors: vc,
          color: vc ? undefined : 0x888888,
          sizeAttenuation: true,
        });
        pointsMaterial = material;
        object = new THREE.Points(geometry, material);
      }

      loadingProgress.value = 95;
      loadingDetail.value = "Adding to scene";

      scene.add(object);

      const center = new THREE.Vector3();
      geometry.computeBoundingBox();
      geometry.boundingBox!.getCenter(center);
      camera.position.set(center.x + 3, center.y + 3, center.z + 3);
      camera.lookAt(center);
      controls.target.copy(center);

      const gridSize = Math.max(size.x, size.z) * scale * 2;
      gridHelper = new THREE.GridHelper(gridSize, 10, 0x333344, 0x222233);
      gridHelper.visible = showGrid.value;
      scene.add(gridHelper);

      loadingProgress.value = 100;
      loading.value = false;
      modelLoaded.value = true;
      modelName.value = hasFaces ? "3D Mesh" : "3D Point Cloud";
    },
    (event: any) => {
      if (event.total) {
        const pct = Math.round((event.loaded / event.total) * 100);
        loadingProgress.value = Math.min(pct * 0.7, 70);
        loadingDetail.value = `${(event.loaded / 1024 / 1024).toFixed(1)} / ${(event.total / 1024 / 1024).toFixed(1)} MB`;
      } else if (event.loaded) {
        const mb = (event.loaded / 1024 / 1024).toFixed(1);
        loadingDetail.value = `${mb} MB loaded`;
      }
    },
    (err: any) => {
      console.error("PLY load error:", err);
      loading.value = false;
      loadingPhase.value = "Failed to load model";
    },
  );
}

// ---------- Animate ----------
function animate() {
  frameId = requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  updateGizmo();

  frameCount++;
  const now = performance.now();
  if (now - lastTime >= 500) {
    fps.value = ((frameCount / (now - lastTime)) * 1000).toFixed(1);
    frameCount = 0;
    lastTime = now;
  }
}

// ---------- Resize ----------
function onResize() {
  if (!container.value) return;
  const width = container.value.clientWidth;
  const height = container.value.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}

// ---------- Lifecycle ----------
onMounted(() => {
  if (!container.value) return;

  const width = container.value.clientWidth;
  const height = container.value.clientHeight;

  initScene();
  initCamera(width, height);
  initRenderer(width, height);
  initControls();
  initGizmo();

  if (props.src) loadPLY(props.src);

  window.addEventListener("resize", onResize);
  animate();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  renderer?.dispose();
  gizmoRenderer?.dispose();
  window.removeEventListener("resize", onResize);
});
</script>

<style scoped>
.ply-viewer {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
}
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}
</style>
