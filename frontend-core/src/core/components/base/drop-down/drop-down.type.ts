export interface DropDownOption {
  value: string;
  text: string;
}

export interface DropDownProps {
  label?: string;
  name?: string;
  options: DropDownOption[];
  placeholder?: string;
  disabled?: boolean;
  rules?: ValidationRule[];
}

export interface ValidationRule {
  (value: string): boolean | string;
  message?: string;
}
