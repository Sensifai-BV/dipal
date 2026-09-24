import ToastContainer from "@core/components/base/toast/toast-container.vue";
import { toastService } from "@core/services/toast.service";
import type { App } from "vue";

export const toastPlugin = {
  install(app: App) {
    // Provide toast service and toasts globally
    app.provide("toasts", toastService.toasts);
    app.provide("removeToast", (id: string) => toastService.remove(id));

    // Make toast service available globally
    app.config.globalProperties.$toast = toastService;

    // Register toast container component globally
    app.component("ToastContainer", ToastContainer);
  },
};

declare module "@vue/runtime-core" {
  interface ComponentCustomProperties {
    $toast: typeof toastService;
  }
}
