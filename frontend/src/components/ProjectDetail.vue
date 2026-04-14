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
            <code class="repo-url">{{ project.repo_url }}</code>
            <span :class="['status-pill', repoStatus]">{{ statusText }}</span>
          </div>
        </div>
      </div>

      <div class="btn-group">
        <button v-if="repoStatus === 'missing'" class="btn download" @click="handleAction('download')">
          <Download :size="16" /> 开始下载源码
        </button>
        
        <button v-else class="btn update" :disabled="repoStatus === 'syncing'" @click="handleAction('update')">
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
          <div class="stat">
            <span class="label">Issue 缓存</span>
            <span class="value">{{ issues.length }} 条</span>
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
              {{ isGeneratingMap ? `生成中… ${mapProgress}%` : (mapExists ? '重新生成' : '生成图谱') }}
            </span>
          </button>
          <span v-if="mapErr" class="map-err">{{ mapErr }}</span>
        </div>
      </section>

      <section class="info-card wide">
        <div class="card-header-flex">
            <div class="header-left">
                <MessageSquare :size="18" />
                <h3>仓库 ISSUE 列表</h3>
            </div>
            <button class="btn-inline-sync" @click="handleAction('sync_issues')" :disabled="isSyncingIssues">
                <RotateCw :size="14" :class="{ 'spin': isSyncingIssues }" />
                <span>{{ isSyncingIssues ? '正在同步...' : '同步更新' }}</span>
            </button>
            </div>

        <div v-if="issues && issues.length > 0" class="issue-list">
          <div 
            v-for="issue in issues" 
            :key="issue.id" 
            class="issue-card-item"
            @click="openIssueModal(issue)"
          >
            <div class="issue-main">
              <span class="issue-num">#{{ issue.number }}</span>
              <span class="issue-title">{{ issue.title }}</span>
            </div>
            <div class="issue-badge">{{ issue.state }}</div>
            <ChevronRight :size="14" class="arrow" />
          </div>
        </div>
        <div v-else class="empty-placeholder">
          暂无本地缓存数据，点击右上角同步获取。
        </div>
      </section>
    </div>

    <Transition name="scale">
      <div v-if="selectedIssue" class="modal-overlay" @click.self="closeModal">
        <div class="issue-modal">
          <div class="modal-header">
            <div class="modal-title-group">
              <span class="m-num">#{{ selectedIssue.number }}</span>
              <span class="m-title">审计诊断详情</span>
            </div>
            <button class="close-btn" @click="closeModal"><X :size="20" /></button>
          </div>

          <div class="modal-body">
            <h2 class="full-title">{{ selectedIssue.title }}</h2>
            
            <div class="body-section">
              <div class="section-tag">原始描述</div>
              <div class="markdown-body content-box" v-html="renderMarkdown(selectedIssue.body)"></div>
            </div>

            <div class="ai-action-area">
              <button class="ai-run-btn" @click="analyzeWithAI" :disabled="isAnalyzing">
                <Sparkles v-if="!isAnalyzing" :size="18" />
                <RotateCw v-else :size="18" class="spin" />
                {{ isAnalyzing ? 'AI 正在分析源码并定位漏洞...' : '召唤 AI 专家进行诊断' }}
              </button>
            </div>

            <div v-if="aiResult" class="ai-result-section">
              <div class="section-tag ai">AI 诊断建议</div>
              <div class="markdown-body ai-content-box" v-html="renderMarkdown(aiResult)"></div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { 
  ChevronLeft, Download, RefreshCw, XCircle, CheckCircle, 
  Info, MessageSquare, RotateCw, X, Sparkles, ChevronRight, Database, Activity
} from 'lucide-vue-next'
import { marked } from 'marked'

const props = defineProps(['project', 'apiBase']) 
const emit = defineEmits(['back'])

// 基础状态
const repoStatus = ref('missing') 
const tipMsg = ref('')
const tipType = ref('info')
const issues = ref([])
const isSyncingIssues = ref(false)

// UI Map 状态
const mapExists = ref(false)
const mapUpdatedAt = ref('')
const isGeneratingMap = ref(false)
const mapProgress = ref(0)
const mapErr = ref('')

// 弹窗状态
const selectedIssue = ref(null)
const aiResult = ref('')
const isAnalyzing = ref(false)

const statusText = computed(() => {
  const map = { 'missing': '未下载', 'syncing': '同步中', 'ready': '本地已就绪' }
  return map[repoStatus.value] || '未知'
})

const renderMarkdown = (text) => marked.parse(text || '无详细内容')

const fetchStatus = async () => {
  try {
    const res = await fetch(`${props.apiBase}/admin/status/${props.project.id}`)
    if (res.ok) {
      const data = await res.json()
      repoStatus.value = data.status
    }
  } catch (e) { console.error("Sync failed:", e) }
}

