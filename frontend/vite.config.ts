import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/accounts": "http://localhost:8000", // allauth 内部流程（SSO）
    },
  },
});
