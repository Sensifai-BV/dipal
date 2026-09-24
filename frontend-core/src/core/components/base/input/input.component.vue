<template>
  <div class="flex flex-col gap-2">
    <label
      v-if="props.label"
      class="font-sans text-sm leading-3.5 text-neutral-950"
    >
      {{ props.label }}
    </label>
    <div
      class="relative flex items-center bg-neutral-100 rounded border border-transparent focus-within:border-primary px-3 py-2"
      :class="{
        'border-red-500 focus-within:border-red-500': fieldErrors.length > 0,
      }"
    >
      <slot name="prefix"></slot>
      <input
        v-bind="$attrs"
        :value="modelValue"
        :type="props.type"
        :placeholder="props.placeholder"
        :disabled="props.disabled"
        @input="handleInput(($event.target as HTMLInputElement)?.value)"
        @blur="handleBlur"
        class="w-full bg-transparent font-sans text-sm leading-5 text-neutral-950 outline-none placeholder:text-secondary disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <slot name="suffix"></slot>
    </div>
    <span v-if="fieldErrors.length > 0" class="text-sm text-red-500 mt-1">
      {{ fieldErrors[0] }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, watch } from "vue";
import type { FormContext } from "../form/form.type";
import type { InputEmits, InputProps } from "./input.type";

const modelValue = defineModel<any>();
const emit = defineEmits<InputEmits>();

const props = withDefaults(defineProps<InputProps>(), {
  type: "text",
  placeholder: "",
  disabled: false,
  rules: () => [],
  name: "",
});

const formContext = inject<FormContext>("formContext");

const fieldErrors = computed(() => {
  if (formContext && props.name) {
    return formContext.getFieldErrors(props.name);
  }
  return [];
});

const handleInput = (value: string) => {
  modelValue.value = value;
  emit("update:modelValue", value);

  if (formContext && props.name) {
    formContext.updateField(props.name, value);
  }

  const isValid = fieldErrors.value.length === 0;
  emit("validation", isValid, fieldErrors.value);
};

const handleBlur = () => {
  if (formContext && props.name) {
    formContext.validateField(props.name);
  }
};

onMounted(() => {
  if (formContext && props.name) {
    formContext.registerField(props.name, modelValue.value || "", props.rules);
  }
});

watch(
  () => modelValue.value,
  (newValue) => {
    if (formContext && props.name && newValue !== undefined) {
      formContext.updateField(props.name, newValue);
    }
  },
  { immediate: true },
);
</script>

<style scoped>
/* Chrome, Safari, Edge, Opera */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Firefox */
input[type="number"] {
  -moz-appearance: textfield;
}
</style>
