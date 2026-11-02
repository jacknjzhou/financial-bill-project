<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { authApi } from "../api/auth";
import { useAuthStore } from "../stores/auth";

/**
 * forced=true：强制改密（must_change 状态）——不可关闭，取消 = 退出登录，必带旧密码。
 * forced=false：顶栏自愿「设置/修改密码」——可关闭；SSO 建号用户（未设本地密码）旧密码可留空。
 */
const props = withDefaults(defineProps<{ forced?: boolean }>(), { forced: true });
const emit = defineEmits<{ done: []; cancel: [] }>();

const store = useAuthStore();
const loading = ref(false);
const form = reactive({ old: "", next: "", confirm: "" });

async function submit() {
  if (form.next.length < 8) {
    ElMessage.warning("新密码至少 8 位");
    return;
  }
  if (form.next !== form.confirm) {
    ElMessage.warning("两次输入的新密码不一致");
    return;
  }
  if (props.forced && !form.old) {
    ElMessage.warning("请输入旧密码");
    return;
  }
  loading.value = true;
  try {
    await authApi.changePassword(props.forced ? form.old : form.old || null, form.next);
    await store.refresh();
    ElMessage.success("密码已更新");
    emit("done");
  } catch (e: unknown) {
    ElMessage.error(
      (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ??
        "改密失败",
    );
  } finally {
    loading.value = false;
  }
}

function onCancel() {
  emit("cancel");
}
</script>

<template>
  <el-dialog
    :title="props.forced ? '修改密码' : '设置 / 修改密码'"
    :close-on-press-escape="!props.forced"
    :close-on-click-modal="!props.forced"
    :show-close="!props.forced"
    width="420px"
    @close="onCancel"
  >
    <p v-if="props.forced" class="tip">您的密码需要修改后才能继续使用系统。</p>
    <el-form @submit.prevent="submit">
      <el-form-item :label="props.forced ? '旧密码' : '旧密码（未设过可留空）'" :required="props.forced">
        <el-input v-model="form.old" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码" required>
        <el-input v-model="form.next" type="password" show-password placeholder="至少 8 位" />
      </el-form-item>
      <el-form-item label="确认新密码" required>
        <el-input v-model="form.confirm" type="password" show-password />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" native-type="submit">保存</el-button>
        <el-button @click="onCancel">{{ props.forced ? "退出登录" : "取消" }}</el-button>
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.tip { color: #d46b08; margin-top: 0; }
</style>
