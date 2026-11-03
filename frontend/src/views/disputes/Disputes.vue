<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { projectApi } from "../../api/rules";
import type { ReconcileProject } from "../../api/rules";
import { disputeApi } from "../../api/disputes";
import type { DisputeRow, HandleLogRow } from "../../api/disputes";
import { http } from "../../api/client";

const TYPE_LABEL: Record<string, string> = { one_a: "单边A", one_b: "单边B", wrong: "错账" };
const TYPE_TAG: Record<string, string> = { one_a: "warning", one_b: "warning", wrong: "danger" };
const STATUS_LABEL: Record<string, string> = { open: "待处理", processing: "处理中", closed: "已处理" };
const STATUS_TYPE: Record<string, string> = { open: "danger", processing: "warning", closed: "success" };
const ACTION_LABEL: Record<string, string> = {
  registered: "登记",
  processing: "转处理中",
  handled: "处理完成",
  reopened: "重对刷新",
  closed_by_rerun: "重对后保留",
};

const table = ref<InstanceType<typeof PagTable>>();
const projects = ref<ReconcileProject[]>([]);
const fProject = ref<number | undefined>();
const fDate = ref("");
const fStatus = ref("");
const fType = ref("");

const handleOpen = ref(false);
const current = ref<DisputeRow | null>(null);
const handleForm = reactive({ dispute_type_id: 0, remark: "", to_processing: false });
const disputeTypes = ref<Array<{ id: number; name: string; description: string }>>([]);

const logsOpen = ref(false);
const logs = ref<HandleLogRow[]>([]);

onMounted(async () => {
  const [p, t] = await Promise.all([
    projectApi.list(1, 200),
    httpGetDisputeTypes(),
  ]);
  projects.value = p.items;
  disputeTypes.value = t;
});

async function httpGetDisputeTypes() {
  const r = await http.get<{ items: Array<{ id: number; name: string; description: string }> }>("/dispute-types", { params: { page: 1, page_size: 100 } });
  return r.data.items.filter((x) => x.name); // 仅交易组（一期差异均为交易型）
}

function openHandle(row: DisputeRow) {
  current.value = row;
  handleForm.dispute_type_id = disputeTypes.value[0]?.id ?? 0;
  handleForm.remark = "";
  handleForm.to_processing = false;
  handleOpen.value = true;
}

async function submitHandle() {
  if (!current.value) return;
  if (!handleForm.remark.trim()) {
    ElMessage.warning("处理备注为必填项");
    return;
  }
  try {
    await disputeApi.handle(current.value.id, { ...handleForm });
    ElMessage.success("已提交");
    handleOpen.value = false;
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "提交失败");
  }
}

async function openLogs(row: DisputeRow) {
  logs.value = (await disputeApi.logs(row.id)).items;
  logsOpen.value = true;
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-select v-model="fProject" placeholder="全部项目" clearable class="w220" @change="table?.reload()">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id!" />
      </el-select>
      <el-date-picker v-model="fDate" type="date" value-format="YYYY-MM-DD" placeholder="对账日期" class="w160" @change="table?.reload()" />
      <el-select v-model="fStatus" placeholder="全部状态" clearable class="w130" @change="table?.reload()">
        <el-option v-for="(l, k) in STATUS_LABEL" :key="k" :label="l" :value="k" />
      </el-select>
      <el-select v-model="fType" placeholder="全部类型" clearable class="w130" @change="table?.reload()">
        <el-option v-for="(l, k) in TYPE_LABEL" :key="k" :label="l" :value="k" />
      </el-select>
    </div>

    <PagTable
      ref="table"
      :fetcher="(p: number, s: number) => disputeApi.list({ page: p, page_size: s, project: fProject, reconcile_date: fDate || undefined, status: fStatus || undefined, type: fType || undefined })"
    >
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
      <el-table-column prop="project_name" label="项目" min-width="140" />
      <el-table-column prop="order_no" label="单号" min-width="160" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="(TYPE_TAG as Record<string, any>)[row.type]">{{ TYPE_LABEL[row.type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="金额（元）" width="110" align="right">
        <template #default="{ row }">{{ row.amount_yuan }}</template>
      </el-table-column>
      <el-table-column label="状态" width="95">
        <template #default="{ row }">
          <el-tag :type="(STATUS_TYPE as Record<string, any>)[row.status]">{{ STATUS_LABEL[row.status] }}</el-tag>
          <el-tag v-if="row.superseded" type="info" size="small" class="ml4">已覆盖</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="dispute_type_name" label="SOP" width="110" />
      <el-table-column prop="handler_name" label="处理人" width="100" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'closed'" link type="primary" @click="openHandle(row)">处理</el-button>
          <el-button link type="info" @click="openLogs(row)">留痕</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="handleOpen" title="处理差异（按 SOP）" width="560px">
      <el-form label-width="110px" v-if="current">
        <el-form-item label="差异">{{ TYPE_LABEL[current.type] }} · {{ current.order_no }} · {{ current.amount_yuan }} 元</el-form-item>
        <el-form-item label="处理类型（SOP）">
          <el-select v-model="handleForm.dispute_type_id" class="wfull">
            <el-option v-for="t in disputeTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <div class="sop-desc">{{ disputeTypes.find((t) => t.id === handleForm.dispute_type_id)?.description }}</div>
        </el-form-item>
        <el-form-item label="仅转处理中">
          <el-switch v-model="handleForm.to_processing" />
        </el-form-item>
        <el-form-item label="备注（必填）">
          <el-input v-model="handleForm.remark" type="textarea" :rows="3" placeholder="处理说明、依据、渠道截图编号等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleOpen = false">取消</el-button>
        <el-button type="primary" @click="submitHandle">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="logsOpen" title="处理留痕（时间线）" size="420px">
      <el-timeline>
        <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="log.created_at?.slice(0, 19).replace('T', ' ')">
          <div class="log-action">{{ ACTION_LABEL[log.action] ?? log.action }}（{{ log.operator_name || "系统" }}）</div>
          <div v-if="log.remark" class="log-remark">{{ log.remark }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 12px; }
.w130 { width: 130px; }
.w160 { width: 160px; }
.w220 { width: 220px; }
.wfull { width: 100%; }
.ml4 { margin-left: 4px; }
.sop-desc { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.5; }
.log-action { font-weight: 600; font-size: 13px; }
.log-remark { font-size: 12px; color: #6b7280; margin-top: 2px; }
</style>
