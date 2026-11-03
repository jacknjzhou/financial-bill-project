<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { fetchTaskApi, parseRuleApi } from "../../api/rules";
import type { FetchTask, ParseRule } from "../../api/rules";
import { channelApi, fundAccountApi } from "../../api/meta";
import type { Channel, FundAccount } from "../../api/types";

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<FetchTask | null>(null);

const rules = ref<ParseRule[]>([]);
const channels = ref<Channel[]>([]);
const accounts = ref<FundAccount[]>([]);

const form = reactive<FetchTask>({
  name: "",
  side: "platform",
  channel: null,
  account: null,
  parse_rule: 0,
  mode: "manual_upload",
});

onMounted(async () => {
  // 下拉数据源（页容量放大一次拉全）
  const [r, c, a] = await Promise.all([
    parseRuleApi.list(1, 200),
    channelApi.list(1, 200),
    fundAccountApi.list(1, 200),
  ]);
  rules.value = r.items;
  channels.value = c.items;
  accounts.value = a.items;
});

function openCreate() {
  editing.value = null;
  Object.assign(form, { name: "", side: "platform", channel: null, account: null, parse_rule: rules.value[0]?.id ?? 0, mode: "manual_upload" });
  dialogOpen.value = true;
}

function openEdit(row: FetchTask) {
  editing.value = row;
  Object.assign(form, JSON.parse(JSON.stringify(row)));
  dialogOpen.value = true;
}

function onSideChange() {
  if (form.side === "platform") {
    form.channel = null;
    form.account = null;
  }
}

async function submit() {
  if (!form.name) return ElMessage.warning("请填写名称");
  if (!form.parse_rule) return ElMessage.warning("请选择解析规则");
  if (form.side === "channel" && !form.channel) return ElMessage.warning("渠道侧任务必须选择渠道");
  try {
    if (editing.value?.id) await fetchTaskApi.update(editing.value.id, { ...form });
    else await fetchTaskApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: FetchTask) {
  try {
    await ElMessageBox.confirm(`确认删除获取任务「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await fetchTaskApi.remove(row.id!);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}

const SIDE_LABEL: Record<string, string> = { platform: "自有平台", channel: "渠道" };
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增获取任务</el-button>
    </div>
    <PagTable ref="table" :fetcher="fetchTaskApi.list">
      <el-table-column prop="name" label="名称" width="200" />
      <el-table-column label="侧别" width="100">
        <template #default="{ row }">
          <el-tag :type="row.side === 'platform' ? 'primary' : 'warning'">{{ SIDE_LABEL[row.side] ?? row.side }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="channel_name" label="渠道" width="140">
        <template #default="{ row }">{{ row.channel_name ?? "—" }}</template>
      </el-table-column>
      <el-table-column prop="account_name" label="资金账户" width="160">
        <template #default="{ row }">{{ row.account_name ?? "—" }}</template>
      </el-table-column>
      <el-table-column prop="parse_rule_name" label="解析规则" min-width="160" />
      <el-table-column prop="mode" label="方式" width="110">
        <template #default="{ row }">{{ row.mode === "manual_upload" ? "手工上传" : row.mode }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑获取任务' : '新增获取任务'" width="560px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="form.name" placeholder="如 微信支付-清算文件" /></el-form-item>
        <el-form-item label="侧别">
          <el-radio-group v-model="form.side" @change="onSideChange">
            <el-radio-button value="platform">自有平台</el-radio-button>
            <el-radio-button value="channel">渠道</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.side === 'channel'" label="渠道">
          <el-select v-model="form.channel" placeholder="选择渠道" class="wfull">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id!" />
          </el-select>
        </el-form-item>
        <el-form-item label="资金账户">
          <el-select v-model="form.account" placeholder="可选（结算对账用）" class="wfull" clearable>
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id!" />
          </el-select>
        </el-form-item>
        <el-form-item label="解析规则">
          <el-select v-model="form.parse_rule" class="wfull">
            <el-option v-for="r in rules" :key="r.id" :label="`${r.name}（${r.target}）`" :value="r.id!" />
          </el-select>
        </el-form-item>
        <el-form-item label="获取方式">
          <el-tag>手工上传（一期）</el-tag>
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
.wfull { width: 100%; }
</style>
