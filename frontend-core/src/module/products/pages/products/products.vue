<template>
  <div>
    <div class="flex flex-row justify-between mb-24">
      <page-description />
    </div>

    <!-- Job Selector (shown when no job ID in route) -->
    <div v-if="!selectedJobId" class="flex flex-col items-center justify-center py-16">
      <div class="bg-white border border-border rounded-2xl p-8 w-full max-w-lg">
        <h3 class="text-lg font-semibold text-neutral-800 mb-2">Select a Job</h3>
        <p class="text-sm text-neutral-400 mb-6">Choose a completed processing job to view its products.</p>
        <div v-if="jobListLoading" class="flex justify-center py-4">
          <span class="w-8 h-8 rounded-full border-4 border-white border-b-primary-200 inline-block animate-spin" />
        </div>
        <div v-else-if="jobList.length === 0" class="text-center text-neutral-400 py-4">
          No completed jobs found.
        </div>
        <div v-else class="flex flex-col gap-2 max-h-80 overflow-y-auto">
          <button
            v-for="job in jobList"
            :key="job.id"
            class="flex items-center justify-between p-3 rounded-md border border-border hover:bg-blue-50 hover:border-blue-200 transition-colors text-left cursor-pointer"
            @click="selectJob(job.id)"
          >
            <div class="flex flex-col gap-0.5">
              <span class="text-sm font-medium text-neutral-900">{{ job.dataset_name }}</span>
              <span class="text-xs text-neutral-400">GSD: {{ job.resolution_gsd }} cm/px</span>
            </div>
            <div class="flex items-center gap-2">
              <base-badge class="text-xs bg-bg-success text-green-800">{{ job.status }}</base-badge>
              <base-icon name="ChevronRight" :size="16" :stroke-width="2" class="text-neutral-400" />
            </div>
          </button>
        </div>
      </div>
    </div>

    <!-- Products Content -->
    <div v-else>
      <!-- Job In Progress Banner -->
      <div
        v-if="isJobActive"
        class="mb-4 border border-blue-200 bg-blue-50 rounded-xl p-4"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="w-4 h-4 rounded-full border-2 border-blue-400 border-b-transparent inline-block animate-spin" />
          <span class="text-sm font-semibold text-blue-800">Job in progress</span>
        </div>
        <p class="text-xs text-blue-700">
          <template v-if="jobStageLabel">Stage: <strong>{{ jobStageLabel }}</strong></template>
          <template v-if="jobProgress !== null"> &mdash; {{ jobProgress }}% complete</template>
          <template v-if="!jobStageLabel && jobProgress === null">Processing is underway. Products will appear here as each stage completes.</template>
        </p>
      </div>

      <!-- Job Failed Banner -->
      <div
        v-if="jobStatus === 'failed'"
        class="mb-4 border border-red-200 bg-red-50 rounded-xl p-4"
      >
        <div class="flex items-center gap-2 mb-1">
          <base-icon name="CircleX" :size="18" :stroke-width="2" class="text-red-600" />
          <span class="text-sm font-semibold text-red-800">Job failed</span>
        </div>
        <p class="text-xs text-red-700">
          This processing job encountered an error and did not complete successfully. You can retry it from the Jobs list.
        </p>
      </div>

      <!-- Missing Core Products Alert (only shown when job is terminal and not failed) -->
      <div
        v-if="!isJobActive && jobStatus !== 'failed' && missingCoreProducts.length > 0"
        class="mb-4 border border-amber-200 bg-amber-50 rounded-xl p-4"
      >
        <div class="flex items-center gap-2 mb-2">
          <base-icon name="AlertTriangle" :size="18" :stroke-width="2" class="text-amber-600" />
          <span class="text-sm font-semibold text-amber-800">
            {{ missingCoreProducts.length }} expected product{{ missingCoreProducts.length > 1 ? 's' : '' }} not available
          </span>
        </div>
        <p class="text-xs text-amber-700 mb-3">
          The following results were not generated. You may need to retry the processing job.
        </p>
        <div class="flex flex-wrap gap-2">
          <base-badge
            v-for="product in missingCoreProducts"
            :key="product"
            class="text-xs bg-amber-100 text-amber-800"
          >
            {{ product }}
          </base-badge>
        </div>
      </div>

      <!-- Multispectral Products Unavailable -->
      <div
        v-if="missingMultispectralProducts.length > 0"
        class="mb-4 border border-neutral-200 bg-neutral-50 rounded-xl p-4"
      >
        <div class="flex items-center gap-2 mb-2">
          <base-icon name="Info" :size="18" :stroke-width="2" class="text-neutral-500" />
          <span class="text-sm font-semibold text-neutral-700">
            Multispectral products unavailable
          </span>
        </div>
        <p class="text-xs text-neutral-500 mb-3">
          The following products are not available because the dataset does not contain multispectral images.
        </p>
        <div class="flex flex-wrap gap-2">
          <base-badge
            v-for="product in missingMultispectralProducts"
            :key="product.type"
            class="text-xs bg-neutral-100 text-neutral-600"
          >
            {{ product.label }}
          </base-badge>
        </div>
      </div>

      <!-- Products Table -->
      <base-table
        :headers="ProductTableHeaders"
        :data="dataTableValue"
        :dataRowCount="tableProps.dataRowCount"
        :loading="tableProps.loading"
        :initialPageSize="20"
        @change="onPageChange"
      >
        <template #cell-type_display="{ value, row }">
          <span>{{ value || row.type }}</span>
        </template>

        <template #cell-resolution_cm="{ value }">
          <span v-if="value">{{ value }} cm/px</span>
          <span v-else class="text-neutral-400">—</span>
        </template>

        <template #cell-created_at="{ value }">
          <div class="flex flex-row gap-1.5 items-center">
            <base-icon name="Calendar" :size="15" :stroke-width="2" class="inline" />
            <span v-format-date:datetime="value"></span>
          </div>
        </template>

        <template #cell-actions="{ row }">
          <div class="flex justify-end gap-1.5 items-center">
            <div
              v-if="isViewable(row)"
              class="border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors cursor-pointer"
              title="View"
              @click="onRowClick(row)"
            >
              <base-icon name="Eye" :size="18" :stroke-width="2" />
            </div>
            <div
              class="border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors cursor-pointer"
              title="Download"
              @click="downloadProduct(row)"
            >
              <base-icon name="Download" :size="18" :stroke-width="2" />
            </div>
          </div>
        </template>
      </base-table>

      <div class="mt-4 flex justify-end">
        <base-button variant="ghost" size="sm" @click="downloadJobResultsJson">
          <base-icon name="FileJson" :size="16" :stroke-width="2" class="mr-1.5" />
          Download Results JSON
        </base-button>
      </div>
    </div>

    <!-- Product Viewer (Fullscreen overlay) -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showViewer"
          class="fixed inset-0 z-2000 flex flex-col bg-neutral-900"
        >
          <!-- Viewer Header -->
          <div class="flex items-center justify-between px-5 py-3 bg-neutral-800 border-b border-neutral-700 shrink-0">
            <div class="flex items-center gap-3">
              <base-icon name="Eye" :size="18" :stroke-width="2" class="text-neutral-300" />
              <span class="text-sm font-medium text-white">{{ viewerTitle }}</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                class="p-2 rounded-md hover:bg-neutral-700 transition-colors text-neutral-300 hover:text-white"
                title="Download"
                @click="downloadProduct(viewerItem!)"
              >
                <base-icon name="Download" :size="18" :stroke-width="2" />
              </button>
              <button
                class="p-2 rounded-md hover:bg-neutral-700 transition-colors text-neutral-300 hover:text-white"
                title="Close"
                @click="closeViewer"
              >
                <base-icon name="X" :size="20" :stroke-width="2" />
              </button>
            </div>
          </div>

          <!-- Viewer Body -->
          <div class="flex-1 relative overflow-hidden">
            <div v-if="viewerLoading" class="absolute inset-0 flex justify-center items-center">
              <span class="w-10 h-10 rounded-full border-4 border-neutral-700 border-b-blue-400 inline-block animate-spin" />
            </div>
            <ThreeViewer
              v-if="viewerType === 'three' && imageUrl"
              :key="viewerKey"
              :src="imageUrl"
              class="w-full h-full"
            />
            <TifViewer
              v-if="viewerType === 'tif' && imageUrl"
              :key="viewerKey"
              :src="imageUrl"
              class="w-full h-full"
            />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { baseIcon, baseTable, baseButton, baseBadge } from "@/core/components/base";
