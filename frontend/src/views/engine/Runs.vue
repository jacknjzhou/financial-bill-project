<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { projectApi } from "../../api/rules";
import type { ReconcileProject } from "../../api/rules";
import { runApi } from "../../api/engine";
import type { ReconcileRun } from "../../api/engine";

const STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  failed: "失败",
};
const STATUS_TYPE: Record<string, string> = {
  pending: "info",
  running: "warning",
  success: "success",
  failed: "danger",
};
const TRIGGER_LABEL: Record<string, string> = { auto: "定时", manual: "手工", rerun: "重对" };

const table = ref<InstanceType<typeof PagTable>>();
const projects = ref<ReconcileProject[]>([]);
const selectedProject = ref<number | undefined>();
const fStatus = ref("");
const runDate = ref(yesterday());
let pollTimer: number | undefined;

onMounted(async () => {
  const r = await projectApi.list(1, 200);
  projects.value = r.items;
  pollTimer = window.setInterval(() => table.value?.reload(), 5000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
});

function yesterday(): string {
  const d = new Date(Date.now() - 86400000);
  return d.toISOString().slice(0, 10);
}

async function trigger(row: ReconcileProject, rerun: boolean) {
  const date = runDate.value || yesterday();
  try {
    await ElMessageBox.confirm(
      rerun
        ? `确认重对「${row.name}」${date}？将清除该日已有结果后重新计算。`
        : `确认执行「${row.name}」${date} 的对账？`,
      "提示",
      { type: "warning" },
    );
  } catch {
    return;
  }
  try {
    await runApi.trigger(row.id!, { rerun, date });
    ElMessage.success("已触发，执行中…");
    table.value?.reload();
  } catch (e) {
    ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "触发失败");
  }
}

function showProjects() {
  return projects.value;
}

const errorOpen = ref(false);
const errorRun = ref<ReconcileRun | null>(null);

function showError(row: ReconcileRun) {
  errorRun.value = row;
  errorOpen.value = true;
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-date-picker v-model="runDate" type="date" placeholder="对账日期" value-format="YYYY-MM-DD" class="w160" />
      <el-select v-model="selectedProject" placeholder="全部项目" clearable class="w240" @change="table?.reload()">
        <el-option v-for="p in showProjects()" :key="p.id" :label="p.name" :value="p.id!" />
      </el-select>
      <el-select v-model="fStatus" placeholder="全部状态" clearable class="w160" @change="table?.reload()">
        <el-option v-for="(label, key) in STATUS_LABEL" :key="key" :label="label" :value="key" />
      </el-select>
    </div>

    <div class="actions">
      <el-button
        v-for="p in showProjects()"
        :key="p.id"
        size="small"
        @click="trigger(p, false)"
      >执行：{{ p.name }}</el-button>
    </div>

    <PagTable
      ref="table"
      :fetcher="(p: number, s: number) => runApi.list({ page: p, page_size: s, project: selectedProject, status: fStatus || undefined })"
    >
      <el-table-column prop="project_name" label="项目" min-width="160" />
      <el-table-column prop="reconcile_date" label="对账日期" width="110" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="(STATUS_TYPE as Record<string, any>)[row.status] ?? 'info'">{{ STATUS_LABEL[row.status] ?? row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="触发" width="80">
        <template #default="{ row }">{{ TRIGGER_LABEL[row.trigger] ?? row.trigger }}</template>
      </el-table-column>
      <el-table-column label="A/B 笔数" width="100" align="center">
        <template #default="{ row }">{{ row.a_total }} / {{ row.b_total }}</template>
      </el-table-column>
      <el-table-column prop="match_cnt" label="对平" width="70" align="center" />
      <el-table-column prop="one_a_cnt" label="单边A" width="75" align="center" />
      <el-table-column prop="one_b_cnt" label="单边B" width="75" align="center" />
      <el-table-column prop="wrong_cnt" label="错账" width="70" align="center" />
      <el-table-column label="起止" width="200">
        <template #default="{ row }">
          <span class="mono">{{ (row.started_at || "—").slice(11, 19) }} ~ {{ (row.finished_at || "—").slice(11, 19) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button v-if="row.status === 'failed'" link type="danger" @click="showError(row)">原因</el-button>
          <el-button link type="primary" @click="trigger({ id: row.project, name: row.project_name } as ReconcileProject, true)">重对</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="errorOpen" title="失败原因" width="640px">
      <pre class="err-pre">{{ errorRun?.error || "（无）" }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 12px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.w160 { width: 160px; }
.w240 { width: 240px; }
.mono { font-family: monospace; }
.err-pre { white-space: pre-wrap; max-height: 50vh; overflow: auto; font-size: 12px; }
</style>