const fetchMapStatus = async () => {
  try {
    mapErr.value = ''
    const res = await fetch(`${props.apiBase}/map_status/${props.project.id}`)
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
    const res = await fetch(`${props.apiBase}/map/${props.project.id}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'real' })
    })
    if (!res.ok) throw new Error(`任务创建失败 (${res.status})`)
    const { task_id } = await res.json()
    if (!task_id) throw new Error('后端未返回 task_id')

    for (let i = 0; i < 120; i++) {
      const st = await fetch(`${props.apiBase}/map/tasks/${task_id}`)
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
  handleAction('sync_issues')
})

const openIssueModal = async (issue) => {
  // 1. 初始化弹窗状态
  selectedIssue.value = issue;
  aiResult.value = ''; // 先清空上一个 Issue 的结果
  document.body.style.overflow = 'hidden'; 

  // 2. 静默查询：检查后端是否有已保存的诊断结果
  try {
    const res = await fetch(`${props.apiBase}/admin/analyze_issue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        app_id: props.project.id,
        issue_number: issue.number,
        title: issue.title,
        body: issue.body,
        // 这里可以增加一个标识，告诉后端如果是新问题先不要触发 AI 消耗
        // 但根据我们目前的后端逻辑，只要 issue_number 匹配不到缓存，它就会去请求 AI
        // 如果你希望更彻底的静默，可以增加一个 check_only: true 并在后端做判断
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      // 如果后端直接返回了缓存的诊断内容，则赋值
      if (data.analysis) {
        aiResult.value = data.analysis;
      }
    }
  } catch (e) {
    console.error("查询缓存失败，将由用户手动触发诊断:", e);
  }
};

const closeModal = () => {
  selectedIssue.value = null
  aiResult.value = ''
  document.body.style.overflow = ''
}

const analyzeWithAI = async () => {
  if (isAnalyzing.value) return
  isAnalyzing.value = true
  try {
    const res = await fetch(`${props.apiBase}/admin/analyze_issue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        app_id: props.project.id,
        issue_number: selectedIssue.value.number,
        title: selectedIssue.value.title,
        body: selectedIssue.value.body
      })
    })
    const data = await res.json()
    aiResult.value = data.analysis
  } catch (e) {
    aiResult.value = "### ❌ 诊断失败\n" + e.message
  } finally {
    isAnalyzing.value = false
  }
}

const handleAction = async (type) => {
  if (type === 'sync_issues') isSyncingIssues.value = true
  else repoStatus.value = 'syncing'

  try {
    const res = await fetch(`${props.apiBase}/admin/task/${props.project.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type })
    })
    const data = await res.json()
    tipMsg.value = data.message
    tipType.value = (data.status === 'success' || data.status === 'latest' || data.status === 'exists') ? 'success' : 'error'
    
    if (data.issues) issues.value = data.issues
    if (data.repo_status) repoStatus.value = data.repo_status
    else await fetchStatus()
  } catch (e) {
    tipMsg.value = "连接失败: " + e.message
    tipType.value = 'error'
  } finally {
    isSyncingIssues.value = false
  }
}
</script>

<style scoped>
.project-detail { animation: fadeIn 0.3s ease-out; }

/* Header & Breadcrumb */
.breadcrumb { display: flex; align-items: center; gap: 5px; color: #10b981; cursor: pointer; font-weight: 600; margin-bottom: 24px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
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
.info-card.wide { grid-column: span 2; }
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

/* Issue Card Items */
.issue-card-item { display: flex; align-items: center; padding: 16px; background: white; border-radius: 12px; margin-bottom: 10px; border: 1px solid #edf2f7; cursor: pointer; transition: 0.2s; }
.issue-card-item:hover { border-color: #10b981; transform: translateX(4px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
.issue-num { font-weight: 800; color: #10b981; margin-right: 12px; font-family: monospace; }
.issue-title { flex: 1; font-size: 14px; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.issue-badge { font-size: 10px; background: #f1f5f9; color: #64748b; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin: 0 16px; }

/* Modal Design (沉浸式浮动窗口) */
.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); z-index: 5000; display: flex; align-items: center; justify-content: center; padding: 40px; }
.issue-modal { width: 100%; max-width: 900px; max-height: 90vh; background: white; border-radius: 24px; display: flex; flex-direction: column; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); overflow: hidden; }
.modal-header { padding: 20px 32px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
.modal-title-group { display: flex; align-items: center; gap: 12px; }
.m-num { color: #10b981; font-weight: 800; font-size: 18px; }
.modal-body { padding: 32px; overflow-y: auto; }
.full-title { font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 24px; line-height: 1.4; }
.section-tag { font-size: 11px; font-weight: 800; text-transform: uppercase; color: #94a3b8; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
.section-tag::before { content: ""; width: 4px; height: 12px; background: #10b981; border-radius: 2px; }
.section-tag.ai::before { background: #8b5cf6; }
.content-box { background: #f8fafc; border-radius: 12px; padding: 20px; border: 1px solid #f1f5f9; font-size: 14px; color: #475569; }

/* AI Action */
.ai-run-btn { background: #10b981; color: white; border: none; padding: 14px 32px; border-radius: 14px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 10px; margin: 24px 0; }
.ai-result-section { border-radius: 16px; background: #0f172a; padding: 24px; color: #f1f5f9; }
.ai-result-section :deep(pre) { background: #1e293b; padding: 16px; border-radius: 8px; font-size: 13px; color: #818cf8; overflow-x: auto; }

/* Animations */
.spin { animation: spin 2s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.scale-enter-active, .scale-leave-active { transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.scale-enter-from, .scale-leave-to { opacity: 0; transform: scale(0.95); }

/* 让标题和按钮并排 */
.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #edf2f7; /* 增加分割感 */
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #1e293b;
}

.header-left h3 {
  margin: 0; /* 清除默认间距 */
  font-size: 16px;
  font-weight: 700;
}

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