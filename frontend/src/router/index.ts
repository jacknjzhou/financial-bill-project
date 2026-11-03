import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import Login from "../views/Login.vue";
import SsoCallback from "../views/SsoCallback.vue";
import Dashboard from "../views/Dashboard.vue";
import ComingSoon from "../views/ComingSoon.vue";
import Channels from "../views/meta/Channels.vue";
import FundAccounts from "../views/meta/FundAccounts.vue";
import BizTypes from "../views/meta/BizTypes.vue";
import DisputeTypes from "../views/meta/DisputeTypes.vue";
import ParseRules from "../views/rules/ParseRules.vue";
import FetchTasks from "../views/rules/FetchTasks.vue";
import Projects from "../views/rules/Projects.vue";
import Files from "../views/dataio/Files.vue";
import DataQuery from "../views/dataio/DataQuery.vue";
import MainLayout from "../layouts/MainLayout.vue";

/**
 * 路由表：T2 建骨架（守卫 + 布局 + 占位视图）；
 * T11/T12/T13/T14 起逐个把占位换成真实视图（路径不变）。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: Login, meta: { public: true } },
    { path: "/sso/callback", name: "sso-callback", component: SsoCallback, meta: { public: true } },
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", name: "dashboard", component: Dashboard },
        { path: "projects", name: "projects", component: Projects, meta: { title: "对账项目" } },
        { path: "results", name: "results", component: ComingSoon, meta: { title: "对账结果" } },
        { path: "disputes", name: "disputes", component: ComingSoon, meta: { title: "差错处理" } },
        { path: "runs", name: "runs", component: ComingSoon, meta: { title: "对账运行" } },
        { path: "files", name: "files", component: Files, meta: { title: "文件管理" } },
        { path: "data-query", name: "data-query", component: DataQuery, meta: { title: "数据查询" } },
        { path: "channels", name: "channels", component: Channels, meta: { title: "渠道配置" } },
        { path: "fund-accounts", name: "fund-accounts", component: FundAccounts, meta: { title: "资金账户" } },
        { path: "biz-types", name: "biz-types", component: BizTypes, meta: { title: "业务类型" } },
        { path: "dispute-types", name: "dispute-types", component: DisputeTypes, meta: { title: "差错处理类型" } },
        { path: "parse-rules", name: "parse-rules", component: ParseRules, meta: { title: "解析规则" } },
        { path: "fetch-tasks", name: "fetch-tasks", component: FetchTasks, meta: { title: "获取任务" } },
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
