import type { icons } from "lucide-vue-next";

export interface MenuItem {
  label: string;
  icon: keyof typeof icons;
  route: string;
  active?: boolean;
  disabled?: boolean;
}

export interface UserInfo {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  username: string;
  is_email_verified: boolean;
}

export interface MenuProps {
  items: MenuItem[];
  user?: UserInfo;
  logoText?: string;
  subtitle?: string;
}

export interface MenuEmits {
  (e: "signOut"): void;
}
