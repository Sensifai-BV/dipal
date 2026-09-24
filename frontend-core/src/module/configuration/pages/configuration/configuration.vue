<template>
  <div>
    <div class="flex flex-row justify-between mb-24">
      <page-description />
    </div>

    <!-- System Health -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
      <div
        v-for="metric in healthMetrics"
        :key="metric.label"
        class="bg-white border border-border rounded-2xl p-5 flex flex-col gap-1"
      >
        <div class="flex items-center gap-2">
          <base-icon :name="metric.icon" :size="18" :stroke-width="2" class="text-neutral-500" />
          <span class="text-sm text-neutral-500">{{ metric.label }}</span>
        </div>
        <span v-if="healthLoading" class="text-sm text-neutral-400">Loading...</span>
        <template v-else>
          <span class="text-lg font-semibold" :class="metric.color">{{ metric.value }}</span>
          <span v-if="metric.detail" class="text-xs text-neutral-400">{{ metric.detail }}</span>
        </template>
      </div>
    </div>

    <!-- Services Table -->
    <div class="bg-white border border-border rounded-2xl p-6 mb-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h3 class="text-lg font-semibold text-neutral-800">Services</h3>
          <p class="text-sm text-neutral-400 mt-1">
            Processing pipeline services and their current status.
          </p>
        </div>
        <base-badge class="text-xs bg-blue-50 text-blue-700">
          {{ activeServicesCount }} Active
        </base-badge>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border text-left text-neutral-500">
              <th class="pb-3 font-medium">Service Name</th>
              <th class="pb-3 font-medium">Description</th>
              <th class="pb-3 font-medium">Status</th>
              <th class="pb-3 font-medium">Latency</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="service in services"
              :key="service.name"
              class="border-b border-border last:border-b-0"
            >
              <td class="py-3 font-medium text-neutral-900">{{ service.name }}</td>
              <td class="py-3 text-neutral-500">{{ service.description }}</td>
              <td class="py-3">
                <base-badge
                  class="text-xs"
                  :class="service.status === 'healthy' ? 'bg-green-100 text-green-800' : service.status === 'degraded' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'"
                >
                  {{ service.status === 'healthy' ? 'Active' : service.status === 'degraded' ? 'Degraded' : 'Inactive' }}
                </base-badge>
              </td>
              <td class="py-3 text-neutral-500">
                {{ service.latency != null ? service.latency + ' ms' : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- S3 Buckets Table -->
    <div v-if="s3Buckets.length > 0" class="bg-white border border-border rounded-2xl p-6 mb-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h3 class="text-lg font-semibold text-neutral-800">S3 Buckets</h3>
          <p class="text-sm text-neutral-400 mt-1">
            AWS S3 storage buckets used for datasets, processing, and results.
          </p>
        </div>
        <base-badge
          class="text-xs"
          :class="allBucketsReachable ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'"
        >
          {{ reachableBucketsCount }}/{{ s3Buckets.length }} Reachable
        </base-badge>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border text-left text-neutral-500">
              <th class="pb-3 font-medium">Purpose</th>
              <th class="pb-3 font-medium">Bucket Name</th>
              <th class="pb-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="bucket in s3Buckets"
              :key="bucket.label"
              class="border-b border-border last:border-b-0"
            >
              <td class="py-3 font-medium text-neutral-900">{{ bucket.label }}</td>
              <td class="py-3 text-neutral-500">
                <code class="bg-neutral-50 px-2 py-0.5 rounded text-xs">{{ bucket.name }}</code>
              </td>
              <td class="py-3">
                <base-badge
                  class="text-xs"
                  :class="bucket.status === 'reachable' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'"
                >
                  {{ bucket.status === 'reachable' ? 'Reachable' : 'Unreachable' }}
                </base-badge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Webhooks Section -->
    <div class="bg-white border border-border rounded-2xl p-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h3 class="text-lg font-semibold text-neutral-800">Webhooks</h3>
          <p class="text-sm text-neutral-400 mt-1">
            Receive notifications when events occur in your pipeline.
          </p>
        </div>
        <base-button variant="primary" size="sm" @click="openCreateDialog">
          <base-icon name="Plus" :size="16" :stroke-width="2" class="mr-1.5" />
          Add Webhook
        </base-button>
      </div>

      <div v-if="loading" class="flex justify-center py-8">
        <span class="w-10 h-10 rounded-full border-4 border-white border-b-primary-200 inline-block animate-spin" />
      </div>

      <div v-else-if="webhooks.length === 0" class="text-center text-neutral-400 py-8">
        No webhooks configured yet.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border text-left text-neutral-500">
              <th class="pb-3 font-medium">URL</th>
              <th class="pb-3 font-medium">Events</th>
              <th class="pb-3 font-medium">Status</th>
              <th class="pb-3 font-medium">Created</th>
              <th class="pb-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="webhook in webhooks"
              :key="webhook.id"
              class="border-b border-border last:border-b-0"
            >
              <td class="py-3 font-medium text-neutral-900">
                <div class="flex items-center gap-2">
                  <base-icon name="Globe" :size="16" :stroke-width="2" class="text-neutral-400 shrink-0" />
                  <span class="truncate max-w-xs">{{ webhook.url }}</span>
                </div>
              </td>
              <td class="py-3">
                <div class="flex flex-wrap gap-1.5">
                  <base-badge
                    v-for="event in webhook.events"
                    :key="event"
                    class="text-xs bg-blue-50 text-blue-700"
                  >
                    {{ eventLabel(event) }}
                  </base-badge>
                </div>
              </td>
              <td class="py-3">
                <base-badge
                  class="text-xs"
                  :class="webhook.active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'"
                >
                  {{ webhook.active ? "Active" : "Inactive" }}
                </base-badge>
              </td>
              <td class="py-3 text-neutral-500">
                <div class="flex items-center gap-1.5">
                  <base-icon name="Calendar" :size="14" :stroke-width="2" class="text-neutral-400" />
                  <span v-format-date:datetime="webhook.created_at"></span>
                </div>
              </td>
              <td class="py-3 text-right">
                <div class="flex justify-end gap-1.5">
                  <div
                    class="border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors cursor-pointer"
                    title="Edit"
                    @click="openEditDialog(webhook)"
                  >
                    <base-icon name="Pencil" :size="16" :stroke-width="2" />
                  </div>
                  <div
                    class="border border-red-200 p-1.5 px-2.5 rounded-md hover:bg-red-50 transition-colors cursor-pointer"
                    title="Delete"
                    @click="openDeleteWebhookDialog(webhook.id)"
                  >
                    <base-icon name="Trash" :size="16" :stroke-width="2" class="text-red-600" />
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create/Edit Webhook Dialog -->
    <base-dialog v-model="showWebhookDialog" :title="isEditing ? 'Edit Webhook' : 'Create Webhook'">
      <template #body>
        <div class="flex flex-col gap-4">
          <base-input
            v-model="webhookForm.url"
            label="Webhook URL"
            placeholder="https://your-server.com/webhook"
            name="url"
          />

          <div class="flex flex-col gap-2">
            <span class="text-sm font-medium text-neutral-800">Events</span>
            <label
              v-for="event in availableEvents"
              :key="event.value"
              class="inline-flex items-center gap-3 text-sm"
            >
              <input
                type="checkbox"
                :value="event.value"
                v-model="webhookForm.events"
              />
              <span>{{ event.label }}</span>
            </label>
          </div>

          <div v-if="isEditing" class="flex items-center gap-3">
            <span class="text-sm font-medium text-neutral-800">Active</span>
            <input type="checkbox" v-model="webhookForm.active" />
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <base-button variant="ghost" @click="showWebhookDialog = false">Cancel</base-button>
          <base-button
            variant="primary"
            :disabled="!webhookForm.url || webhookForm.events.length === 0"
            :loading="saving"
            @click="saveWebhook"
          >
            {{ isEditing ? "Update" : "Create" }}
          </base-button>
        </div>
      </template>
    </base-dialog>

    <!-- Delete Confirmation -->
    <confirm-dialog
      v-model="showDeleteWebhookConfirm"
      title="Delete Webhook"
      message="Are you sure you want to delete this webhook? This action cannot be undone."
      confirm-text="Delete"
      cancel-text="Cancel"
      @confirm="onDeleteWebhook"
      @cancel="showDeleteWebhookConfirm.show = false"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { baseIcon, baseButton, baseDialog, baseInput, baseBadge } from "@/core/components/base/index";
import { PageDescription } from "@/core/components/others/index";
import ConfirmDialog from "@/core/components/others/confirm-dialog/confirm-dialog.vue";
import { toastService } from "@/core/services/toast.service";
import {
  getWebhookList,
  createWebhook,
  updateWebhook,
  deleteWebhook,
  getSystemHealth,
} from "../../service/configuration.service";
import { AVAILABLE_WEBHOOK_EVENTS } from "../../service/configuration.type";
import type { WebhookItem } from "../../service/configuration.type";

interface ServiceItem {
  name: string;
  description: string;
  status: string;
  latency: number | null;
}

interface HealthMetric {
  label: string;
  icon: string;
  value: string;
  detail: string;
  color: string;
}

interface BucketItem {
  label: string;
  name: string;
  status: string;
}

const healthLoading = ref(false);
const healthData = ref<any>(null);

const services = ref<ServiceItem[]>([
  { name: "Database", description: "PostgreSQL primary storage", status: "unknown", latency: null },
  { name: "Redis", description: "Message broker and caching", status: "unknown", latency: null },
  { name: "Celery Workers", description: "Background task processing", status: "unknown", latency: null },
]);

const activeServicesCount = computed(() =>
  services.value.filter((s) => s.status === "healthy").length
);

const BUCKET_LABELS: Record<string, string> = {
  raw_images: "Raw Images",
  ai: "AI Processing",
  results: "Results",
};

const s3Buckets = computed<BucketItem[]>(() => {
  const buckets = healthData.value?.checks?.s3?.buckets ?? {};
  return Object.entries(buckets).map(([key, val]: [string, any]) => ({
    label: BUCKET_LABELS[key] ?? key,
    name: val.bucket ?? "—",
    status: val.status ?? "unknown",
  }));
});

const reachableBucketsCount = computed(() =>
  s3Buckets.value.filter((b) => b.status === "reachable").length
);

const allBucketsReachable = computed(() =>
  s3Buckets.value.length > 0 && s3Buckets.value.every((b) => b.status === "reachable")
);

const healthMetrics = computed<HealthMetric[]>(() => {
  const checks = healthData.value?.checks ?? {};
  const overall = healthData.value?.status ?? "unknown";
  const uptime = healthData.value?.uptime_seconds ?? 0;

  const uptimeHours = Math.floor(uptime / 3600);
  const uptimeMinutes = Math.floor((uptime % 3600) / 60);

  const dbLatency = checks.database?.latency_ms;
  const redisMemory = checks.redis?.memory_usage_percent;

  return [
    {
      label: "Overall Status",
      icon: "Activity",
      value: overall === "healthy" ? "Healthy" : overall === "degraded" ? "Degraded" : "Unhealthy",
      detail: `Uptime: ${uptimeHours}h ${uptimeMinutes}m`,
      color: overall === "healthy" ? "text-green-700" : overall === "degraded" ? "text-yellow-700" : "text-red-700",
    },
    {
      label: "Database",
      icon: "Database",
      value: dbLatency != null ? `${dbLatency} ms` : "—",
      detail: checks.database?.status === "healthy" ? "Connected" : "Disconnected",
      color: checks.database?.status === "healthy" ? "text-green-700" : "text-red-700",
    },
    {
      label: "Redis Memory",
      icon: "HardDrive",
      value: redisMemory != null ? `${redisMemory}%` : "—",
      detail: checks.redis?.status === "healthy" ? "Connected" : "Disconnected",
      color: checks.redis?.status === "healthy" ? "text-green-700" : "text-red-700",
    },
    {
      label: "Celery Workers",
      icon: "Cpu",
      value: checks.celery?.worker_count != null ? `${checks.celery.worker_count} workers` : "—",
      detail: checks.celery?.latency_ms != null ? `${checks.celery.latency_ms} ms latency` : "",
      color: checks.celery?.status === "healthy" ? "text-green-700" : "text-red-700",
    },
    {
      label: "S3 Storage",
      icon: "Cloud",
      value: checks.s3?.status === "healthy" ? "Connected" : checks.s3?.status === "unhealthy" ? "Unreachable" : "—",
      detail: checks.s3?.session_latency_ms != null ? `${checks.s3.session_latency_ms} ms session` : "",
      color: checks.s3?.status === "healthy" ? "text-green-700" : "text-red-700",
    },
  ];
});

const fetchHealth = async () => {
  healthLoading.value = true;
  try {
    const data = await getSystemHealth();
    healthData.value = data;

    const checks = data.checks ?? {};

    services.value = [
      {
        name: "Database",
        description: "PostgreSQL primary storage",
        status: checks.database?.status ?? "unknown",
        latency: checks.database?.latency_ms ?? null,
      },
      {
        name: "Redis",
        description: "Message broker and caching",
        status: checks.redis?.status ?? "unknown",
        latency: checks.redis?.latency_ms ?? null,
      },
      {
        name: "Celery Workers",
        description: "Background task processing",
        status: checks.celery?.status ?? "unknown",
        latency: checks.celery?.latency_ms ?? null,
      },
      {
        name: "S3 Storage",
        description: "AWS S3 object storage",
        status: checks.s3?.status ?? "unknown",
        latency: checks.s3?.session_latency_ms ?? null,
      },
    ];
  } catch (error) {
    console.error("Error fetching health:", error);
  } finally {
    healthLoading.value = false;
  }
};

const loading = ref(false);
const saving = ref(false);
const webhooks = ref<WebhookItem[]>([]);

const availableEvents = AVAILABLE_WEBHOOK_EVENTS;

const eventLabel = (value: string) => {
  return availableEvents.find((e) => e.value === value)?.label ?? value;
};

const fetchWebhooks = async () => {
  loading.value = true;
  try {
    const data = await getWebhookList();
    webhooks.value = Array.isArray(data) ? data : data.results ?? [];
  } catch (error) {
    console.error("Error fetching webhooks:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchHealth();
  fetchWebhooks();
});

const showWebhookDialog = ref(false);
const isEditing = ref(false);
const editingId = ref<string | null>(null);

const webhookForm = ref({
  url: "",
  events: [] as string[],
  active: true,
});

const openCreateDialog = () => {
  isEditing.value = false;
  editingId.value = null;
  webhookForm.value = { url: "", events: [], active: true };
  showWebhookDialog.value = true;
};

const openEditDialog = (webhook: WebhookItem) => {
  isEditing.value = true;
  editingId.value = webhook.id;
  webhookForm.value = {
    url: webhook.url,
    events: [...webhook.events],
    active: webhook.active,
  };
  showWebhookDialog.value = true;
};

const saveWebhook = async () => {
  saving.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateWebhook(editingId.value, {
        url: webhookForm.value.url,
        events: webhookForm.value.events,
        active: webhookForm.value.active,
      });
    } else {
      await createWebhook({
        url: webhookForm.value.url,
        events: webhookForm.value.events,
      });
    }
    showWebhookDialog.value = false;
    await fetchWebhooks();
  } catch (error: any) {
    if (!error?._toastShown) {
      toastService.error("Error", "Failed to save webhook");
    }
  } finally {
    saving.value = false;
  }
};

const showDeleteWebhookConfirm = ref<{ show: boolean; item: string }>({
  show: false,
  item: "",
});

const openDeleteWebhookDialog = (id: string) => {
  showDeleteWebhookConfirm.value = { show: true, item: id };
};

const onDeleteWebhook = async () => {
  try {
    await deleteWebhook(showDeleteWebhookConfirm.value.item);
    await fetchWebhooks();
  } catch (error: any) {
    if (!error?._toastShown) {
      toastService.error("Error", "Failed to delete webhook");
    }
  } finally {
    showDeleteWebhookConfirm.value.show = false;
  }
};
</script>
