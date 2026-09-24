<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-3">
      <ToastComponent
        v-for="toast in toasts"
        :key="toast.id"
        :toast="toast"
        @close="removeToast"
      />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { inject } from "vue";
import ToastComponent from "./toast.component.vue";
import type { Toast } from "./toast.type";

const toasts = inject<Toast[]>("toasts", []);
const removeToast = inject<(id: string) => void>("removeToast", () => {});
</script>
