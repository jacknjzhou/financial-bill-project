<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { useAuthStore } from "../stores/auth";
import MustChangeDialog from "../components/MustChangeDialog.vue";

const route = useRoute();
const router = useRouter();
const store = useAuthStore();

const voluntaryOpen = ref(false);

const menus: Array<
  | { path: string; title: string; adminOnly?: boolean }
  | { title: string; children: Array<{ path: string; title: string; adminOnly?: boolean }> }
> = [
  { path: "/", title: "工作台" },
  { path: "/projects", title: "对账项目" },
  { path: "/results", title: "对账结果" },
  { path: "/disputes", title: "差错处理" },
  { path: "/runs", title: "对账运行" },
  {
    title: "数据管理",
    children: [{ path: "/files", title: "文件管理" }],
  },
  {
    title: "基础配置",
    children: [
      { path: "/channels", title: "渠道配置" },
      { path: "/fund-accounts", title: "资金账户" },
      { path: "/biz-types", title: "业务类型" },
      { path: "/dispute-types", title: "差错处理类型" },
      { path: "/parse-rules", title: "解析规则" },
    ],
  },
  { path: "/users", title: "系统管理", adminOnly: true },
];

const isGroup = (m: (typeof menus)[number]): m is { title: string; children: Array<{ path: string; title: string; adminOnly?: boolean }> } =>
  "children" in m;

const visibleMenus = computed(() =>
  menus
    .map((m) => {
      if (isGroup(m)) {
        const children = m.children.filter((c) => !c.adminOnly || store.isAdmin);
        return { ...m, children };
      }
      return m;
    })
    .filter((m) => (isGroup(m) ? m.children.length > 0 : !m.adminOnly || store.isAdmin)),
);

function onCommand(cmd: string) {
  if (cmd === "changepwd") voluntaryOpen.value = true;
  else if (cmd === "logout") {
    ElMessageBox.confirm("确认退出登录？", "提示", { type: "warning" })
      .then(async () => {
        await store.logout();
        router.push("/login");
      })
      .catch(() => {});
  }
}

function onForcedCancel() {
  // 强制改密不允许跳过：退出登录
  void store.logout();
  router.push("/login");
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">对账系统</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#fff"
      >
        <template v-for="m in visibleMenus" :key="'title' in m && isGroup(m) ? m.title : m.path">
          <el-sub-menu v-if="isGroup(m)" :index="m.title">
            <template #title>{{ m.title }}</template>
            <el-menu-item v-for="c in m.children" :key="c.path" :index="c.path">{{ c.title }}</el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="m.path">{{ m.title }}</el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ route.meta.title || "工作台" }}</span>
        <el-dropdown @command="onCommand">
          <span class="user">
            {{ store.user?.username }}（{{ store.user?.role }}）
            <el-icon><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="changepwd">设置 / 修改密码</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
    <MustChangeDialog v-if="store.mustChange" forced @cancel="onForcedCancel" />
    <MustChangeDialog
      v-if="voluntaryOpen"
      :forced="false"
      @done="voluntaryOpen = false"
      @cancel="voluntaryOpen = false"
    />
  </el-container>
</template>

<style scoped>
.layout { height: 100vh; }
.aside { background: #001529; }
.logo { color: #fff; font-size: 18px; font-weight: 600; text-align: center; line-height: 56px; }
.aside :deep(.el-menu) { border-right: none; }
.header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e5e7eb; }
.title { font-size: 16px; font-weight: 600; }
.user { cursor: pointer; color: #374151; }
</style>
