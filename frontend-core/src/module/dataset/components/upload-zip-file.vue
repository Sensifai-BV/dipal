<template>
  <div>
    <div class="flex flex-col gap-3">
      <base-input v-model:model-value="dataSetName" label="Date Set Name:" />
      <upload-dataset v-model:files="files" />
    </div>
    <div class="noticBox border border-blue-200 bg-neutral-50 rounded-md mt-16">
      <p class="text-neutral-900 text-sm p-12">
        ZIP file containing JPEG or TIFF images with EXIF metadata (GPS
        coordinates, camera parameters)
      </p>
    </div>
  </div>
</template>
<script setup lang="ts">
import { baseInput } from "@/core/components/base";
import UploadDataset from "@/module/dataset/components/upload-data-set.vue";
const dataSetName = defineModel<string>("fileName");
const files = defineModel<Array<File>>("collectedFile");
</script>
