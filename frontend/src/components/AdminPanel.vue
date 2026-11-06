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
              <form class="import-wizard" @submit.prevent="submitImport">
                <div class="wizard-heading"><div><strong>导入 App</strong><span>源码仓库或 APK；默认创建新项目，也可以加入已有项目。</span></div><span class="stage">{{ importStage }}</span></div>
                <div class="wizard-grid">
                  <label>来源<select v-model="sourceType"><option value="source">源码仓库</option><option value="apk">APK 文件</option></select></label>
                  <label>归属<select v-model="projectMode"><option value="new">创建新项目</option><option value="existing">加入已有项目</option></select></label>
                  <label v-if="projectMode === 'new'">项目 ID<input v-model="projectId" required pattern="[A-Za-z0-9][A-Za-z0-9_-]*"></label>
                  <label v-else>已有项目<select v-model="projectId" required><option value="">选择项目</option><option v-for="project in projectOptions" :key="project.id" :value="project.id">{{ project.name }}（{{ project.id }}）</option></select></label>
                  <label v-if="projectMode === 'new'">项目名称<input v-model="projectName" required></label>
                  <label>App ID<input v-model="appId" required pattern="[A-Za-z0-9][A-Za-z0-9_-]*"></label>
                  <label>App 名称<input v-model="appName" required></label>
                  <label v-if="sourceType === 'source'" class="wide">Git 仓库地址<input v-model="repoUrl" type="url" required placeholder="https://github.com/org/repo.git"></label>
                  <label v-else class="wide">APK 文件<input type="file" accept=".apk,application/vnd.android.package-archive" required @change="onApkSelected"></label>
                  <label>Map<select v-model="mapMode"><option value="none">暂不生成</option><option value="fast">Fast（本地静态分析，不调用模型）</option><option value="full" :disabled="sourceType === 'apk'">Full（模型分析）</option></select></label>
                </div>
                <div v-if="sourceType === 'apk'" class="wizard-note">APK 会先由 JADX 反编译。Full Map 尚未支持 APK，因此只能选择不生成或 Fast。</div>
                <div v-if="mapMode === 'full'" class="full-model"><strong>Full 使用模型</strong><ModelSettings :api-base="apiBase" :admin="false" @change="fullModel = $event"/><p v-if="fullModel">将使用 {{ fullModel.providerID }} / {{ fullModel.modelID }}</p><p v-else>请选择已在“模型服务”中配置凭证的模型。</p></div>
                <label v-if="mapMode === 'full'" class="full-confirm"><input v-model="fullConfirmed" type="checkbox" required><span>我确认 Full 会把源码与静态分析结果发送给上面选择的模型。消耗取决于项目规模，当前无法准确估算，可能产生供应商费用。</span></label>
                <div class="wizard-actions"><button type="submit" :disabled="isImporting || (mapMode === 'full' && (!fullConfirmed || !fullModel))">{{ isImporting ? '正在导入…' : '开始导入' }}</button><span v-if="importError" class="import-error">{{ importError }}</span></div>
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

          <div v-if="activeTab === 'models'" class="view-card model-service-view">
            <ModelSettings :api-base="apiBase" :admin="true" />
          </div>
          <div v-if="activeTab === 'environment'" class="view-card"><EnvironmentDiagnostics :api-base="apiBase" /></div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { X, Settings, Database, Terminal, ShieldCheck, ChevronRight, Bot, Wrench } from 'lucide-vue-next'
import ProjectDetail from './ProjectDetail.vue' // 引入详情子组件
import ModelSettings from './ModelSettings.vue'
import EnvironmentDiagnostics from './EnvironmentDiagnostics.vue'
import { authFetch } from '../utils/auth'

const props = defineProps(['appList', 'apiBase'])
const emit = defineEmits(['close', 'imported'])

