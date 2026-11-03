<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { channelApi, fundAccountApi } from "../../api/meta";
import type { Channel, FundAccount } from "../../api/types";

const table = ref<InstanceType<typeof PagTable>>();
const channels = ref<Channel[]>([]);
const dialogOpen = ref(false);
const editing = ref<FundAccount | null>(null);
// 金额以元输入，提交转分（×100 取整）
const form = reactive({
  channel: undefined as number | undefined,
  name: "",
  account_no: "",
  start_date: "",
  start_balance_yuan: 0,
  enabled: true,
});

onMounted(() => {
  channelApi.list(1, 200).then((r) => (channels.value = r.items));
});

function openCreate() {
  editing.value = null;
  Object.assign(form, { channel: undefined, name: "", account_no: "", start_date: "", start_balance_yuan: 0, enabled: true });
  dialogOpen.value = true;
}

function openEdit(row: FundAccount) {
  editing.value = row;
  Object.assign(form, {
    channel: row.channel,
    name: row.name,
    account_no: row.account_no,
    start_date: row.start_date,
    start_balance_yuan: row.start_balance / 100,
    enabled: row.enabled,
  });
  dialogOpen.value = true;
}

async function submit() {
  if (!form.channel || !form.name || !form.start_date) {
    ElMessage.warning("渠道、名称、启用日期为必填");
    return;
  }
  const data = {
    channel: form.channel,
    name: form.name,
    account_no: form.account_no,
    start_date: form.start_date,
    // 元 → 分：×100 取整（避免浮点误差用 round）
    start_balance: Math.round(form.start_balance_yuan * 100),
    enabled: form.enabled,
  };
  try {
    if (editing.value) await fundAccountApi.update(editing.value.id, data);
    else await fundAccountApi.create(data);
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: FundAccount) {
  try {
    await ElMessageBox.confirm(`确认删除账户「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await fundAccountApi.remove(row.id);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}

function yuan(fen: number) {
  return (fen / 100).toFixed(2);
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增资金账户</el-button>
    </div>
    <PagTable ref="table" :fetcher="fundAccountApi.list">
      <el-table-column prop="name" label="账户名称" />
      <el-table-column prop="channel_name" label="所属渠道" width="140" />
      <el-table-column prop="account_no" label="商户号/账号" width="160" />
      <el-table-column prop="start_date" label="启用日期" width="120" />
      <el-table-column label="启用余额（元）" width="140" align="right">
        <template #default="{ row }">{{ yuan(row.start_balance) }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "启用" : "停用" }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑资金账户' : '新增资金账户'" width="480px">
      <el-form label-width="100px">
        <el-form-item label="所属渠道">
          <el-select v-model="form.channel" placeholder="选择渠道">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="账户名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="商户号/账号"><el-input v-model="form.account_no" /></el-form-item>
        <el-form-item label="启用日期">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="启用余额（元）">
          <el-input-number v-model="form.start_balance_yuan" :precision="2" :min="0" />
        </el-form-item>
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
