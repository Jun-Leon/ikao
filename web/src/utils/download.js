/**
 * 把接口返回的 Blob 保存成本地文件。
 * @param {Blob} blob 后端二进制响应
 * @param {string} filename 建议的文件名（含扩展名）
 */
export function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
