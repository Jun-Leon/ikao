<template>
  <div class="page page-wide">
    <h2 class="page-title">{{ isEdit ? `编辑题目 #${questionId}` : '新增题目' }}</h2>
    <p class="page-desc">
      题干、选项、答案、解析都支持 Markdown 与 LaTeX 公式（如 <code>$E=mc^2$</code>、<code>$$\frac{a}{b}$$</code>），右侧实时预览
    </p>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="block" v-loading="loading">
          <el-form label-width="88px" label-position="right">
            <el-form-item label="题型">
              <el-radio-group v-model="form.type" @change="onTypeChange">
                <el-radio-button v-for="item in QUESTION_TYPES" :key="item.value" :value="item.value">
                  {{ item.label }}
                </el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="题干">
              <el-input
                v-model="form.title"
                type="textarea"
                :rows="4"
                placeholder="例：卷积神经网络中，$3\times3$ 卷积核在步长为 1 时输出尺寸的公式是？"
              />
            </el-form-item>

            <template v-if="isChoice">
              <el-form-item label="选项">
                <div class="option-editor">
                  <div v-for="(option, index) in form.options" :key="index" class="option-row">
                    <el-input v-model="option.key" class="option-key-input" maxlength="2" />
                    <el-input v-model="option.text" placeholder="选项内容（支持公式）" />
                    <el-button
                      :icon="Delete"
                      text
                      type="danger"
                      :disabled="form.options.length <= 2"
                      @click="removeOption(index)"
                    />
                  </div>
                  <el-space>
                    <el-button :icon="Plus" text type="primary" @click="addOption">添加选项</el-button>
                    <el-button text @click="resetOptions">重置为 A~D</el-button>
                  </el-space>
                </div>
              </el-form-item>

              <el-form-item label="正确答案">
                <el-select
                  v-if="form.type === 'single'"
                  v-model="form.answer"
                  placeholder="请选择唯一正确答案"
                  style="width: 220px"
                >
                  <el-option
                    v-for="option in form.options"
                    :key="option.key"
                    :label="`${option.key}. ${optionText(option)}`"
                    :value="normalizeKey(option.key)"
                    :disabled="!option.key.trim()"
                  />
                </el-select>

                <el-checkbox-group v-else v-model="form.answer">
                  <el-checkbox
                    v-for="option in form.options"
                    :key="option.key"
                    :value="normalizeKey(option.key)"
                    :disabled="!option.key.trim()"
                  >
                    {{ normalizeKey(option.key) }}
                  </el-checkbox>
                </el-checkbox-group>
              </el-form-item>
            </template>

            <el-form-item v-if="form.type === 'judge'" label="正确答案">
              <el-radio-group v-model="form.answer">
                <el-radio-button :value="true">正确</el-radio-button>
                <el-radio-button :value="false">错误</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="form.type === 'short'" label="参考答案">
              <el-input
                v-model="form.answer"
                type="textarea"
                :rows="3"
                placeholder="简答题参考答案，支持公式"
              />
            </el-form-item>

            <el-form-item label="解析">
              <el-input v-model="form.analysis" type="textarea" :rows="3" placeholder="可选，支持公式" />
            </el-form-item>

            <el-form-item>
              <el-space>
                <el-button type="primary" :loading="saving" @click="submit">
                  {{ isEdit ? '保存修改' : '保存题目' }}
                </el-button>
                <el-button @click="goList">取消</el-button>
                <el-button v-if="isEdit" text type="danger" @click="removeCurrent">删除此题</el-button>
              </el-space>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="block">
          <template #header>
            <span>实时预览</span>
          </template>

          <el-tag :type="typeTag(form.type)" size="small" effect="light">{{ typeLabel(form.type) }}</el-tag>

          <div class="preview-block">
            <MathText :text="form.title || '（题干为空）'" />
          </div>

          <div v-if="isChoice" class="preview-block">
            <div v-for="(option, index) in form.options" :key="index" class="preview-option">
              <span class="option-key">{{ normalizeKey(option.key) || '?' }}</span>
              <MathText :text="option.text || '（空）'" tag="span" />
            </div>
          </div>

          <div class="preview-label">参考答案</div>
          <div class="preview-block answer-block">
            <MathText v-if="form.type === 'short'" :text="form.answer || '（未填写）'" />
            <span v-else class="answer-strong">{{ previewAnswer }}</span>
          </div>

          <div class="preview-label">解析</div>
          <div class="preview-block">
            <MathText :text="form.analysis || '（无解析）'" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import { questionApi } from '@/api'
