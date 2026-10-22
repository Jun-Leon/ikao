// SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
// SPDX-License-Identifier: MIT

import axios from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 统一的 axios 实例。
 * - baseURL 固定 /api，开发期由 vite 代理到后端（见 web/.env.development），打包后由后端托管时同源
 * - 响应拦截器直接返回 data，业务层不用再 .data
 */
const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error?.response?.data?.detail
    const message = typeof detail === 'string' ? detail : error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default http
