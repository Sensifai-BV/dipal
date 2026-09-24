<template>
  <base-dialog
    :model-value="modelValue.show"
     :title="title"   
    :sub-title="subTitle"
  >
    <!-- Body -->
    <template #body>
      <p class="text-sm text-gray-700">
        {{ message }}
      </p>
    </template>

    <!-- Footer -->
    <template #footer>
      <div class="flex justify-end gap-2">
        <base-button
          variant="ghost"
          @click="onCancel"
        >
          {{ cancelText }}
        </base-button>

        <base-button
          variant="primary"
          @click="onConfirm(modelValue?.item)"
        >
          {{ confirmText }}
        </base-button>
      </div>
    </template>
  </base-dialog>
</template>

<script setup lang="ts">
    import {
  baseButton,
 baseDialog
} from "@/core/components/base/index";

const modelValue =defineModel<{show: boolean , item:any}>()

defineProps<{
  title: string
  subTitle?: string
  message: string
  confirmText?: string
  cancelText?: string
}>()

const emit = defineEmits<{
   (e: 'confirm' , item: any): void
  (e: 'cancel'): void
}>()

const onConfirm = (item:any) => {
   
  emit('confirm' , item)
 }

const onCancel = () => {
   emit('cancel')
 }
</script>
