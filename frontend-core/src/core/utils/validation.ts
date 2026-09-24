import type { ValidationRule } from "@core/components/base/input/input.type";

export const required = (
  message = "This field is required"
): ValidationRule => {
  const rule = (value: string) => {
    return value.trim().length > 0 || message;
  };
  rule.message = message;
  return rule;
};

export const minLength = (min: number, message?: string): ValidationRule => {
  const defaultMessage = `Minimum ${min} characters required`;
  const rule = (value: string) => {
    return value.length >= min || message || defaultMessage;
  };
  rule.message = message || defaultMessage;
  return rule;
};

export const email = (
  message = "Please enter a valid email address"
): ValidationRule => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const rule = (value: string) => {
    return emailRegex.test(value) || message;
  };
  rule.message = message;
  return rule;
};

export const matchField = (
  getOtherValue: () => string,
  message = "Fields do not match"
): ValidationRule => {
  const rule = (value: string) => {
    return value === getOtherValue() || message;
  };
  rule.message = message;
  return rule;
};

export const pattern = (
  regex: RegExp,
  message = "Invalid format"
): ValidationRule => {
  const rule = (value: string) => {
    return regex.test(value) || message;
  };
  rule.message = message;
  return rule;
};
