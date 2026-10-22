// SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
// SPDX-License-Identifier: MIT

import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * 使用 hash 模式：离线单机版直接用 file:// 或内嵌静态服务打开时都不会 404。
 * 各阶段页面按需补充，未实现的模块先不挂路由。
 */
const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/practice',
    name: 'practice',
    component: () => import('@/views/PracticeView.vue'),
    meta: { title: '开始刷题' },
  },
  {
    path: '/wrong',
    name: 'wrong-book',
    component: () => import('@/views/WrongBookView.vue'),
    meta: { title: '错题本' },
  },
  {
    path: '/favorites',
    name: 'favorites',
    component: () => import('@/views/FavoriteView.vue'),
    meta: { title: '收藏夹' },
  },
  {
    path: '/stats',
    name: 'stats',
    component: () => import('@/views/StatsView.vue'),
    meta: { title: '统计看板' },
  },
  {
    path: '/import',
    name: 'import',
    component: () => import('@/views/ImportView.vue'),
    meta: { title: '题库导入' },
  },
  {
    path: '/import/logs',
    name: 'import-logs',
    component: () => import('@/views/ImportLogsView.vue'),
    meta: { title: '导入日志' },
  },
  {
    path: '/import/logs/:id',
    name: 'import-log-detail',
    component: () => import('@/views/ImportLogDetailView.vue'),
    meta: { title: '导入明细' },
  },
  {
    path: '/questions',
    name: 'questions',
    component: () => import('@/views/QuestionListView.vue'),
    meta: { title: '题库管理' },
  },
  {
    path: '/questions/new',
    name: 'question-new',
    component: () => import('@/views/QuestionFormView.vue'),
    meta: { title: '新增题目' },
  },
  {
    path: '/questions/:id/edit',
    name: 'question-edit',
    component: () => import('@/views/QuestionFormView.vue'),
    meta: { title: '编辑题目' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · ikao` : 'ikao'
})

export default router
