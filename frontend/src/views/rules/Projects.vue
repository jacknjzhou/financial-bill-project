<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { projectApi } from "../../api/rules";
import type { FilterCond, ReconcileProject } from "../../api/rules";

const STANDARD_FIELDS = [
  "order_no", "pay_no", "channel_order_no", "channel", "account",
  "biz_type", "fee_item", "amount", "fee_amount", "actual_amount",
  "status", "tx_time", "settle_date",
];

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<ReconcileProject | null>(null);

const form = reactive<ReconcileProject>({
  name: "",
  type: "transaction",
  a_source: "payment",
  a_filter: [],
  b_source: "clearing",
  b_filter: [],
  match_key: "order_no",
  a_status_set: ["SUCCESS"],
  b_status_set: ["SUCCESS"],
  b_sum: false,
  start_date: "",
  exec_time: "02:00:00",
  enabled: true,
});

// 类型 → 允许的 A/B 数据源组合（与后端 serializer 校验一致）
const COMBOS: Record<string, Array<[string, string]>> = {
  transaction: [["payment", "clearing"]],
  fund: [["clearing", "settlement"]],
  balance: [],
};
const SOURCE_LABEL: Record<string, string> = {
  payment: "自有支付",
  clearing: "渠道清算",
  settlement: "渠道结算",
};
const TYPE_LABEL: Record<string, string> = {
  transaction: "交易对账",
  fund: "资金对账",
  balance: "余额调节",
};

const aOptions = computed(() => [...new Set((COMBOS[form.type] ?? []).map(([a]) => a))]);
const bOptions = computed(() => [...new Set((COMBOS[form.type] ?? []).map(([, b]) => b))]);

function onTypeChange() {
  const combo = COMBOS[form.type]?.[0];
  if (combo) {
    form.a_source = combo[0];
    form.b_source = combo[1];
  }
}

// 筛选条件编辑器
const aFilterRows = ref<FilterCond[]>([]);
const bFilterRows = ref<FilterCond[]>([]);
// 状态集编辑器（动态标签）
const aStatusInput = ref("");
const bStatusInput = ref("");

function addStatus(side: "a" | "b") {
  const v = (side === "a" ? aStatusInput : bStatusInput).value.trim();
  if (!v) return;
  const set = side === "a" ? form.a_status_set : form.b_status_set;
  if (!set!.includes(v)) set!.push(v);
  (side === "a" ? aStatusInput : bStatusInput).value = "";
}

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    name: "", type: "transaction", a_source: "payment", a_filter: [], b_source: "clearing",
    b_filter: [], match_key: "order_no", a_status_set: ["SUCCESS"], b_status_set: ["SUCCESS"],
    b_sum: false, start_date: "", exec_time: "02:00:00", enabled: true,
  });
  aFilterRows.value = [];
  bFilterRows.value = [];
  dialogOpen.value = true;
}

function openEdit(row: ReconcileProject) {
  editing.value = row;
  Object.assign(form, JSON.parse(JSON.stringify(row)));
  aFilterRows.value = [...(row.a_filter || [])];
  bFilterRows.value = [...(row.b_filter || [])];
  dialogOpen.value = true;
}

