<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

/**
 * SSO 回跳落点：allauth 建会话后 302 到这里。
 * 进入即拉 /me：成功 → 进工作台；失败（如 IdP 拒绝/回调异常）→ 回登录页。
 */
const router = useRouter();
const store = useAuthStore();

onMounted(async () => {
  try {
    await store.refresh();
    router.replace("/");
  } catch {
    router.replace("/login");
  }
});
</script>

<template>
  <div class="sso-callback">
    <el-text type="info" size="large">SSO 登录中，请稍候…</el-text>
  </div>
</template>

<style scoped>
.sso-callback {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
