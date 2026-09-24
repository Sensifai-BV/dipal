<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="model" :class="containerClass">
        <div :class="panelClass" @click.stop>
          <!-- Header -->
          <header class="flex flex-col w-full mb-16 mt-8 gap-1">
            <div class="flex justify-between items-center">
              <span class="text-base font-semibold text-neutral-800">
                {{ props.title }}
              </span>

              <base-icon
                name="X"
                :size="20"
                :stroke-width="2"
                class="cursor-pointer text-neutral-400 hover:text-neutral-600 transition-colors"
                @click="emitClose"
              />
            </div>

            <span v-if="props.subTitle" class="text-sm text-neutral-400">
              {{ props.subTitle }}
            </span>
          </header>

          <!-- Body -->

          <slot name="body" />

          <!-- Footer -->
          <footer class="my-8 mb-2.5">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { baseIcon } from "../index";
import { computed } from "vue";
import type { BaseDialogEmits, BaseDialogProps } from "./dialog.type";

const props = defineProps<BaseDialogProps>();
const emit = defineEmits<BaseDialogEmits>();
const model = defineModel<boolean>();

const containerClass = computed(() =>
  props.leftFull
    ? "fixed inset-0 z-2000 flex items-start justify-start bg-black/50 backdrop-blur-sm"
    : "fixed inset-0 z-2000 flex items-center justify-center bg-black/50 backdrop-blur-sm",
);

const panelClass = computed(() =>
  props.leftFull
    ? "bg-white dark:bg-white rounded-none shadow-2xl w-full max-w-[24rem] h-full p-5 animate-scaleIn overflow-auto flex flex-col flex-1"
    : "bg-white dark:bg-white rounded-md shadow-2xl w-[95%] max-w-[560px] p-5 animate-scaleIn",
);

function emitClose() {
  model.value = false;
  emit("close");
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Small scale animation */
@keyframes scaleIn {
  0% {
    opacity: 0;
    transform: scale(0.92);
  }

  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-scaleIn {
  animation: scaleIn 0.18s ease-out;
}
</style>
