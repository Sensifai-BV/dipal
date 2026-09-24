import type { RouteRecordRaw } from "vue-router";

export const authRoutes: RouteRecordRaw[] = [
  {
    path: "/auth",
    children: [
      {
        path: "login",
        name: "auth-login",
        component: () => import("@auth/pages/login/login.vue"),
        meta: {
          title: "Sign In",
          requiresAuth: false,
        },
      },
      {
        path: "register",
        name: "auth-register",
        component: () => import("@auth/pages/register/register.vue"),
        meta: {
          title: "Sign Up",
          requiresAuth: false,
        },
      },
    ],
    meta: {
      layout: "auth",
      requiresAuth: false,
    },
  },
];

export default authRoutes;
