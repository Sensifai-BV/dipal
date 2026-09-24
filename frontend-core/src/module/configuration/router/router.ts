import type { RouteRecordRaw } from "vue-router";
import { CONFIGURATION_ROUTES } from "./route.constant";

export const configurationRoutes: RouteRecordRaw[] = [
  {
    path: CONFIGURATION_ROUTES.configurationList,
    name: "configuration-list",
    component: () =>
      import("@module/configuration/pages/configuration/configuration.vue"),
    meta: {
      layout: "default",
      requiresAuth: true,
      role: ["admin"],
    },
  },
];

export default configurationRoutes;
