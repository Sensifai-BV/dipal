import type { RouteRecordRaw } from "vue-router";
import { DATASET_ROUTES } from "./route.constant";

export const datasetRoutes: RouteRecordRaw[] = [
  {
    path: DATASET_ROUTES.datasetList,
    name: "dataset-list",
    component: () => import("@module/dataset/pages/data-set/data-set.vue"),
    meta: {
      title: "Datasets",
      layout: "default",
      description: "Upload and manage drone imagery datasets",
      requiresAuth: true,
      role: ["admin"],
    },
  },
];

export default datasetRoutes;
