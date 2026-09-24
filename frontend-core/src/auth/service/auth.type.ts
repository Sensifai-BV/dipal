export interface RegisterPayload {
  email: string;
  password: string;
  confirm_password: string;
  full_name?: string;
  role?: number;
  organization?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  refresh: string;
  access: string;
  refresh_expires_in: number;
  access_expires_in: number;
}
