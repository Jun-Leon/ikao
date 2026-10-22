// SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
// SPDX-License-Identifier: MIT

import http from './http'

/** 基础信息 */
export const metaApi = {
  health: () => http.get('/health'),
  meta: () => http.get('/meta'),
}

/** 题库导入 */
export const importApi = {
  /**
   * 导入题库 JSON
   * @param {{ file?: File, path?: string, threshold?: number }} payload
   */
  upload({ file, path, threshold }) {
    const form = new FormData()
    if (file) form.append('file', file)
    if (path) form.append('path', path)
    if (threshold !== undefined && threshold !== null && threshold !== '') {
      form.append('threshold', String(threshold))
    }
    return http.post('/import/json', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  /**
   * 导入 CSV / Excel 题库（列格式与下载的模板一致）
   * @param {{ file: File, threshold?: number }} payload
   */
  uploadTable({ file, threshold }) {
    const form = new FormData()
    if (file) form.append('file', file)
    if (threshold !== undefined && threshold !== null && threshold !== '') {
      form.append('threshold', String(threshold))
    }
    return http.post('/import/table', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  /** 下载 Excel 题库模板（返回 Blob） */
  downloadTemplate() {
    return http.get('/import/template', { responseType: 'blob' })
  },
  logs(params) {
    return http.get('/import/logs', { params })
  },
  logDetail(id, params) {
    return http.get(`/import/logs/${id}`, { params })
  },
  removeLog(id) {
    return http.delete(`/import/logs/${id}`)
  },
}

/** 题库管理（后台） */
export const questionApi = {
  /**
   * 分页检索题目
   * @param {{ page?: number, page_size?: number, type?: string, keyword?: string, order?: string }} params
   */
  list(params) {
    return http.get('/questions', { params })
  },
  stats() {
    return http.get('/questions/stats')
  },
  detail(id) {
    return http.get(`/questions/${id}`)
  },
  create(payload) {
    return http.post('/questions', payload)
  },
  update(id, payload) {
    return http.put(`/questions/${id}`, payload)
  },
  remove(id) {
    return http.delete(`/questions/${id}`)
  },
  /** 按题干查重，返回 { duplicate: { question_id, similarity, preview } | null } */
  checkDuplicate(title, excludeId) {
    return http.post('/questions/check-duplicate', { title, exclude_id: excludeId ?? null })
  },
  /**
   * 按当前筛选条件导出题库 CSV（返回 Blob）
   * @param {{ type?: string, keyword?: string, order?: string }} params
   */
  exportCsv(params) {
    return http.get('/questions/export', { params, responseType: 'blob' })
  },
}

/** 刷题（阶段 3 核心业务） */
export const practiceApi = {
  /** 当前档案的刷题概览：{ total, answered, correct, wrong, favorite } */
  stats() {
    return http.get('/practice/stats')
  },
  /**
   * 按模式抽题（默认不含答案与解析；背题模式会带上 answer / analysis）
   * @param {{ mode?: string, type?: string, keyword?: string, count?: number, page?: number }} params
   * mode: sequence 顺序 / recite 背题 / random 随机 / wrong 错题 / favorite 收藏
   */
  questions(params) {
    return http.get('/practice/questions', { params })
  },
  /** 提交作答，返回 { is_correct, correct_answer, analysis, need_self_eval, state } */
  answer(payload) {
    return http.post('/practice/answer', payload)
  },
  /** 简答题自评 */
  selfEvaluate(payload) {
    return http.post('/practice/self-evaluate', payload)
  },
  /** 收藏切换，返回 { question_id, is_favorite } */
  toggleFavorite(questionId) {
    return http.post(`/practice/favorites/${questionId}/toggle`)
  },
  /** 移出错题本 */
  removeWrong(questionId) {
    return http.delete(`/practice/wrong/${questionId}`)
  },
  /**
   * 错题本分页（含答案与解析）
   * @param {{ page?: number, page_size?: number, type?: string, keyword?: string, order?: string }} params
   * order: recent 最近作答 / oldest 最早作答 / wrong 错次最多
   */
  wrong(params) {
    return http.get('/practice/wrong', { params })
  },
  /** 收藏夹分页（含答案与解析） */
  favorites(params) {
    return http.get('/practice/favorites', { params })
  },
}

/** 统计看板（阶段 4） */
export const statsApi = {
  /** 一次拿到概览 / 题型 / 模式 / 趋势 / 高频错题 */
  board(params) {
    return http.get('/stats/board', { params })
  },
}

/** 本地档案 */
export const profileApi = {
  list: () => http.get('/profiles'),
  current: () => http.get('/profiles/current'),
  create: (name) => http.post('/profiles', { name }),
  switch: (id) => http.post(`/profiles/${id}/switch`),
  remove: (id) => http.delete(`/profiles/${id}`),
}
