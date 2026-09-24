<template>
  <div>
    <div class="flex flex-row justify-between mb-24">
      <page-description />
    </div>

    <div
      class="flex gap-2 items-center bg-white p-5 rounded-md border border-border"
    >
      <base-input
        v-model="searchText"
        name="search"
        type="search"
        class="w-full"
        icon="Search"
        placeholder="Search dataset..."
        @keyup.enter="fetchProcessingJobs()"
      >
        <template #prefix>
          <base-icon
            name="Search"
            :size="16"
            color="#6A7282"
            class="mr-2"
            :stroke-width="2"
          />
        </template>
      </base-input>

      <button
        type="button"
        :class="[
          'px-3 py-1 flex gap-1 items-center rounded border text-sm',
          hasActiveFilters
            ? 'bg-blue-50 border-blue-200 text-blue-700'
            : 'border-border',
        ]"
        @click="openFilterDialog"
        aria-label="Open filters"
      >
        <base-icon name="Funnel" :size="16" color="#6A7282" :stroke-width="2" />
        Filter
      </button>
    </div>

    <div class="mt-24">
      <base-table
        :headers="ProcessingJobTableHeaders"
        :data="dataTableValue"
        :dataRowCount="tableProps.dataRowCount"
        :loading="tableProps.loading"
        @change="onPageChange"
      >
        <template #cell-id="{ value }"> #{{ value }} </template>
        <template #cell-status="{ value, row }">
          <div class="flex flex-col items-start gap-1">
            <base-badge
              class="text-xs"
              :class="badgeColor(value as string)"
              :title="value === 'failed' && row.error_message ? row.error_message : undefined"
            >
              {{ value }}
            </base-badge>
            <span
              v-if="value === 'failed' && row.error_message"
              class="text-xs text-red-600 max-w-[280px] truncate"
              :title="row.error_message"
            >{{ row.error_message }}</span>
          </div>
        </template>
        <template #cell-progress="{ value }">
          <base-progress-bar :progress="value as number" variant="primary" />
        </template>
        <template #cell-created_at="{ value }">
          <div class="flex flex-row gap-1.5 items-center">
            <base-icon
              name="Calendar"
              :size="15"
              :stroke-width="2"
              class="inline"
            />
            <span v-format-date:datetime="value"></span>
          </div>
        </template>
        <template #cell-duration_seconds="{ value }">
          {{ formatDuration(value as number) }}
        </template>
        <template #cell-stage="{ value }">
          {{ formatStage(value as string) }}
        </template>
        <template #cell-actions="{ row }">
          <div class="flex flex-row gap-1.5 justify-end">
            <router-link
              :to="{
                name: 'products',
                params: { processJobId: row.id },
              }"
            >
              <div
                class="border border-rose-800 p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors"
                title="Products"
              >
                <base-icon
                  name="Eye"
                  :size="18"
                  :stroke-width="2"
                  class="cursor-pointer text-rose-800"
                />
              </div>
            </router-link>

            <div
              v-if="['processing', 'queued', 'pending'].includes(row.status)"
              class="border border-amber-500 p-1.5 px-2.5 rounded-md hover:bg-amber-50 transition-colors"
              title="Cancel Job"
            >
              <base-icon
                name="CircleStop"
                :size="18"
                :stroke-width="2"
                class="cursor-pointer text-amber-600"
                @click="openCancelDialog(row.id)"
              />
            </div>
            <div
              v-if="['failed', 'cancelled'].includes(row.status)"
              class="border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors"
              title="Retry Job"
            >
              <base-icon
                name="RotateCcw"
                :size="18"
                :stroke-width="2"
                class="cursor-pointer"
                @click="retryProcessingJob(row.id)"
              />
            </div>
            <div
              class="border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors"
              title="Delete Job"
            >
              <base-icon
                name="Trash"
                :size="18"
                :stroke-width="2"
                class="cursor-pointer"
                @click="openDeleteDialog(row.id)"
              />
            </div>
          </div>
        </template>
      </base-table>
    </div>

    <!-- Retry Choice Dialog -->
    <base-dialog v-model="showRetryChoiceDialog" title="Retry Processing Job">
      <template #body>
        <p class="text-sm text-neutral-500 mb-5">
          Choose how you'd like to retry this job.
        </p>
        <div class="flex flex-col gap-3">
          <button
            class="flex items-center gap-4 p-4 rounded-xl border border-border hover:border-blue-300 hover:bg-blue-50 transition-colors text-left cursor-pointer group"
            @click="retryJobs(false)"
          >
            <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50 group-hover:bg-blue-100 shrink-0">
              <base-icon name="Play" :size="20" :stroke-width="2" class="text-blue-600" />
            </div>
            <div class="flex flex-col gap-0.5">
              <span class="text-sm font-medium text-neutral-900">Continue from Last Step</span>
              <span class="text-xs text-neutral-400">Resume where the pipeline stopped</span>
            </div>
          </button>
          <button
            class="flex items-center gap-4 p-4 rounded-xl border border-border hover:border-amber-300 hover:bg-amber-50 transition-colors text-left cursor-pointer group"
            @click="retryJobs(true)"
          >
            <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-amber-50 group-hover:bg-amber-100 shrink-0">
              <base-icon name="RotateCcw" :size="20" :stroke-width="2" class="text-amber-600" />
            </div>
            <div class="flex flex-col gap-0.5">
              <span class="text-sm font-medium text-neutral-900">Restart from Beginning</span>
              <span class="text-xs text-neutral-400">Re-process the entire pipeline from scratch</span>
            </div>
          </button>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end">
          <base-button variant="ghost" size="sm" @click="showRetryChoiceDialog = false">
            Cancel
          </base-button>
        </div>
      </template>
    </base-dialog>

    <confirm-dialog
      v-model="showCancelDialog"
      title="Cancel processing job"
      message="Are you sure you want to cancel this running job? This action cannot be undone."
      confirm-text="Cancel Job"
      cancel-text="Go Back"
      @confirm="cancelProcessingJob"
      @cancel="showCancelDialog.show = false"
    />

    <confirm-dialog
      v-model="showDeleteDialog"
      title="Delete processing job"
      message="Are you sure you want to delete this job?"
      confirm-text="Delete"
      cancel-text="Cancel"
      @confirm="deleteProcessingJob"
      @cancel="showDeleteDialog.show = false"
    />

    <!-- TODO: component -->
    <base-dialog
      v-model="filterDialog"
      title="Filter Jobs"
      persistent
      leftFull
      subTitle="Filter processing jobs by status, stage, progress, and date range"
    >
      <template #body>
        <div class="flex flex-col h-full justify-between p-3">
          <div class="flex flex-col gap-4">
            <div
              class="flex flex-col gap-1 border-b border-border mb-8 pb-8 text-sm"
            >
              status
              <label
                v-for="option in statusOptions"
                :key="option"
                class="inline-flex items-center gap-3"
              >
                <input
                  type="checkbox"
                  :value="option"
                  v-model="selectedStatuses"
                />
                <span class="capitalize">{{ option }}</span>
              </label>
            </div>

            <div class="mb-4 text-sm">Processing stage</div>
            <div
              class="flex flex-col gap-1 mb-8 border-b border-border pb-8 text-sm"
            >
              <label
                v-for="stage in stageOptions"
                :key="stage"
                class="inline-flex items-center gap-3"
              >
                <input
                  type="checkbox"
                  :value="stage"
                  v-model="selectedStages"
                />
                <span class="capitalize">{{ stage }}</span>
              </label>
            </div>

            <DateModePicker v-model="mode" />
            <VDatePicker v-model.range="range" :mode="mode" :rules="rules" />
          </div>

          <div class="flex flex-row gap-2 justify-between mt-2">
            <button
              class="px-3 py-1.5 rounded border border-gray-200 w-full"
              @click="clearFilters"
              type="button"
            >
              Clear All
            </button>
            <button
              class="px-3 py-1.5 rounded bg-primary text-white w-full"
              @click="applyFilters"
              type="button"
            >
              Apply Filter
            </button>
          </div>
        </div>
      </template>
    </base-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  baseBadge,
  baseIcon,
  baseProgressBar,
  baseInput,
  baseDialog,
  baseTable,
  baseButton,
} from "@/core/components/base/index";
import { PageDescription } from "@/core/components/others/index";
import { reactive, ref, computed } from "vue";
import { ProcessingJobTableHeaders } from "./processing-job.constant";
import type { ProcessingJobItem } from "./processing-job.type";
import {
  getJobList,
  deleteJob,
  retryJob,
  cancelJob,
} from "@/module/processing-job/service/processing-jobs.service";
import { toastService } from "@/core/services/toast.service";
import ConfirmDialog from "@/core/components/others/confirm-dialog/confirm-dialog.vue";

