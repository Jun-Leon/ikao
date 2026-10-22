import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { createPinia } from 'pinia'

import 'element-plus/dist/index.css'
import 'katex/dist/katex.min.css'
import '@/styles/index.css'

import App from '@/App.vue'
import router from '@/router'

const app = createApp(App)

// 全量注册 Element Plus 图标，模板中可直接用 <el-icon><Upload /></el-icon>
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
