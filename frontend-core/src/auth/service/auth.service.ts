import api from "@/core/services/axios";
import type { LoginPayload, RegisterPayload } from "./auth.type";
import { AUTH_SERVICE_ROUTE } from "./service.route";

export const AuthService = {
  login: (data: LoginPayload) => api.post(AUTH_SERVICE_ROUTE.LOGIN, data),
  register: (data: RegisterPayload) =>
    api.post(AUTH_SERVICE_ROUTE.REGISTER, data),
};
