<template>
  <div>
    <div class="flex flex-row justify-between mb-24">
      <page-description />
      <base-button variant="primary" class="mb-6" @click="openUploadDialog">
        <div class="flex flex-row justify-between">
          <base-icon
            name="Upload"
            :size="16"
            :stroke-width="2"
            class="inline mr-2"
          />
          <span>Upload Dataset</span>
        </div>
      </base-button>
    </div>

    <div class="mt-16">
      <base-table
        :headers="DataSetTableHeaders"
        :data="dataTableValue"
        :dataRowCount="tableProps.dataRowCount"
        @change="fetchDataSets"
        :loading="tableProps.loading"
      >
        <template #cell-actions="{ row }">
          <div class="flex flex-row gap-1.5 justify-end">
            <div
              v-if="row.status === 'FAILED'"
              title="Retry Upload"
              class="cursor-pointer border border-yellow-300 p-1.5 px-2.5 rounded-md hover:bg-yellow-50 transition-colors"
              @click="openRetryDialog(row.id)"
            >
              <base-icon name="RotateCcw" :size="18" :stroke-width="2" class="text-yellow-600" />
            </div>
            <div
              title="Start Processing"
              class="cursor-pointer border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors"
              @click="configurationDataSet(row.name, row.id)"
            >
              <base-icon name="Play" :size="18" :stroke-width="2" />
            </div>
            <div
              title="Download"
              class="cursor-pointer border border-border p-1.5 px-2.5 rounded-md hover:bg-neutral-100 transition-colors"
              @click="onDownloadDataset(row.id)"
            >
              <base-icon name="Download" :size="18" :stroke-width="2" />
            </div>
            <div
              title="Delete"
              class="cursor-pointer border border-red-200 p-1.5 px-2.5 rounded-md hover:bg-red-50 transition-colors"
              @click="openDeleteDialog(row.id, row.name)"
            >
              <base-icon name="Trash" :size="18" :stroke-width="2" class="text-red-600" />
            </div>
          </div>
        </template>
        <template #cell-status="{ value, row }">
          <div class="flex flex-col gap-1">
            <base-badge
              class="text-xs cursor-default"
              :class="badgeColor(value as string)"
              :title="value === 'FAILED' && row.error_message ? row.error_message : ''"
            >
              {{ value }}
            </base-badge>
            <span
              v-if="value === 'FAILED' && row.error_message"
              class="text-xs text-red-600 max-w-[260px] truncate"
              :title="row.error_message"
            >
              {{ row.error_message }}
            </span>
          </div>
        </template>

        <template #cell-total_files="{ value }">
          <div class="flex flex-row gap-1.5 items-center">
            <base-icon name="Image" :size="15" :stroke-width="2" class="text-neutral-500" />
            <span>{{ value }}</span>
          </div>
        </template>

        <template #cell-created_at="{ value }">
          <div class="flex flex-row gap-1.5 items-center">
            <base-icon
              name="Calendar"
              :size="15"
              :stroke-width="2"
              class="inline"
            />
            <span v-format-date="value"></span>
          </div>
        </template>

        <template #cell-total_size="{ value }">
          <span>
           {{ value ? (Number(value) / (1024 * 1024)).toFixed(2) + ' MB' : '—' }}
          </span>
        </template>
      </base-table>
    </div>
  </div>

  <base-dialog
    v-model="showUploadDatasetDialog"
    :title="dialogHeader.title"
    :sub-title="dialogHeader.subTitle"
    @close="closeDialog"
  >
    <template #body>
      <Switch
        :switch-items="dialogSwitchContent"
        @change-item="switchContent"
      />
      <amazon-section
        v-if="dialogSwitchContent['amazon']?.isActive"
        v-model="amazonLink"
        v-model:data-set-name="amazonDataSetName"
      />
      <upload-zip-file
        v-if="dialogSwitchContent['zip']?.isActive"
        v-model:fileName="collectDataSet.dataSetName"
        v-model:collectedFile="collectDataSet.files"
      />
      <div class="mt-2.5" v-if="dialogSwitchContent['zip']?.isActive">
        <base-progress-bar :progress="uploadProgress" variant="success" />
      </div>
    </template>
    <template #footer>
      <base-button
        v-if="dialogSwitchContent['zip']?.isActive"
        variant="primary"
        class="mt-12"
        block
        :disabled="disabledUploadBtn"
        @click="uploadDataFile"
        :loading="uploadLoading"
        size="md"
      >
        <span>Upload Dataset</span>
      </base-button>

      <base-button
        v-else
        variant="primary"
        class="mt-12"
        block
        :disabled="amazonLink.length === 0 || amazonDataSetName.trim().length === 0"
        @click="uploadS3Link"
        :loading="uploadLoading"
        size="md"
      >
        <span>Import From S3</span>
      </base-button>
    </template>
  </base-dialog>

  <processing-configuration v-model="showProcessDialog" />

  <confirm-dialog
    v-model="showDeleteDatasetDialog"
    title="Delete Dataset"
    message="Are you sure you want to delete this dataset? This action cannot be undone."
    confirm-text="Delete"
    cancel-text="Cancel"
    @confirm="onDeleteDataset"
    @cancel="showDeleteDatasetDialog.show = false"
  />

  <base-dialog v-model="showRetryDialog" title="Retry S3 Import">
    <template #body>
      <p class="text-sm text-neutral-600 mb-4">
        The previous import for this dataset failed. Provide a new S3 URL to retry.
      </p>
      <base-input v-model="retryLink" label="Amazon S3 Link:" placeholder="Enter S3 URL" />
    </template>
    <template #footer>
      <base-button variant="ghost" @click="showRetryDialog = false">Cancel</base-button>
      <base-button
        variant="primary"
        :disabled="retryLink.length === 0"
        :loading="uploadLoading"
        @click="retryUpload"
      >
        Retry Import
      </base-button>
    </template>
  </base-dialog>
