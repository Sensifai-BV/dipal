<template>
  <div ref="container" class="tiff-viewer">
    <div v-if="errorMsg" class="error-overlay">{{ errorMsg }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { fromArrayBuffer } from "geotiff";

const props = defineProps<{ src: string }>();

const container = ref<HTMLDivElement | null>(null);
const errorMsg = ref<string | null>(null);

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let frameId = 0;

function animate() {
  frameId = requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

async function loadTiff(url: string) {
  if (!container.value) return;
  errorMsg.value = null;

  try {
    const res = await fetch(url);
    const buffer = await res.arrayBuffer();
    const tiff = await fromArrayBuffer(buffer);
    const image = await tiff.getImage();

    const imgWidth = image.getWidth();
    const imgHeight = image.getHeight();
    const samplesPerPixel = image.getSamplesPerPixel();
    const bitsPerSample = image.getBitsPerSample();
    const area = imgWidth * imgHeight;

    const gdalNoData = image.getGDALNoData();
    const noData = gdalNoData !== null ? Number(gdalNoData) : null;

    const rasters = await image.readRasters();
    const rgba = new Uint8Array(area * 4);

    if (samplesPerPixel >= 3 && bitsPerSample[0] === 8) {
      const r = rasters[0] as Uint8Array;
      const g = rasters[1] as Uint8Array;
      const b = rasters[2] as Uint8Array;
      const a = samplesPerPixel >= 4 ? (rasters[3] as Uint8Array) : null;
      for (let i = 0; i < area; i++) {
        const qi = i * 4;
        rgba[qi]     = r[i];
        rgba[qi + 1] = g[i];
        rgba[qi + 2] = b[i];
        rgba[qi + 3] = a ? a[i] : 255;
      }
    } else if (samplesPerPixel >= 3 && bitsPerSample[0] === 16) {
      const r = rasters[0] as Uint16Array;
      const g = rasters[1] as Uint16Array;
      const b = rasters[2] as Uint16Array;
      for (let i = 0; i < area; i++) {
        const qi = i * 4;
        rgba[qi]     = r[i] >> 8;
        rgba[qi + 1] = g[i] >> 8;
        rgba[qi + 2] = b[i] >> 8;
        rgba[qi + 3] = 255;
      }
    } else if (samplesPerPixel >= 3) {
      const bands = [];
      for (let b = 0; b < 3; b++) bands.push(rasters[b] as Float32Array | Float64Array);
      const stats = bands.map(band => bandMinMax(band, noData));
      for (let i = 0; i < area; i++) {
        const qi = i * 4;
        for (let b = 0; b < 3; b++) {
          const v = (bands[b] as any)[i];
          const { min, range } = stats[b];
          rgba[qi + b] = isFinite(v) ? Math.round(((v - min) / range) * 255) : 0;
        }
        rgba[qi + 3] = 255;
      }
    } else {
      const band = rasters[0] as Float32Array | Float64Array | Uint8Array | Uint16Array | Int16Array;
      const isInteger8 = bitsPerSample[0] === 8;
      if (isInteger8) {
        for (let i = 0; i < area; i++) {
          const qi = i * 4;
          const v = band[i];
          rgba[qi] = rgba[qi + 1] = rgba[qi + 2] = v;
          rgba[qi + 3] = 255;
        }
      } else {
        const { min, range } = bandMinMax(band, noData);
        for (let i = 0; i < area; i++) {
          const qi = i * 4;
          const v = band[i];
          if (!isFinite(v) || (noData !== null && v === noData)) {
            rgba[qi + 3] = 0;
            continue;
          }
          const t = (v - min) / range;
          const [cr, cg, cb] = viridis(t);
          rgba[qi]     = cr;
          rgba[qi + 1] = cg;
          rgba[qi + 2] = cb;
          rgba[qi + 3] = 255;
        }
      }
    }

    const texture = new THREE.DataTexture(rgba, imgWidth, imgHeight, THREE.RGBAFormat);
    texture.needsUpdate = true;

    const geometry = new THREE.PlaneGeometry(imgWidth / 100, imgHeight / 100);
    const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide });
    const plane = new THREE.Mesh(geometry, material);
    plane.rotation.x = -Math.PI / 2;
    scene.add(plane);
  } catch (e) {
    console.error("Failed to load TIFF:", e);
    errorMsg.value = "Failed to load image. The file may be corrupted or too large.";
  }
}

function bandMinMax(band: ArrayLike<number>, noData: number | null = null): { min: number; max: number; range: number } {
  let fMin = Infinity, fMax = -Infinity;
  for (let i = 0; i < band.length; i++) {
    const v = band[i];
    if (!isFinite(v)) continue;
    if (noData !== null && v === noData) continue;
    if (v < fMin) fMin = v;
    if (v > fMax) fMax = v;
  }
  return { min: fMin, max: fMax, range: fMax - fMin || 1 };
}

function viridis(t: number): [number, number, number] {
  return VIRIDIS_LUT[Math.round(Math.max(0, Math.min(1, t)) * 255)];
}

const VIRIDIS_LUT: [number, number, number][] = (() => {
  const anchors: [number, number, number, number][] = [
    [0.0,   68,   1,  84],
    [0.13,  71,  44, 122],
    [0.25,  59,  81, 139],
    [0.38,  44, 113, 142],
    [0.50,  33, 144, 141],
    [0.63,  39, 173, 129],
    [0.75,  92, 200,  99],
    [0.88, 170, 220,  50],
    [1.0,  253, 231,  37],
  ];
  const lut: [number, number, number][] = new Array(256);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let lo = 0;
    for (let j = 1; j < anchors.length; j++) {
      if (anchors[j][0] >= t) { lo = j - 1; break; }
    }
    const a = anchors[lo], b = anchors[lo + 1];
    const f = (t - a[0]) / (b[0] - a[0]);
    lut[i] = [
      Math.round(a[1] + f * (b[1] - a[1])),
      Math.round(a[2] + f * (b[2] - a[2])),
      Math.round(a[3] + f * (b[3] - a[3])),
    ];
  }
  return lut;
})();

function onResize() {
  if (!container.value) return;
  const width = container.value.clientWidth;
  const height = container.value.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}

onMounted(() => {
  if (!container.value) return;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1020);

  const width = container.value.clientWidth;
  const height = container.value.clientHeight;
  camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
  camera.position.set(0, 5, 5);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);
  container.value.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI / 2.05;

  scene.add(new THREE.AmbientLight(0xffffff, 0.4));

  if (props.src) loadTiff(props.src);

  window.addEventListener("resize", onResize);
  animate();
});

watch(
  () => props.src,
  (newSrc) => {
    if (newSrc) loadTiff(newSrc);
  }
);

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  renderer.dispose();
  window.removeEventListener("resize", onResize);
});
</script>

<style scoped>
.tiff-viewer {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #0b1020;
  position: relative;
}
.error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f87171;
  font-size: 0.875rem;
  z-index: 10;
  pointer-events: none;
}
</style>
