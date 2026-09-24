import { AuthRoute } from "@auth/router/route.constant";
import { DASHBOARD_ROUTES } from "@module/dashboard/router/router.constant";
import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";
import { collectRoutes } from "./core/utils/utils";

const history = createWebHistory();
const routes: RouteRecordRaw[] = collectRoutes();
export const router = createRouter({
  history,
  routes: routes,
});

router.beforeEach((to, _, next) => {
  const token = localStorage.getItem("user");

  if (to.path === AuthRoute.LOGIN) {
    if (!token) return next();
    return next(DASHBOARD_ROUTES.dashboard);
  }

  if (to.meta.requiresAuth && !token) {
    return next(AuthRoute.LOGIN);
  }

  if (to.path === "/") {
    return next(DASHBOARD_ROUTES.dashboard);
  }

  next();
});