import { getProductListWithFilter, getCompletedJobList, getJobDetail } from "../../service/products.service";
import { ProductTableHeaders, EXPECTED_PRODUCTS, DOWNLOAD_ONLY_TYPES, MULTISPECTRAL_PRODUCT_TYPES, ACTIVE_JOB_STATUSES, STAGE_LABELS } from "./products.constant";
import { PageDescription } from "@/core/components/others/index";
import TifViewer from "@/core/components/others/three-viewer/tif-viewer.vue";
import ThreeViewer from "@/core/components/others/three-viewer/three-viewer.vue";
import { getFile, saveFile } from "@/core/utils/indexedDb";

const route = useRoute();
const router = useRouter();

const tableProps = ref<{ loading: boolean; dataRowCount: number }>({
  loading: false,
  dataRowCount: 0,
});

const dataTableValue = ref<Array<any>>([]);

const jobList = ref<Array<any>>([]);
const jobListLoading = ref(false);

const selectedJobId = computed(() => route.params.processJobId as string | undefined);

const allProductTypes = ref<Set<string>>(new Set());
const jobAnalysisMode = ref<string | null>(null);
const jobStatus = ref<string | null>(null);
const jobStage = ref<string | null>(null);
const jobProgress = ref<number | null>(null);

const isJobActive = computed(() =>
  jobStatus.value ? ACTIVE_JOB_STATUSES.has(jobStatus.value) : false
);