import MathText from '@/components/MathText.vue'
import { QUESTION_TYPES, optionKeyAt, typeLabel, typeTag } from '@/utils/questionTypes'

const route = useRoute()
const router = useRouter()

const questionId = computed(() => Number(route.params.id || 0))
const isEdit = computed(() => questionId.value > 0)

const form = reactive({
  type: 'single',
  title: '',
  options: [],
  answer: '',
  analysis: '',
})

const saving = ref(false)
const loading = ref(false)
const extId = ref('')

const isChoice = computed(() => form.type === 'single' || form.type === 'multiple')

const previewAnswer = computed(() => {
  if (form.type === 'judge') return form.answer === true ? '正确' : '错误'
  if (form.type === 'multiple') return form.answer?.length ? form.answer.join('、') : '（未选择）'
  return form.answer || '（未选择）'
})

function normalizeKey(value) {
  return String(value ?? '').trim().toUpperCase()
}

function optionText(option) {
  const text = (option.text || '').replace(/\s+/g, ' ').trim()
  return text.length > 12 ? `${text.slice(0, 12)}...` : text || '（空）'
}

function defaultOptions() {
  return ['A', 'B', 'C', 'D'].map((key) => ({ key, text: '' }))
}

function addOption() {
  const used = new Set(form.options.map((item) => normalizeKey(item.key)))
  let index = form.options.length
  while (used.has(optionKeyAt(index))) index += 1
  form.options.push({ key: optionKeyAt(index), text: '' })
}

function removeOption(index) {
  if (form.options.length <= 2) return
  form.options.splice(index, 1)
}

function resetOptions() {
  form.options = defaultOptions()
}

/** 切换题型时重置答案结构，避免残留非法值 */
function onTypeChange(value) {
  if (value === 'multiple') form.answer = []
  else if (value === 'judge') form.answer = true
  else form.answer = ''
}

/** 选项变动后，把已删除选项从答案里剔除 */
watch(
  () => form.options.map((item) => normalizeKey(item.key)).join(','),
  () => {
    const keys = form.options.map((item) => normalizeKey(item.key)).filter(Boolean)
    if (form.type === 'single') {
      if (!keys.includes(form.answer)) form.answer = ''
    } else if (form.type === 'multiple') {
      form.answer = (Array.isArray(form.answer) ? form.answer : []).filter((item) => keys.includes(item))
    }
  },
)

function validate() {
  if (!form.title.trim()) return '题干不能为空'

  if (isChoice.value) {
    if (form.options.length < 2) return '选择题至少需要 2 个选项'
    const keys = form.options.map((item) => normalizeKey(item.key))
    if (keys.some((key) => !key)) return '选项序号不能为空'
    if (new Set(keys).size !== keys.length) return '选项序号不能重复'
    if (form.options.some((item) => !item.text.trim())) return '选项内容不能为空'

    if (form.type === 'single') {
      if (!form.answer) return '请选择唯一正确答案'
      if (!keys.includes(form.answer)) return '正确答案不在选项范围内'
    } else {
      const answer = Array.isArray(form.answer) ? form.answer : []
      if (!answer.length) return '请至少选择 1 个正确答案'
      if (answer.length < 2) return '多选题的正确答案应多于 1 个，若只有 1 个请改为单选题'
      if (answer.some((item) => !keys.includes(item))) return '正确答案不在选项范围内'
    }
  }

  if (form.type === 'judge' && typeof form.answer !== 'boolean') return '请选择判断结果'
  return ''
}

