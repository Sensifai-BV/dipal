<template>
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
              <input type="checkbox" :value="stage" v-model="selectedStages" />
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
</template>

<script setup lang="ts">
import { baseDialog } from "@/core/components/base";
import { ref } from "vue";

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

function applyFilters() {
  const createdAfter =
    range.value && range.value.start
      ? new Date(range.value.start).toISOString()
      : undefined;
  const createdBefore =
    range.value && range.value.end
      ? new Date(range.value.end).toISOString()
      : undefined;

  //   emit
  //   fetchProcessingJobs(
  //     selectedStatuses.value.length ? selectedStatuses.value : undefined,
  //     selectedStages.value.length ? selectedStages.value : undefined,
  //     createdAfter,
  //     createdBefore,
  //   );
  //   filterDialog.value = false;
}

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
</script>

<style scoped></style>
