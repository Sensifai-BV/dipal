<template>
          <div
        class="flex flex-row justify-baseline switchContent bg-neutral-150 p-1 gap-2 rounded-full transition-all duration-300 mb-6"
      >
        <div
          v-for="(item, index) in props.switchItems"
          :key="index"
          :class="item.isActive ? 'bg-white shadow-md' : 'bg-transparent'"
          class="flex flex-row gap-2.5 w-full p-1.5 rounded-full justify-center cursor-pointer"
          @click="switchTab(index as string)"
        >
          <base-icon
            :name="item.icon"
            :size="16"
            class="text-black"
            :stroke-width="1.5"
          />
          <span class="text-sm">{{ item.name }}</span>
        </div>
      </div>
</template>

<script setup lang="ts">
import type { SwitchEmits, SwitchProps } from './switch.type';
const props = defineProps<SwitchProps>()
const emit = defineEmits<SwitchEmits>()

const switchTab = (index: string) => {
  emit("changeItem", index);
};
</script>