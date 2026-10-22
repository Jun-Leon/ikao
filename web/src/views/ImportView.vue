<!--
  SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
  SPDX-License-Identifier: MIT
-->
<template>
  <div class="page">
    <h2 class="page-title">题库导入</h2>
    <p class="page-desc">
      支持 JSON / CSV / Excel 题库。导入时自动做题干相似度去重，重复题目会被跳过并记入日志。
    </p>

    <el-card shadow="never" class="block">
      <div class="template-bar">
        <span class="template-text">没有现成题库？先下载 Excel 模板，按列填好后上传。</span>
        <el-button size="small" :icon="Download" :loading="downloading" @click="downloadTemplate">
          下载 Excel 模板
        </el-button>
      </div>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="上传文件" name="file">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".json,.csv,.xlsx,.xlsm,application/json"
            v-model:file-list="fileList"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :on-exceed="onExceed"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">把文件拖到这里，或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">
                支持 .json / .csv / .xlsx，单文件不超过 32MB
                <span v-if="selectedFileName"> · 已选：{{ selectedFileName }}</span>
              </div>
            </template>
          </el-upload>
        </el-tab-pane>

        <el-tab-pane label="本地路径" name="path">
          <el-input
            v-model="localPath"
            placeholder="例如 D:\\questions\\all_questions.json"
            clearable
          >
            <template #prepend>绝对路径</template>
          </el-input>
          <div class="el-upload__tip">仅支持 JSON，适合题库文件已放在本机固定位置的情况</div>
        </el-tab-pane>
      </el-tabs>

      <el-form label-width="96px" class="form">
        <el-form-item label="去重阈值">
          <el-slider
            v-model="threshold"
            :min="0.5"
            :max="1"
            :step="0.01"
            show-input
            :show-input-controls="false"
            @change="thresholdTouched = true"
          />
          <div class="el-upload__tip">
            越大越严格（1.0 表示只拦完全相同的题干）。默认 {{ appStore.dedupThreshold }}
          </div>
        </el-form-item>
      </el-form>

      <el-space>
        <el-button
          type="primary"
          :icon="Upload"
          :loading="importing"
          @click="doImport"
        >
          开始导入
        </el-button>
        <el-button :icon="RefreshLeft" @click="resetForm">重置</el-button>
        <el-button text :icon="Document" @click="router.push('/import/logs')">查看导入日志</el-button>
      </el-space>
    </el-card>

    <el-alert
      v-if="errorText"
      type="error"
      :title="`导入请求失败：${errorText}`"
      description="请确认后端已启动（浏览器打开 后端地址 + /api/health 应返回 JSON），并检查 web/.env.development 里的 VITE_API_TARGET 是否与后端端口一致；改完需重启 npm run dev。"
      :closable="false"
      show-icon
      class="alert"
    />

    <el-card v-if="result" shadow="never" class="block">
      <template #header>
        <span>导入结果</span>
      </template>

      <el-alert
        :type="alertType"
        :title="result.message || '导入完成'"
        :closable="false"
        show-icon
        class="alert"
      />

      <el-row :gutter="16" class="result-row">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">题目总数</div>
            <div class="stat-value">{{ result.total }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">成功入库</div>
            <div class="stat-value">{{ result.imported }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">重复跳过</div>
            <div class="stat-value warning">{{ result.duplicated }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">解析失败</div>
            <div class="stat-value danger">{{ result.failed }}</div>
          </div>
        </el-col>
      </el-row>

      <el-space class="result-actions">
        <el-button type="primary" plain @click="router.push(`/import/logs/${result.log_id}`)">
          查看本次明细
        </el-button>
        <el-button @click="refreshHome">刷新题库总数</el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Download, RefreshLeft, Upload, UploadFilled } from '@element-plus/icons-vue'
import { importApi } from '@/api'
import { useAppStore } from '@/stores/app'
import { saveBlob } from '@/utils/download'

const router = useRouter()
const appStore = useAppStore()

const activeTab = ref('file')
const fileList = ref([])
const localPath = ref('')
const threshold = ref(appStore.dedupThreshold ?? 0.9)
const thresholdTouched = ref(false)
const importing = ref(false)
const downloading = ref(false)
const result = ref(null)
const errorText = ref('')

// 元信息（含默认阈值）是异步加载的，等它到位后同步到滑块上（用户已手动调过则不覆盖）
watch(
  () => appStore.dedupThreshold,
  (value) => {
    if (!thresholdTouched.value && value) threshold.value = value
  },
)

const selectedFileName = computed(() => fileList.value[0]?.name || '')

const alertType = computed(() => {
  if (!result.value) return 'info'
  if (result.value.status === 'success') return 'success'
  if (result.value.status === 'partial') return 'warning'
  return 'error'
})

function onFileChange(file, files) {
  // 只保留最后一次选择的文件
  fileList.value = files.slice(-1)
}

function onFileRemove() {
  fileList.value = []
}

function onExceed() {
  ElMessage.warning('一次只能导入一个文件，请先移除已选文件')
}

function resetForm() {
  fileList.value = []
  localPath.value = ''
  result.value = null
  errorText.value = ''
}

async function downloadTemplate() {
  if (downloading.value) return
  downloading.value = true
  try {
    const blob = await importApi.downloadTemplate()
    saveBlob(blob, 'ikao-question-template.xlsx')
    ElMessage.success('模板已下载，填好后回到本页上传即可')
  } catch (error) {
    console.error('[下载模板失败]', error)
  } finally {
    downloading.value = false
  }
}

async function doImport() {
  if (importing.value) return

  const payload = { threshold: threshold.value }
  if (activeTab.value === 'file') {
    const file = fileList.value[0]
    if (!file || !file.raw) {
      ElMessage.warning('请先拖拽或点击选择要导入的文件')
      return
    }
    const name = file.name || ''
    if (/\.json$/i.test(name)) {
      payload.file = file.raw
      payload.table = false
    } else if (/\.(csv|xlsx|xlsm)$/i.test(name)) {
      payload.file = file.raw
      payload.table = true
    } else {
      ElMessage.warning('只支持 .json / .csv / .xlsx 文件')
      return
    }
  } else {
    const path = localPath.value.trim()
    if (!path) {
      ElMessage.warning('请填写 JSON 文件的绝对路径')
      return
    }
    if (!/\.json$/i.test(path)) {
      ElMessage.warning('本地路径方式仅支持 .json 文件')
      return
    }
    payload.path = path
  }

  importing.value = true
  errorText.value = ''
  try {
    const data = payload.table
      ? await importApi.uploadTable({ file: payload.file, threshold: payload.threshold })
      : await importApi.upload(payload)
    result.value = data
    if (data.status === 'failed') {
      ElMessage.error('导入失败，请查看下方提示与日志明细')
    } else {
      ElMessage.success(`导入完成：入库 ${data.imported}，重复 ${data.duplicated}，失败 ${data.failed}`)
    }
    await appStore.refreshCount()
  } catch (error) {
    // 页面内也留一份错误信息，方便排查（后端未启动 / 代理失败都会走到这里）
    errorText.value = error?.response?.data?.detail || error?.message || '导入请求失败'
    console.error('[导入失败]', error)
  } finally {
    importing.value = false
  }
}

async function refreshHome() {
  await appStore.refreshCount()
  ElMessage.success(`当前题库共 ${appStore.questionCount} 题`)
}
</script>

<style scoped>
.block {
  margin-top: 16px;
  border-radius: 10px;
}

.form {
  margin-top: 16px;
  max-width: 560px;
}

.template-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: var(--ikao-primary-soft);
}

.template-text {
  font-size: 13px;
  color: var(--ikao-text-sub);
}

.upload-icon {
  font-size: 48px;
  color: var(--ikao-primary);
}

.alert {
  margin-bottom: 16px;
}

.result-row {
  margin-bottom: 8px;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-value.danger {
  color: #f56c6c;
}
</style>
