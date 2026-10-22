<template>
  <div class="page page-wide">
    <!-- 顶部欢迎区 -->
    <div class="hero">
      <div class="hero-main">
        <h2 class="hero-title">欢迎使用 {{ appStore.appName }}</h2>
        <p class="hero-desc">题海砺剑，考场争锋 —— 今日多练一题，明日多一分底气</p>
        <div class="hero-tags">
          <span class="hero-tag">当前档案：{{ appStore.currentProfileName || '—' }}</span>
          <span class="hero-tag">题库总题数：{{ appStore.questionCount }}</span>
        </div>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" :icon="EditPen" @click="router.push('/practice')">
          开始刷题
        </el-button>
        <el-button size="large" :icon="Refresh" :loading="loading" @click="refresh">刷新数据</el-button>
      </div>
    </div>

    <!-- 学习概览（统计看板摘要） -->
    <el-card shadow="never" class="block">
      <template #header>
        <div class="card-header">
          <span>学习概览</span>
          <el-button link type="primary" @click="router.push('/stats')">
            查看完整统计看板<el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>

      <el-row :gutter="12">
        <el-col v-for="card in overviewCards" :key="card.label" :xs="12" :sm="8" :md="4">
          <div class="stat-card">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value" :class="card.cls">{{ card.value }}</div>
          </div>
        </el-col>
      </el-row>

      <div v-if="hasData" ref="trendRef" class="chart" v-loading="loading" />
      <el-empty v-else :image-size="70" description="还没有刷题数据，点右上角「开始刷题」开始吧" />
    </el-card>

    <!-- 题库维护入口（其余功能已在顶栏直达，这里不重复） -->
    <el-card shadow="never" class="block">
      <template #header>
        <span>题库维护</span>
      </template>
      <el-row :gutter="16">
        <el-col v-for="entry in entries" :key="entry.path" :xs="24" :sm="12" :md="8">
          <div class="entry" @click="router.push(entry.path)">
            <div class="entry-icon" :style="{ background: entry.bg, color: entry.color }">
              <el-icon :size="20"><component :is="entry.icon" /></el-icon>
            </div>
            <div class="entry-text">
              <div class="entry-title">{{ entry.title }}</div>
              <div class="entry-desc">{{ entry.desc }}</div>
            </div>
            <el-icon class="entry-arrow"><ArrowRight /></el-icon>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  ArrowRight,
  Document,
  EditPen,
  Refresh,
  Tickets,
  Upload,
} from '@element-plus/icons-vue'
import { statsApi } from '@/api'
import { useAppStore } from '@/stores/app'

const TREND_DAYS = 14
const COLOR_PRIMARY = '#3a8aff'

const router = useRouter()
const appStore = useAppStore()

const loading = ref(false)
const board = ref({ overview: {}, trend: [] })
const trendRef = ref(null)
let chart = null

const entries = [
  {
    path: '/questions',
    title: '题库管理',
    desc: '检索、编辑、新增与删除题目',
    icon: Tickets,
    bg: '#eaf2ff',
    color: '#3a8aff',
  },
  {
    path: '/import',
    title: '题库导入',
    desc: '导入 JSON 题库并自动相似度去重',
    icon: Upload,
    bg: '#e9f8ef',
    color: '#2e9c52',
  },
  {
    path: '/import/logs',
    title: '导入日志',
    desc: '查看历史导入批次与明细',
    icon: Document,
    bg: '#fff5e8',
    color: '#d38a20',
  },
]

const hasData = computed(
  () => Number(board.value.overview.answered || 0) > 0 || Number(board.value.overview.attempts || 0) > 0,
)

function percent(value) {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

const overviewCards = computed(() => {
  const o = board.value.overview
  return [
    { label: '已作答', value: `${o.answered ?? 0} / ${o.total_questions ?? 0}`, cls: '' },
    { label: '答对', value: o.correct ?? 0, cls: 'is-ok' },
    { label: '答错', value: o.wrong ?? 0, cls: 'is-wrong' },
    { label: '正确率', value: percent(o.accuracy), cls: 'is-ok' },
    { label: '收藏', value: o.favorite ?? 0, cls: '' },
    { label: '连续练习', value: `${o.streak_days ?? 0} 天`, cls: '' },
  ]
})

function renderChart() {
  if (!hasData.value || !trendRef.value) {
    disposeChart()
    return
  }
  // 空态切回有数据时容器会重建，旧实例要丢弃重新绑定
  if (chart && chart.getDom() !== trendRef.value) disposeChart()
  if (!chart) chart = echarts.init(trendRef.value)
  const rows = board.value.trend
  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: { data: ['答题数', '正确率'], top: 0, left: 'center' },
      grid: { left: 44, right: 52, top: 36, bottom: 28 },
      xAxis: { type: 'category', data: rows.map((item) => item.date.slice(5)) },
      yAxis: [
        { type: 'value', name: '题数', minInterval: 1 },
        {
          type: 'value',
          name: '正确率',
          min: 0,
          max: 1,
          axisLabel: { formatter: (value) => `${Math.round(value * 100)}%` },
        },
      ],
      series: [
        {
          name: '答题数',
          type: 'bar',
          barMaxWidth: 18,
          data: rows.map((item) => item.attempts),
          itemStyle: { color: COLOR_PRIMARY, borderRadius: [4, 4, 0, 0] },
        },
        {
          name: '正确率',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          connectNulls: true,
          data: rows.map((item) => item.accuracy),
          itemStyle: { color: '#2e9c52' },
          lineStyle: { width: 2 },
        },
      ],
    },
    true,
  )
}

function disposeChart() {
  if (chart) {
    chart.dispose()
    chart = null
  }
}

function handleResize() {
  if (chart) chart.resize()
}

async function loadBoard() {
  loading.value = true
  try {
    board.value = await statsApi.board({ trend_days: TREND_DAYS })
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await Promise.all([appStore.refreshCount(), loadBoard()])
}

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  if (!appStore.loaded) await appStore.loadMeta()
  await loadBoard()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeChart()
})

watch(() => appStore.currentProfileId, loadBoard)
</script>

<style scoped>
.page-wide {
  max-width: 1320px;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  padding: 24px 28px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3a8aff, #7db4ff);
  color: #fff;
  box-shadow: 0 8px 20px rgba(58, 138, 255, 0.18);
}

.hero-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
}

.hero-desc {
  margin: 0 0 12px;
  font-size: 13px;
  opacity: 0.9;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-tag {
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.22);
  font-size: 12px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.block {
  margin-top: 16px;
  border-radius: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-value.is-ok {
  color: #2e9c52;
}

.stat-value.is-wrong {
  color: #d94b4b;
}

.chart {
  width: 100%;
  height: 260px;
  margin-top: 16px;
}

.entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
  border: 1px solid var(--ikao-border);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.entry:hover {
  border-color: var(--ikao-primary);
  box-shadow: 0 6px 16px rgba(58, 138, 255, 0.12);
  transform: translateY(-1px);
}

.entry-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.entry-text {
  flex: 1;
  min-width: 0;
}

.entry-title {
  font-size: 14px;
  font-weight: 600;
}

.entry-desc {
  margin-top: 2px;
  color: var(--ikao-text-sub);
  font-size: 12px;
}

.entry-arrow {
  color: var(--ikao-text-sub);
}
</style>
