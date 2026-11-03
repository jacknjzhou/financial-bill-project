import axios from "axios";
import type { InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../stores/auth";

/**
 * 业务 API 客户端：/api/v1 前缀；会话 cookie 同域自动携带。
 *
 * CSRF 关键点：axios 默认把 csrftoken cookie 放进 `X-XSRFToken` 头，
 * 但 Django 只认 `X-CSRFToken`（WSGI 映射为 HTTP_X_CSRFTOKEN）——
 * 且 DRF 视图对 Django CSRF 中间件 csrf_exempt、仅在存在会话用户时
 * 由 SessionAuthentication 强制 CSRF，所以必须在请求拦截器显式设置，
 * 否则登录成功后的首个 POST（如改密）会 403。
 */
function readCsrfToken(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export const http = axios.create({
  baseURL: "/api/v1",
  xsrfHeaderName: "X-CSRFToken", // 覆盖 axios 默认的 X-XSRFToken
});

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = readCsrfToken();
  if (token) {
    config.headers.set("X-CSRFToken", token);
  }
  return config;
});

/** 拉取 csrftoken cookie（登录后首个 POST 需要）；失败静默。 */
export async function ensureCsrf(): Promise<void> {
  try {
    await http.get("/auth/csrf");
  } catch {
    /* 未登录状态无所谓 */
  }
}

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status;
    const code = err.response?.data?.error?.code as string | undefined;
    if (code === "MUST_CHANGE_PASSWORD") {
      // 强制改密中：弹全局对话框，不跳登录页
      useAuthStore().mustChange = true;
    } else if (code === "CSRF_FAILED") {
      // cookie 可能已轮换：重新种一次 token 后刷新
      void ensureCsrf();
      window.location.reload();
    } else if (status === 401 || code === "UNAUTHORIZED") {
      // 会话过期：回登录页（保留来源路径）
      const path = window.location.pathname;
      if (path !== "/login") {
        window.location.href = path === "/" ? "/login" : `/login?redirect=${encodeURIComponent(path)}`;
      }
    }
    return Promise.reject(err);
  },
);
