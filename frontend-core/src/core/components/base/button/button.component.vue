<template>
  <button :type="props.type" :disabled="props.disabled || props.loading"
    :class="`${buttonClasses} ${props.loading ? 'cursor-not-allowed' : props.disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`">
    <slot name="prefix" />
    <div class="flex flex-row items-center gap-3">
      <base-button-loading v-if="props.loading" />
      <slot />
    </div>
    <slot name="suffix" />
  </button>
</template>

<script setup lang="ts">
import { baseButtonLoading } from "@/core/components/base/index";
import type { ButtonProps } from "./button.type";
import { useButtonClasses } from "./useButtonClasses";

const props = withDefaults(defineProps<ButtonProps>(), {
  variant: "primary",
  size: "md",
  type: "button",
  loading: false,
  disabled: false,
  block: false,
});

const buttonClasses = useButtonClasses(props);
</script>
