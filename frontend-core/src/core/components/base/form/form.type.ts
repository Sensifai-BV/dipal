import type { ValidationRule } from "../input/input.type";

export interface FormField {
  name: string;
  value: string;
  rules?: ValidationRule[];
  errors: string[];
  isValid: boolean;
}

export interface FormProps {
  validateOnSubmit?: boolean;
  validateOnChange?: boolean;
}

export interface FormEmits {
  (e: "submit", data: Record<string, any>): void;
  (e: "validation", isValid: boolean): void;
}

export interface FormContext {
  registerField: (
    name: string,
    value: string,
    rules?: ValidationRule[]
  ) => void;
  updateField: (name: string, value: string) => void;
  validateField: (name: string) => boolean;
  validateForm: () => boolean;
  getFieldErrors: (name: string) => string[];
  isFieldValid: (name: string) => boolean;
}
