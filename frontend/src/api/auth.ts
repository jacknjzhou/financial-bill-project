import { http } from "./client";
import type { LoginResp, UserInfo } from "./types";

export const authApi = {
  login: (username: string, password: string) =>
    http.post<LoginResp>("/auth/login", { username, password }),
  logout: () => http.post("/auth/logout"),
  me: () => http.get<UserInfo>("/auth/me"),
  config: () => http.get<{ sso_enabled: boolean }>("/auth/config"),
  changePassword: (oldPassword: string | null, newPassword: string) =>
    http.post("/auth/change-password", {
      ...(oldPassword ? { old_password: oldPassword } : {}),
      new_password: newPassword,
    }),
};
