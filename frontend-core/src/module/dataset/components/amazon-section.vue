<template>
  <div class="flex flex-col gap-3">
    <base-input v-model="dataSetName" label="Dataset Name:" placeholder="Enter dataset name" />
    <base-input v-model="modelValue" label="Amazon S3 Link:" placeholder="Enter S3 URL" />
    <span class="text-secondary text-sm">Paste the public S3 URL or pre-signed URL for your dataset</span>
  </div>

  <div class="flex flex-col gap-2 border border-gray-300 rounded-md p-3.5 mt-3 bg-soft-white">
    <span class="text-sm text-secondary-900">Example formats:</span>
    <p class="bg-white rounded-sm p-2 text-sm text-secondary">
      https://my-bucket.s3.us-east-1.amazonaws.com/dataset.zip
    </p>
    <p class="bg-white rounded-sm p-2 text-sm text-secondary">
      https://my-bucket.s3.amazonaws.com/images/survey-2024.zip
    </p>
  </div>

  <div class="border border-blue-200 bg-blue-50 rounded-md mt-3 p-3">
    <p class="text-neutral-700 text-sm">
      ZIP file containing JPEG or TIFF images with EXIF metadata (GPS
      coordinates, camera parameters)
    </p>
  </div>
</template>
<script setup lang="ts">
import { baseInput } from "@/core/components/base";

const modelValue = defineModel({
  type: String,
  default: "",
});
const dataSetName = defineModel<string>("dataSetName");
</script>
