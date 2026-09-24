<template>
  <base-dialog
    v-model="isShowDialog.show"
    :title="dialogInfo.title"
    :sub-title="dialogInfo.subTitle"
    @close="closeDialog"
  >
    <template #body>
      <div class="flex flex-col gap-3.5 py-3.5">
        <div
          class="data-set-name flex flex-col gap-1.5 bg-soft-white p-3.5 border border-neutral-150 rounded-md"
        >
          <span class="font-medium text-sm text-neutral-900">
            Selected Dataset:
          </span>
          <span class="font-medium text-base text-neutral-950">
            {{ isShowDialog.fileName }}
          </span>
        </div>

        <div
          class="flex flex-col gap-3 font-normal py-2 border-b border-neutral-100"
        >
          <base-input
            v-model="processingConfig.resolution_gsd"
            type="number"
            label="Resolution (GSD - Ground Sample Distance)"
            min="0.5"
            max="50"
            step="0.5"
          >
            <template #suffix>
              <span class="text-secondary text-sm font-normal">cm/px</span>
            </template>
          </base-input>

          <span v-if="gsdError" class="text-red-500 text-sm font-normal">
            {{ gsdError }}
          </span>
          <span class="text-secondary text-sm font-normal w-4/5 pb-3">
            Lower values provide higher resolution output (typical range: 2-10
            cm/px)
          </span>
        </div>

        <div class="flex flex-col gap-2 py-2">
          <span class="text-sm font-medium text-neutral-900">Analysis Mode</span>
          <div class="flex flex-col gap-2">
            <button
              type="button"
              class="flex items-start gap-3 p-3 rounded-lg border transition-colors text-left"
              :class="processingConfig.analysis_mode === 'fast' ? 'border-blue-300 bg-blue-50' : 'border-border hover:bg-neutral-50'"
              @click="processingConfig.analysis_mode = 'fast'"
            >
              <div
                class="mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0"
                :class="processingConfig.analysis_mode === 'fast' ? 'border-blue-600' : 'border-neutral-300'"
              >
                <div
                  v-if="processingConfig.analysis_mode === 'fast'"
                  class="w-2 h-2 rounded-full bg-blue-600"
                />
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="text-sm font-medium text-neutral-900">Fast (RGB Only)</span>
                <span class="text-xs text-neutral-500">
                  Generates RGB orthomosaic, DSM, and point cloud. Best for quick previews and visual inspections.
                </span>
              </div>
            </button>
            <button
              type="button"
              class="flex items-start gap-3 p-3 rounded-lg border transition-colors text-left"
              :class="processingConfig.analysis_mode === 'full' ? 'border-blue-300 bg-blue-50' : 'border-border hover:bg-neutral-50'"
              @click="processingConfig.analysis_mode = 'full'"
            >
              <div
                class="mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0"
                :class="processingConfig.analysis_mode === 'full' ? 'border-blue-600' : 'border-neutral-300'"
              >
                <div
                  v-if="processingConfig.analysis_mode === 'full'"
                  class="w-2 h-2 rounded-full bg-blue-600"
                />
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="text-sm font-medium text-neutral-900">Full (Multispectral + Indices)</span>
                <span class="text-xs text-neutral-500">
                  Includes all Fast outputs plus NDVI, NDRE, GNDVI vegetation indices and radiometric calibration. Recommended for agricultural analysis.
                </span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex flex-row-reverse gap-2 mt-12">
        <base-button
          variant="primary"
          block
          class="w-1/3!"
          :disabled="buttonProperty.disabled || !!gsdError"
          @click="startProcessing"
          :loading="buttonProperty.loading"
          size="md"
        >
          <div class="flex items-center">
            <base-icon
              name="Play"
              :size="16"
              :stroke-width="2"
              class="inline mr-2"
            />
            <span>Start Processing</span>
          </div>
        </base-button>
        <base-button
          variant="secondary"
          class="w-[90px]!"
          block
          size="md"
          @click="closeDialog"
        >
          <span class="font-bold">Cancel</span>
        </base-button>
      </div>
    </template>
  </base-dialog>
</template>

<script setup lang="ts">
import {
  baseButton,
  baseDialog,
  baseIcon,
  baseInput,
} from "@/core/components/base/index";
import { reactive, computed } from "vue";
import { startDataSetProcess } from "@module/dataset/service/data-set.service";
import { toastService } from "@/core/services/toast.service";
import { useRouter } from "vue-router";
import { PROCESSING_JOB_ROUTES } from "@module/processing-job/router/route.constant";

const router = useRouter();

const isShowDialog = defineModel<{
  show: boolean;
  datasetId: string;
  fileName?: string;
}>({
  required: true,
});

const dialogInfo = reactive({
  title: "Processing Configuration",
  subTitle: "Configure processing parameters for the dataset",
});

const closeDialog = () => {
  isShowDialog.value.show = false;
};

const buttonProperty = reactive({
  disabled: false,
  loading: false,
});

const processingConfig = reactive({
  resolution_gsd: 5,
  analysis_mode: "full" as "fast" | "full",
});

const gsdError = computed(() => {
  const val = Number(processingConfig.resolution_gsd);
  if (isNaN(val) || val === 0) return "GSD is required";
  if (val < 0.5) return "GSD must be at least 0.5 cm/px";
  if (val > 50) return "GSD must be at most 50 cm/px";
  return null;
});

const startProcessing = async () => {
  buttonProperty.disabled = true;
  buttonProperty.loading = true;

  try {
    const data = await startDataSetProcess({
      ...processingConfig,
      dataset_id: isShowDialog.value.datasetId,
    });

    router.push({
      name: PROCESSING_JOB_ROUTES.processingJobList,
    });
    console.log("data", data);
  } catch (error: any) {
    if (!error?._toastShown) {
      const msg = error?.response?.data?.error || error?.response?.data?.detail || "Failed to start processing";
      toastService.error("Error", msg);
    }
  } finally {
    Object.assign(buttonProperty, {
      disabled: false,
      loading: false,
    });
  }
};
</script>