const jobStageLabel = computed(() =>
  jobStage.value ? (STAGE_LABELS[jobStage.value] ?? jobStage.value) : null
);

const hasAnyMultispectralProduct = computed(() => {
  return MULTISPECTRAL_PRODUCT_TYPES.some((t) => allProductTypes.value.has(t));
});

const isMultispectralJob = computed(() => {
  if (hasAnyMultispectralProduct.value) return true;
  if (jobAnalysisMode.value === "full") return true;
  if (jobAnalysisMode.value) return false;
  return null;
});

const missingProducts = computed(() => {
  return EXPECTED_PRODUCTS.filter((ep) => !allProductTypes.value.has(ep.type));
});

const missingMultispectralProducts = computed(() => {
  if (isMultispectralJob.value !== false) return [];
  return missingProducts.value.filter((ep) => MULTISPECTRAL_PRODUCT_TYPES.includes(ep.type));
});

const missingCoreProducts = computed(() => {
  const multispectralMissing = new Set(missingMultispectralProducts.value.map((ep) => ep.type));
  return missingProducts.value.filter((ep) => !multispectralMissing.has(ep.type)).map((ep) => ep.label);
});

const isViewable = (row: any): boolean => {
  return !DOWNLOAD_ONLY_TYPES.includes(row.type);
};

const fetchJobList = async () => {
  jobListLoading.value = true;
  try {
    const data = await getCompletedJobList();
    jobList.value = data.results ?? [];
  } catch (error) {
    console.error("Error fetching job list:", error);
  } finally {
    jobListLoading.value = false;
  }
};

const selectJob = (jobId: string) => {
  router.push({ path: `/products/${jobId}` });
};

const fetchProducts = async (page: number, pageSize: number) => {
  if (!selectedJobId.value) return;
  dataTableValue.value = [];
  tableProps.value.loading = true;

  try {
    const products = await getProductListWithFilter(
      selectedJobId.value,
      page,
      pageSize,
    );

    tableProps.value.dataRowCount = products.count;
    dataTableValue.value = [...products.results];
    products.results.forEach((p: any) => allProductTypes.value.add(p.type));
  } catch (error) {
    console.error("Error fetching products:", error);
  } finally {
    tableProps.value.loading = false;
  }
};

const onPageChange = (page: number, pageSize: number) => {
  fetchProducts(page, pageSize);
};

// --- Job status polling (runs while the job is in an active state) ---
let pollTimer: ReturnType<typeof setInterval> | null = null;
const POLL_INTERVAL_MS = 5000;

