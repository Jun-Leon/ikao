<template>
  <div class="page page-wide">
    <h2 class="page-title">错题本</h2>
    <p class="page-desc">最近一次作答为错的题目会自动收进这里；复盘后可「移出错题本」，或在刷题页选择「错题重做」集中攻克</p>

    <ReviewList mode="wrong" />
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
