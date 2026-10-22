<template>
  <div class="page page-wide">
    <h2 class="page-title">统计看板</h2>
    <p class="page-desc">
      当前档案的刷题数据总览<span v-if="loaded">
        · 已学习 {{ board.overview.study_days }} 天 · 累计答题 {{ board.overview.attempts }} 次</span>
    </p>

    <el-row :gutter="12">
      <el-col v-for="card in overviewCards" :key="card.label" :xs="12" :sm="6" :md="3">
        <div class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.cls">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>

    <template v-if="hasData">
      <el-card shadow="never" class="block">
        <template #header>
          <div class="card-header">
            <span>练习趋势</span>
            <el-radio-group v-model="trendDays" size="small" @change="load">
              <el-radio-button v-for="day in TREND_OPTIONS" :key="day" :value="day">
                近 {{ day }} 天
              </el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <div ref="trendRef" class="chart chart-lg" v-loading="loading" />
      </el-card>

      <el-row :gutter="16" class="block">
        <el-col :xs="24" :lg="14">
          <el-card shadow="never" class="full-card">
            <template #header><span>题型分布</span></template>
            <div ref="typeRef" class="chart" v-loading="loading" />
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="10">
          <el-card shadow="never" class="full-card">
            <template #header><span>练习方式占比</span></template>
            <div ref="modeRef" class="chart" v-loading="loading" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="block">
        <template #header><span>高频错题 Top 10</span></template>
        <el-table :data="board.top_wrong" stripe>
          <el-table-column label="排名" width="70" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="题型" width="92">
            <template #default="{ row }">
              <el-tag :type="typeTag(row.type)" size="small" effect="light">{{ typeShort(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="题干" min-width="360">
            <template #default="{ row }">
              <div class="stem"><MathText :text="row.title" /></div>
            </template>
          </el-table-column>
          <el-table-column prop="wrong_count" label="错误次数" width="110" align="center">
            <template #default="{ row }">
              <span class="wrong-count">{{ row.wrong_count }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最近状态" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.last_correct === false" type="danger" size="small" effect="light">仍待攻克</el-tag>
              <el-tag v-else-if="row.last_correct === true" type="success" size="small" effect="light">已答对</el-tag>
              <el-tag v-else type="info" size="small" effect="light">未判定</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-card v-else shadow="never" class="block">
      <el-empty description="还没有刷题数据，先去练几道题吧">
        <el-button type="primary" @click="router.push('/practice')">开始刷题</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import MathText from '@/components/MathText.vue'
import { statsApi } from '@/api'
import { useAppStore } from '@/stores/app'
import { typeShort, typeTag } from '@/utils/questionTypes'

const TREND_OPTIONS = [7, 14, 30, 90]
const COLOR_PRIMARY = '#3a8aff'
const COLOR_WRONG = '#f56c6c'
const COLOR_OK = '#2e9c52'

const router = useRouter()
const appStore = useAppStore()

const trendDays = ref(14)
const loading = ref(false)
const loaded = ref(false)
const board = ref({
  overview: {},
  by_type: [],
  by_mode: [],
  trend: [],
  top_wrong: [],
})

const trendRef = ref(null)
const typeRef = ref(null)
const modeRef = ref(null)
const charts = {}

const hasData = computed(
  () => Number(board.value.overview.answered || 0) > 0 || Number(board.value.overview.attempts || 0) > 0,
)

function percent(value) {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

function formatDuration(ms) {
  const total = Number(ms || 0)
  if (!total) return '—'
  const minutes = Math.round(total / 60000)
  if (minutes < 60) return `${minutes} 分`
  return `${(minutes / 60).toFixed(1)} 时`
}

const overviewCards = computed(() => {
  const o = board.value.overview
  return [
    { label: '题库题目', value: o.total_questions ?? 0, cls: '' },
    { label: '已作答', value: o.answered ?? 0, cls: '' },
    { label: '答对', value: o.correct ?? 0, cls: 'is-ok' },
    { label: '答错', value: o.wrong ?? 0, cls: 'is-wrong' },
    { label: '正确率', value: percent(o.accuracy), cls: 'is-ok' },
    { label: '收藏', value: o.favorite ?? 0, cls: '' },
    { label: '连续练习', value: `${o.streak_days ?? 0} 天`, cls: '' },
    { label: '累计时长', value: formatDuration(o.duration_ms), cls: '' },
  ]
})

// ------------------------------------------------------------------ 图表
function initChart(el, option) {
  if (!el) return null
  const instance = echarts.getInstanceByDom(el) || echarts.init(el)
  instance.setOption(option, true)
  return instance
}

function trendOption() {
  const rows = board.value.trend
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['答题数', '正确率'], top: 0, left: 'center' },
    grid: { left: 48, right: 56, top: 40, bottom: 32 },
    xAxis: {
      type: 'category',
      data: rows.map((item) => item.date.slice(5)),
      boundaryGap: true,
    },
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
        barMaxWidth: 22,
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
        itemStyle: { color: COLOR_OK },
        lineStyle: { width: 2 },
      },
    ],
  }
}

function typeOption() {
  const rows = board.value.by_type
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['题目总数', '已作答', '答错'], top: 0 },
    grid: { left: 48, right: 24, top: 40, bottom: 32 },
    xAxis: { type: 'category', data: rows.map((item) => item.label) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '题目总数', type: 'bar', data: rows.map((item) => item.total), itemStyle: { color: '#c9d8f5' } },
      { name: '已作答', type: 'bar', data: rows.map((item) => item.answered), itemStyle: { color: COLOR_PRIMARY } },
      { name: '答错', type: 'bar', data: rows.map((item) => item.wrong), itemStyle: { color: COLOR_WRONG } },
    ],
  }
}

function modeOption() {
  const rows = board.value.by_mode.filter((item) => item.attempts > 0)
  return {
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 次（{d}%）' },
    legend: { bottom: 0 },
    series: [
      {
        name: '练习方式',
        type: 'pie',
        radius: ['42%', '66%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        label: { formatter: '{b}\n{c}' },
        data: rows.map((item) => ({ name: item.label, value: item.attempts })),
      },
    ],
  }
}

function renderCharts() {
  if (!hasData.value) return
  charts.trend = initChart(trendRef.value, trendOption())
  charts.type = initChart(typeRef.value, typeOption())
  charts.mode = initChart(modeRef.value, modeOption())
}

function disposeCharts() {
  Object.values(charts).forEach((instance) => instance && instance.dispose())
  for (const key of Object.keys(charts)) delete charts[key]
}

function handleResize() {
  Object.values(charts).forEach((instance) => instance && instance.resize())
}

async function load() {
  loading.value = true
  try {
    board.value = await statsApi.board({ trend_days: trendDays.value })
    loaded.value = true
    await nextTick()
    if (hasData.value) renderCharts()
    else disposeCharts()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})

watch(() => appStore.currentProfileId, load)
</script>

<style scoped>
.page-wide {
  max-width: 1320px;
}

.block {
  margin-top: 16px;
  border-radius: 10px;
}

.full-card {
  border-radius: 10px;
  height: 100%;
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
  height: 300px;
}

.chart-lg {
  height: 320px;
}

.stem {
  line-height: 1.6;
}

.wrong-count {
  color: #d94b4b;
  font-weight: 600;
}
</style>
