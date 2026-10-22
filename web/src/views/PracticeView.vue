<!--
  SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
  SPDX-License-Identifier: MIT
-->
<template>
  <div class="page page-wide">
    <h2 class="page-title">刷题</h2>
    <p class="page-desc">选好模式与范围后开始练习；作答提交后即时判分，简答题对照参考答案自评，背题模式直接看答案与解析</p>

    <el-row :gutter="12">
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-label">题库题目</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-label">已作答</div>
          <div class="stat-value">{{ stats.answered }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-label">错题</div>
          <div class="stat-value">{{ stats.wrong }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-label">收藏</div>
          <div class="stat-value">{{ stats.favorite }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="block">
      <el-space wrap :size="12">
        <el-radio-group v-model="mode">
          <el-radio-button v-for="item in PRACTICE_MODES" :key="item.value" :value="item.value">
            {{ item.label }}
          </el-radio-button>
        </el-radio-group>

        <el-select v-model="filter.type" placeholder="全部题型" clearable style="width: 130px">
          <el-option v-for="item in QUESTION_TYPES" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-select v-model="filter.count" style="width: 120px">
          <el-option v-for="size in [10, 20, 50, 100]" :key="size" :label="`${size} 题`" :value="size" />
        </el-select>

        <el-button type="primary" :icon="RefreshRight" :loading="loading" @click="start">
          {{ questions.length ? '重新开始' : '开始刷题' }}
        </el-button>
      </el-space>
      <div class="mode-desc">{{ currentModeDesc }}</div>
    </el-card>

    <el-row v-if="questions.length" :gutter="16" class="practice-body">
      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="question-card">
          <div class="q-head">
            <div class="q-head-left">
              <span class="q-position">第 {{ currentIndex + 1 }} / {{ questions.length }} 题</span>
              <el-tag :type="typeTag(currentQuestion.type)" size="small" effect="light">
                {{ typeLabel(currentQuestion.type) }}
              </el-tag>
              <span v-if="currentQuestion.practice_count" class="q-meta">
                已练 {{ currentQuestion.practice_count }} 次
              </span>
              <span v-if="currentQuestion.wrong_count" class="q-meta is-wrong">
                错 {{ currentQuestion.wrong_count }} 次
              </span>
            </div>
            <div class="q-head-right">
              <el-button text :icon="isFavorite ? StarFilled : Star" @click="toggleFavorite">
                {{ isFavorite ? '已收藏' : '收藏' }}
              </el-button>
              <el-button v-if="sessionMode === 'wrong'" text type="danger" :icon="Delete" @click="removeFromWrong">
                移出错题本
              </el-button>
            </div>
          </div>

          <div class="q-stem">
            <MathText :text="currentQuestion.title" />
          </div>

          <!-- 背题模式：只读展示，直接高亮正确答案 -->
          <template v-if="isRecite">
            <div v-if="currentQuestion.type === 'judge'" class="option-group">
              <div class="option-row is-static" :class="judgeClass(true)">
                <span class="opt-key">对</span>
                <span>正确</span>
              </div>
              <div class="option-row is-static" :class="judgeClass(false)">
                <span class="opt-key">错</span>
                <span>错误</span>
              </div>
            </div>
            <div v-else-if="currentQuestion.type !== 'short'" class="option-group">
              <div
                v-for="option in currentQuestion.options"
                :key="option.key"
                class="option-row is-static"
                :class="optionRowClass(option.key)"
              >
                <span class="opt-key">{{ option.key }}</span>
                <MathText :text="option.text" tag="span" />
              </div>
            </div>
          </template>

          <!-- 单选 -->
          <el-radio-group
            v-else-if="currentQuestion.type === 'single'"
            v-model="currentAnswer"
            class="option-group"
            :disabled="submitted"
          >
            <div
              v-for="option in currentQuestion.options"
              :key="option.key"
              class="option-row"
              :class="optionRowClass(option.key)"
            >
              <el-radio :value="option.key" class="option-radio">
                <span class="opt-key">{{ option.key }}</span>
                <MathText :text="option.text" tag="span" />
              </el-radio>
            </div>
          </el-radio-group>

          <!-- 多选 -->
          <el-checkbox-group
            v-else-if="currentQuestion.type === 'multiple'"
            v-model="currentAnswer"
            class="option-group"
            :disabled="submitted"
          >
            <div
              v-for="option in currentQuestion.options"
              :key="option.key"
              class="option-row"
              :class="optionRowClass(option.key)"
            >
              <el-checkbox :value="option.key" class="option-radio">
                <span class="opt-key">{{ option.key }}</span>
                <MathText :text="option.text" tag="span" />
              </el-checkbox>
            </div>
          </el-checkbox-group>

          <!-- 判断 -->
          <el-radio-group
            v-else-if="currentQuestion.type === 'judge'"
            v-model="currentAnswer"
            :disabled="submitted"
          >
            <el-radio-button :value="true" :class="judgeClass(true)">正确</el-radio-button>
            <el-radio-button :value="false" :class="judgeClass(false)">错误</el-radio-button>
          </el-radio-group>

          <!-- 简答 -->
          <el-input
            v-else
            v-model="currentAnswer"
            type="textarea"
            :rows="5"
            :disabled="submitted"
            placeholder="请输入你的作答（支持 Markdown 与 LaTeX）"
          />

          <!-- 背题模式：直接展示答案与解析 -->
          <div v-if="isRecite" class="recite-answer">
            <div class="ref-label">正确答案</div>
            <div class="ref-value">
              <MathText :text="answerText(currentQuestion.type, currentQuestion.answer)" />
            </div>
            <div class="ref-label ref-label-gap">解析</div>
            <MathText :text="currentQuestion.analysis || '（该题暂无解析）'" />
          </div>

          <div v-if="submitted" class="result-bar" :class="verdictClass">
            <el-icon>
              <component :is="verdictIcon" />
            </el-icon>
            <span v-if="currentResult.need_self_eval">已提交，请对照参考答案自评</span>
            <span v-else-if="currentResult.is_correct === null">该题缺少参考答案，暂无法自动判分</span>
            <span v-else-if="currentResult.is_correct">回答正确</span>
            <span v-else>
              回答错误，正确答案：<b>{{ answerText(currentQuestion.type, currentResult.correct_answer) }}</b>
            </span>
          </div>

          <div v-if="submitted && currentQuestion.type === 'short'" class="ref-answer">
            <div class="ref-label">参考答案</div>
            <MathText :text="currentResult.correct_answer || '（该题暂无参考答案）'" />
          </div>

          <div v-if="submitted && currentResult.need_self_eval" class="self-eval">
            <span>对照参考答案，你这道题答得怎么样？</span>
            <el-button type="success" size="small" @click="selfEvaluate(true)">我答对了</el-button>
            <el-button type="danger" size="small" @click="selfEvaluate(false)">我答错了</el-button>
          </div>

          <div class="q-actions">
            <el-button :icon="ArrowLeft" :disabled="currentIndex === 0" @click="go(-1)">上一题</el-button>
            <el-button
              v-if="!isRecite && !submitted"
              type="primary"
              :loading="submitting"
              @click="submitCurrent"
            >
              提交答案
            </el-button>
            <el-button v-else-if="!isRecite" :icon="Document" @click="analysisVisible = true">查看解析</el-button>
            <el-button
              type="primary"
              plain
              :disabled="currentIndex >= questions.length - 1"
              @click="go(1)"
            >
              下一题<el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </el-card>

        <div v-if="isRecite && questions.length < reciteTotal" class="load-more">
          <el-button :loading="loadingMore" @click="loadMore">
            加载更多（已背 {{ questions.length }} / {{ reciteTotal }} 题）
          </el-button>
        </div>
      </el-col>

      <el-col :xs="24" :lg="7">
        <el-card shadow="never" class="sheet-card">
          <template #header>
            <div class="sheet-header">
              <span>{{ currentModeLabel }}</span>
              <span class="sheet-total">共 {{ questions.length }} 题</span>
            </div>
          </template>
          <AnswerSheet
            :questions="questions"
            :status-map="statusMap"
            :current-index="currentIndex"
            @select="jumpTo"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-else shadow="never" class="block">
      <el-empty :description="emptyHint">
        <el-button v-if="stats.total === 0" type="primary" @click="router.push('/import')">去导入题库</el-button>
        <el-button v-else type="primary" @click="start">重新抽题</el-button>
      </el-empty>
    </el-card>

    <AnswerAnalysisDialog
      v-model="analysisVisible"
      :question="currentQuestion"
      :user-answer="currentPick"
      :correct-answer="currentResult?.correct_answer"
      :analysis="currentResult?.analysis || ''"
      :is-correct="currentResult?.is_correct ?? null"
      :need-self-eval="Boolean(currentResult?.need_self_eval)"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  CircleCheckFilled,
  CircleCloseFilled,
  Delete,
  Document,
  RefreshRight,
  Star,
  StarFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { questionApi, practiceApi } from '@/api'
import AnswerAnalysisDialog from '@/components/AnswerAnalysisDialog.vue'
import AnswerSheet from '@/components/AnswerSheet.vue'
import MathText from '@/components/MathText.vue'
import { useAppStore } from '@/stores/app'
import {
  PRACTICE_MODES,
  QUESTION_TYPES,
  answerText,
  typeLabel,
  typeTag,
} from '@/utils/questionTypes'

const router = useRouter()
const appStore = useAppStore()

const mode = ref('sequence')
const sessionMode = ref('sequence')
const filter = reactive({ type: '', count: 20 })

const stats = reactive({ total: 0, answered: 0, correct: 0, wrong: 0, favorite: 0 })

const questions = ref([])
const currentIndex = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const submitting = ref(false)
const analysisVisible = ref(false)
/** 背题模式的分页游标与题目总数 */
const page = ref(1)
const reciteTotal = ref(0)

/** 抽题请求序号，用于丢弃快速切换模式时返回的旧响应 */
let requestSeq = 0

/** qid -> 待提交作答；qid -> 作答结果；qid -> 是否收藏 */
const picks = reactive({})
const results = reactive({})
const favorites = reactive({})
let startedAt = Date.now()

const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
const currentPick = computed(() => (currentQuestion.value ? picks[currentQuestion.value.id] : null))
const currentResult = computed(() => (currentQuestion.value ? results[currentQuestion.value.id] : null))
const submitted = computed(() => Boolean(currentResult.value))
/** 背题模式：只展示答案与解析，不作答、不判分、不计入统计 */
const isRecite = computed(() => sessionMode.value === 'recite')
/** 当前应高亮的正确答案：背题模式取自题目本身，其余模式取自判分结果 */
const correctAnswer = computed(() => {
  const question = currentQuestion.value
  if (!question) return null
  return isRecite.value ? question.answer : currentResult.value?.correct_answer
})
const isFavorite = computed(() =>
  currentQuestion.value ? Boolean(favorites[currentQuestion.value.id]) : false,
)

const currentAnswer = computed({
  get: () => (currentQuestion.value ? picks[currentQuestion.value.id] : undefined),
  set: (value) => {
    if (currentQuestion.value) picks[currentQuestion.value.id] = value
  },
})

const statusMap = computed(() => {
  const map = {}
  for (const question of questions.value) {
    const result = results[question.id]
    if (!result) map[question.id] = 'unanswered'
    else if (result.need_self_eval || result.is_correct === null) map[question.id] = 'pending'
    else map[question.id] = result.is_correct ? 'correct' : 'wrong'
  }
  return map
})

const currentModeLabel = computed(
  () => PRACTICE_MODES.find((item) => item.value === sessionMode.value)?.label || '练习',
)
const currentModeDesc = computed(
  () => PRACTICE_MODES.find((item) => item.value === mode.value)?.desc || '',
)

const emptyHint = computed(() => {
  if (stats.total === 0) return '题库还是空的，先去导入题库吧'
  if (mode.value === 'wrong') return '错题本是空的，先做几道题吧'
  if (mode.value === 'favorite') return '还没有收藏题目，刷题时点「收藏」即可加入'
  return '没有抽到题目，换个筛选条件试试'
})

const verdictClass = computed(() => {
  const result = currentResult.value
  if (!result) return ''
  if (result.need_self_eval || result.is_correct === null) return 'is-pending'
  return result.is_correct ? 'is-correct' : 'is-wrong'
})

const verdictIcon = computed(() => {
  const result = currentResult.value
  if (!result) return Document
  if (result.need_self_eval || result.is_correct === null) return WarningFilled
  return result.is_correct ? CircleCheckFilled : CircleCloseFilled
})

// ------------------------------------------------------------------ 抽题
function emptyPick(type) {
  if (type === 'multiple') return []
  if (type === 'judge') return null
  return ''
}

async function start() {
  const seq = ++requestSeq
  loading.value = true
  try {
    const data = await practiceApi.questions({
      mode: mode.value,
      type: filter.type || undefined,
      count: filter.count,
      page: 1,
    })
    // 期间又切换了模式：丢弃这次结果，交给最新一次请求
    if (seq !== requestSeq) return

    sessionMode.value = data.mode
    page.value = 1
    reciteTotal.value = data.total
    loadingMore.value = false

    for (const key of Object.keys(picks)) delete picks[key]
    for (const key of Object.keys(results)) delete results[key]
    for (const key of Object.keys(favorites)) delete favorites[key]

    questions.value = data.items
    for (const question of data.items) {
      picks[question.id] = emptyPick(question.type)
      favorites[question.id] = question.is_favorite
    }
    currentIndex.value = 0
    startedAt = Date.now()

    if (!data.items.length) ElMessage.info(emptyHint.value)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

/** 背题模式：按页往后追加题目，便于连续背完整题库 */
async function loadMore() {
  if (loadingMore.value) return
  const seq = requestSeq
  loadingMore.value = true
  try {
    const data = await practiceApi.questions({
      mode: sessionMode.value,
      type: filter.type || undefined,
      count: filter.count,
      page: page.value + 1,
    })
    if (seq !== requestSeq) return
    reciteTotal.value = data.total
    if (!data.items.length) return
    page.value += 1
    for (const question of data.items) {
      picks[question.id] = emptyPick(question.type)
      favorites[question.id] = question.is_favorite
    }
    questions.value = [...questions.value, ...data.items]
  } finally {
    if (seq === requestSeq) loadingMore.value = false
  }
}

// ------------------------------------------------------------------ 作答
function isBlank(type, value) {
  if (type === 'multiple') return !Array.isArray(value) || value.length === 0
  if (type === 'judge') return value === null || value === undefined
  return !String(value ?? '').trim()
}

async function submitCurrent() {
  const question = currentQuestion.value
  if (!question || submitted.value) return

  const answer = picks[question.id]
  if (isBlank(question.type, answer)) {
    ElMessage.warning('请先作答再提交')
    return
  }

  submitting.value = true
  try {
    const result = await practiceApi.answer({
      question_id: question.id,
      user_answer: question.type === 'short' ? String(answer) : answer,
      mode: sessionMode.value,
      duration_ms: Date.now() - startedAt,
    })
    results[question.id] = result
    favorites[question.id] = result.state.is_favorite
    refreshStats()
  } finally {
    submitting.value = false
  }
}

async function selfEvaluate(isCorrect) {
  const question = currentQuestion.value
  if (!question) return
  const result = await practiceApi.selfEvaluate({
    question_id: question.id,
    is_correct: isCorrect,
    mode: sessionMode.value,
  })
  results[question.id] = { ...results[question.id], ...result }
  favorites[question.id] = result.state.is_favorite
  refreshStats()
}

async function toggleFavorite() {
  const question = currentQuestion.value
  if (!question) return
  const result = await practiceApi.toggleFavorite(question.id)
  favorites[question.id] = result.is_favorite
  ElMessage.success(result.is_favorite ? '已加入收藏' : '已取消收藏')
  refreshStats()
}

async function removeFromWrong() {
  const question = currentQuestion.value
  if (!question) return
  await practiceApi.removeWrong(question.id)
  ElMessage.success('已移出错题本')
  questions.value = questions.value.filter((item) => item.id !== question.id)
  if (currentIndex.value >= questions.value.length) {
    currentIndex.value = Math.max(0, questions.value.length - 1)
  }
  refreshStats()
}

// ------------------------------------------------------------------ 导航
function go(step) {
  const next = currentIndex.value + step
  if (next < 0) return
  if (next >= questions.value.length) {
    ElMessage.info('已经是最后一题了')
    return
  }
  jumpTo(next)
}

function jumpTo(index) {
  if (index < 0 || index >= questions.value.length) return
  currentIndex.value = index
  startedAt = Date.now()
}

// ------------------------------------------------------------------ 展示
function keysOf(type, value) {
  if (value === null || value === undefined || type === 'judge') return []
  if (Array.isArray(value)) return value.map((item) => String(item).toUpperCase())
  return [String(value).toUpperCase()]
}

function optionRowClass(key) {
  const question = currentQuestion.value
  const correct = correctAnswer.value
  if (!question || correct === null || correct === undefined) return ''
  if (keysOf(question.type, correct).includes(key)) return 'is-answer'
  if (currentResult.value && keysOf(question.type, picks[question.id]).includes(key)) return 'is-wrong-pick'
  return ''
}

function judgeClass(value) {
  const correct = correctAnswer.value
  if (correct === null || correct === undefined) return ''
  if (currentResult.value?.need_self_eval) return ''
  if (correct === value) return 'is-answer'
  if (currentResult.value && picks[currentQuestion.value.id] === value) return 'is-wrong-pick'
  return ''
}

async function refreshStats() {
  const data = await practiceApi.stats()
  Object.assign(stats, data)
}

onMounted(async () => {
  await refreshStats()
  if (stats.total > 0) start()
})

// 切换练习模式后立即按新模式重新抽题，无需再点「开始刷题」
watch(mode, () => {
  if (stats.total > 0) {
    start()
    return
  }
  requestSeq += 1
  questions.value = []
  currentIndex.value = 0
  reciteTotal.value = 0
})

// 切换档案后重抽题，避免把上一个档案的作答状态带过来
watch(
  () => appStore.currentProfileId,
  async () => {
    await refreshStats()
    if (stats.total > 0) start()
    else {
      questions.value = []
      currentIndex.value = 0
    }
  },
)
</script>

<style scoped>
.block {
  margin-top: 16px;
  border-radius: 10px;
}

.mode-desc {
  margin-top: 10px;
  color: var(--ikao-text-sub);
  font-size: 13px;
}

.practice-body {
  margin-top: 16px;
}

.load-more {
  margin-top: 12px;
  text-align: center;
}

.question-card,
.sheet-card {
  border-radius: 10px;
}

.sheet-card {
  position: sticky;
  top: 78px;
}

.q-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.q-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.q-position {
  font-weight: 600;
}

.q-meta {
  color: var(--ikao-text-sub);
  font-size: 12px;
}

.q-meta.is-wrong {
  color: #d94b4b;
}

.q-stem {
  padding: 12px 14px;
  border-radius: 8px;
  background: #fbfcfe;
  border: 1px solid var(--ikao-border);
  margin-bottom: 16px;
  font-size: 15px;
}

.option-group {
  display: block;
}

.option-row {
  border: 1px solid var(--ikao-border);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 10px;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}

.option-row:hover {
  border-color: var(--ikao-primary);
}

.option-row.is-answer {
  border-color: #b6e5c4;
  background: #f2fbf5;
}

.option-row.is-wrong-pick {
  border-color: #f4c2c2;
  background: #fdeeee;
}

.option-radio {
  width: 100%;
  height: auto;
  align-items: flex-start;
  margin-right: 0;
}

.option-radio :deep(.el-radio__label),
.option-radio :deep(.el-checkbox__label) {
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  white-space: normal;
  line-height: 1.7;
}

.opt-key {
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

:deep(.el-radio-button.is-answer .el-radio-button__inner) {
  background: #f2fbf5;
  border-color: #b6e5c4;
  color: #2e9c52;
}

:deep(.el-radio-button.is-wrong-pick .el-radio-button__inner) {
  background: #fdeeee;
  border-color: #f4c2c2;
  color: #d94b4b;
}

.result-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
}

.result-bar.is-correct {
  background: #f2fbf5;
  border: 1px solid #d6f0de;
  color: #2e9c52;
}

.result-bar.is-wrong {
  background: #fdf3f3;
  border: 1px solid #f6d7d7;
  color: #d94b4b;
}

.result-bar.is-pending {
  background: #fff8ec;
  border: 1px solid #f6e2bd;
  color: #d38a20;
}

.option-row.is-static {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.7;
}

.recite-answer {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #fbfcfe;
  border: 1px solid var(--ikao-border);
}

.ref-value {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ikao-primary);
}

.ref-label-gap {
  margin-top: 12px;
}

.ref-answer {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #fbfcfe;
  border: 1px solid var(--ikao-border);
}

.ref-label {
  margin-bottom: 6px;
  color: var(--ikao-text-sub);
  font-size: 13px;
  font-weight: 600;
}

.self-eval {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 14px;
}

.q-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--ikao-border);
}

.sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sheet-total {
  color: var(--ikao-text-sub);
  font-size: 13px;
}
</style>
