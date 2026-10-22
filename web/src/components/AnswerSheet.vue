<template>
  <div class="answer-sheet">
    <div class="sheet-head">
      <span class="sheet-title">答题卡</span>
      <span class="sheet-progress">{{ answeredCount }} / {{ questions.length }}</span>
    </div>

    <div v-if="questions.length" class="sheet-grid">
      <button
        v-for="(question, index) in questions"
        :key="question.id"
        type="button"
        class="sheet-cell"
        :class="[`is-${statusOf(question.id)}`, { 'is-active': index === currentIndex }]"
        :title="`第 ${index + 1} 题`"
        @click="$emit('select', index)"
      >
        {{ index + 1 }}
      </button>
    </div>
    <el-empty v-else :image-size="60" description="暂无题目" />

    <div class="sheet-legend">
      <span><i class="dot is-unanswered" />未作答</span>
      <span><i class="dot is-correct" />答对</span>
      <span><i class="dot is-wrong" />答错</span>
      <span><i class="dot is-pending" />待自评</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 答题卡：题号网格，按作答结果着色，点击可跳转任意题。
 * statusMap: { [questionId]: 'unanswered' | 'correct' | 'wrong' | 'pending' }
 */
const props = defineProps({
  questions: { type: Array, default: () => [] },
  statusMap: { type: Object, default: () => ({}) },
  currentIndex: { type: Number, default: 0 },
})

defineEmits(['select'])

const answeredCount = computed(
  () => Object.values(props.statusMap).filter((value) => value && value !== 'unanswered').length,
)

function statusOf(id) {
  return props.statusMap[id] || 'unanswered'
}
</script>

<style scoped>
.sheet-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sheet-title {
  font-weight: 600;
}

.sheet-progress {
  color: var(--ikao-text-sub);
  font-size: 13px;
}

.sheet-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(34px, 1fr));
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.sheet-cell {
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--ikao-border);
  background: #fff;
  color: var(--ikao-text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.sheet-cell:hover {
  border-color: var(--ikao-primary);
  color: var(--ikao-primary);
}

.sheet-cell.is-active {
  box-shadow: 0 0 0 2px var(--ikao-primary);
  border-color: var(--ikao-primary);
}

.sheet-cell.is-correct {
  background: #eefaf1;
  border-color: #b6e5c4;
  color: #2e9c52;
}

.sheet-cell.is-wrong {
  background: #fdeeee;
  border-color: #f4c2c2;
  color: #d94b4b;
}

.sheet-cell.is-pending {
  background: #fff6e8;
  border-color: #f4dcb0;
  color: #d38a20;
}

.sheet-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: var(--ikao-text-sub);
  font-size: 12px;
}

.sheet-legend span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  border: 1px solid var(--ikao-border);
  background: #fff;
}

.dot.is-correct {
  background: #b6e5c4;
  border-color: #b6e5c4;
}

.dot.is-wrong {
  background: #f4c2c2;
  border-color: #f4c2c2;
}

.dot.is-pending {
  background: #f4dcb0;
  border-color: #f4dcb0;
}
</style>
