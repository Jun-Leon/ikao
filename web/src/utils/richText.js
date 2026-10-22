// SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
// SPDX-License-Identifier: MIT

import MarkdownIt from 'markdown-it'
import katex from 'katex'

/**
 * 富文本渲染：Markdown + KaTeX。
 *
 * 思路：先把 $...$ / $$...$$ 抽成占位符（防止 markdown-it 转义 LaTeX 反斜杠），
 * 交给 markdown-it 渲染后再用 KaTeX 的 HTML 替换回占位符。
 */

const md = new MarkdownIt({ breaks: true, linkify: true, html: false })

const MATH_RE = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\))/g

const PLACEHOLDER_PREFIX = '@@IKAOMATH'
const PLACEHOLDER_RE = /@@IKAOMATH(\d+)@@/g

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMathExpression(raw) {
  let expr = raw
  let displayMode = false

  if (raw.startsWith('$$')) {
    displayMode = true
    expr = raw.slice(2, -2)
  } else if (raw.startsWith('\\[')) {
    displayMode = true
    expr = raw.slice(2, -2)
  } else if (raw.startsWith('\\(')) {
    expr = raw.slice(2, -2)
  } else {
    expr = raw.slice(1, -1)
  }

  try {
    return katex.renderToString(expr.trim(), {
      displayMode,
      throwOnError: false,
      strict: false,
      output: 'html',
      trust: true,
    })
  } catch (error) {
    // 渲染失败时原样显示，避免内容丢失
    return `<code>${escapeHtml(raw)}</code>`
  }
}

/**
 * 把一段文本渲染成 HTML（Markdown + 公式）。
 * @param {string} text 原始文本
 * @returns {string} HTML 字符串
 */
export function renderRichText(text) {
  if (!text) return ''
  const source = String(text)

  if (!source.includes('$') && !source.includes('\\(') && !source.includes('\\[')) {
    return md.render(source)
  }

  const mathTokens = []
  const withPlaceholders = source.replace(MATH_RE, (match) => {
    mathTokens.push(renderMathExpression(match))
    return `${PLACEHOLDER_PREFIX}${mathTokens.length - 1}@@`
  })

  const html = md.render(withPlaceholders)
  return html.replace(PLACEHOLDER_RE, (_match, index) => mathTokens[Number(index)] ?? '')
}

export default renderRichText