async function submit() {
  if (!form.name) return ElMessage.warning("请填写名称");
  if (!form.start_date) return ElMessage.warning("请选择启用日期");
  form.a_filter = aFilterRows.value.filter((r) => r.field && r.value !== "");
  form.b_filter = bFilterRows.value.filter((r) => r.field && r.value !== "");
  try {
    if (editing.value?.id) await projectApi.update(editing.value.id, { ...form });
    else await projectApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: ReconcileProject) {
  try {
    await ElMessageBox.confirm(`确认删除对账项目「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await projectApi.remove(row.id!);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增对账项目</el-button>
    </div>
    <PagTable ref="table" :fetcher="projectApi.list">
      <el-table-column prop="name" label="名称" width="200" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }"><el-tag>{{ TYPE_LABEL[row.type] ?? row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column label="A/B 数据源" width="160">
        <template #default="{ row }">
          {{ SOURCE_LABEL[row.a_source] ?? row.a_source }} / {{ SOURCE_LABEL[row.b_source] ?? row.b_source }}
        </template>
      </el-table-column>
      <el-table-column prop="match_key" label="匹配键" width="140" />
      <el-table-column label="状态集" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">A: {{ (row.a_status_set || []).join(",") || "—" }}；B: {{ (row.b_status_set || []).join(",") || "—" }}</template>
      </el-table-column>
      <el-table-column label="B 汇总" width="80">
        <template #default="{ row }">{{ row.b_sum ? "是" : "否" }}</template>
      </el-table-column>
      <el-table-column prop="start_date" label="启用日期" width="110" />
      <el-table-column prop="last_date" label="最后对账日" width="110">
        <template #default="{ row }">{{ row.last_date ?? "—" }}</template>
      </el-table-column>
      <el-table-column prop="exec_time" label="执行时间" width="90" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑对账项目' : '新增对账项目'" width="860px" top="4vh">
      <el-form label-width="110px">
        <el-row :gutter="12">
          <el-col :span="8"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="8">
            <el-form-item label="类型">
              <el-select v-model="form.type" @change="onTypeChange" :disabled="!!editing">
                <el-option label="交易对账" value="transaction" />
                <el-option label="资金对账" value="fund" />
                <el-option label="余额调节（二期）" value="balance" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="匹配键">
              <el-select v-model="form.match_key" filterable>
                <el-option v-for="f in STANDARD_FIELDS" :key="f" :label="f" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="A 方数据源">
              <el-select v-model="form.a_source">
                <el-option v-for="s in aOptions" :key="s" :label="SOURCE_LABEL[s]" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="B 方数据源">
              <el-select v-model="form.b_source">
                <el-option v-for="s in bOptions" :key="s" :label="SOURCE_LABEL[s]" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="B 方汇总">
              <el-switch v-model="form.b_sum" active-text="同键多行求和" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="启用日期">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" class="wfull" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="每日执行">
              <el-time-select v-model="form.exec_time" start="00:00" step="00:30" end="23:30" class="wfull" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">A 方期望状态集（命中则视为状态正常）</el-divider>
        <div class="status-row">
          <el-tag v-for="s in form.a_status_set" :key="s" closable @close="form.a_status_set = form.a_status_set.filter((x) => x !== s)">{{ s }}</el-tag>
          <el-input v-model="aStatusInput" placeholder="如 SUCCESS 回车添加" class="w220" size="small" @keyup.enter="addStatus('a')" />
        </div>

        <el-divider content-position="left">B 方期望状态集</el-divider>
        <div class="status-row">
          <el-tag v-for="s in form.b_status_set" :key="s" closable type="warning" @close="form.b_status_set = form.b_status_set.filter((x) => x !== s)">{{ s }}</el-tag>
          <el-input v-model="bStatusInput" placeholder="如 SUCCESS 回车添加" class="w220" size="small" @keyup.enter="addStatus('b')" />
        </div>

        <el-divider content-position="left">A 方筛选条件（只对满足条件的记录参与对账）</el-divider>
        <div v-for="(r, i) in aFilterRows" :key="'af' + i" class="filter-row">
          <el-select v-model="r.field" placeholder="字段" class="w200" filterable>
            <el-option v-for="f in STANDARD_FIELDS" :key="f" :label="f" :value="f" />
          </el-select>
          <el-select v-model="r.op" class="w100">
            <el-option label="=" value="eq" />
            <el-option label="≠" value="neq" />
            <el-option label="∈" value="in" />
          </el-select>
          <el-input v-model="r.value" placeholder="值（in 用逗号分隔）" class="w260" />
          <el-button link type="danger" @click="aFilterRows.splice(i, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="aFilterRows.push({ field: '', op: 'eq', value: '' })">+ 加一行</el-button>

        <el-divider content-position="left">B 方筛选条件</el-divider>
        <div v-for="(r, i) in bFilterRows" :key="'bf' + i" class="filter-row">
          <el-select v-model="r.field" placeholder="字段" class="w200" filterable>
            <el-option v-for="f in STANDARD_FIELDS" :key="f" :label="f" :value="f" />
          </el-select>
          <el-select v-model="r.op" class="w100">
            <el-option label="=" value="eq" />
            <el-option label="≠" value="neq" />
            <el-option label="∈" value="in" />
          </el-select>
          <el-input v-model="r.value" placeholder="值（in 用逗号分隔）" class="w260" />
          <el-button link type="danger" @click="bFilterRows.splice(i, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="bFilterRows.push({ field: '', op: 'eq', value: '' })">+ 加一行</el-button>
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
.status-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.filter-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.w100 { width: 100px; }
.w200 { width: 200px; }
.w220 { width: 220px; }
.w260 { width: 260px; }
.wfull { width: 100%; }
</style>