function buildPayload() {
  return {
    ext_id: extId.value || null,
    type: form.type,
    title: form.title.trim(),
    options: isChoice.value
      ? form.options.map((item) => ({ key: normalizeKey(item.key), text: item.text.trim() }))
      : [],
    answer: form.type === 'short' ? form.answer || '' : form.answer,
    analysis: form.analysis.trim() || null,
  }
}

async function submit() {
  const invalid = validate()
  if (invalid) {
    ElMessage.warning(invalid)
    return
  }

  saving.value = true
  try {
    // 保存前查重：命中则让用户决定要不要继续
    const proceed = await confirmDuplicate()
    if (!proceed) return

    const payload = buildPayload()
    if (isEdit.value) {
      await questionApi.update(questionId.value, payload)
      ElMessage.success('已保存修改')
    } else {
      await questionApi.create(payload)
      ElMessage.success('题目已新增')
    }
    goList()
  } finally {
    saving.value = false
  }
}

async function confirmDuplicate() {
  try {
    const data = await questionApi.checkDuplicate(
      form.title.trim(),
      isEdit.value ? questionId.value : null,
    )
    const hit = data?.duplicate
    if (!hit) return true

    await ElMessageBox.confirm(
      `题库中已有相似题目 #${hit.question_id}（相似度 ${(hit.similarity * 100).toFixed(1)}%）：${hit.preview || ''}`,
      '检测到重复题目',
      {
        type: 'warning',
        confirmButtonText: '仍然保存',
        cancelButtonText: '返回修改',
        distinguishCancelAndClose: true,
      },
    )
    return true
  } catch (error) {
    // 用户点了「返回修改」→ 中止保存；查重接口本身出错 → 不阻塞保存
    if (error === 'cancel' || error === 'close') return false
    console.warn('[查重失败，跳过检查]', error)
    return true
  }
}

async function loadDetail() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const data = await questionApi.detail(questionId.value)
    form.type = data.type
    form.title = data.title || ''
    form.analysis = data.analysis || ''
    extId.value = data.ext_id || ''

    form.options = (data.options || []).map((item) => ({ key: item.key, text: item.text }))
    if (form.options.length < 2 && data.type !== 'judge' && data.type !== 'short') {
      form.options = defaultOptions()
    }

    if (data.type === 'multiple') form.answer = Array.isArray(data.answer) ? [...data.answer] : []
    else if (data.type === 'judge') form.answer = data.answer === true
    else if (data.type === 'short') form.answer = typeof data.answer === 'string' ? data.answer : ''
    else form.answer = typeof data.answer === 'string' ? data.answer : ''
  } finally {
    loading.value = false
  }
}

async function removeCurrent() {
  try {
    await ElMessageBox.confirm(
      `确定删除题目 #${questionId.value} 吗？该题的作答记录与收藏也会一并清除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户取消
  }
  await questionApi.remove(questionId.value)
  ElMessage.success('已删除')
  goList()
}

function goList() {
  router.push('/questions')
}

onMounted(async () => {
  if (isEdit.value) {
    await loadDetail()
  } else {
    form.options = defaultOptions()
    form.answer = ''
  }
})
</script>

<style scoped>
.page-wide {
  max-width: 1320px;
}

.block {
  margin-top: 16px;
  border-radius: 10px;
}

.option-editor {
  width: 100%;
}

.option-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.option-key-input {
  width: 64px;
  flex-shrink: 0;
}

.preview-block {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid var(--ikao-border);
  border-radius: 8px;
  background: #fbfcfe;
}

.preview-label {
  margin-top: 14px;
  font-size: 13px;
  color: var(--ikao-text-sub);
  font-weight: 600;
}

.answer-block {
  background: #f2fbf5;
  border-color: #d6f0de;
}

.answer-strong {
  color: #52b46b;
  font-weight: 600;
}

.preview-option {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 6px;
}

.preview-option:last-child {
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
</style>
