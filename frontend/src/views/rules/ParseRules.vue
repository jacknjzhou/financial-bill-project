<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { parseRuleApi } from "../../api/rules";
import type { ParseRule } from "../../api/rules";

const STANDARD_FIELDS = [
  "order_no", "pay_no", "channel_order_no", "channel", "account",
  "biz_type", "fee_item", "amount", "fee_amount", "actual_amount",
  "status", "tx_time", "settle_date",
];

const table = ref<InstanceType<typeof PagTable>>();
const dialogOpen = ref(false);
const editing = ref<ParseRule | null>(null);

const form = reactive<ParseRule>({
  name: "",
  target: "clearing",
  file_format: "csv",
  encoding: "utf-8-sig",
  delimiter: ",",
  header_row: 1,
  column_map: {},
  value_maps: {},
  amount_scale: 100,
  time_format: "%Y-%m-%d %H:%M:%S",
});

// 列映射动态编辑器：[{列名, 标准字段}]
const mapRows = ref<Array<{ col: string; field: string }>>([]);
// 值映射编辑器：[{字段, 文件值, 标准值}]
const mapValueRows = ref<Array<{ field: string; from: string; to: string }>>([]);

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    name: "", target: "clearing", file_format: "csv", encoding: "utf-8-sig",
    delimiter: ",", header_row: 1, column_map: {}, value_maps: {},
    amount_scale: 100, time_format: "%Y-%m-%d %H:%M:%S",
  });
  mapRows.value = [{ col: "", field: "" }];
  mapValueRows.value = [];
  dialogOpen.value = true;
}

function openEdit(row: ParseRule) {
  editing.value = row;
  Object.assign(form, JSON.parse(JSON.stringify(row)));
  mapRows.value = Object.entries(row.column_map || {})
    .filter(([col]) => col)
    .map(([col, field]) => ({ col, field }));
  mapValueRows.value = Object.entries(row.value_maps || {}).flatMap(([field, mapping]) =>
    Object.entries(mapping || {}).map(([from, to]) => ({ field, from, to: String(to) })),
  );
  dialogOpen.value = true;
}

async function submit() {
  const cm: Record<string, string> = {};
  for (const r of mapRows.value) if (r.col && r.field) cm[r.col] = r.field;
  form.column_map = cm;
  if (Object.keys(cm).length === 0) {
    ElMessage.warning("至少映射一个字段");
    return;
  }
  const vm: Record<string, Record<string, string>> = {};
  for (const r of mapValueRows.value) {
    if (!r.field || !r.from) continue;
    (vm[r.field] ??= {})[r.from] = r.to;
  }
  form.value_maps = vm;
  try {
    if (editing.value?.id) await parseRuleApi.update(editing.value.id, { ...form });
    else await parseRuleApi.create({ ...form });
    ElMessage.success("已保存");
    dialogOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "保存失败");
  }
}

async function remove(row: ParseRule) {
  try {
    await ElMessageBox.confirm(`确认删除解析规则「${row.name}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await parseRuleApi.remove(row.id!);
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "删除失败");
  }
}

const TARGET_LABEL: Record<string, string> = { payment: "自有支付", clearing: "渠道清算", settlement: "渠道结算" };
const FORMAT_LABEL: Record<string, string> = { xlsx: "Excel", csv: "CSV", txt: "TXT" };
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增解析规则</el-button>
    </div>
    <PagTable ref="table" :fetcher="parseRuleApi.list">
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column label="目标表" width="110">
        <template #default="{ row }">{{ TARGET_LABEL[row.target] ?? row.target }}</template>
      </el-table-column>
      <el-table-column label="格式" width="80">
        <template #default="{ row }">{{ FORMAT_LABEL[row.file_format] ?? row.file_format }}</template>
      </el-table-column>
      <el-table-column label="列映射" show-overflow-tooltip>
        <template #default="{ row }">
          {{ Object.entries(row.column_map || {}).filter(([k]) => k).map(([k, v]) => `${k}→${v}`).join("；") }}
        </template>
      </el-table-column>
      <el-table-column prop="amount_scale" label="金额进制" width="90" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="dialogOpen" :title="editing ? '编辑解析规则' : '新增解析规则'" width="860px" top="4vh">
      <el-form label-width="100px">
        <el-row :gutter="12">
          <el-col :span="8"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="8">
            <el-form-item label="目标表">
              <el-select v-model="form.target">
                <el-option label="自有支付" value="payment" />
                <el-option label="渠道清算" value="clearing" />
                <el-option label="渠道结算" value="settlement" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="文件格式">
              <el-select v-model="form.file_format">
                <el-option label="Excel" value="xlsx" />
                <el-option label="CSV" value="csv" />
                <el-option label="TXT" value="txt" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="编码">
              <el-select v-model="form.encoding" filterable allow-create>
                <el-option label="UTF-8 (BOM)" value="utf-8-sig" />
                <el-option label="GBK" value="gbk" />
                <el-option label="GB18030" value="gb18030" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="分隔符"><el-input v-model="form.delimiter" placeholder=", 或 \t" /></el-form-item>
          </el-col>
          <el-col :span="8"><el-form-item label="表头行号"><el-input-number v-model="form.header_row" :min="1" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="金额进制"><el-input-number v-model="form.amount_scale" :min="1" /></el-form-item>
          </el-col>
          <el-col :span="16"><el-form-item label="时间格式"><el-input v-model="form.time_format" placeholder="%Y-%m-%d %H:%M:%S" /></el-form-item></el-col>
        </el-row>

        <el-divider content-position="left">列映射（文件列名 → 标准字段；留空忽略）</el-divider>
        <div v-for="(r, i) in mapRows" :key="i" class="map-row">
          <el-input v-model="r.col" placeholder="文件列名，如 商户单号" class="w320" />
          <span class="arrow">→</span>
          <el-select v-model="r.field" placeholder="标准字段" class="w200" filterable>
            <el-option v-for="f in STANDARD_FIELDS" :key="f" :label="f" :value="f" />
          </el-select>
          <el-button link type="danger" @click="mapRows.splice(i, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="mapRows.push({ col: '', field: '' })">+ 加一行</el-button>

        <el-divider content-position="left">值映射（状态 / 业务类型归一化）</el-divider>
        <div v-for="(r, i) in mapValueRows" :key="'v' + i" class="map-row">
          <el-select v-model="r.field" placeholder="字段" class="w200" filterable>
            <el-option v-for="f in STANDARD_FIELDS" :key="f" :label="f" :value="f" />
          </el-select>
          <el-input v-model="r.from" placeholder="文件值，如 成功" class="w200" />
          <span class="arrow">→</span>
          <el-input v-model="r.to" placeholder="标准值，如 SUCCESS" class="w200" />
          <el-button link type="danger" @click="mapValueRows.splice(i, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="mapValueRows.push({ field: 'status', from: '', to: '' })">+ 加一行</el-button>
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
.map-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.arrow { color: #909399; }
.w200 { width: 200px; }
.w320 { width: 320px; }
</style>
