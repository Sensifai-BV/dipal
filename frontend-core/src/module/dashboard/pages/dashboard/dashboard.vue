<template>
  <div class="mb-24">
    <page-description />
  </div>
  <div>
    <div class="flex flex-row gap-6">
      <base-card v-for="(item, key) in cardsInfo" :key="`card-${key}`">
        <template #default>
          <div class="flex flex-row justify-between w-full">
            <div class="flex flex-col gap-3">
              <span class="text-secondary font-normal text-base">
                {{ item.title }}
              </span>
              <span class="text-black font-normal text-base">
                {{ item?.value }}
              </span>
              <span class="text-secondary text-sm">{{ item.date }}</span>
            </div>
            <div>
              <div class="bg-neutral-50 p-3 rounded-md">
                <base-icon
                  :name="item.icon || 'Database'"
                  :size="25"
                  :stroke-width="2"
                  :default-class="item.color || 'text-primary'"
                />
              </div>
            </div>
          </div>
        </template>
      </base-card>
    </div>
    <div
      class="content grid grid-cols-[70%_calc(30%-23px)] gap-24 mt-6 min-h-80"
    >
      <div
        class="recent-activities bg-white flex flex-col gap-2 p-6 rounded-xl border border-border overflow-auto max-h-160 h-full"
      >
        <span class="text-base text-black font-normal">Recent Activities</span>
        <div
          class="border-b border-border pb-3.5 flex flex-row items-center gap-3 last:border-0"
          v-for="value in activityItems"
          :key="value.title"
        >
          <div class="bg-neutral-50 p-2 rounded-md">
            <base-icon
              :name="value.icon || 'Activity'"
              :size="20"
              :stroke-width="2"
              :default-class="'text-primary'"
            />
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-base font"> {{ value.title }}</span>
            <div class="flex flex-row items-center">
              <base-icon
                name="Clock"
                :size="12"
                :stroke-width="2"
                :default-class="'text-secondary inline-block mr-1.5'"
              />
              <span class="text-secondary text-sm">
                {{ value.time }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div
        class="flex flex-col gap-6 quick-actions bg-white rounded-xl p-6 border border-border"
      >
        <span class="text-base text-black font-normal block mb-2">
          Quick Actions
        </span>
        <div class="flex flex-col gap-3">
          <div
            class="flex flex-row gap-2 border text-sm border-border p-2 px-3 rounded-md items-center cursor-pointer hover:bg-primary hover:text-white transition-colors group"
            v-for="(item, index) in quickActions"
            :key="`${item.title}-${index}`"
          >
            <router-link
              :to="item.path"
              class="flex flex-row gap-2 items-center w-full"
            >
              <base-icon
                :name="item.icon || 'Database'"
                :size="15"
                :stroke-width="2"
                default-class="text-black group-hover:text-white"
              />
              <span>{{ item.title }}</span>
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { baseCard, baseIcon } from "@/core/components/base/index";
import { PageDescription } from "@/core/components/others/index";
import { DATASET_ROUTES } from "@/module/dataset/router/route.constant";
import { onMounted, reactive, ref } from "vue";
import type { ActivityItem, QuickAction } from "./dashboard.type";
import {
  getDashboardData,
  getDashboardActivities,
} from "@/module/dashboard/service/dashboard.service";

const cardsInfo = reactive<Record<string, any>>({
  dataset: {
    title: "Total Datasets",
    value: 0,
    icon: "Database",
    color: "text-primary",
    date: "This month",
  },
  products: {
    title: "Total Products",
    value: 0,
    icon: "Package",
    color: "text-blue-600",
    date: "This month",
  },
  completeJobs: {
    title: "Completed Jobs",
    value: 0,
    icon: "CircleCheckBig",
    color: "text-green-600",
    date: "This month",
  },
});

const updateCardsInfo = async () => {
  const data = await getDashboardData();

  if (!data) return;

  cardsInfo.dataset.value = data.total_datasets || 0;
  cardsInfo.products.value = data.total_products || 0;
  cardsInfo.completeJobs.value = data.total_completed_jobs || 0;
};

const activityItems = ref<ActivityItem[]>([]);

const getActivityIcon = (type: string): string => {
  const iconMap: Record<string, string> = {
    dataset_upload: "Upload",
    job_started: "Play",
    dataset_delete: "Trash2",
    job_completed: "CircleCheckBig",
    job_failed: "CircleX",
    user_registered: "UserPlus",
    product_created: "Package",
  };
  return iconMap[type] || "Activity";
};

const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffInMs = now.getTime() - date.getTime();
  const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
  const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
  const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));

  if (diffInMinutes < 1) return "Just now";
  if (diffInMinutes < 60)
    return `${diffInMinutes} minute${diffInMinutes > 1 ? "s" : ""} ago`;
  if (diffInHours < 24)
    return `${diffInHours} hour${diffInHours > 1 ? "s" : ""} ago`;
  if (diffInDays < 30)
    return `${diffInDays} day${diffInDays > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
};

const updateActivities = async () => {
  const response = await getDashboardActivities();

  if (!response?.activities) return;

  activityItems.value = response.activities.map((activity: any) => ({
    title: activity.description || `${activity.type.replace(/_/g, " ")}`,
    time: formatRelativeTime(activity.date),
    icon: getActivityIcon(activity.type),
  }));
};

onMounted(async () => {
  await Promise.all([updateCardsInfo(), updateActivities()]);
});

const quickActions: Array<QuickAction> = [
  {
    title: "Upload Dataset",
    icon: "Upload",
    path: DATASET_ROUTES.datasetList,
  },
  // {
  //   title: "Start Job",
  //   icon: "Play",
  //   path: "#",
  // },
  // {
  //   title: "View Products",
  //   icon: "CircleCheckBig",
  //   path: "#",
  // },
  // {
  //   title: "System Config",
  //   icon: "Server",
  //   path: "#",
  // },
];
</script>

<style scoped>
/* width */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

/* track */
::-webkit-scrollbar-track {
  background: #fff;
}

/* thumb */
::-webkit-scrollbar-thumb {
  background-color: #c8cbcf;
  border-radius: 6px;
}

/* hover */
::-webkit-scrollbar-thumb:hover {
  background-color: #778495;
}
</style>
