<template>
  <div
    class="border-2 border-gray-300 bg-soft-white rounded-xl flex items-center justify-center hover:bg-primary-50 transition-colors p-12 relative"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
    :class="{ 'border-primary-500': isDragging }"
  >
    <input
      type="file"
      ref="fileInput"
      class="hidden"
      @change="handleFileChange"
      multiple
      accept=".zip"
    />
    <div class="flex flex-col items-center justify-center p-16 gap-2">
      <base-icon
        name="Upload"
        :size="48"
        :stroke-width="2"
        class="text-secondary-100 mb-4"
      />
      <div class="flex flex-col gap-1.5 text-center">
        <span class="text-gray-900">Drag and drop ZIP files here </span>
        <span class="text-sm text-gray-500">or click to browse files </span>
      </div>
      <base-button variant="secondary" class="mt-16" @click="openFileBrowser">
        Select ZIP Files
      </base-button>
      <div v-if="selectedFiles.length" class="mt-4 text-sm text-gray-700">
        <span>Selected File:</span>
        <ul>
          <li
            v-for="file in selectedFiles"
            :key="file.name"
            class="flex flex-row justify-between"
          >
            <span class="truncate w-40">{{ file.name }}</span>
            <base-icon
              name="X"
              :size="20"
              :stroke-width="2"
              class="cursor-pointer text-red-500 hover:text-red-700 transition-colors"
              @click="removeFile(file.name)"
            />
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { baseButton, baseIcon } from "@/core/components/base";
import { ref } from "vue";

const isDragging = ref<boolean>(false);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = defineModel<File[]>("files", { default: () => [] });

const allowTyping = ["zip"];

const openFileBrowser = () => {
  fileInput.value?.click();
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const fileTyping = target.value.split(".").pop()?.toLowerCase();
  if (target.files && allowTyping.includes(fileTyping!)) {
    const filesArray = Array.from(target.files);
    const alreadyExists = filesArray.filter((file) =>
      selectedFiles.value.some((selected) => selected.name === file.name)
    );
    if (alreadyExists.length === 0)
      selectedFiles.value = [...selectedFiles.value, ...filesArray];
  }
};

const handleDragOver = () => {
  isDragging.value = true;
};

const handleDragLeave = () => {
  isDragging.value = false;
};

const handleDrop = (event: DragEvent) => {
  isDragging.value = false;
  if (!event.dataTransfer?.files) return;

  const filesArray = Array.from(event.dataTransfer.files);

  const fileTyping = filesArray[0]?.name.split(".").pop()?.toLowerCase();
  console.log("File type based on extension:", fileTyping);

  const duplicates = filesArray.filter((file) =>
    selectedFiles.value.some((selected) => selected.name === file.name)
  );

  const newFiles = filesArray.filter((file) => !duplicates.includes(file));

  selectedFiles.value = [...selectedFiles.value, ...newFiles];
  console.log("Final files:", selectedFiles.value);
};

const removeFile = (name: string) => {
  const index = selectedFiles.value.findIndex((el) => el.name === name);
  if (index !== -1) {
    selectedFiles.value.splice(index, 1);
  }
};
</script>
