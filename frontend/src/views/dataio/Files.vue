<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadRequestOptions } from "element-plus";
import PagTable from "../../components/PagTable.vue";
import { fetchTaskApi } from "../../api/rules";
import type { FetchTask } from "../../api/rules";
import { filesApi } from "../../api/dataio";
import type { InFile } from "../../api/dataio";

const STATUS_LABEL: Record<string, string> = {
  pending: "待解析",
  parsing: "解析中",
  parsed: "已入库",
  failed: "解析失败",
};
const STATUS_TYPE: Record<string, string> = {
  pending: "info",
  parsing: "warning",
  parsed: "success",
  failed: "danger",
};

const table = ref<InstanceType<typeof PagTable>>();
const tasks = ref<FetchTask[]>([]);
const selectedTask = ref<number | undefined>();
const detailOpen = ref(false);
const detailRow = ref<InFile | null>(null);
let pollTimer: number | undefined;

const hasActive = computed(() =>
  (table.value?.$data?.rows as InFile[] | undefined)?.some?.((r) => r.status === "parsing" || r.status === "pending"),
);

onMounted(async () => {
  const r = await fetchTaskApi.list(1, 200);
  tasks.value = r.items;
  pollTimer = window.setInterval(() => {
    // 存在解析中的记录时轻量轮询刷新
    const rows = (table.value as unknown as { $data?: { rows?: InFile[] } })?.$data?.rows ?? [];
    if (rows.some((x) => x.status === "parsing" || x.status === "pending")) table.value?.reload();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
});

async function doUpload(options: UploadRequestOptions) {
  if (!selectedTask.value) {
    ElMessage.warning("请先选择获取任务");
    return Promise.reject(new Error("no task"));
  }
  try {
    // 默认覆盖重传：当日同名文件重复上传视为替换（已被对账引用的文件由后端 409 拦截）
    const item = await filesApi.upload(selectedTask.value, options.file, true);
    ElMessage.success(`已上传：${STATUS_LABEL[item.status] ?? item.status}`);
    table.value?.reload();
  } catch (e) {
    const msg = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "上传失败";
    ElMessage.error(msg);
    return Promise.reject(e);
  }
  return options.file;
}

async function overwrite(row: InFile) {
  try {
    await ElMessageBox.confirm(
      `确认覆盖重传「${row.file_name}」？旧文件数据将被删除并重新解析（已参与对账的数据会被拒绝）。`,
      "覆盖重传",
      { type: "warning", confirmButtonText: "选择文件并覆盖" },
    );
  } catch {
    return;
  }
  const input = document.createElement("input");
  input.type = "file";
  input.onchange = async () => {
    const f = input.files?.[0];
    if (!f) return;
    try {
      const item = await filesApi.upload(row.fetch_task, f, true);
      ElMessage.success(`已覆盖：${STATUS_LABEL[item.status] ?? item.status}`);
      table.value?.reload();
    } catch (e) {
      ElMessage.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? "覆盖失败");
    }
  };
  input.click();
}

function showDetail(row: InFile) {
  detailRow.value = row;
  detailOpen.value = true;
}

function download(row: InFile) {
  window.open(filesApi.downloadUrl(row.id), "_blank");
}
</script>

<template>
  <div>
    <div class="toolbar">
      <el-select v-model="selectedTask" placeholder="选择获取任务上传…" class="w280">
        <el-option v-for="t in tasks" :key="t.id" :label="`${t.name}（${t.side === 'platform' ? '平台' : '渠道'}）`" :value="t.id!" />
      </el-select>
      <el-upload :http-request="doUpload" :show-file-list="false" accept=".xlsx,.csv,.txt,.dat">
        <el-button type="primary" :disabled="!selectedTask">上传文件</el-button>
      </el-upload>
    </div>
    <PagTable ref="table" :fetcher="(p: number, s: number) => filesApi.list({ page: p, page_size: s, fetch_task: selectedTask })">
      <el-table-column prop="file_name" label="文件名" min-width="220" />
      <el-table-column prop="fetch_task_name" label="获取任务" width="170" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="(STATUS_TYPE as Record<string, any>)[row.status] ?? 'info'">{{ STATUS_LABEL[row.status] ?? row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_rows" label="总行数" width="90" />
      <el-table-column prop="size_mb" label="大小(MB)" width="95" />
      <el-table-column prop="uploaded_by_name" label="上传人" width="110" />
      <el-table-column prop="created_at" label="上传时间" width="170">
        <template #default="{ row }">{{ (row.created_at || "").slice(0, 19).replace("T", " ") }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button v-if="row.status === 'failed'" link type="danger" @click="showDetail(row)">失败原因</el-button>
          <el-button link type="primary" @click="download(row)">下载</el-button>
          <el-button link type="warning" @click="overwrite(row)">覆盖重传</el-button>
        </template>
      </el-table-column>
    </PagTable>

    <el-dialog v-model="detailOpen" title="解析失败原因（含行号清单，最多 100 条）" width="720px">
      <pre class="err-pre">{{ detailRow?.error_msg || "（无）" }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.w280 { width: 280px; }
.err-pre { white-space: pre-wrap; max-height: 55vh; overflow: auto; font-size: 12px; line-height: 1.7; }
</style>
