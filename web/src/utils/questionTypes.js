// SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
// SPDX-License-Identifier: MIT

/**
 * 题型相关的常量与展示辅助，供列表页 / 表单页 / 后续刷题页共用。
 * 取值与后端 models.py 中的 QUESTION_TYPES 保持一致。
 */
export const QUESTION_TYPES = [
  { value: 'single', label: '单选题', short: '单选', tag: 'primary' },
  { value: 'multiple', label: '多选题', short: '多选', tag: 'success' },
  { value: 'judge', label: '判断题', short: '判断', tag: 'warning' },
  { value: 'short', label: '简答题', short: '简答', tag: 'info' },
]

const TYPE_MAP = Object.fromEntries(QUESTION_TYPES.map((item) => [item.value, item]))

export function typeLabel(value) {
  return TYPE_MAP[value]?.label || value || '未知'
}

export function typeShort(value) {
  return TYPE_MAP[value]?.short || value || '未知'
}

export function typeTag(value) {
  return TYPE_MAP[value]?.tag || 'info'
}

/** 选项序号：0 -> A，25 -> Z，26 -> AA */
export function optionKeyAt(index) {
  let key = ''
  let n = index
  do {
    key = String.fromCharCode(65 + (n % 26)) + key
    n = Math.floor(n / 26) - 1
  } while (n >= 0)
  return key
}

/** 练习模式（与后端 practice_service.PRACTICE_MODES 一致） */
export const PRACTICE_MODES = [
  { value: 'sequence', label: '顺序练习', desc: '按题号从前往后逐题练习' },
  { value: 'recite', label: '背题模式', desc: '直接显示答案与解析，边看边背，不计入作答统计' },
  { value: 'random', label: '随机练习', desc: '随机抽题，适合快速自测' },
  { value: 'wrong', label: '错题重做', desc: '只练最近一次做错的题' },
  { value: 'favorite', label: '我的收藏', desc: '只练已收藏的题' },
]

/** 把答案转成完整可读文字（判断题→正确/错误，多选→AB，简答→原文） */
export function answerText(type, answer) {
  if (type === 'judge') {
    if (answer === true) return '正确'
    if (answer === false) return '错误'
    return '—'
  }
  if (type === 'multiple') {
    if (Array.isArray(answer)) return answer.length ? answer.join('') : '—'
    return answer ? String(answer) : '—'
  }
  if (type === 'single') return answer ? String(answer) : '—'
  const text = answer === null || answer === undefined ? '' : String(answer)
  return text.trim() ? text : '—'
}

/** 把答案转成列表页里的一行文字 */
export function formatAnswer(row) {
  const text = answerText(row?.type, row?.answer)
  if (row?.type !== 'short') return text
  const compact = text.replace(/\s+/g, ' ').trim()
  if (!compact || compact === '—') return '—'
  return compact.length > 40 ? `${compact.slice(0, 40)}...` : compact
}