const dataTableValue = ref<Array<ProcessingJobItem>>([]);
const tableProps = reactive<{ loading: boolean; dataRowCount: number }>({
  loading: false,
  dataRowCount: 0,
});

const searchText = ref<string>("");
const selectedStatuses = ref<Array<string>>([]);
const selectedStages = ref<Array<string>>([]);

const hasActiveFilters = computed(
  () =>
    selectedStatuses.value.length > 0 ||
    selectedStages.value.length > 0 ||
    !!(range.value && (range.value.start || range.value.end)),
);

const badgeColor = (status: string) => {
  switch (status?.toLowerCase()) {
    case "processing":
      return "bg-blue-100 text-blue-800";
    case "completed":
      return "bg-bg-success text-green-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "pending":
      return "bg-yellow-100 text-yellow-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const formatDuration = (seconds: number | null | undefined): string => {
  if (seconds == null || seconds <= 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h} h ${m} m`;
  if (m > 0) return `${m} m`;
  return `${Math.round(seconds)} s`;
};

const formatStage = (stage: string | null | undefined): string => {
  if (!stage) return "—";
  return stage
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

// Filter Dialog
const filterDialog = ref(false);

const statusOptions = ["pending", "processing", "completed", "failed"];
const stageOptions = [
  "queued",
  "preprocessing",
  "sfm",
  "mvs",
  "Ortho",
  "Generation",
  "Publishing",
];

function openFilterDialog() {
  filterDialog.value = true;
}

function clearFilters() {
  selectedStatuses.value = [];
  selectedStages.value = [];

  range.value = { start: null, end: null };
  filterDialog.value = false;

  fetchProcessingJobs();
}

function applyFilters() {
  const createdAfter =
    range.value && range.value.start
      ? new Date(range.value.start).toISOString()
      : undefined;
  const createdBefore =
    range.value && range.value.end
      ? new Date(range.value.end).toISOString()
      : undefined;

  fetchProcessingJobs(
    selectedStatuses.value.length ? selectedStatuses.value : undefined,
    selectedStages.value.length ? selectedStages.value : undefined,
    createdAfter,
    createdBefore,
  );
  filterDialog.value = false;
}

const range = ref<{ start: Date | null; end: Date | null }>({
  start: null,
  end: null,
});
const mode = ref("date");
const rules = ref([
  {
    hours: 0,
    minutes: 0,
    seconds: 0,
    milliseconds: 0,
  },
  {
    hours: 23,
    minutes: 59,
    seconds: 59,
    milliseconds: 999,
  },
]);

const fetchProcessingJobs = async (
  statuses?: string[],
  stages?: string[],
  createdAfter?: string,
  createdBefore?: string,
  page?: number,
  pageSize?: number,
) => {
  try {
    tableProps.loading = true;
    const useStatuses = statuses ?? selectedStatuses.value;
    const useStages = stages ?? selectedStages.value;

    const useCreatedAfter =
      createdAfter ??
      (range.value && range.value.start
        ? new Date(range.value.start).toISOString()
        : undefined);
    const useCreatedBefore =
      createdBefore ??
      (range.value && range.value.end
        ? new Date(range.value.end).toISOString()
        : undefined);

    const data = await getJobList(
      searchText.value,
      useStatuses,
      useStages,
      useCreatedAfter,
      useCreatedBefore,
      page,
      pageSize,
    );

    dataTableValue.value = data.results;
    tableProps.loading = false;
    tableProps.dataRowCount = data.count;
  } catch (error) {
    console.error("Error fetching processing jobs:", error);
  }
};
fetchProcessingJobs();

const onPageChange = (page: number, pageSize: number) => {
  fetchProcessingJobs(undefined, undefined, undefined, undefined, page, pageSize);
};

const showRetryDialog = ref({ show: false, item: "" });
const showRetryChoiceDialog = ref(false);
async function retryProcessingJob(jobId: string) {
  showRetryDialog.value.item = jobId;
  showRetryChoiceDialog.value = true;
}

async function retryJobs(forceRestart: boolean) {
  try {
    await retryJob(showRetryDialog.value.item, forceRestart);
    await fetchProcessingJobs();
  } catch (err: any) {
    if (!err?._toastShown) {
      const message =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to retry job";
      toastService.error("Error", message);
    }
  } finally {
    showRetryChoiceDialog.value = false;
    showRetryDialog.value.show = false;
  }
}

const showCancelDialog = ref({ show: false, item: "" });
function openCancelDialog(jobId: string) {
  showCancelDialog.value.show = true;
  showCancelDialog.value.item = jobId;
}

async function cancelProcessingJob() {
  try {
    await cancelJob(showCancelDialog.value.item);
    await fetchProcessingJobs();
  } catch (err: any) {
    if (!err?._toastShown) {
      const message =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        "Failed to cancel job";
      toastService.error("Error", message);
    }
  } finally {
    showCancelDialog.value.show = false;
  }
}

const showDeleteDialog = ref({ show: false, item: "" });
async function openDeleteDialog(jobId: string) {
  showDeleteDialog.value.show = true;
  showDeleteDialog.value.item = jobId;
}

async function deleteProcessingJob() {
  try {
    await deleteJob(showDeleteDialog.value.item);
    await fetchProcessingJobs();
  } catch (err: any) {
    if (!err?._toastShown) {
      toastService.error("Error", "Failed to delete job");
    }
  } finally {
    showDeleteDialog.value.show = false;
  }
}
</script>
