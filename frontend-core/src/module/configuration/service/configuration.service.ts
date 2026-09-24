import api from "@/core/services/axios";
import { toastService } from "@/core/services/toast.service";
import to from "await-to-js";
import { CONFIGURATION_API_ROUTE } from "./configuration.route";
import type { WebhookCreatePayload, WebhookUpdatePayload } from "./configuration.type";

export const getWebhookList = async () => {
  const [err, res] = await to(api.get(CONFIGURATION_API_ROUTE.webhooks));
  if (err) throw err;
  return res.data;
};

export const createWebhook = async (payload: WebhookCreatePayload) => {
  const [err, res] = await to(api.post(CONFIGURATION_API_ROUTE.webhooks, payload));
  if (err) throw err;
  toastService.success("Created", "Webhook created successfully");
  return res.data;
};

export const updateWebhook = async (id: string, payload: WebhookUpdatePayload) => {
  const url = CONFIGURATION_API_ROUTE.webhookDetail.replace("{id}", id);
  const [err, res] = await to(api.put(url, payload));
  if (err) throw err;
  toastService.success("Updated", "Webhook updated successfully");
  return res.data;
};

export const deleteWebhook = async (id: string) => {
  const url = CONFIGURATION_API_ROUTE.webhookDetail.replace("{id}", id);
  const [err, res] = await to(api.delete(url));
  if (err) throw err;
  toastService.success("Deleted", "Webhook deleted successfully");
  return res.data;
};

export const getSystemHealth = async () => {
  const baseUrl = import.meta.env.VITE_BASE_URL as string;
  const rootUrl = baseUrl.replace(/v1\/$/, "");
  const [err, res] = await to(api.get(rootUrl + CONFIGURATION_API_ROUTE.health));
  if (err) throw err;
  return res.data;
};
