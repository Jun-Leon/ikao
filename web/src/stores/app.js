import { defineStore } from 'pinia'
import { metaApi, profileApi } from '@/api'

/**
 * 全局元信息 + 当前档案。
 * 离线单机版通过「档案」隔离不同人的作答数据。
 */
export const useAppStore = defineStore('app', {
  state: () => ({
    appName: 'ikao',
    version: '',
    dedupThreshold: 0.9,
    questionCount: 0,
    profiles: [],
    currentProfileId: null,
    currentProfileName: '',
    loaded: false,
  }),
  actions: {
    async loadMeta() {
      const data = await metaApi.meta()
      this.appName = data.app_name
      this.version = data.version
      this.dedupThreshold = data.dedup_threshold
      this.questionCount = data.question_count
      this.currentProfileId = data.current_profile_id
      this.currentProfileName = data.current_profile_name
      this.loaded = true
    },
    async loadProfiles() {
      this.profiles = await profileApi.list()
    },
    async switchProfile(id) {
      const profile = await profileApi.switch(id)
      this.currentProfileId = profile.id
      this.currentProfileName = profile.name
    },
    async createProfile(name) {
      const profile = await profileApi.create(name)
      await this.loadProfiles()
      return profile
    },
    /** 导入完成后刷新题目总数 */
    async refreshCount() {
      const data = await metaApi.meta()
      this.questionCount = data.question_count
    },
  },
})
