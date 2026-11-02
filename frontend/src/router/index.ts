import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import Login from "../views/Login.vue";
import Dashboard from "../views/Dashboard.vue";
import ComingSoon from "../views/ComingSoon.vue";
import MainLayout from "../layouts/MainLayout.vue";

/**
 * 路由表：T2 建骨架（守卫 + 布局 + 占位视图）；
 * T11/T12/T13/T14 起逐个把占位换成真实视图（路径不变）。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: Login, meta: { public: true } },
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", name: "dashboard", component: Dashboard },
        { path: "projects", name: "projects", component: ComingSoon, meta: { title: "对账项目" } },
        { path: "results", name: "results", component: ComingSoon, meta: { title: "对账结果" } },
        { path: "disputes", name: "disputes", component: ComingSoon, meta: { title: "差错处理" } },
        { path: "runs", name: "runs", component: ComingSoon, meta: { title: "对账运行" } },
        { path: "files", name: "files", component: ComingSoon, meta: { title: "文件管理" } },
        { path: "channels", name: "channels", component: ComingSoon, meta: { title: "渠道配置" } },
        { path: "parse-rules", name: "parse-rules", component: ComingSoon, meta: { title: "解析规则" } },
        { path: "users", name: "users", component: ComingSoon, meta: { title: "系统管理", adminOnly: true } },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  const store = useAuthStore();
  if (to.meta.public) return true;
  // 未登录或刷新页面（内存态丢失）：拉一次 /me
  if (!store.user) {
    try {
      await store.refresh();
    } catch {
      return { name: "login", query: { redirect: to.fullPath } };
    }
  }
  if (to.meta.adminOnly && !store.isAdmin) return { name: "dashboard" };
  return true;
});

export default router;
