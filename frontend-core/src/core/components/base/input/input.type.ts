export interface ValidationRule {
  (value: string): boolean | string;
  message?: string;
}

export interface InputProps {
  label?: string;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
  id?: string;
  rules?: ValidationRule[];
  name?: string;
}

export interface InputEmits {
  (e: "update:modelValue", value: string): void;
  (e: "validation", isValid: boolean, errors: string[]): void;
}
