<script setup lang="ts">
import { onMounted, ref } from "vue";

/**
 * 通用分页列表：父组件通过默认插槽放置 el-table-column，
 * 通过 ref 调 reload() 刷新；fetcher 返回 PageResponse 信封。
 */
const props = defineProps<{
  fetcher: (page: number, pageSize: number) => Promise<{ total: number; items: unknown[] }>;
}>();

const rows = ref<unknown[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const r = await props.fetcher(page.value, pageSize.value);
    rows.value = r.items;
    total.value = r.total;
  } finally {
    loading.value = false;
  }
}

defineExpose({ reload: load });
onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <el-table :data="rows" border stripe>
      <slot />
    </el-table>
    <el-pagination
      class="pager"
      layout="total, sizes, prev, pager, next"
      :total="total"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      @change="load"
    />
  </div>
</template>

<style scoped>
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
