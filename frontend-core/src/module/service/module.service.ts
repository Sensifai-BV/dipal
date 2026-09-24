import api from "@/core/services/axios";
import to from "await-to-js";
import { MODULE_SERVICE_ROUTES } from "./module.route";

export const fecthUserInfo = async () => {
  const [err, res] = await to(api.get(MODULE_SERVICE_ROUTES.profile));
  if (err) {
    throw err;
  }
  return res.data.data;
};
