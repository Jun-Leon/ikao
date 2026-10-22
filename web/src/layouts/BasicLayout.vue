<!--
  SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
  SPDX-License-Identifier: MIT
-->
<template>
  <el-container class="layout">
    <el-header class="layout-header">
      <div class="brand" @click="router.push('/')">
        <span class="brand-dot" />
        <span class="brand-name">{{ appStore.appName }}</span>
        <el-tag v-if="appStore.version" size="small" effect="plain" round>
          v{{ appStore.version }}
        </el-tag>
      </div>

      <el-menu
        class="layout-menu"
        mode="horizontal"
        :default-active="activeMenu"
        :ellipsis="false"
        @select="onSelect"
      >
        <template v-for="item in menus" :key="item.index">
          <el-sub-menu v-if="item.children" :index="item.index">
            <template #title>{{ item.label }}</template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              {{ child.label }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.index">{{ item.label }}</el-menu-item>
        </template>
      </el-menu>

      <div class="profile-box">
        <span class="profile-label">当前档案</span>
        <el-select
          v-model="appStore.currentProfileId"
          size="default"
          style="width: 140px"
          @change="onSwitchProfile"
        >
          <el-option
            v-for="profile in appStore.profiles"
            :key="profile.id"
            :label="profile.name"
            :value="profile.id"
          />
        </el-select>
        <el-button :icon="Plus" text @click="createDialog = true">新建</el-button>
      </div>
    </el-header>

    <el-main class="layout-main">
      <router-view v-slot="{ Component }">
        <component :is="Component" />
      </router-view>
    </el-main>

    <el-dialog v-model="createDialog" title="新建档案" width="360px">
      <el-input v-model="newProfileName" placeholder="例如：张三 / 复习专用" maxlength="16" show-word-limit />
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreateProfile">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()

// 练习相关入口直接铺开在顶栏，避免下拉里藏功能；题库维护类收纳进「题库」分组
const menus = [
  { index: '/', label: '首页' },
  { index: '/practice', label: '开始刷题' },
  { index: '/wrong', label: '错题本' },
  { index: '/favorites', label: '收藏夹' },
  { index: '/stats', label: '统计看板' },
  {
    index: 'bank',
    label: '题库',
    children: [
      { index: '/questions', label: '题库管理' },
      { index: '/import', label: '题库导入' },
      { index: '/import/logs', label: '导入日志' },
    ],
  },
]

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/import/logs')) return '/import/logs'
  if (path.startsWith('/import')) return '/import'
  if (path.startsWith('/questions')) return '/questions'
  if (path.startsWith('/practice')) return '/practice'
  if (path.startsWith('/wrong')) return '/wrong'
  if (path.startsWith('/favorites')) return '/favorites'
  if (path.startsWith('/stats')) return '/stats'
  return path
})

const createDialog = ref(false)
const newProfileName = ref('')
const creating = ref(false)

function onSelect(index) {
  if (index !== route.path) router.push(index)
}

async function onSwitchProfile(id) {
  await appStore.switchProfile(id)
  ElMessage.success(`已切换到「${appStore.currentProfileName}」`)
}

async function onCreateProfile() {
  const name = newProfileName.value.trim()
  if (!name) {
    ElMessage.warning('请输入档案名称')
    return
  }
  creating.value = true
  try {
    await appStore.createProfile(name)
    ElMessage.success('档案已创建')
    createDialog.value = false
    newProfileName.value = ''
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await Promise.all([appStore.loadMeta(), appStore.loadProfiles()])
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.layout-header {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 58px;
  background: #fff;
  border-bottom: 1px solid var(--ikao-border);
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex-shrink: 0;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: linear-gradient(135deg, #3a8aff, #7db4ff);
}

.brand-name {
  font-size: 16px;
  font-weight: 600;
}

.layout-menu {
  flex: 1;
  border-bottom: none;
}

.profile-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.profile-label {
  color: var(--ikao-text-sub);
  font-size: 13px;
}

.layout-main {
  padding: 20px 24px 40px;
}
</style>
