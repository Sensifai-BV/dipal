import type { RouteRecordRaw } from "vue-router";
import { DASHBOARD_ROUTES } from "./router.constant";

export const dashboardRoutes: RouteRecordRaw[] = [
  {
    path: DASHBOARD_ROUTES.dashboard,
    name: "dashboard-home",
    component: () => import("@module/dashboard/pages/dashboard/dashboard.vue"),
    meta: {
      title: "Dashboard Home",
      layout: "default",
      requiresAuth: true,
      role: ["admin"],
    },
  },
];

export default dashboardRoutes;
