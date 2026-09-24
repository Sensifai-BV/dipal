<template>
  <div class="flex flex-col gap-1">
    <label
      v-if="props.label"
      class="font-sans text-sm leading-[14px] text-neutral-950"
    >
      {{ props.label }}
    </label>
    <div class="relative" ref="dropdownRef">
      <div
        @click="toggleDropdown"
        class="w-full bg-neutral-100 border rounded px-3 py-2 font-sans text-sm cursor-pointer flex items-center justify-between transition-colors"
        :class="[
          isOpen ? 'border-primary' : 'border-transparent',
          fieldErrors.length ? 'border-red-500' : '',
          props.disabled
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:border-primary/50',
        ]"
      >
        <span :class="selectedOption ? 'text-neutral-950' : 'text-secondary'">
          {{ selectedOption?.text || props.placeholder || "Select an option" }}
        </span>
        <base-icon
          name="ChevronDown"
          :size="16"
          color="#6A7282"
          :stroke-width="2"
          :default-class="`transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`"
        />
      </div>

      <Transition
        enter-active-class="transition ease-out duration-100"
        enter-from-class="transform opacity-0 scale-95"
        enter-to-class="transform opacity-100 scale-100"
        leave-active-class="transition ease-in duration-75"
        leave-from-class="transform opacity-100 scale-100"
        leave-to-class="transform opacity-0 scale-95"
      >
        <div
          v-if="isOpen"
          class="absolute z-50 w-full mt-1 bg-white border border-border-light rounded-md shadow-lg max-h-60 overflow-auto"
        >
          <div
            v-for="option in props.options"
            :key="option.value"
            @click="selectOption(option)"
            class="px-3 py-2 font-sans text-sm cursor-pointer transition-colors"
            :class="[
              modelValue === option.value
                ? 'bg-blue-50 text-primary'
                : 'text-neutral-950 hover:bg-neutral-100',
            ]"
          >
            {{ option.text }}
          </div>
        </div>
      </Transition>
    </div>
    <span v-if="fieldErrors" class="text-sm text-red-500 mt-1">
      {{ fieldErrors[0] }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { baseIcon, type FormContext } from "@core/components/base/index";
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import type { DropDownProps } from "./drop-down.type";

const modelValue = defineModel<string>();
const formContext = inject<FormContext>("formContext");

const props = withDefaults(defineProps<DropDownProps>(), {
  placeholder: "Select an option",
  disabled: false,
});

const fieldErrors = computed(() => {
  if (formContext && props.name) {
    return formContext.getFieldErrors(props.name);
  }
  return [];
});

const isOpen = ref<boolean>(false);

const selectedOption = computed(() => {
  return props.options.find((option) => option.value === modelValue.value);
});

const toggleDropdown = () => {
  if (props.disabled) return;
  isOpen.value = !isOpen.value;
};

const selectOption = (option: { value: string; text: string }) => {
  modelValue.value = option.value;
  isOpen.value = false;
  if (formContext && props.name && option.value !== undefined) {
    formContext.updateField(props.name, option.value);
  }
};

const dropdownRef = ref<HTMLElement | null>(null);

const closeDropdown = (event: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    isOpen.value = false;
  }
};

onMounted(() => {
  document.addEventListener("click", closeDropdown);
  if (formContext && props.name) {
    formContext.registerField(props.name, modelValue.value || "", props.rules);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("click", closeDropdown);
});
</script>
