<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { channelApi } from "../../api/meta";
import type { Channel } from "../../api/types";

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<Channel | null>(null);
const form = reactive({ code: "", name: "", enabled: true });

function openCreate() {
  editing.value = null;
  Object.assign(form, { code: "", name: "", enabled: true });
  dialogOpen.value = true;
}

function openEdit(row: Channel) {
  editing.value = row;
  Object.assign(form, { code: row.code, name: row.name, enabled: row.enabled });
  dialogOpen.value = true;
}

async function submit() {
  try {
    if (editing.value) await channelApi.update(editing.value.id, { ...form });
    else await channelApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function toggle(row: Channel) {
  await channelApi.update(row.id, { enabled: row.enabled });
}

async function remove(row: Channel) {
  try {
    await ElMessageBox.confirm(`确认删除渠道「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await channelApi.remove(row.id);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增渠道</el-button>
    </div>
    <PagTable ref="table" :fetcher="channelApi.list">
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑渠道' : '新增渠道'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="编码"><el-input v-model="form.code" :disabled="!!editing" placeholder="如 wxpay" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
