<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { dashboardApi } from "../api/dashboard";
import type { AlertRow, Overview } from "../api/dashboard";

const STATUS_LABEL: Record<string, string> = { pending: "待执行", running: "执行中", success: "成功", failed: "失败" };
const STATUS_TYPE: Record<string, string> = { pending: "info", running: "warning", success: "success", failed: "danger" };

const router = useRouter();
const overview = ref<Overview | null>(null);
const alertsOpen = ref(false);
const alerts = ref<AlertRow[]>([]);
let timer: number | undefined;

async function load() {
  overview.value = await dashboardApi.overview();
}

async function openAlerts() {
  alerts.value = await dashboardApi.alerts(true);
  alertsOpen.value = true;
}

async function markAllRead() {
  await dashboardApi.markRead();
  alerts.value = await dashboardApi.alerts(true);
  await load();
}

async function rerunFailed(run: { project: number; project_name: string; reconcile_date: string }) {
  const { default: http } = await import("../api/client");
  try {
    await http.post(`/reconcile-projects/${run.project}/runs`, { date: run.reconcile_date, rerun: true });
    await load();
  } catch (e) {
    const msg = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "触发失败";
    alert(msg);
  }
}

onMounted(() => {
  void load();
  timer = window.setInterval(load, 15000);
});
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <div v-if="overview">
    <div class="cards">
      <el-card class="card">
        <div class="card-title">对账日期 {{ overview.reconcile_date }}</div>
        <el-tag
          v-for="run in overview.runs"
          :key="run.id"
          :type="(STATUS_TYPE as Record<string, any>)[run.status] ?? 'info'"
          class="run-tag"
          @click="router.push('/runs')"
        >
          {{ run.project_name }}·{{ STATUS_LABEL[run.status] }}
        </el-tag>
        <div v-if="!overview.runs.length" class="muted">今日暂无运行记录</div>
      </el-card>
      <el-card class="card clickable" @click="router.push('/disputes')">
        <div class="card-title">待处理差异</div>
        <div class="big" :class="{ warn: overview.pending_disputes > 0 }">{{ overview.pending_disputes }}</div>
      </el-card>
      <el-card class="card clickable" @click="openAlerts">
        <div class="card-title">未读告警</div>
        <div class="big" :class="{ warn: overview.alerts_unread > 0 }">{{ overview.alerts_unread }}</div>
      </el-card>
    </div>

    <el-card>
      <template #header>最近失败运行</template>
      <el-table :data="overview.failed_runs" border size="small">
        <el-table-column prop="project_name" label="项目" min-width="140" />
        <el-table-column prop="reconcile_date" label="对账日期" width="110" />
        <el-table-column prop="error" label="失败原因" min-width="260" show-overflow-tooltip />
        <el-table-column prop="triggered_by_name" label="触发人" width="100" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="rerunFailed(row)">重跑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!overview.failed_runs.length" description="暂无失败运行" :image-size="60" />
    </el-card>

    <el-drawer v-model="alertsOpen" title="告警" size="440px">
      <div class="alert-actions">
        <el-button size="small" @click="markAllRead">全部标为已读</el-button>
      </div>
      <div v-for="a in alerts" :key="a.id" class="alert-item">
        <el-tag :type="a.kind === 'failed' ? 'danger' : 'warning'" size="small">
          {{ a.kind === "failed" ? "失败" : "差异" }}
        </el-tag>
        <span class="alert-msg">{{ a.message }}</span>
        <span class="alert-time">{{ a.created_at?.slice(0, 19).replace("T", " ") }}</span>
      </div>
      <el-empty v-if="!alerts.length" description="暂无告警" :image-size="60" />
    </el-drawer>
  </div>
</template>

<style scoped>
.cards { display: flex; gap: 16px; margin-bottom: 16px; }
.card { flex: 1; }
.card-title { font-weight: 600; margin-bottom: 8px; }
.big { font-size: 34px; font-weight: 700; }
.warn { color: #e6a23c; }
.muted { color: #909399; font-size: 13px; }
.run-tag { margin-right: 8px; cursor: pointer; }
.clickable { cursor: pointer; }
.alert-actions { margin-bottom: 10px; }
.alert-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 8px; }
.alert-msg { flex: 1; font-size: 13px; }
.alert-time { font-size: 12px; color: #909399; }
</style>
