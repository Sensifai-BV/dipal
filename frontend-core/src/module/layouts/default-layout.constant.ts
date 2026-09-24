import type { MenuItem } from "@/core/components/others";
import { DASHBOARD_ROUTES } from "@module/dashboard/router/router.constant";
import { DATASET_ROUTES } from "@module/dataset/router/route.constant";
import { PROCESSING_JOB_ROUTES } from "@module/processing-job/router/route.constant";
import { PRODUCTS_ROUTES } from "@module/products/router/route.constant";
import { CONFIGURATION_ROUTES } from "../configuration/router/route.constant";

export const MENU_ROUTES: MenuItem[] = [
  {
    label: "Dashboard",
    icon: "LayoutDashboard",
    route: DASHBOARD_ROUTES.dashboard,
  },
  {
    label: "Datasets",
    icon: "Database",
    route: DATASET_ROUTES.datasetList,
  },
  {
    label: "Processing Jobs",
    icon: "Cpu",
    route: PROCESSING_JOB_ROUTES.processingJobList,
  },
  {
    label: "Products",
    icon: "Box",
    route: PRODUCTS_ROUTES.productList,
  },
  {
    label: "Configuration",
    icon: "Settings",
    route: CONFIGURATION_ROUTES.configurationList,
  },
];
