import { twMerge } from "tailwind-merge";
import type { ButtonProps, ButtonSize, ButtonVariant } from "./button.type";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-primary-100 disabled:bg-blue-600/50",
  secondary:
    "bg-white border border-border text-neutral-950 hover:border-primary disabled:bg-neutral-100",
  text: "bg-transparent text-primary hover:bg-primary/5 disabled:text-primary/50",
  ghost:
    "bg-transparent text-neutral-950 hover:bg-neutral-100 disabled:text-neutral-950/50",
};

const sizes: Record<ButtonSize, string> = {
  sm: "text-xs leading-4 px-2 py-1",
  md: "text-sm leading-5 px-3 py-2",
  lg: "text-base leading-6 px-4 py-3",
};

export const useButtonClasses = (props: ButtonProps) => {
  const variant = (props.variant ?? "primary") as ButtonVariant;
  const size = (props.size ?? "md") as ButtonSize;

  return twMerge(
    "inline-flex items-center  justify-center transition-all duration-200 font-sans rounded gap-2 relative p-3  ",
    variants[variant],
    sizes[size],
    props.block ? "w-full" : "w-auto",
    // !props.disabled || !props.loading ? "cursor-not-allowed" : "cursor-pointer",
    props.loading && "cursor-not-allowed"
  );
};

export const getSpinnerClasses = (size: ButtonSize) => {
  return twMerge(
    "animate-spin",
    {
      sm: "w-3 h-3",
      md: "w-4 h-4",
      lg: "w-5 h-5",
    }[size]
  );
};
