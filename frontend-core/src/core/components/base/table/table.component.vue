<template>
  <div
    class="base-table relative rounded-2xl w-full bg-white border border-border min-h-64"
  >
    <!-- Header -->
    <div
      class="base-header hidden lg:grid grid-cols-12 border-b border-border font-medium p-2.5"
    >
      <span
        v-for="(item, index) in headers"
        :key="`${item.text}-${index}`"
        class="text-sm capitalize"
        :class="item.styles"
      >
        {{ item.text }}
      </span>
    </div>

    <!-- Empty -->
    <div v-if="!data.length && !loading" class="py-16 flex justify-center">
      <div class="text-center text-neutral-400">No Data Available</div>
    </div>

    <span
      v-if="loading"
      class="w-14 h-14 rounded-full border-6 border-white border-b-primary-200 inline-block animate-spin absolute top-1/2 right-1/2 -translate-y-1/2 -translate-x-1/2"
    />

    <!-- Body -->
    <div
      v-if="data.length"
      ref="scrollRoot"
      class="overflow-y-auto custom-scroll"
    >
      <div
        v-for="(row, rIndex) in data"
        :key="`row-${rIndex}`"
        class="p-4 text-sm lg:hidden border-b border-border"
      >
        <div
          v-for="(header, hIndex) in headers"
          :key="`cell-${rIndex}-${hIndex}`"
          class="p-2 flex justify-between"
        >
          <span> {{ header.text }}: </span>
          <slot
            :name="`cell-${String(header.field)}`"
            :row="row"
            :value="header.field ? row[header.field] : undefined"
          >
            {{ header.field ? row[header.field] : "" }}
          </slot>
        </div>
      </div>

      <div
        v-for="(row, rIndex) in data"
        :key="`row-${rIndex}`"
        class="p-2.5 border-b border-border hidden lg:grid grid-cols-12 items-center last:border-b-0 text-sm"
      >
        <div
          v-for="(header, hIndex) in headers"
          :key="`cell-${rIndex}-${hIndex}`"
          class="table-cell"
          :class="header.field ? findColumnClass(header.field) : ''"
        >
          <slot
            :name="`cell-${String(header.field)}`"
            :row="row"
            :value="header.field ? row[header.field] : undefined"
          >
            {{ header.field ? row[header.field] : "" }}
          </slot>
        </div>
      </div>

      <div ref="observerEl" class="h-px w-full opacity-0 pointer-events-none" />

      <div
        v-if="!props.hidePagination"
        class="flex text-sm justify-end p-3 items-center gap-6"
      >
        <button
          @click="prevPage"
          :disabled="currentPage === 1"
          class="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 text-xs"
        >
          Prev
        </button>
        <span class=""> Page {{ currentPage }} of {{ totalPages }} </span>
        <button
          @click="nextPage"
          :disabled="currentPage === totalPages"
          class="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 text-xs"
        >
          Next
        </button>

        <select
          v-model="pageSize"
          @change="onPageSizeChange"
          class="ml-4 px-2 py-0.5 border border-gray-300 rounded"
        >
          <option v-for="size in pageSizes" :key="size" :value="size">
            {{ size }} / page
          </option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T">
import { computed, nextTick, onBeforeUnmount, ref, watch, watchEffect } from "vue";
import type { BaseTableEmits, BaseTableProps } from "./table.type";

const props = defineProps<BaseTableProps<T>>();
const emit = defineEmits<BaseTableEmits<T>>();

const findColumnClass = (field: keyof T) => {
  return props.headers.find((header) => header.field === field)?.styles || "";
};

const observerEl = ref<HTMLElement | null>(null);
const scrollRoot = ref<HTMLElement | null>(null);

let observer: IntersectionObserver | null = null;

const setupObserver = async () => {
  await nextTick();
  if (!scrollRoot.value || !observerEl.value) return;

  observer?.disconnect();

  observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (entry?.isIntersecting && props.hasMore) {
        emit("loadMore");
      }
    },
    {
      root: scrollRoot.value,
      rootMargin: "100px",
      threshold: 0,
    },
  );

  observer.observe(observerEl.value);
};

onBeforeUnmount(() => {
  observer?.disconnect();
});

watchEffect(() => {
  if (props.data.length) {
    nextTick(() => {
      setupObserver();
    });
  }
});

// Pagination
const currentPage = ref(1);
const pageSize = ref(props.initialPageSize && [5, 10, 20, 40].includes(props.initialPageSize) ? props.initialPageSize : 10);

const pageSizes = [5, 10, 20, 40];

const totalPages = computed(() =>
  Math.max(1, Math.ceil(props.dataRowCount / pageSize.value)),
);

watch(
  () => props.dataRowCount,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = Math.max(1, totalPages.value);
    }
  },
);

function emitChange() {
  emit("change", currentPage.value, pageSize.value);
}

function prevPage() {
  if (currentPage.value === 1) return;
  currentPage.value--;
  emitChange();
}

function nextPage() {
  if (currentPage.value === totalPages.value) return;
  currentPage.value++;
  emitChange();
}

function onPageSizeChange() {
  currentPage.value = 1;
  emit("change", currentPage.value, pageSize.value);
}
</script>

<style scoped>
.custom-scroll::-webkit-scrollbar {
  width: 6px;
}

.custom-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scroll::-webkit-scrollbar-thumb {
  background-color: var(--color-neutral-300);
  border-radius: 9999px;
}

.custom-scroll {
  scrollbar-width: thin;
  scrollbar-color: #d1d5dc transparent;
}

.loader {
  width: 48px;
  height: 48px;
  border: 5px solid #fff;
  border-bottom-color: transparent;
  border-radius: 50%;
  display: inline-block;
  box-sizing: border-box;
  animation: rotation 1s linear infinite;
}

@keyframes rotation {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
