<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { disputeTypeApi } from "../../api/meta";
import type { DisputeType } from "../../api/types";

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<DisputeType | null>(null);
const form = reactive({ group: "TRANSACTION" as DisputeType["group"], name: "", description: "" });

const GROUP_LABEL: Record<DisputeType["group"], string> = { TRANSACTION: "交易", FUND: "资金" };

function openCreate() {
  editing.value = null;
  Object.assign(form, { group: "TRANSACTION", name: "", description: "" });
  dialogOpen.value = true;
}

function openEdit(row: DisputeType) {
  editing.value = row;
  Object.assign(form, { group: row.group, name: row.name, description: row.description });
  dialogOpen.value = true;
}

async function submit() {
  try {
    if (editing.value) await disputeTypeApi.update(editing.value.id, { ...form });
    else await disputeTypeApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: DisputeType) {
  try {
    await ElMessageBox.confirm(`确认删除差错处理类型「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await disputeTypeApi.remove(row.id);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增差错处理类型（SOP）</el-button>
    </div>
    <PagTable ref="table" :fetcher="disputeTypeApi.list">
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column label="分组" width="100">
        <template #default="{ row }">
          <el-tag>{{ GROUP_LABEL[row.group as DisputeType["group"]] ?? row.group }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="SOP 说明" show-overflow-tooltip />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑差错处理类型' : '新增差错处理类型'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="分组">
          <el-select v-model="form.group" :disabled="form.group === 'FUND'">
            <el-option label="交易" value="TRANSACTION" />
            <el-option label="资金" value="FUND" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="SOP 说明">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="处理该类差异的标准操作流程" />
        </el-form-item>
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
