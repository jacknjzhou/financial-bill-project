import { defineStore } from "pinia";
import { authApi } from "../api/auth";
import type { UserInfo } from "../api/types";

interface AuthState {
  user: UserInfo | null;
  mustChange: boolean;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    mustChange: false,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    role: (s) => s.user?.role ?? "",
    isAdmin: (s) => s.user?.role === "admin",
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await authApi.login(username, password);
      this.user = data.user;
      this.mustChange = data.must_change_password;
    },
    async refresh() {
      const { data } = await authApi.me();
      this.user = data;
      this.mustChange = data.must_change_password;
    },
    async logout() {
      try {
        await authApi.logout();
      } finally {
        this.user = null;
        this.mustChange = false;
      }
    },
  },
});
