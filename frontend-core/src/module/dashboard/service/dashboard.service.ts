import { DASHBOARD_API } from "./dashboard.api";
import api from "@/core/services/axios";
import to from "await-to-js";

export const getDashboardData = async (): Promise<any> => {
  const [err, res] = await to(api.get(DASHBOARD_API.status));

  if (err) {
    throw err;
  }
  return res.data;
};

export const getDashboardActivities = async (): Promise<any> => {
  const [err, res] = await to(api.get(DASHBOARD_API.activities));

  if (err) {
    throw err;
  }
  return res.data;
};
