<template>
  <div class="page">
    <h2 class="page-title">导入日志</h2>
    <p class="page-desc">每次导入都会留下一条记录，包含成功 / 重复 / 失败的数量与逐条明细</p>

    <el-card shadow="never" class="block">
      <el-space class="toolbar">
        <el-select v-model="status" placeholder="全部状态" clearable style="width: 140px" @change="reload">
          <el-option label="全部状态" value="" />
          <el-option label="全部成功" value="success" />
          <el-option label="部分成功" value="partial" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button :icon="Refresh" @click="reload">刷新</el-button>
        <el-button type="primary" :icon="Upload" @click="router.push('/import')">去导入</el-button>
      </el-space>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column prop="source_name" label="来源文件" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="总数" width="80" align="center" />
        <el-table-column label="成功" width="80" align="center">
          <template #default="{ row }">
            <span class="num ok">{{ row.imported }}</span>
          </template>
        </el-table-column>
        <el-table-column label="重复" width="80" align="center">
          <template #default="{ row }">
            <span class="num warn">{{ row.duplicated }}</span>
          </template>
        </el-table-column>
        <el-table-column label="失败" width="80" align="center">
          <template #default="{ row }">
            <span class="num bad">{{ row.failed }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="threshold" label="阈值" width="80" align="center" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/import/logs/${row.id}`)">明细</el-button>
            <el-button link type="danger" @click="removeLog(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有导入记录" />
        </template>
      </el-table>

      <el-pagination
        class="pager"
        background
        layout="total, sizes, prev, pager, next"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Upload } from '@element-plus/icons-vue'
import { importApi } from '@/api'

const router = useRouter()

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
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

function formatTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const data = await importApi.logs({
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined,
    })
    rows.value = data.items
    total.value = data.total
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

async function removeLog(row) {
  await ElMessageBox.confirm(
    `确定删除导入日志 #${row.id} 吗？已入库的题目不受影响。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await importApi.removeLog(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.block {
  margin-top: 16px;
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
</style>
