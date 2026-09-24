<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="transform translate-x-full opacity-0"
    enter-to-class="transform translate-x-0 opacity-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="transform translate-x-0 opacity-100"
    leave-to-class="transform translate-x-full opacity-0"
  >
    <div
      :class="[
        'border border-solid rounded-xl p-5 flex items-start gap-4 relative min-w-80 max-w-96',
        toastTypeClasses[toast.type].background,
        toastTypeClasses[toast.type].border,
      ]"
    >
      <!-- Icon -->
      <div class="w-6 h-6 shrink-0 relative">
        <baseIcon
          :name="toastTypeClasses[toast.type].icon"
          :size="24"
          color="white"
          :stroke-width="2"
        />
      </div>

      <!-- Message Content -->
      <div class="flex flex-col gap-1 flex-1">
        <h4
          class="font-sans font-semibold text-sm leading-normal text-white capitalize"
        >
          {{ toast.title }}
        </h4>
        <p class="font-sans text-xs leading-relaxed text-white">
          {{ toast.message }}
        </p>
      </div>

      <!-- Action Button -->
      <div v-if="toast.action" class="flex items-center justify-center">
        <button
          @click="toast.action.handler"
          class="bg-black bg-opacity-15 border border-white border-opacity-60 rounded-md px-3 py-2.5 text-xs text-white font-sans leading-none hover:bg-opacity-25 transition-colors"
        >
          {{ toast.action.label }}
        </button>
      </div>

      <!-- Close Button -->
      <button
        v-if="toast.closable !== false"
        @click="handleClose"
        class="p-1 hover:bg-white hover:bg-opacity-10 rounded transition-colors shrink-0"
      >
        <baseIcon name="X" :size="10" color="white" :stroke-width="2" />
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { baseIcon } from "../index";
import type { ToastEmits, ToastProps, ToastType } from "./toast.type";

const props = defineProps<ToastProps>();
const emit = defineEmits<ToastEmits>();

const toastTypeClasses: Record<
  ToastType,
  { background: string; border: string; icon: any }
> = {
  success: {
    background: "bg-green-500",
    border: "border-green-400",
    icon: "Check",
  },
  error: {
    background: "bg-red-500",
    border: "border-red-400",
    icon: "X",
  },
  warning: {
    background: "bg-yellow-500",
    border: "border-yellow-400",
    icon: "AlertTriangle",
  },
  info: {
    background: "bg-blue-500",
    border: "border-blue-400",
    icon: "Info",
  },
};

const handleClose = () => {
  emit("close", props.toast.id);
};
</script>