</template>

<script setup lang="ts">
import {
  baseBadge,
  baseButton,
  baseDialog,
  baseIcon,
  baseInput,
  baseProgressBar,
  baseTable,
} from "@/core/components/base/index";
import { PageDescription, Switch } from "@/core/components/others/index";
import amazonSection from "@/module/dataset/components/amazon-section.vue";
import ProcessingConfiguration from "@/module/dataset/components/processing-configuration/processing-configuration.vue";
import uploadZipFile from "@/module/dataset/components/upload-zip-file.vue";
import {
  getDataSet,
  uploadAmazonS3Link,
  uploadDataSet,
  uploadDataSetInBucket,
  downloadDataset,
  deleteDataset,
} from "@module/dataset/service/data-set.service";
import { computed, onMounted, reactive, ref } from "vue";
// import { useDatasetSocket } from "../../composable/useDatasetSocket";
import { DataSetTableHeaders } from "./data-set.constant";
import type {
  DataSetItem,
  InitFileResponse,
  UploadDataSet,
} from "./data-set.type";
import ConfirmDialog from "@/core/components/others/confirm-dialog/confirm-dialog.vue";
import { toastService } from "@/core/services/toast.service";

const collectDataSet = ref({
  files: [] as File[],
  dataSetName: "",
});

const uploadLoading = ref<boolean>(false);
const uploadProgress = ref<number>(0);
const dataTableValue = ref<Array<DataSetItem>>([]);

const tableProps = reactive<{
  loading: boolean;
  dataRowCount: number;
}>({
  loading: false,
  dataRowCount: 0,
});
const dialogHeader = {
  title: "Upload Dataset",
  subTitle: "Upload drone imagery as a ZIP file or import from Amazon S3",
};
const showUploadDatasetDialog = ref<boolean>(false);
const amazonLink = ref<string>("");
const amazonDataSetName = ref<string>("");
const dialogSwitchContent = ref<UploadDataSet>({
  zip: { name: "ZIP File", icon: "FileArchive", isActive: true },
  amazon: { name: "Amazon S3", icon: "Link2", isActive: false },
});

const switchContent = (key: string) => {
  Object.keys(dialogSwitchContent.value).forEach((itemKey) => {
    dialogSwitchContent.value[itemKey]!.isActive = itemKey === key;
  });
};

const disabledUploadBtn = computed(() => {
  return (
    collectDataSet.value.files.length === 0 ||
    collectDataSet.value.dataSetName.trim() === ""
  );
});

const openUploadDialog = () => {
  showUploadDatasetDialog.value = !showUploadDatasetDialog.value;
};

const uploadDataFile = async () => {
  try {
    for (const file of collectDataSet.value.files) {
      const uploadPayload = {
        dataset_name: collectDataSet.value.dataSetName,
        file_name: file.name,
        file_size: file.size,
      };
      const data = await uploadDataSet(uploadPayload);
      await uploadFiledInBucket(data, file);
    }
  } catch (error) {
    console.error("Error uploading dataset:", error);
  } finally {
    closeDialog();
  }
};

const uploadS3Link = async () => {
  try {
    await uploadAmazonS3Link(amazonLink.value, amazonDataSetName.value);
  } catch (error) {
    console.error("Error uploading dataset from S3:", error);
  } finally {
    closeDialog();
  }
};

// const startProcessing = async () => {
//   try {
//     const body = {
//       ...processingModel,
//     };

//     await startDataSetProcess(body);
//   } catch (error) {
//     console.error("Error starting dataset processing:", error);
//   } finally {
//     processingModel.dataset_id = 0;
//     processingModel.radiometric_calibration = false;
//     processingModel.resolution_gsd = 0;
//   }
// };

const fetchDataSets = async (page: number, pageSize: number) => {
  dataTableValue.value = [];
  try {
    tableProps.loading = true;

    const dataSets = await getDataSet(page, pageSize);

    tableProps.dataRowCount = dataSets.count;

    dataTableValue.value = [...dataSets.results];
  } catch (error) {
    console.error("Error fetching datasets:", error);
  } finally {
    tableProps.loading = false;
  }
};

