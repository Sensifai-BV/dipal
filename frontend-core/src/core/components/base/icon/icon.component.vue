<script lang="ts" setup>
import * as icons from "lucide-vue-next";
import { computed } from "vue";
import type { IconProps } from "./icon.type";

const props = defineProps<IconProps>();

const icon = computed(() => icons[props.name]);
</script>

<template>
  <component
    :is="icon"
    :size="props.size"
    :color="props.color"
    :stroke-width="props.strokeWidth"
    :class="props.defaultClass"
  />
</template>
