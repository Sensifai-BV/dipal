<template>
  <div class="progress-container w-full">
    <!-- Label and Percentage -->
    <div
      v-if="showLabel || showPercentage"
      class="flex justify-between items-center mb-2"
    >
      <span v-if="showLabel" class="text-sm font-medium text-neutral-700">
        {{ label }}
      </span>
      <span v-if="showPercentage" class="text-sm font-medium text-neutral-600">
        {{ Math.round(progress) }}%
      </span>
    </div>

    <!-- Progress Bar -->
    <div
      class="progress-track w-full rounded-full overflow-hidden"
      :class="[sizeClasses.track, trackClass]"
    >
      <div
        class="progress-bar rounded-full transition-all duration-300 ease-out"
        :class="[sizeClasses.bar, variantClasses, barClass]"
        :style="{ width: `${clampedProgress}%` }"
      />
    </div>

    <!-- Status Text -->
    <div v-if="statusText" class="mt-1.5">
      <span class="text-xs text-neutral-500">{{ statusText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ProgressBarProps } from "./progress-bar.type";

const props = withDefaults(defineProps<ProgressBarProps>(), {
  progress: 0,
  variant: "primary",
  size: "md",
  showPercentage: true,
  showLabel: false,
  label: "Progress",
  animated: true,
});

const clampedProgress = computed(() => {
  return Math.min(100, Math.max(0, props.progress));
});

const sizeClasses = computed(() => {
  const sizes = {
    sm: { track: "h-1.5 bg-neutral-200", bar: "h-1.5" },
    md: { track: "h-2.5 bg-neutral-200", bar: "h-2.5" },
    lg: { track: "h-4 bg-neutral-200", bar: "h-4" },
  };
  return sizes[props.size];
});

const variantClasses = computed(() => {
  const variants = {
    primary: "bg-primary",
    success: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
    info: "bg-blue-500",
  };

  let classes = variants[props.variant];

  if (props.animated && clampedProgress.value < 100) {
    classes += " animate-pulse";
  }

  return classes;
});
</script>
