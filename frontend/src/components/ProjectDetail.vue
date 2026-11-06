<template>
  <div class="project-detail">
    <div class="breadcrumb" @click="$emit('back')">
      <ChevronLeft :size="16" /> 返回项目列表
    </div>

    <header class="detail-header">
      <div class="title-section">
        <div class="app-icon">{{ project.name[0] }}</div>
        <div>
          <h1>{{ project.name }}</h1>
          <div class="repo-info">
            <code class="repo-url">{{ project.source_type === 'apk' ? 'APK 导入项目' : project.repo_url }}</code>
            <span :class="['status-pill', repoStatus]">{{ statusText }}</span>
          </div>
        </div>
      </div>

      <div class="btn-group">
        <button v-if="repoStatus === 'missing' && project.source_type !== 'apk'" class="btn download" @click="handleAction('download')">
          <Download :size="16" /> 开始下载源码
        </button>
        
        <button v-else-if="project.source_type !== 'apk'" class="btn update" :disabled="repoStatus === 'syncing'" @click="handleAction('update')">
          <RefreshCw :class="{ 'spin': repoStatus === 'syncing' }" :size="16" /> 
          {{ repoStatus === 'syncing' ? '同步中...' : '检查代码更新' }}
        </button>
      </div>
    </header>

    <Transition name="fade">
      <div v-if="tipMsg" :class="['tip-banner', tipType]">
        <CheckCircle v-if="tipType === 'success'" :size="14" style="margin-right:8px" />
        <XCircle v-if="tipType === 'error'" :size="14" style="margin-right:8px" />
        {{ tipMsg }}
      </div>
    </Transition>

    <RunWorkbench v-if="repoStatus === 'ready'" :app-id="project.id" :api-base="apiBase" />

    <div class="detail-grid">
      <section class="info-card">
        <h3><Info :size="18" /> 审计对象详情</h3>
        <div class="info-item">
          <label>内部标识</label>
          <span>{{ project.id }}</span>
        </div>
        <div class="info-item">
          <label>存储路径</label>
          <span class="path-text">/app/repos/{{ project.id }}</span>
        </div>
      </section>

      <section class="info-card">
        <h3><Database :size="18" /> 数据同步状态</h3>
        <div class="stats-row">
          <div class="stat">
            <span class="label">代码状态</span>
            <span :class="['value', repoStatus === 'ready' ? 'green' : '']">{{ statusText }}</span>
          </div>
        </div>
      </section>

      <section class="info-card">
        <h3><Activity :size="18" /> UI Map 状态</h3>
        <div class="stats-row">
          <div class="stat">
            <span class="label">图谱状态</span>
            <span :class="['value', mapExists ? 'green' : '']">
              {{ mapExists ? '已生成' : '未生成' }}
            </span>
          </div>
          <div class="stat" v-if="mapUpdatedAt">
            <span class="label">更新时间</span>
            <span class="value small">{{ mapUpdatedAt }}</span>
          </div>
        </div>

        <div class="map-actions">
          <button
            class="btn-inline-sync"
            @click="generateUiMap"
            :disabled="isGeneratingMap || repoStatus !== 'ready'"
            :title="repoStatus !== 'ready' ? '请先下载并准备好代码仓库' : ''"
          >
            <RotateCw :size="14" :class="{ 'spin': isGeneratingMap }" />
            <span>
              {{ isGeneratingMap ? `生成中… ${mapProgress}%` : (mapExists ? 'Fast 重新出图' : 'Fast 出图') }}
            </span>
          </button>
          <span v-if="mapErr" class="map-err">{{ mapErr }}</span>
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import RunWorkbench from './RunWorkbench.vue'
import { ref, computed, onMounted } from 'vue'
import { 
  ChevronLeft, Download, RefreshCw, XCircle, CheckCircle, 
  Info, RotateCw, Database, Activity
} from 'lucide-vue-next'
import { authFetch } from '../utils/auth'

const props = defineProps(['project', 'apiBase']) 
const emit = defineEmits(['back'])

// 基础状态
const repoStatus = ref('missing') 
const tipMsg = ref('')
const tipType = ref('info')

// UI Map 状态
const mapExists = ref(false)
const mapUpdatedAt = ref('')
const isGeneratingMap = ref(false)
const mapProgress = ref(0)
const mapErr = ref('')

const statusText = computed(() => {
  const map = { 'missing': '未下载', 'syncing': '同步中', 'ready': '本地已就绪' }
  return map[repoStatus.value] || '未知'
})


const fetchStatus = async () => {
  try {
    const res = await authFetch(`${props.apiBase}/admin/status/${props.project.id}`)
    if (res.ok) {
      const data = await res.json()
      repoStatus.value = data.status
    }
  } catch (e) { console.error("Sync failed:", e) }
}

