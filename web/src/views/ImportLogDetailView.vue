<template>
  <div class="page">
    <el-page-header class="header" @back="router.back()">
      <template #content>
        <span class="page-title">导入明细 #{{ logId }}</span>
      </template>
    </el-page-header>

    <el-card v-if="log" shadow="never" class="block">
      <el-descriptions :column="4" border size="default">
        <el-descriptions-item label="来源文件">{{ log.source_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(log.status)" size="small" effect="light">
            {{ statusText(log.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="去重阈值">{{ log.threshold }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(log.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="题目总数">{{ log.total }}</el-descriptions-item>
        <el-descriptions-item label="成功入库">
          <span class="num ok">{{ log.imported }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="重复跳过">
          <span class="num warn">{{ log.duplicated }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="解析失败">
          <span class="num bad">{{ log.failed }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="说明" :span="4">{{ log.message || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="block">
      <el-space class="toolbar">
        <el-radio-group v-model="status" @change="reload">
          <el-radio-button value="">全部 ({{ log?.total ?? 0 }})</el-radio-button>
          <el-radio-button value="success">成功</el-radio-button>
          <el-radio-button value="duplicate">重复</el-radio-button>
          <el-radio-button value="failed">失败</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </el-space>

      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="row_index" label="#" width="70" />
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="itemType(row.status)" size="small" effect="light">
              {{ itemText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题干摘要" min-width="280">
          <template #default="{ row }">
            <span v-if="row.title_preview">{{ row.title_preview }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ muted: !row.reason }">{{ row.reason || '—' }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有符合条件的明细" />
        </template>
      </el-table>

      <el-pagination
        class="pager"
        background
        layout="total, sizes, prev, pager, next"
        :total="itemsTotal"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { importApi } from '@/api'

const route = useRoute()
const router = useRouter()

const logId = computed(() => Number(route.params.id))

const log = ref(null)
const items = ref([])
const itemsTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('')
const loading = ref(false)

function statusType(value) {
  if (value === 'success') return 'success'
  if (value === 'partial') return 'warning'
  return 'danger'
}

function statusText(value) {
  if (value === 'success') return '全部成功'
  if (value === 'partial') return '部分成功'
  return '失败'
}

function itemType(value) {
  if (value === 'success') return 'success'
  if (value === 'duplicate') return 'warning'
  return 'danger'
}

function itemText(value) {
  if (value === 'success') return '已入库'
  if (value === 'duplicate') return '重复'
  return '失败'
}

function formatTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const data = await importApi.logDetail(logId.value, {
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined,
    })
    log.value = data.log
    items.value = data.items
    itemsTotal.value = data.items_total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function onPageChange(value) {
  page.value = value
  load()
}

function onSizeChange(value) {
  pageSize.value = value
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.header {
  margin-bottom: 16px;
}

.block {
  margin-bottom: 16px;
  border-radius: 10px;
}

.toolbar {
  margin-bottom: 14px;
}

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.num.ok {
  color: #67c23a;
  font-weight: 600;
}

.num.warn {
  color: #e6a23c;
  font-weight: 600;
}

.num.bad {
  color: #f56c6c;
  font-weight: 600;
}

.muted {
  color: var(--ikao-text-sub);
}
</style>
