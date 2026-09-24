import type { icons } from "lucide-vue-next";

export interface cardsInfoProps {
  title: string;
  value?: number | string;
  date?: string;
  icon?: keyof typeof icons;
  color?: string;
}

type iconType = Pick<cardsInfoProps, "icon">["icon"];

export interface ActivityItem {
  title: string;
  time: string;
  icon: string;
}

export interface QuickAction {
  title: string;
  icon: iconType;
  path: string;
}
