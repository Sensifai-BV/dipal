import { toastService } from "@/core/services/toast.service";
import { AuthService } from "@auth/service/auth.service";
import type { LoginPayload, RegisterPayload } from "@auth/service/auth.type";
import { to } from "await-to-js";
import { defineStore } from "pinia";

interface tokenInfo {
  access: string;
  access_expires_in: number;
  refresh: string;
  refresh_expires_in: number;
}

export const useUserStore = defineStore("user", {
  state: () => ({
    token: null as tokenInfo | null,
    user: null as any,
  }),

  actions: {
    async login(data: LoginPayload) {
      const [err, res] = await to(AuthService.login(data));

      if (err) {
        if (!(err as any)?._toastShown) {
          toastService.error("Error", err.message || "Login failed.");
        }
        throw err;
      }
      this.token = res.data.data;
      toastService.success("Success!", "Login successful.");
      return res;
    },

    async register(data: RegisterPayload) {
      const [err, res] = await to(AuthService.register(data));
      if (err) {
        if (!(err as any)?._toastShown) {
          toastService.error("Error", err.message || "Registration failed.");
        }
        throw err;
      }

      toastService.success("Success!", "Registration successful.");
      return res;
    },

    logout() {
      this.$reset();
    },
  },

  persist: true,
});
