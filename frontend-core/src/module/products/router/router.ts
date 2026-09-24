import type { RouteRecordRaw } from "vue-router";
import { PRODUCTS_ROUTES } from "./route.constant";

export const productRoutes: RouteRecordRaw[] = [
  {
    path: PRODUCTS_ROUTES.productListWithJob,
    name: "products",
    component: () => import("@module/products/pages/products/products.vue"),
    meta: {
      title: "Products",
      description: "Manage your product listings",
      layout: "default",
      requiresAuth: true,
      role: ["admin"],
    },
  },
];

export default productRoutes;
