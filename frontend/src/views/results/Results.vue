<script setup lang="ts">
import { onMounted, ref } from "vue";
import PagTable from "../../components/PagTable.vue";
import { projectApi } from "../../api/rules";
import type { ReconcileProject } from "../../api/rules";
import { resultApi } from "../../api/results";
import type { ReconcileResultRow, ResultDetail } from "../../api/results";

const STATUS_LABEL: Record<string, string> = {
  match: "对平",
  one_a: "单边A",
  one_b: "单边B",
  wrong: "错账",
};
const STATUS_TYPE: Record<string, string> = {
  match: "success",
  one_a: "warning",
  one_b: "warning",
  wrong: "danger",
};
const DIFF_LABEL: Record<string, string> = { none: "—", amount: "金额差", status: "状态不符", both: "金额+状态" };

const table = ref<InstanceType<typeof PagTable>>();
const projects = ref<ReconcileProject[]>([]);
const selectedProject = ref<number | undefined>();
const fDate = ref("");
const fStatus = ref("");
const detailOpen = ref(false);
const detail = ref<ResultDetail | null>(null);

onMounted(async () => {
  const r = await projectApi.list(1, 200);
  projects.value = r.items;
});

async function openDetail(row: ReconcileResultRow) {
  detail.value = await resultApi.get(row.id);
  detailOpen.value = true;
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && /amount/.test("")) return String(v);
  return String(v);
}

const A_FIELDS = ["order_no", "pay_no", "amount_yuan", "amount", "status", "tx_time", "reconcile_date", "biz_type"];
const B_FIELDS = ["channel_order_no", "order_no", "amount_yuan", "amount", "status", "tx_time", "reconcile_date"];
</script>

<template>
  <div>
    <div class="toolbar">
      <el-select v-model="selectedProject" placeholder="全部项目" clearable class="w240" @change="table?.reload()">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id!" />
      </el-select>
      <el-date-picker v-model="fDate" type="date" value-format="YYYY-MM-DD" placeholder="对账日期" class="w160" @change="table?.reload()" />
      <el-select v-model="fStatus" placeholder="全部状态" clearable class="w140" @change="table?.reload()">
        <el-option v-for="(l, k) in STATUS_LABEL" :key="k" :label="l" :value="k" />
      </el-select>
    </div>

    <PagTable
      ref="table"
      :fetcher="(p: number, s: number) => resultApi.list({ page: p, page_size: s, project: selectedProject, date: fDate || undefined, status: fStatus || undefined })"
    >
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
      <el-table-column prop="project_name" label="项目" min-width="150" />
      <el-table-column prop="order_no" label="单号" min-width="170" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="(STATUS_TYPE as Record<string, any>)[row.status] ?? 'info'">{{ STATUS_LABEL[row.status] ?? row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="差异金额（元）" width="130" align="right">
        <template #default="{ row }">{{ row.diff_amount_yuan }}</template>
      </el-table-column>
      <el-table-column label="差异类型" width="100">
        <template #default="{ row }">{{ DIFF_LABEL[row.diff_type] ?? row.diff_type }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="detailOpen" title="结果明细（A/B 双方原文，聚合组取整组）" width="900px" top="4vh">
      <template v-if="detail">
        <el-descriptions :column="4" border size="small" class="mb12">
          <el-descriptions-item label="状态">
            <el-tag :type="(STATUS_TYPE as Record<string, any>)[detail.result.status]">{{ STATUS_LABEL[detail.result.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="匹配键">{{ detail.result.match_key }}</el-descriptions-item>
          <el-descriptions-item label="差异金额">{{ detail.result.diff_amount_yuan }} 元</el-descriptions-item>
          <el-descriptions-item label="差异类型">{{ DIFF_LABEL[detail.result.diff_type] }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detail.a_row" class="side">
          <div class="side-title">A 方（自有支付）</div>
          <el-table :data="[detail.a_row]" border size="small">
            <el-table-column v-for="f in A_FIELDS" :key="f" :prop="f" :label="f" min-width="110">
              <template #default="{ row }">{{ fmt(row[f]) }}</template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="detail.b_rows.length" class="side">
          <div class="side-title">B 方（渠道清算，{{ detail.b_rows.length }} 行）</div>
          <el-table :data="detail.b_rows" border size="small">
            <el-table-column v-for="f in B_FIELDS" :key="f" :prop="f" :label="f" min-width="110">
              <template #default="{ row }">{{ fmt(row[f]) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 12px; }
.w140 { width: 140px; }
.w160 { width: 160px; }
.w240 { width: 240px; }
.mb12 { margin-bottom: 12px; }
.side { margin-bottom: 12px; }
.side-title { font-weight: 600; margin-bottom: 6px; font-size: 13px; }
</style>
