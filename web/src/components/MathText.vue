<template>
  <component :is="tag" class="rich-text" v-html="html" />
</template>

<script setup>
import { computed } from 'vue'
import { renderRichText } from '@/utils/richText'

/**
 * 富文本展示组件：题干、选项、答案、解析统一用它渲染，
 * 保证 Markdown 与 KaTeX 公式的显示一致。
 */
const props = defineProps({
  text: { type: String, default: '' },
  tag: { type: String, default: 'div' },
})

const html = computed(() => renderRichText(props.text))
</script>
