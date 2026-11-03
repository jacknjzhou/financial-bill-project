<script setup lang="ts">
import { ref } from "vue";
import PagTable from "../../components/PagTable.vue";
import { clearingsApi, paymentsApi, settlementsApi } from "../../api/dataio";
import type { ClearingRow, PaymentRow, SettlementRow } from "../../api/dataio";

const tab = ref<"payments" | "clearings" | "settlements">("payments");
const fDate = ref("");
const fNo = ref("");
const fStatus = ref("");
const table = ref<InstanceType<typeof PagTable>>();

function doSearch() {
  table.value?.reload();
}

function params(p: number, s: number) {
  const q: Record<string, string | number> = { page: p, page_size: s };
  if (fDate.value) q.reconcile_date = fDate.value;
  if (fStatus.value) q.status = fStatus.value;
  if (fNo.value) {
    if (tab.value === "clearings") q.channel_order_no = fNo.value;
    else q.order_no = fNo.value;
  }
  return q;
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-tabs v-model="tab" @tab-change="doSearch">
        <el-tab-pane label="自有支付" name="payments" />
        <el-tab-pane label="渠道清算" name="clearings" />
        <el-tab-pane label="渠道结算" name="settlements" />
      </el-tabs>
    </div>
    <div class="filters">
      <el-date-picker v-model="fDate" type="date" value-format="YYYY-MM-DD" placeholder="对账日期" class="w160" clearable />
      <el-input v-model="fNo" placeholder="单号（模糊）" class="w220" clearable @keyup.enter="doSearch" />
      <el-input v-model="fStatus" placeholder="状态，如 SUCCESS" class="w180" clearable @keyup.enter="doSearch" />
      <el-button type="primary" @click="doSearch">查询</el-button>
    </div>

    <PagTable v-if="tab === 'payments'" ref="table" :fetcher="(p: number, s: number) => paymentsApi.list(params(p, s))">
      <el-table-column prop="order_no" label="商户单号" width="200" />
      <el-table-column prop="pay_no" label="支付单号" width="180" />
      <el-table-column prop="channel_name" label="渠道" width="120" />
      <el-table-column prop="biz_type_code" label="业务类型" width="110" />
      <el-table-column label="金额（元）" width="120" align="right">
        <template #default="{ row }">{{ row.amount_yuan }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'SUCCESS' ? 'success' : 'danger'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="tx_time" label="交易时间" min-width="170">
        <template #default="{ row }">{{ (row.tx_time || "").slice(0, 19).replace("T", " ") }}</template>
      </el-table-column>
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
    </PagTable>

    <PagTable v-else-if="tab === 'clearings'" ref="table" :fetcher="(p: number, s: number) => clearingsApi.list(params(p, s))">
      <el-table-column prop="channel_order_no" label="渠道单号" width="200" />
      <el-table-column prop="order_no" label="商户单号" width="200" />
      <el-table-column prop="channel_name" label="渠道" width="120" />
      <el-table-column label="金额（元）" width="120" align="right">
        <template #default="{ row }">{{ row.amount_yuan }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="tx_time" label="交易时间" min-width="170">
        <template #default="{ row }">{{ (row.tx_time || "").slice(0, 19).replace("T", " ") }}</template>
      </el-table-column>
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
    </PagTable>

    <PagTable v-else ref="table" :fetcher="(p: number, s: number) => settlementsApi.list(params(p, s))">
      <el-table-column prop="fee_item" label="费用项" min-width="160" />
      <el-table-column label="金额（元）" width="120" align="right">
        <template #default="{ row: r }: { row: SettlementRow }">{{ (r.amount / 100).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="手续费（元）" width="130" align="right">
        <template #default="{ row: r }: { row: SettlementRow }">{{ r.fee_amount != null ? (r.fee_amount / 100).toFixed(2) : "—" }}</template>
      </el-table-column>
      <el-table-column label="实收（元）" width="120" align="right">
        <template #default="{ row: r }: { row: SettlementRow }">{{ r.actual_amount != null ? (r.actual_amount / 100).toFixed(2) : "—" }}</template>
      </el-table-column>
      <el-table-column prop="settle_date" label="结算日期" width="110" />
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
    </PagTable>
  </div>
</template>

<style scoped>
.toolbar { margin-bottom: 4px; }
.filters { display: flex; gap: 10px; margin-bottom: 12px; }
.w160 { width: 160px; }
.w180 { width: 180px; }
.w220 { width: 220px; }
</style>
