import type { RouteRecordRaw } from "vue-router";

export const collectRoutes = () => {
  const authRoutes = import.meta.glob("@auth/router/router.ts", {
    eager: true,
  }) as Record<string, { default: RouteRecordRaw[] }>;
  const moduleRoutes = import.meta.glob("@module/**/router/router.ts", {
    eager: true,
  }) as Record<string, { default: RouteRecordRaw[] }>;
  const allRoutes = { ...authRoutes, ...moduleRoutes };
  let routes: RouteRecordRaw[] = [];
  for (const path in allRoutes) {
    const module = allRoutes[path];
    if (module?.default) {
      routes = routes.concat(module.default);
    }
  }

  return routes;
};

export const generateUUID = () => {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};
