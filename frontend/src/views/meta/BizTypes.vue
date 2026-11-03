<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { bizTypeApi } from "../../api/meta";
import type { BizType } from "../../api/types";

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<BizType | null>(null);
const form = reactive({ code: "", name: "", group: "INCOME" as BizType["group"] });

const GROUP_LABEL: Record<BizType["group"], string> = { INCOME: "收款", REFUND: "退款", FEE: "费用" };

function openCreate() {
  editing.value = null;
  Object.assign(form, { code: "", name: "", group: "INCOME" });
  dialogOpen.value = true;
}

function openEdit(row: BizType) {
  editing.value = row;
  Object.assign(form, { code: row.code, name: row.name, group: row.group });
  dialogOpen.value = true;
}

async function submit() {
  try {
    if (editing.value) await bizTypeApi.update(editing.value.id, { ...form });
    else await bizTypeApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: BizType) {
  try {
    await ElMessageBox.confirm(`确认删除业务类型「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await bizTypeApi.remove(row.id);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增业务类型</el-button>
    </div>
    <PagTable ref="table" :fetcher="bizTypeApi.list">
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="分组" width="120">
        <template #default="{ row }">
          <el-tag>{{ GROUP_LABEL[row.group as BizType["group"]] ?? row.group }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑业务类型' : '新增业务类型'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="编码"><el-input v-model="form.code" :disabled="!!editing" placeholder="如 PAY / REFUND / FEE" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分组">
          <el-select v-model="form.group">
            <el-option label="收款" value="INCOME" />
            <el-option label="退款" value="REFUND" />
            <el-option label="费用" value="FEE" />
          </el-select>
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