const fetchMapStatus = async () => {
  try {
    mapErr.value = ''
    const res = await authFetch(`${props.apiBase}/map_status/${props.project.id}`)
    if (!res.ok) return
    const data = await res.json()
    mapExists.value = !!data.exists
    mapUpdatedAt.value = data.updated_at ? new Date(data.updated_at).toLocaleString() : ''
  } catch (e) {
    console.error('Fetch map status failed:', e)
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const generateUiMap = async () => {
  if (isGeneratingMap.value) return
  if (repoStatus.value !== 'ready') {
    mapErr.value = '代码仓库未就绪，请先下载/更新'
    return
  }
  isGeneratingMap.value = true
  mapProgress.value = 0
  mapErr.value = ''
  try {
    const res = await authFetch(`${props.apiBase}/map/${props.project.id}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'fast' })
    })
    if (!res.ok) throw new Error(`任务创建失败 (${res.status})`)
    const { task_id } = await res.json()
    if (!task_id) throw new Error('后端未返回 task_id')

    for (let i = 0; i < 120; i++) {
      const st = await authFetch(`${props.apiBase}/map/tasks/${task_id}`)
      if (!st.ok) throw new Error(`任务状态查询失败 (${st.status})`)
      const data = await st.json()
      mapProgress.value = Number(data.progress ?? mapProgress.value)
      if (data.status === 'success') {
        await fetchMapStatus()
        return
      }
      if (data.status === 'error') {
        throw new Error(data.message || '生成失败')
      }
      await sleep(800)
    }
    throw new Error('生成超时')
  } catch (e) {
    mapErr.value = e?.message || '生成失败'
  } finally {
    isGeneratingMap.value = false
  }
}

onMounted(async () => {
  await fetchStatus()
  await fetchMapStatus()
})

const handleAction = async (type) => {
  repoStatus.value = 'syncing'

  try {
    const res = await authFetch(`${props.apiBase}/admin/task/${props.project.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type })
    })
    const data = await res.json()
    tipMsg.value = data.message
    tipType.value = (data.status === 'success' || data.status === 'latest' || data.status === 'exists') ? 'success' : 'error'
    
    if (data.repo_status) repoStatus.value = data.repo_status
    else await fetchStatus()
  } catch (e) {
    tipMsg.value = "连接失败: " + e.message
    tipType.value = 'error'
  }
}
</script>

<style scoped>
.project-detail { animation: fadeIn 0.3s ease-out; }

/* Header & Breadcrumb */
.breadcrumb { display: flex; align-items: center; gap: 5px; color: #10b981; cursor: pointer; font-weight: 600; margin-bottom: 24px; }
.detail-header { display: flex; flex-wrap:wrap; gap:16px; justify-content: space-between; align-items: center; margin-bottom: 32px; }
.title-section{min-width:0;overflow-wrap:anywhere}.title-section>div{min-width:0}.detail-header .btn{white-space:nowrap}.app-icon{flex-shrink:0}
.title-section { display: flex; align-items: center; gap: 20px; }
.app-icon { width: 56px; height: 56px; background: #10b981; color: white; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 800; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }
.repo-url { color: #64748b; font-size: 14px; font-family: monospace; }
.status-pill { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 700; text-transform: uppercase; margin-left: 10px; }
.status-pill.missing { background: #fee2e2; color: #ef4444; }
.status-pill.ready { background: #dcfce7; color: #10b981; }

/* Buttons */
.btn-group { display: flex; gap: 12px; }
.btn { padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; display: flex; align-items: center; gap: 8px; }
.btn.download { background: #10b981; color: white; }
.btn.update { background: #f1f5f9; color: #0f172a; border: 1px solid #e2e8f0; }

/* Project Info Cards (恢复之前的布局) */
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.info-card { background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; }
.info-card h3 { display: flex; align-items: center; gap: 8px; font-size: 16px; margin-bottom: 16px; color: #1e293b; }
.info-item { margin-bottom: 12px; }
.info-item label { display: block; font-size: 12px; color: #94a3b8; text-transform: uppercase; }
.info-item span { font-weight: 500; color: #334155; }
.path-text { font-family: monospace; color: #64748b; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }

/* Stats Stats */
.stats-row { display: flex; gap: 40px; }
.stat { display: flex; flex-direction: column; }
.stat .label { font-size: 12px; color: #94a3b8; }
.stat .value { font-size: 18px; font-weight: 700; color: #1e293b;}
.value.green { color: #10b981; }

/* Animations */
.spin { animation: spin 2s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
/* 按钮风格统一化 */
.btn-inline-sync {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: #ffffff;
  color: #10b981;
  border: 1.5px solid #10b981;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-inline-sync:hover:not(:disabled) {
  background: #10b981;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
  transform: translateY(-1px);
}

.btn-inline-sync:active {
  transform: translateY(0);
}

.btn-inline-sync:disabled {
  border-color: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

/* 图标旋转动画 */
.spin {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
