<!--
  SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
  SPDX-License-Identifier: MIT
-->
<template>
  <div class="page page-wide">
    <h2 class="page-title">题库管理</h2>
    <p class="page-desc">按题型、关键词检索题目，支持查看、编辑、删除与手工新增</p>

    <el-row :gutter="12" class="stat-row">
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-label">题目总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
      </el-col>
      <el-col v-for="item in QUESTION_TYPES" :key="item.value" :span="4">
        <div class="stat-card clickable" @click="filterByType(item.value)">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value" :class="`type-${item.value}`">
            {{ stats.counts[item.value] || 0 }}
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card clickable" @click="filterByType('')">
          <div class="stat-label">当前筛选结果</div>
          <div class="stat-value">{{ total }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="block">
      <el-space wrap class="toolbar">
        <el-select v-model="query.type" placeholder="全部题型" clearable style="width: 130px" @change="reload">
          <el-option v-for="item in QUESTION_TYPES" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-input
          v-model="query.keyword"
          placeholder="搜索题干 / 选项 / 解析"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
          @clear="reload"
        >
          <template #append>
            <el-button :icon="Search" @click="reload" />
          </template>
        </el-input>

        <el-select v-model="query.order" style="width: 140px" @change="reload">
          <el-option label="最新优先" value="newest" />
          <el-option label="最早优先" value="oldest" />
        </el-select>

        <el-button :icon="Refresh" @click="reload">刷新</el-button>
        <el-button
          :icon="Download"
          :loading="exporting"
          :disabled="!total"
          @click="exportCsv"
        >
          导出 CSV
        </el-button>
        <el-button type="primary" :icon="Plus" @click="router.push('/questions/new')">新增题目</el-button>
      </el-space>

      <el-table :data="rows" v-loading="loading" stripe @row-click="openDetail">
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column label="题型" width="92">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small" effect="light">{{ typeShort(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题干" min-width="360">
          <template #default="{ row }">
            <div class="stem">
              <MathText :text="row.title" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="答案" width="110">
          <template #default="{ row }">
            <span class="answer">{{ formatAnswer(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">查看</el-button>
            <el-button link type="primary" @click.stop="router.push(`/questions/${row.id}/edit`)">编辑</el-button>
            <el-button link type="danger" @click.stop="removeQuestion(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="hasFilter ? '没有符合筛选条件的题目' : '题库还是空的，先去导入题库吧'">
            <el-button v-if="!hasFilter" type="primary" @click="router.push('/import')">去导入</el-button>
          </el-empty>
        </template>
      </el-table>

      <el-pagination
        class="pager"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </el-card>

    <el-drawer v-model="detailVisible" :title="detail ? `题目 #${detail.id}` : '题目详情'" size="620px">
      <template v-if="detail">
        <el-space class="detail-head">
          <el-tag :type="typeTag(detail.type)" size="small" effect="light">{{ typeLabel(detail.type) }}</el-tag>
        </el-space>

        <h4 class="detail-label">题干</h4>
        <div class="detail-box"><MathText :text="detail.title" /></div>

        <template v-if="detail.options?.length">
          <h4 class="detail-label">选项</h4>
          <div class="detail-box">
            <div v-for="option in detail.options" :key="option.key" class="option-line">
              <span class="option-key">{{ option.key }}</span>
              <MathText :text="option.text" tag="span" />
            </div>
          </div>
        </template>

        <h4 class="detail-label">参考答案</h4>
        <div class="detail-box answer-box">
          <MathText v-if="detail.type === 'short'" :text="detail.answer || '（未填写）'" />
          <span v-else class="answer-strong">{{ formatAnswer(detail) }}</span>
        </div>

        <h4 class="detail-label">解析</h4>
        <div class="detail-box">
          <MathText :text="detail.analysis || '（无解析）'" />
        </div>

        <div class="detail-actions">
          <el-button type="primary" @click="router.push(`/questions/${detail.id}/edit`)">编辑此题</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Refresh, Search } from '@element-plus/icons-vue'
import { questionApi } from '@/api'
import MathText from '@/components/MathText.vue'
import { saveBlob } from '@/utils/download'
import { QUESTION_TYPES, formatAnswer, typeLabel, typeShort, typeTag } from '@/utils/questionTypes'

const router = useRouter()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const stats = ref({ total: 0, counts: {} })
const detailVisible = ref(false)
const detail = ref(null)

const query = reactive({
  page: 1,
  page_size: 20,
  type: '',
  keyword: '',
  order: 'newest',
})

const hasFilter = computed(() => Boolean(query.type || query.keyword.trim()))

async function load() {
  loading.value = true
  try {
    const data = await questionApi.list({
      page: query.page,
      page_size: query.page_size,
      type: query.type || undefined,
      keyword: query.keyword.trim() || undefined,
      order: query.order,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  stats.value = await questionApi.stats()
}

function reload() {
  query.page = 1
  load()
}

function refreshAll() {
  loadMeta()
  load()
}

function filterByType(value) {
  query.type = value
  reload()
}

function onPageChange(value) {
  query.page = value
  load()
}

function onSizeChange(value) {
  query.page_size = value
  query.page = 1
  load()
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

async function exportCsv() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await questionApi.exportCsv({
      type: query.type || undefined,
      keyword: query.keyword.trim() || undefined,
      order: query.order,
    })
    saveBlob(blob, 'ikao-questions.csv')
    ElMessage.success('已导出当前筛选结果')
  } finally {
    exporting.value = false
  }
}

async function removeQuestion(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除题目 #${row.id} 吗？该题的作答记录与收藏也会一并清除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户取消
  }
  await questionApi.remove(row.id)
  ElMessage.success('已删除')
  // 删掉当前页最后一条时回退一页，避免停在空页
  if (rows.value.length === 1 && query.page > 1) query.page -= 1
  refreshAll()
}

onMounted(refreshAll)
</script>

<style scoped>
.page-wide {
  max-width: 1320px;
}

.stat-row {
  margin-bottom: 4px;
}

.stat-card.clickable {
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.stat-card.clickable:hover {
  border-color: var(--ikao-primary);
  box-shadow: 0 2px 10px rgba(58, 138, 255, 0.12);
}

.stat-value.type-single {
  color: #3a8aff;
}

.stat-value.type-multiple {
  color: #52b46b;
}

.stat-value.type-judge {
  color: #e6a23c;
}

.stat-value.type-short {
  color: #8b7bd8;
}

.block {
  margin-top: 16px;
  border-radius: 10px;
}

.toolbar {
  margin-bottom: 14px;
}

.stem {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  cursor: pointer;
  line-height: 1.6;
}

.answer {
  color: #52b46b;
  font-weight: 600;
}

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.detail-head {
  margin-bottom: 12px;
}

.detail-label {
  margin: 16px 0 8px;
  font-size: 13px;
  color: var(--ikao-text-sub);
  font-weight: 600;
}

.detail-box {
  border: 1px solid var(--ikao-border);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfcfe;
}

.answer-box {
  background: #f2fbf5;
  border-color: #d6f0de;
}

.answer-strong {
  color: #52b46b;
  font-weight: 600;
  font-size: 15px;
}

.option-line {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 6px;
}

.option-line:last-child {
  margin-bottom: 0;
}

.option-key {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  border-radius: 50%;
  background: var(--ikao-primary-soft);
  color: var(--ikao-primary);
  font-size: 12px;
  font-weight: 600;
}

.detail-actions {
  margin-top: 20px;
}
</style>
