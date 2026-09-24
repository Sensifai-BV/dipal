<template>
  <form @submit.prevent="handleSubmit">
    <slot />
  </form>
</template>

<script setup lang="ts">
import { provide, reactive, ref } from "vue";
import type { ValidationRule } from "../input/input.type";
import type { FormContext, FormEmits, FormField, FormProps } from "./form.type";

const props = withDefaults(defineProps<FormProps>(), {
  validateOnSubmit: true,
  validateOnChange: true,
});

const emit = defineEmits<FormEmits>();

const fields = reactive<Record<string, FormField>>({});
const isFormValid = ref(false);

const validateField = (name: string): boolean => {
  const field = fields[name];
  if (!field || !field.rules || field.rules.length === 0) {
    if (field) {
      field.isValid = true;
      field.errors = [];
    }
    return true;
  }

  const errors: string[] = [];
  let isValid = true;

  for (const rule of field.rules) {
    const result = rule(field.value);
    if (result !== true) {
      isValid = false;
      const errorMessage =
        typeof result === "string" ? result : rule.message || "Invalid value";
      errors.push(errorMessage);
    }
  }

  field.errors = errors;
  field.isValid = isValid;

  // Update overall form validity
  updateFormValidity();

  return isValid;
};

const updateFormValidity = () => {
  const allValid = Object.values(fields).every((field) => field.isValid);
  isFormValid.value = allValid;
  emit("validation", allValid);
};

const validateForm = (): boolean => {
  let allValid = true;

  for (const name in fields) {
    const fieldValid = validateField(name);
    if (!fieldValid) {
      allValid = false;
    }
  }

  return allValid;
};

const registerField = (
  name: string,
  value: string,
  rules?: ValidationRule[]
) => {
  fields[name] = {
    name,
    value,
    rules: rules || [],
    errors: [],
    isValid: true,
  };

  // Initial validation if field has value
  if (value && rules && rules.length > 0) {
    validateField(name);
  }
};

const updateField = (name: string, value: string) => {
  if (fields[name]) {
    fields[name].value = value;

    // Always validate on change for real-time feedback
    if (props.validateOnChange) {
      validateField(name);
    }
  }
};

const getFieldErrors = (name: string): string[] => {
  return fields[name]?.errors || [];
};

const isFieldValid = (name: string): boolean => {
  return fields[name]?.isValid ?? true;
};

const handleSubmit = () => {
  if (props.validateOnSubmit) {
    const isValid = validateForm();
    if (!isValid) {
      return;
    }
  }

  const formData: Record<string, any> = {};
  for (const name in fields) {
    formData[name] = fields[name]!.value;
  }

  emit("submit", formData);
};

// Provide form context to child components
const formContext: FormContext = {
  registerField,
  updateField,
  validateField,
  validateForm,
  getFieldErrors,
  isFieldValid,
};

provide("formContext", formContext);
</script>
