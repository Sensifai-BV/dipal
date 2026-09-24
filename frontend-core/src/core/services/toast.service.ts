import type { Toast, ToastType } from "@core/components/base/toast/toast.type";
import { reactive } from "vue";

class ToastService {
  private state = reactive({
    toasts: [] as Toast[],
  });

  get toasts() {
    return this.state.toasts;
  }

  private generateId(): string {
    return `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  show(
    type: ToastType,
    title: string,
    message: string,
    options?: {
      duration?: number;
      action?: { label: string; handler: () => void };
      closable?: boolean;
    }
  ): string {
    const id = this.generateId();
    const toast: Toast = {
      id,
      type,
      title,
      message,
      duration: options?.duration ?? 5000,
      action: options?.action,
      closable: options?.closable ?? true,
    };

    this.state.toasts.push(toast);

    // Auto remove after duration
    if (toast.duration && toast.duration > 0) {
      setTimeout(() => {
        this.remove(id);
      }, toast.duration);
    }

    return id;
  }

  success(
    title: string,
    message: string,
    options?: {
      duration?: number;
      action?: { label: string; handler: () => void };
    }
  ) {
    return this.show("success", title, message, options);
  }

  error(
    title: string,
    message: string,
    options?: {
      duration?: number;
      action?: { label: string; handler: () => void };
    }
  ) {
    return this.show("error", title, message, {
      ...options,
      duration: options?.duration ?? 8000,
    });
  }

  warning(
    title: string,
    message: string,
    options?: {
      duration?: number;
      action?: { label: string; handler: () => void };
    }
  ) {
    return this.show("warning", title, message, options);
  }

  info(
    title: string,
    message: string,
    options?: {
      duration?: number;
      action?: { label: string; handler: () => void };
    }
  ) {
    return this.show("info", title, message, options);
  }

  remove(id: string) {
    const index = this.state.toasts.findIndex((toast) => toast.id === id);
    if (index > -1) {
      this.state.toasts.splice(index, 1);
    }
  }

  clear() {
    this.state.toasts.splice(0);
  }
}

export const toastService = new ToastService();
export { ToastService };
