<!--
  SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
  SPDX-License-Identifier: MIT
-->
<template>
  <div class="page page-wide">
    <h2 class="page-title">收藏夹</h2>
    <p class="page-desc">刷题时点「收藏」即可把题目收进这里，方便随时回看题干、答案与解析</p>

    <ReviewList mode="favorite" />
  </div>
</template>

<script setup>
import ReviewList from '@/components/ReviewList.vue'
</script>

<style scoped>
.page-wide {
  max-width: 1320px;
}
</style>
