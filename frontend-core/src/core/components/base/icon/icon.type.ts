import type { icons } from "lucide-vue-next";

export interface IconProps {
  name: keyof typeof icons;
  size: number;
  color?: string;
  strokeWidth: number;
  defaultClass?: string;
}
