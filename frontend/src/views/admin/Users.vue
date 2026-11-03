<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { http } from "../../api/client";

interface UserRow {
  id: number;
  username: string;
  role: "admin" | "operator";
  must_change_password: boolean;
  is_active: boolean;
  created_at: string;
}

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<UserRow | null>(null);
const form = reactive({ username: "", password: "", role: "operator" });
const resetOpen = ref(false);
const resetTarget = ref<UserRow | null>(null);
const newPassword = ref("");

const fetcher = (p: number, s: number) =>
  http.get<{ total: number; items: UserRow[] }>("/users", { params: { page: p, page_size: s } }).then((r) => r.data);

function openCreate() {
  editing.value = null;
  Object.assign(form, { username: "", password: "", role: "operator" });
  dialogOpen.value = true;
}

async function submit() {
  try {
    if (editing.value?.id) {
      await http.patch(`/users/${editing.value.id}`, { role: form.role });
    } else {
      await http.post("/users", { ...form });
    }
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function toggleActive(row: UserRow) {
  try {
    await http.patch(`/users/${row.id}`, { is_active: !row.is_active });
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "操作失败");
    table.value?.reload();
  }
}

async function openReset(row: UserRow) {
  try {
    await ElMessageBox.confirm(`确认重置「${row.username}」的本地密码？重置后用户首次登录需改密。`, "重置密码", { type: "warning" });
  } catch {
    return;
  }
  resetTarget.value = row;
  newPassword.value = "";
  resetOpen.value = true;
}

async function submitReset() {
  if (!resetTarget.value) return;
  try {
    await http.post(`/users/${resetTarget.value.id}/reset-password`, { new_password: newPassword.value });
    ElMessage.success("已重置");
    resetOpen.value = false;
  } catch (e) {
    const details = (e as { response?: { data?: { error?: { message?: string; details?: unknown } } } })?.response?.data?.error;
    ElMessage.error(details?.message ?? "重置失败");
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增用户</el-button>
      <el-link type="primary" href="/api/docs/" target="_blank" class="docs-link">API 文档（Swagger UI）</el-link>
    </div>
    <PagTable ref="table" :fetcher="fetcher">
      <el-table-column prop="username" label="用户名" width="180" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">{{ row.role === "admin" ? "管理员" : "对账员" }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" @change="toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="must_change_password" label="待改密" width="90">
        <template #default="{ row }">{{ row.must_change_password ? "是" : "否" }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="170">
        <template #default="{ row }">{{ (row.created_at || "").slice(0, 19).replace("T", " ") }}</template>
      </el-table-column>
      <el-table-column label="操作" width="170">
        <template #default="{ row }">
          <el-button link type="warning" @click="openReset(row)">重置密码</el-button>
          <el-button
            link
            type="primary"
            @click="((editing = row), (form.username = row.username), (form.role = row.role), (dialogOpen = true))"
          >编辑</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑用户' : '新增用户'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item v-if="!editing" label="初始密码">
          <el-input v-model="form.password" type="password" show-password placeholder="≥8 位，含字母数字" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="对账员" value="operator" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetOpen" :title="`重置密码：${resetTarget?.username ?? ''}`" width="420px">
      <el-input v-model="newPassword" type="password" show-password placeholder="新密码（≥8 位，含字母数字）" />
      <template #footer>
        <el-button @click="resetOpen = false">取消</el-button>
        <el-button type="primary" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.docs-link { margin-left: auto; }
</style>
