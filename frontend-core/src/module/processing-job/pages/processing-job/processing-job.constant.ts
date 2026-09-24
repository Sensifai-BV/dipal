import type { ProcessingJobItem } from "./processing-job.type";

export const ProcessingJobTableHeaders: Array<{
  text: string;
  field?: keyof ProcessingJobItem;
  sortable?: boolean;
  styles?: string;
}> = [
  // { text: "Job ID", field: "id" },
  // { text: "Dataset ID", field: "dataset_id" },
  { text: "Dataset", field: "dataset_name", styles: "col-span-1" },
  { text: "Status", field: "status", styles: "col-span-2" },
  { text: "Stage", field: "stage", styles: "col-span-1" },
  { text: "Progress", field: "progress", styles: "col-span-2" },
  {
    text: "Resolution(GSD)",
    field: "resolution_gsd",
    styles: "col-span-2 text-center",
  },
  { text: "Start Time", field: "created_at", styles: "col-span-2 " },
  { text: "Duration", field: "duration_seconds" },
  {
    text: "Actions",
    field: "actions",
    sortable: false,
    styles: "text-right",
  },
];
