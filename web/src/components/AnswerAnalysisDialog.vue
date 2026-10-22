<template>
  <el-dialog
    :model-value="modelValue"
    title="答案解析"
    width="640px"
    top="6vh"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-if="question" class="analysis">
      <div class="analysis-head">
        <el-tag :type="typeTag(question.type)" size="small" effect="light">
          {{ typeLabel(question.type) }}
        </el-tag>
      </div>

      <h4 class="analysis-label">题干</h4>
      <div class="analysis-box"><MathText :text="question.title" /></div>

      <h4 class="analysis-label">你的作答</h4>
      <div class="analysis-box" :class="verdictClass">
        <MathText v-if="question.type === 'short'" :text="userAnswerText" />
        <span v-else class="verdict-strong">{{ verdictText }}</span>
      </div>

      <h4 class="analysis-label">正确答案</h4>
      <div class="analysis-box correct-box">
        <MathText v-if="question.type === 'short'" :text="correctAnswerText" />
        <span v-else class="correct-strong">{{ correctAnswerText }}</span>
      </div>

      <h4 class="analysis-label">解析</h4>
      <div class="analysis-box">
        <MathText :text="analysis || '（该题暂无解析）'" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import MathText from '@/components/MathText.vue'
import { answerText, typeLabel, typeTag } from '@/utils/questionTypes'

/**
 * 答案解析弹窗：题干 + 你的作答 + 正确答案 + 解析。
 * 客观题只展示答案字母/正确错误，简答题按富文本完整展示。
 */
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  question: { type: Object, default: null },
  userAnswer: { type: [String, Array, Boolean, Number], default: null },
  correctAnswer: { type: [String, Array, Boolean, Number], default: null },
  analysis: { type: String, default: '' },
  isCorrect: { type: Boolean, default: null },
  needSelfEval: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const userAnswerText = computed(() => {
  const value = props.question?.type === 'short' ? props.userAnswer : answerText(props.question?.type, props.userAnswer)
  const text = value === null || value === undefined ? '' : String(value)
  return text.trim() ? text : '（未作答）'
})

const correctAnswerText = computed(() => {
  if (props.question?.type === 'short') {
    const text = props.correctAnswer === null || props.correctAnswer === undefined ? '' : String(props.correctAnswer)
    return text.trim() ? text : '（该题暂无参考答案）'
  }
  return answerText(props.question?.type, props.correctAnswer)
})

const verdictText = computed(() => {
  if (props.needSelfEval) return '待自评'
  if (props.isCorrect === true) return '回答正确'
  if (props.isCorrect === false) return '回答错误'
  return userAnswerText.value
})

const verdictClass = computed(() => {
  if (props.needSelfEval || props.isCorrect === null) return 'pending-box'
  return props.isCorrect ? 'correct-box' : 'wrong-box'
})
</script>

<style scoped>
.analysis-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.analysis-label {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ikao-text-sub);
}

.analysis-box {
  border: 1px solid var(--ikao-border);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfcfe;
}

.correct-box {
  background: #f2fbf5;
  border-color: #d6f0de;
}

.wrong-box {
  background: #fdf3f3;
  border-color: #f6d7d7;
}

.pending-box {
  background: #fff8ec;
  border-color: #f6e2bd;
}

.correct-strong {
  color: #2e9c52;
  font-weight: 600;
  font-size: 15px;
}

.verdict-strong {
  font-weight: 600;
  font-size: 15px;
}
</style>