const uploadFiledInBucket = async (data: InitFileResponse, file: File) => {
  try {
    uploadLoading.value = true;
    await uploadDataSetInBucket(data, file, progressBarHandler).finally(() => {
      uploadLoading.value = false;
    });
    closeDialog();

    dataTableValue.value = [];

    await fetchDataSets(1, 10);
  } catch (error) {
    console.error("Error uploading dataset to S3 bucket:", error);
    uploadLoading.value = false;
    closeDialog();
  }
};

const closeDialog = () => {
  collectDataSet.value.files = [];
  collectDataSet.value.dataSetName = "";
  amazonLink.value = "";
  amazonDataSetName.value = "";
  uploadProgress.value = 0;
  if (dialogSwitchContent.value.amazon) {
    dialogSwitchContent.value.amazon.isActive = true;
  }

  if (dialogSwitchContent.value.zip) {
    dialogSwitchContent.value.zip.isActive = false;
  }

  uploadLoading.value = false;
  showUploadDatasetDialog.value = false;
};

const showProcessDialog = ref<{
  show: boolean;
  datasetId: string;
  fileName?: string;
}>({
  show: false,
  datasetId: "",
  fileName: "",
});

const configurationDataSet = (fileName: string, datasetId: string) => {
  showProcessDialog.value.show = true;
  showProcessDialog.value.datasetId = datasetId;
  showProcessDialog.value.fileName = fileName;
};

const showDeleteDatasetDialog = ref<{ show: boolean; item: string }>({
  show: false,
  item: "",
});

const openDeleteDialog = (datasetId: string, fileName: string) => {
  showDeleteDatasetDialog.value.show = true;
  showDeleteDatasetDialog.value.item = datasetId;
};

const onDeleteDataset = async () => {
  try {
    await deleteDataset(showDeleteDatasetDialog.value.item);
    await fetchDataSets(1, 10);
  } catch (error: any) {
    if (!error?._toastShown) {
      toastService.error("Error", "Failed to delete dataset");
    }
  } finally {
    showDeleteDatasetDialog.value.show = false;
  }
};

const showRetryDialog = ref(false);
const retryDatasetId = ref("");
const retryLink = ref("");

const openRetryDialog = (datasetId: string) => {
  retryDatasetId.value = datasetId;
  retryLink.value = "";
  showRetryDialog.value = true;
};

const retryUpload = async () => {
  try {
    uploadLoading.value = true;
    const dataset = dataTableValue.value.find((d) => d.id === retryDatasetId.value);
    const name = dataset?.name || "Retry Import";
    await uploadAmazonS3Link(retryLink.value, name, retryDatasetId.value);
    showRetryDialog.value = false;
    await fetchDataSets(1, 10);
  } catch (error: any) {
    if (!error?._toastShown) {
      toastService.error("Error", "Failed to retry import");
    }
  } finally {
    uploadLoading.value = false;
  }
};

const downloadPollingMap = ref<Record<string, boolean>>({});

const onDownloadDataset = async (datasetId: string) => {
  if (downloadPollingMap.value[datasetId]) return;
  downloadPollingMap.value[datasetId] = true;
  toastService.info("Preparing", "Starting dataset export...");

  try {
    const jobId = await downloadDataset(datasetId);
    await pollExportStatus(jobId);
  } catch (error: any) {
    if (!error?._toastShown) {
      toastService.error("Error", "Failed to start dataset export");
    }
  } finally {
    downloadPollingMap.value[datasetId] = false;
  }
};

const pollExportStatus = async (jobId: string) => {
  const { getExportJobStatus } = await import("@module/dataset/service/data-set.service");
  const maxAttempts = 60;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    try {
      const status = await getExportJobStatus(jobId);
      if (status.status === "COMPLETED" && status.download_url) {
        window.open(status.download_url, "_blank");
        toastService.success("Downloaded", "Dataset export is ready");
        return;
      } else if (status.status === "FAILED") {
        toastService.error("Error", status.error || "Dataset export failed");
        return;
      }
    } catch (err: any) {
      if (err?.response?.status === 404) {
        toastService.error("Error", "Export job not found or expired");
      } else {
        toastService.error("Error", "Failed to check export status");
      }
      return;
    }
  }
  toastService.warning("Timeout", "Export is still processing. Check back later.");
};

const badgeColor = (status: string) => {
  switch (status?.toLowerCase()) {
    case "processing":
      return "bg-yellow-100 text-yellow-800";
    case "completed":
      return "bg-green-100 text-green-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "pending":
    case "downloading":
      return "bg-blue-100 text-blue-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const progressBarHandler = (progress: number) => {
  uploadProgress.value = progress;
};

onMounted(() => {
  fetchDataSets(1, 10);
});
</script>
