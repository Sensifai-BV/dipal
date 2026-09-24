export interface ProgressBarProps {
  progress: number;
  variant?: "primary" | "success" | "warning" | "error" | "info";
  size?: "sm" | "md" | "lg";
  showPercentage?: boolean;
  showLabel?: boolean;
  label?: string;
  statusText?: string;
  animated?: boolean;
  trackClass?: string;
  barClass?: string;
}