function startPolling() {
  if (pollTimer !== null) return;
  pollTimer = setInterval(async () => {
    if (!selectedJobId.value) return;
    try {
      const job = await getJobDetail(selectedJobId.value);
      const prev = jobStatus.value;
      jobStatus.value = job.status ?? null;
      jobStage.value = job.stage ?? null;
      jobProgress.value = job.progress ?? null;
      // When the job transitions out of active state, refresh products too
      if (prev !== job.status && !ACTIVE_JOB_STATUSES.has(job.status ?? "")) {
        await fetchProducts(1, 20);
        try {
          const all = await getProductListWithFilter(selectedJobId.value, 1, 100);
          all.results.forEach((p: any) => allProductTypes.value.add(p.type));
        } catch (_) { /* ignore */ }
      }
    } catch (e) {
      console.error("Error polling job status:", e);
    }
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(isJobActive, (active) => {
  if (active) {
    startPolling();
  } else {
    stopPolling();
  }
}, { immediate: true });

onMounted(async () => {
  if (selectedJobId.value) {
    await fetchProducts(1, 20);
    if (tableProps.value.dataRowCount > dataTableValue.value.length) {
      try {
        const all = await getProductListWithFilter(selectedJobId.value, 1, 100);
        all.results.forEach((p: any) => allProductTypes.value.add(p.type));
      } catch (e) {
        console.error("Error fetching all product types:", e);
      }
    }
    try {
      const job = await getJobDetail(selectedJobId.value);
      jobAnalysisMode.value = job.analysis_mode ?? null;
      jobStatus.value = job.status ?? null;
      jobStage.value = job.stage ?? null;
      jobProgress.value = job.progress ?? null;
    } catch (e) {
      console.error("Error fetching job details:", e);
    }
  } else {
    await fetchJobList();
  }
});

const imageUrl = ref<string | null>(null);
const viewerLoading = ref(false);
const viewerType = ref<"three" | "tif" | null>(null);
const showViewer = ref(false);
const viewerTitle = ref("Product View");
const viewerItem = ref<any>(null);
const viewerKey = ref(0);

async function onRowClick(item: any) {
  if (!isViewable(item)) return;

  viewerKey.value++;
  imageUrl.value = null;
  viewerType.value = null;
  viewerLoading.value = true;
  viewerItem.value = item;
  viewerTitle.value = `${item.type_display || item.type} — ${item.category}`;
  showViewer.value = true;

  try {
    if (!objectUrls.value[item.id]) await downloadImage(item);
    imageUrl.value = objectUrls.value[item.id] ?? null;
    viewerType.value = item.category === "2D Raster" || item.category === "Calibration" ? "tif" : "three";
  } finally {
    viewerLoading.value = false;
  }
}

function closeViewer() {
  showViewer.value = false;
  imageUrl.value = null;
  viewerType.value = null;
  viewerItem.value = null;
  viewerLoading.value = false;
}

const objectUrls = ref<Record<string, string>>({});

async function downloadImage(item: any): Promise<string> {
  if (item.id in objectUrls.value) return objectUrls.value[item.id]!;

  try {
    let blob = await getFile(item.id);

    if (!blob) {
      const response = await fetch(item.download_url);
      if (!response.ok) throw new Error("Download failed");
      blob = await response.blob();
      await saveFile(item.id, blob);
    }

    const url = URL.createObjectURL(blob);
    objectUrls.value[item.id] = url;
    return url;
  } catch (error) {
    console.error("Error downloading product:", error);
    throw error;
  }
}

async function downloadProduct(item: any) {
  try {
    const response = await fetch(item.download_url);
    if (!response.ok) throw new Error("Download failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ext = item.uri?.split(".").pop() || (item.category === "2D Raster" ? "tif" : "ply");
    a.download = `${item.type_display || item.type}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error("Error downloading product:", error);
  }
}

function downloadJobResultsJson() {
  const json = JSON.stringify(dataTableValue.value, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `job-${selectedJobId.value}-results.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

onUnmounted(() => {
  stopPolling();
  for (const key in objectUrls.value) {
    if (objectUrls.value[key]) URL.revokeObjectURL(objectUrls.value[key]);
  }
});
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
