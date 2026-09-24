import type { RouteRecordRaw } from "vue-router";
import { PROCESSING_JOB_ROUTES } from "./route.constant";

export const processingJobRoutes: RouteRecordRaw[] = [
  {
    path: PROCESSING_JOB_ROUTES.processingJobList,
    name: PROCESSING_JOB_ROUTES.processingJobList,
    component: () =>
      import("@module/processing-job/pages/processing-job/processing-job.vue"),
    meta: {
      title: "Processing Jobs",
      layout: "default",
      requiresAuth: true,
      description: "Monitor and manage photogrammetric processing pipelines",
      role: ["admin"],
    },
  },
];

export default processingJobRoutes;
