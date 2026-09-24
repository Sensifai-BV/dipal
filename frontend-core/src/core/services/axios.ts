import { AuthRoute } from "@auth/router/route.constant";
import axios from "axios";
import { toastService } from "./toast.service";
import { router } from "@/router.ts";

const BASE_URL =
  import.meta.env.VITE_BASE_URL

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

function generateRequestId(): string {
  // crypto.randomUUID is only available in secure contexts (HTTPS/localhost).
  // Fall back to a random hex string when it's unavailable (e.g. HTTP origins).
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().slice(0, 8);
  }
  return Math.random().toString(16).slice(2, 10);
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("user");
  const parsedToken = token ? JSON.parse(token).token : null;
  if (parsedToken) {
    config.headers.Authorization = `Bearer ${parsedToken.access}`;
  }
  config.headers["X-Request-ID"] = generateRequestId();
  return config;
});

function extractErrorMessage(error: any): string {
  const data = error.response?.data;
  if (data) {
    if (typeof data === "string") return data;
    if (data.error && typeof data.error === "string") return data.error;
    if (data.detail && typeof data.detail === "string") return data.detail;
    if (data.message && typeof data.message === "string") return data.message;
  }

  if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
    return "Request timed out. Please try again.";
  }
  if (error.code === "ERR_NETWORK" || !error.response) {
    return "Unable to reach the server. Please check your connection.";
  }

  const status = error.response?.status;
  if (status === 403) return "You don't have permission to perform this action.";
  if (status === 404) return "The requested resource was not found.";
  if (status === 500) return "An internal server error occurred. Please try again later.";
  if (status && status >= 500) return "A server error occurred. Please try again later.";

  return "Something went wrong. Please try again.";
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.clear();
      router.push(AuthRoute.LOGIN);
      return Promise.reject(error);
    }

    const message = extractErrorMessage(error);
    toastService.error("Error", message);

    error._toastShown = true;

    return Promise.reject(error);
  },
);

export default api;