const sourceType = ref('source')
const projectMode = ref('new')
const projectId = ref('')
const projectName = ref('')
const appId = ref('')
const appName = ref('')
const repoUrl = ref('')
const mapMode = ref('none')
const fullConfirmed = ref(false)
const fullModel = ref(null)
const apkFile = ref(null)
const isImporting = ref(false)
const importError = ref('')
const importStage = ref('等待配置')
const projectOptions = computed(() => {
  const seen = new Map()
  for (const app of props.appList || []) {
    const id = app.project_id || app.id
    if (!seen.has(id)) seen.set(id, { id, name: app.project_name || id })
  }
  return [...seen.values()]
})
watch(sourceType, value => { if (value === 'apk' && mapMode.value === 'full') mapMode.value = 'fast' })
watch(mapMode, value => { if (value !== 'full') { fullConfirmed.value = false; fullModel.value = null } })
watch(projectMode, () => { projectId.value = ''; projectName.value = '' })
const onApkSelected = (event) => { apkFile.value = event.target.files?.[0] || null }
const pollMap = async (taskId) => {
  for (let attempt = 0; attempt < 180; attempt++) {
    const response = await authFetch(`${props.apiBase}/map/tasks/${taskId}`)
    const task = await response.json()
    if (!response.ok) throw new Error(task.detail || 'Map 状态读取失败')
    importStage.value = `Map ${task.status} · ${task.progress || 0}%`
    if (task.status === 'success') return
    if (task.status === 'error') throw new Error(task.message || 'Map 生成失败')
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  throw new Error('Map 生成超时，可稍后在项目分析区查看任务')
}
const submitImport = async () => {
  if (isImporting.value || (sourceType.value === 'apk' && !apkFile.value)) return
  isImporting.value = true
  importError.value = ''
  importStage.value = sourceType.value === 'apk' ? '上传并反编译 APK' : '克隆源码仓库'
  try {
    let response
    if (sourceType.value === 'apk') {
      const body = new FormData()
      body.set('app_id', appId.value); body.set('app_name', appName.value); body.set('file', apkFile.value); body.set('map_mode', mapMode.value); body.set('project_id', projectId.value)
      if (projectMode.value === 'new') { body.set('project_name', projectName.value); body.set('new_project', 'true') }
      response = await authFetch(`${props.apiBase}/import/apk`, { method: 'POST', body })
    } else {
      response = await authFetch(`${props.apiBase}/import/source`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ app_id: appId.value, name: appName.value, repo_url: repoUrl.value, project_id: projectId.value, project_name: projectMode.value === 'new' ? projectName.value : null, new_project: projectMode.value === 'new', map_mode: mapMode.value, full_confirmed: fullConfirmed.value, model: mapMode.value === 'full' ? fullModel.value : null }) })
    }
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || `导入失败 (${response.status})`)
    importStage.value = result.stage === 'decompiled' ? 'APK 反编译完成' : '源码克隆完成'
    logs.value.push(`[IMPORT] ${new Date().toLocaleTimeString()}: ${appId.value} 导入完成`)
    const importedId = result.app_id
    if (result.map_task_id) await pollMap(result.map_task_id)
    else importStage.value = '完成 · 未生成 Map'
    appId.value = ''; appName.value = ''; repoUrl.value = ''
    apkFile.value = null
    emit('imported', importedId)
  } catch (error) {
    importError.value = error.message || '导入失败'
    importStage.value = '失败'
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
  { id: 'models', label: '模型服务', icon: Bot },
  { id: 'environment', label: '本机环境', icon: Wrench },
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
.import-wizard{margin:20px 0 28px;padding:20px;border:1px solid #dbe4e8;border-radius:14px;background:#f8fafc}.wizard-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}.wizard-heading div{display:flex;flex-direction:column;gap:4px}.wizard-heading span{color:#64748b;font-size:12px}.wizard-heading .stage{padding:5px 9px;border-radius:20px;background:#e2f3ef;color:#0f766e}.wizard-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.wizard-grid label{display:flex;flex-direction:column;gap:6px;color:#475569;font-size:12px;font-weight:600}.wizard-grid label.wide{grid-column:1/-1}.wizard-grid input,.wizard-grid select{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #cbd5e1;border-radius:7px;background:#fff;color:#1e293b}.wizard-note{margin-top:12px;padding:10px 12px;border-left:3px solid #d49b2c;background:#fff8e8;color:#795d22;font-size:12px}.full-confirm{display:flex;align-items:flex-start;gap:9px;margin-top:12px;padding:12px;background:#fff4e5;color:#7c4a13;font-size:12px;line-height:1.5}.full-confirm input{margin-top:3px}.wizard-actions{display:flex;align-items:center;gap:12px;margin-top:16px}.wizard-actions button{padding:10px 16px;border:0;border-radius:7px;background:#0d9488;color:white;cursor:pointer}.wizard-actions button:disabled{opacity:.6;cursor:wait}
.full-model{margin-top:12px;padding:12px;border:1px solid #d5e0e6;border-radius:8px;background:white}.full-model>strong,.full-model>p{display:block;margin:0 0 7px}.full-model :deep(.model-settings){padding:7px 0;border:0}
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
@media(max-width:900px){.admin-screen{padding:12px}.admin-main{flex-direction:column}.admin-main .admin-nav{width:auto;padding:8px;display:flex;flex-wrap:wrap;gap:4px}.admin-main .nav-item{margin:0;padding:8px}.admin-body{padding:16px}.wizard-grid{grid-template-columns:1fr}.wizard-grid label.wide{grid-column:auto}}
.view-card { max-width: 1000px; }
.data-table { width: 100%; border-collapse: collapse; margin-top: 24px; }
.data-table th { text-align: left; padding: 14px; background: #f1f5f9; color: #64748b; font-size: 13px; }
.data-table td { padding: 16px 14px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
.clickable-row { cursor: pointer; }
.clickable-row:hover { background: #f8fafc; }
.arrow-cell { text-align: right; color: #cbd5e1; }
.terminal { background: #0f172a; color: #10b981; padding: 20px; border-radius: 12px; font-family: 'Courier New', monospace; font-size: 13px; min-height: 300px; }
.model-service-view{max-width:820px}
.icon-spin { animation: spin 4s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
