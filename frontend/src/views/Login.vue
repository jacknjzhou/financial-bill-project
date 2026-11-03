<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ensureCsrf } from "../api/client";
import { authApi } from "../api/auth";
import { useAuthStore } from "../stores/auth";
import MustChangeDialog from "../components/MustChangeDialog.vue";

const route = useRoute();
const router = useRouter();
const store = useAuthStore();

const form = reactive({ username: "", password: "" });
const loading = ref(false);
const ssoEnabled = ref(false);

onMounted(() => {
  // 种 csrftoken cookie（会话 POST 需要）
  void ensureCsrf();
  // SSO 开关（env 驱动，默认关）→ 决定是否渲染「SSO 登录」按钮
  authApi
    .config()
    .then((c) => {
      ssoEnabled.value = c.sso_enabled;
    })
    .catch(() => {
      /* 配置拉取失败按关闭处理 */
    });
});

async function submit() {
  loading.value = true;
  try {
    await store.login(form.username, form.password);
    const redirect = (route.query.redirect as string | undefined) || "/";
    router.push(redirect);
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { error?: { message?: string } } } })
        ?.response?.data?.error?.message ?? "登录失败";
    ElMessage.error(msg);
  } finally {
    loading.value = false;
  }
}

function ssoLogin() {
  // 302 → allauth /accounts/{provider}/login/ → 企业 IdP；回跳后进 /sso/callback
  window.location.href = "/api/v1/auth/oidc/login?next=/sso/callback";
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="card-title">对账系统</div>
      </template>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" native-type="submit" class="login-btn">
            登 录
          </el-button>
        </el-form-item>
        <el-form-item v-if="ssoEnabled">
          <el-button size="large" class="login-btn" @click="ssoLogin()">SSO 登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <MustChangeDialog v-if="store.mustChange && store.user" />
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f3b5c 0%, #0d1b2a 100%);
}
.login-card { width: 380px; }
.card-title { text-align: center; font-size: 18px; font-weight: 600; }
.login-btn { width: 100%; }
</style>
