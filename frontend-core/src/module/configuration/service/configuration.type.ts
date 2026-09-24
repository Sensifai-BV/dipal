export interface WebhookItem {
  id: string;
  url: string;
  secret: string;
  events: string[];
  active: boolean;
  headers: Record<string, string>;
  created_at: string;
}

export interface WebhookCreatePayload {
  url: string;
  events: string[];
  headers?: Record<string, string>;
}

export interface WebhookUpdatePayload {
  url?: string;
  events?: string[];
  active?: boolean;
  headers?: Record<string, string>;
}

export const AVAILABLE_WEBHOOK_EVENTS = [
  { value: "job.completed", label: "Job Completed" },
  { value: "job.failed", label: "Job Failed" },
  { value: "upload.completed", label: "Upload Completed" },
];
