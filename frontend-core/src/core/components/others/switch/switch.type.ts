import type { icons } from "lucide-vue-next";

export interface SwitchProps {
    switchItems: Record<string, {
        icon: keyof typeof icons;
        name: string;
        isActive: boolean;
    }>;
}


export interface SwitchEmits {
    (e: 'changeItem', data: string): void
}