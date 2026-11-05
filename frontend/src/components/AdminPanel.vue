<template>
  <div class="admin-screen">
    <div class="admin-layout">
      <header class="admin-topbar">
        <div class="brand">
          <Settings class="icon-spin" :size="20" />
          <span>GUI-Anything 后台管理系统</span>
        </div>
        <button class="close-btn" @click="$emit('close')"><X :size="24" /></button>
      </header>

      <div class="admin-main">
        <aside class="admin-nav">
          <div 
            v-for="item in menuItems" 
            :key="item.id"
            :class="['nav-item', activeTab === item.id ? 'active' : '']"
            @click="activeTab = item.id; selectedProject = null"
          >
            <component :is="item.icon" :size="18" /> {{ item.label }}
          </div>
        </aside>

        <section class="admin-body">
          <div v-if="activeTab === 'projects'">
            <div v-if="!selectedProject" class="view-card">
              <div class="view-header">
                <h2>项目清单 ({{ appList.length }})</h2>
                <p>点击行进入项目详情管理</p>
              </div>
              <form class="apk-import" @submit.prevent="uploadApk">
                <label>导入 APK</label>
                <input v-model="newAppId" placeholder="项目 ID（字母、数字、-、_）" required pattern="[A-Za-z0-9][A-Za-z0-9_-]*" />
                <input type="file" accept=".apk,application/vnd.android.package-archive" required @change="onApkSelected" />
                <button type="submit" :disabled="isImporting">{{ isImporting ? '正在反编译…' : '导入并解析' }}</button>
                <span v-if="importError" class="import-error">{{ importError }}</span>
              </form>
              <table class="data-table">
                <thead>
                  <tr>
                    <th>项目 ID</th>
                    <th>名称</th>
                    <th>关联代码库</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="app in appList" :key="app.id" @click="selectedProject = app" class="clickable-row">
                    <td><b>{{ app.id }}</b></td>
                    <td>{{ app.name }}</td>
                    <td><code>{{ app.repo_url || 'N/A' }}</code></td>
                    <td class="arrow-cell"><ChevronRight :size="16" /></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <ProjectDetail 
            v-else 
            :project="selectedProject" 
            :apiBase="apiBase"  @back="selectedProject = null" 
            @task="onTaskTriggered"
            />
          </div>

          <div v-if="activeTab === 'logs'" class="view-card">
            <h2>系统执行日志</h2>
            <div class="terminal">
              <p v-for="(log, i) in logs" :key="i">{{ log }}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { X, Settings, Database, Terminal, ShieldCheck, ChevronRight } from 'lucide-vue-next'
import ProjectDetail from './ProjectDetail.vue' // 引入详情子组件
import { authFetch } from '../utils/auth'

const props = defineProps(['appList', 'apiBase'])
const emit = defineEmits(['close', 'imported'])

const newAppId = ref('')
const apkFile = ref(null)
const isImporting = ref(false)
const importError = ref('')
const onApkSelected = (event) => { apkFile.value = event.target.files?.[0] || null }
const uploadApk = async () => {
  if (!apkFile.value || isImporting.value) return
  isImporting.value = true
  importError.value = ''
  try {
    const body = new FormData()
    body.set('app_id', newAppId.value)
    body.set('file', apkFile.value)
    const response = await authFetch(`${props.apiBase}/import/apk`, { method: 'POST', body })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || `导入失败 (${response.status})`)
    logs.value.push(`[APK] ${new Date().toLocaleTimeString()}: ${newAppId.value} 导入完成`)
    newAppId.value = ''
    apkFile.value = null
    emit('imported', result.app_id)
  } catch (error) {
    importError.value = error.message || '导入失败'
  } finally {
    isImporting.value = false
  }
}

const activeTab = ref('projects')
const selectedProject = ref(null)
const logs = ref([
  '[SYSTEM] 后台管理系统初始化完成...',
  `[INFO] API 路径: ${props.apiBase}`
])

const menuItems = [
  { id: 'projects', label: '项目资源管理', icon: Database },
  { id: 'logs', label: '任务执行日志', icon: Terminal },
  { id: 'security', label: '审计策略配置', icon: ShieldCheck }
]

const onTaskTriggered = ({ id, type }) => {
  const timestamp = new Date().toLocaleTimeString()
  logs.value.push(`[TASK] ${timestamp}: 对项目 ${id} 触发了 ${type} 指令`)
  alert(`任务已下发: ${type} @ ${id}`)
}
</script>

<style scoped>
.apk-import { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 20px 0; padding: 14px; background: #f1f5f9; border-radius: 10px; }
.apk-import input { max-width: 240px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.apk-import button { padding: 9px 14px; border: 0; border-radius: 6px; background: #0d9488; color: white; cursor: pointer; }
.apk-import button:disabled { opacity: .6; cursor: wait; }
.import-error { width: 100%; color: #b91c1c; font-size: 13px; }
/* 保持你之前喜欢的样式风格 */
.admin-screen { position: fixed; inset: 0; background: rgba(2, 6, 23, 0.9); z-index: 2000; display: flex; padding: 30px; }
.admin-layout { width: 100%; max-width: 1400px; margin: 0 auto; background: #ffffff; border-radius: 20px; display: flex; flex-direction: column; overflow: hidden; }
.admin-topbar { background: #0f172a; color: white; padding: 18px 28px; display: flex; justify-content: space-between; align-items: center; }
.brand { display: flex; align-items: center; gap: 12px; font-weight: 800; }
.admin-main { flex: 1; display: flex; overflow: hidden; }
.admin-nav { width: 240px; background: #f8fafc; border-right: 1px solid #e2e8f0; padding: 20px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-radius: 10px; cursor: pointer; color: #64748b; font-size: 14px; margin-bottom: 6px; transition: 0.2s; }
.nav-item.active { background: #10b981; color: white; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }
.admin-body { flex: 1; min-width: 0; padding: 40px; overflow-y: auto; background: #ffffff; }
@media(max-width:900px){.admin-screen{padding:12px}.admin-main{flex-direction:column}.admin-main .admin-nav{width:auto;padding:8px;display:flex;flex-wrap:wrap;gap:4px}.admin-main .nav-item{margin:0;padding:8px}.admin-body{padding:16px}}
.view-card { max-width: 1000px; }
.data-table { width: 100%; border-collapse: collapse; margin-top: 24px; }
.data-table th { text-align: left; padding: 14px; background: #f1f5f9; color: #64748b; font-size: 13px; }
.data-table td { padding: 16px 14px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
.clickable-row { cursor: pointer; }
.clickable-row:hover { background: #f8fafc; }
.arrow-cell { text-align: right; color: #cbd5e1; }
.terminal { background: #0f172a; color: #10b981; padding: 20px; border-radius: 12px; font-family: 'Courier New', monospace; font-size: 13px; min-height: 300px; }
.icon-spin { animation: spin 4s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
