<template>
  <div>
    <el-card shadow="never" class="block">
      <el-space wrap class="toolbar">
        <el-select v-model="query.type" placeholder="全部题型" clearable style="width: 130px" @change="reload">
          <el-option v-for="item in QUESTION_TYPES" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-input
          v-model="query.keyword"
          placeholder="搜索题干 / 选项"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
          @clear="reload"
        >
          <template #append>
            <el-button :icon="Search" @click="reload" />
          </template>
        </el-input>

        <el-select v-model="query.order" style="width: 150px" @change="reload">
          <el-option v-for="item in orderOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-button :icon="Refresh" @click="reload">刷新</el-button>
      </el-space>

      <el-table :data="rows" v-loading="loading" stripe @row-click="openDetail">
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column label="题型" width="92">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small" effect="light">{{ typeShort(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题干" min-width="320">
          <template #default="{ row }">
            <div class="stem"><MathText :text="row.title" /></div>
          </template>
        </el-table-column>
        <el-table-column label="答案" width="110">
          <template #default="{ row }">
            <span class="answer">{{ formatAnswer(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isWrong" label="错误次数" width="100" align="center">
          <template #default="{ row }">
            <span class="wrong-count">{{ row.wrong_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="练习次数" width="100" align="center">
          <template #default="{ row }">{{ row.practice_count }}</template>
        </el-table-column>
        <el-table-column :label="isWrong ? '最近作答' : '收藏时间'" width="160">
          <template #default="{ row }">{{ formatTime(row.marked_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">查看</el-button>
            <el-button link type="danger" @click.stop="removeRow(row)">
              {{ isWrong ? '移出错题本' : '取消收藏' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        class="pager"
        @size-change="reload"
        @current-change="load"
      />
    </el-card>

    <AnswerAnalysisDialog
      v-model="detailVisible"
      :question="current"
      :user-answer="current?.last_answer"
      :correct-answer="current?.answer"
      :analysis="current?.analysis || ''"
      :is-correct="current?.last_correct ?? null"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { practiceApi } from '@/api'
import AnswerAnalysisDialog from '@/components/AnswerAnalysisDialog.vue'
import MathText from '@/components/MathText.vue'
import { QUESTION_TYPES, formatAnswer, typeShort, typeTag } from '@/utils/questionTypes'

/**
 * 错题本 / 收藏夹共用列表：后端口径不同（wrong / favorite），
 * 其余筛选、排序、分页与详情查看逻辑一致。
 */
const props = defineProps({
  mode: { type: String, default: 'wrong' },
})

const isWrong = computed(() => props.mode === 'wrong')

const query = reactive({
  page: 1,
  page_size: 20,
  type: '',
  keyword: '',
  order: 'recent',
})

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const detailVisible = ref(false)
const current = ref(null)

const orderOptions = computed(() =>
  isWrong.value
    ? [
        { value: 'recent', label: '最近作答' },
        { value: 'oldest', label: '最早作答' },
        { value: 'wrong', label: '错次最多' },
      ]
    : [
        { value: 'recent', label: '最近收藏' },
        { value: 'oldest', label: '最早收藏' },
      ],
)

async function load() {
  loading.value = true
  try {
    const params = {
      page: query.page,
      page_size: query.page_size,
      type: query.type || undefined,
      keyword: query.keyword || undefined,
      order: query.order,
    }
    const data = isWrong.value ? await practiceApi.wrong(params) : await practiceApi.favorites(params)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function reload() {
  query.page = 1
  await load()
}

async function removeRow(row) {
  if (isWrong.value) {
    await practiceApi.removeWrong(row.id)
    ElMessage.success('已移出错题本')
  } else {
    await practiceApi.toggleFavorite(row.id)
    ElMessage.success('已取消收藏')
  }
  if (rows.value.length === 1 && query.page > 1) query.page -= 1
  await load()
}

function openDetail(row) {
  current.value = row
  detailVisible.value = true
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 16)
}

onMounted(load)
</script>

<style scoped>
.block {
  border-radius: 10px;
}

.toolbar {
  margin-bottom: 12px;
}

.stem {
  line-height: 1.6;
}

.answer {
  color: #2e9c52;
  font-weight: 600;
}

.wrong-count {
  color: #d94b4b;
  font-weight: 600;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
