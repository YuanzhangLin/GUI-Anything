<template>
  <div v-if="!isLoggedIn" class="auth-container">
    <div class="auth-bg-glow">
      <div class="glow-circle glow-1"></div>
      <div class="glow-circle glow-2"></div>
    </div>

    <div class="auth-card">
      <div class="auth-header">
        <div class="auth-icon-wrapper">
          <span class="auth-icon">📱</span>
        </div>
        <h1>GUI-Anything</h1>
        <p>Android 静态分析与智能审计平台</p>
      </div>

      <div class="auth-form">
        <div class="input-group">
          <label>Operator ID</label>
          <input v-model="loginForm.username" type="text" placeholder="输入用户名..." />
        </div>
        <div class="input-group">
          <label>Access Token</label>
          <input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="输入访问密钥..." 
            @keyup.enter="isRegistering ? handleRegister() : handleLogin()" 
          />
        </div>
        
        <button class="auth-btn" @click="isRegistering ? handleRegister() : handleLogin()" :disabled="isLoading">
          <span v-if="!isLoading">{{ isRegistering ? '初始化新账号' : '建立安全连接' }}</span>
          <span v-else class="auth-loader"></span>
        </button>

        <p v-if="loginError" class="auth-error-hint">⚠️ {{ loginError }}</p>
      </div>

      <div class="auth-footer">
        <span @click="isRegistering = !isRegistering" class="toggle-link">
          {{ isRegistering ? '已有权限？执行登录协议' : '没有访问权限？申请注册' }}
        </span>
      </div>
    </div>
  </div>

  <div v-else class="app-layout">
    <aside class="app-sidebar">
      <div class="sidebar-header">
        <div class="logo-text">
          <span class="logo-icon">📱</span>
          GUI-Anything
        </div>
        <button @click="createNewChat" class="btn-new-chat-fancy">
          <Plus :size="16" /> <span>新建对话</span>
        </button>
      </div>
      
      <div class="session-list">
        <div 
          v-for="s in sessions" 
          :key="s.id" 
          :class="['session-item', currentSessionId === s.id ? 'active' : '']"
          @click="switchSession(s)"
        >
          <div class="session-item-main">
            <div class="s-title">{{ s.title }}</div>
            <div class="s-meta">{{ s.app_id }}</div>
          </div>
          <button
            type="button"
            class="session-delete"
            :aria-label="'删除会话 ' + s.title"
            @click.stop="deleteSession(s.id)"
          >
            <Trash2 :size="14" />
          </button>
        </div>
      </div>

      <div class="sidebar-bottom">
        <div class="project-picker">
          <label>当前目标</label>
          <select v-model="selectedAppId" @change="onAppChange">
            <option v-for="app in appList" :key="app.id" :value="app.id">
              {{ app.name }}（{{ app.id }}）
            </option>
          </select>
          <div v-if="currentAppMeta" class="project-picker-meta">
            <p v-if="currentAppMeta.description" class="pp-desc">{{ currentAppMeta.description }}</p>
            <p v-if="currentAppMeta.repo_url" class="pp-repo" :title="currentAppMeta.repo_url">
              仓库：{{ currentAppMeta.repo_url }}
            </p>
          </div>
        </div>
        <nav class="footer-nav">
          <button @click="openDocs"><BookOpen :size="16" /> 使用手册</button>
          <button @click="showMap = !showMap"><Activity :size="16" /> 交互图谱</button>
          <button v-if="isAdmin" @click="showAdmin = true" class="admin-entry-btn">
    <Settings :size="16" /> 管理控制台
  </button>
          <button @click="handleLogout" class="exit"><LogOut :size="16" /> 退出</button>
        </nav>
      </div>
    </aside>

    <main class="chat-main">
      <div class="chat-scroller" ref="messageScroll">
        <div class="chat-content">
          <div v-for="(msg, i) in currentMessages" :key="i" :class="['msg-row', msg.role]">
            <div v-if="msg.role === 'assistant'" class="avatar ai">AI</div>
            
            <div class="msg-bubble">
              <div class="msg-content markdown-body">
                <div v-if="msg.role === 'assistant' && !msg.content && isLoading" class="typing-status">
                  <span class="dot-flashing"></span> 正在思考并调取图谱...
                </div>
                <div v-else v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>

            <div v-if="msg.role === 'user'" class="avatar user">ME</div>
          </div>
          
          <div v-if="isLoading && !isStreaming" class="msg-row assistant">
            <div class="avatar ai">AI</div>
            <div class="msg-bubble">
              <div class="msg-content typing">正在检索图谱数据...</div>
            </div>
          </div>
        </div>
      </div>

      <footer class="input-area">
        <div class="composer-card">
          <div v-if="attachedIssues.length || attachedMap" class="composer-chips">
            <span v-for="a in attachedIssues" :key="a.number" class="issue-chip">
              <Tag :size="12" class="chip-icon" />
              <span class="chip-label">#{{ a.number }}</span>
              <span class="chip-title">{{ a.title }}</span>
              <button
                type="button"
                class="chip-remove"
                :aria-label="'移除 Issue ' + a.number"
                @click="removeAttachedIssue(a.number)"
              >
                ×
              </button>
            </span>

            <span v-if="attachedMap" class="issue-chip map-chip">
              <Activity :size="12" class="chip-icon" />
              <span class="chip-label">MAP</span>
              <span class="chip-title">UI Map 摘要: {{ attachedMap.appId }}</span>
              <button
                type="button"
                class="chip-remove"
                aria-label="移除 UI Map"
                @click="removeAttachedMap()"
              >
                ×
              </button>
            </span>
          </div>
          <div class="input-container">
            <textarea
              ref="chatInput"
              v-model="inputMsg"
              @keyup.enter.exact.prevent="sendMessage"
              placeholder="输入审计指令…（Shift+Enter 换行）"
              rows="1"
            ></textarea>
            <button class="send-btn" @click="sendMessage" :disabled="isLoading">
              <Send :size="18" />
            </button>
          </div>
          <div class="composer-toolbar">
            <button type="button" class="toolbar-attach" @click="openIssuePicker">
              <Tag :size="15" />
              添加 ISSUE
            </button>
            <span v-if="issuePickerHint" class="toolbar-hint">{{ issuePickerHint }}</span>
            <button
              type="button"
              class="toolbar-attach"
              :disabled="mapAttachLoading"
              @click="toggleAttachMap"
              :title="attachedMap ? '已添加，点击可移除' : '把当前项目 UI Map 的人类可读摘要作为附件加入对话（非整份 JSON）'"
            >
              <Activity :size="15" />
              {{ attachedMap ? '移除图谱摘要' : (mapAttachLoading ? '加载摘要…' : '添加图谱摘要') }}
            </button>
            <span v-if="mapAttachHint" class="toolbar-hint">{{ mapAttachHint }}</span>

            <div v-if="toolLoopLimitReached && !isLoading" class="tool-loop-actions">
              <button type="button" class="toolbar-attach" @click="continueToolLoop">
                继续
              </button>
              <button type="button" class="toolbar-attach" @click="forceOutput">
                强制输出
              </button>
              <span class="toolbar-hint">已达到工具调用上限</span>
            </div>
          </div>
        </div>
      </footer>

      <div v-if="showIssuePicker" class="issue-picker-overlay" @click.self="showIssuePicker = false">
        <div class="issue-picker" role="dialog" aria-modal="true" aria-labelledby="issue-picker-title">
          <div class="issue-picker-head">
            <h3 id="issue-picker-title">选择要附加的 Issue</h3>
            <button type="button" class="issue-picker-close" @click="showIssuePicker = false" aria-label="关闭">
              <X :size="18" />
            </button>
          </div>
          <p v-if="issuePickerLoading" class="issue-picker-status">加载中…</p>
          <p v-else-if="!issueCatalog.length" class="issue-picker-status">
            当前项目没有 Issue 缓存。请在「管理控制台」中同步仓库 Issue 后再试。
          </p>
          <ul v-else class="issue-picker-list">
            <li
              v-for="issue in issueCatalog"
              :key="issue.id"
              :class="['issue-picker-item', isIssueAttached(issue.number) ? 'attached' : '']"
              @click="toggleAttachIssue(issue)"
            >
              <span class="ip-num">#{{ issue.number }}</span>
              <span class="ip-title">{{ issue.title }}</span>
              <span class="ip-state">{{ issue.state }}</span>
            </li>
          </ul>
        </div>
      </div>
    </main>

    <div v-if="showMap" class="drawer">
      <div class="drawer-header">
        <span>UI Map: {{ selectedAppId }}</span>
        <X @click="showMap = false" class="close-icon" />
      </div>
      <div class="drawer-view">
        <MapCanvas :appId="selectedAppId" />
      </div>
    </div>

    <div v-if="showDocs" class="drawer docs-drawer">
      <div class="drawer-header">
        <span>分析手册</span>
        <X @click="showDocs = false" class="close-icon" />
      </div>
      <div class="drawer-view">
        <div class="docs-markdown" v-html="renderMarkdown(docsContent)"></div>
      </div>
    </div>
  </div>
    <AdminPanel 
    v-if="showAdmin" 
    @close="showAdmin = false" 
    :appList="appList" 
    :apiBase="API_BASE" 
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { Plus, Send, Activity, X, BookOpen, LogOut, Settings, Tag, Trash2 } from 'lucide-vue-next'
import { marked } from 'marked'
import MapCanvas from './components/MapCanvas.vue'
import AdminPanel from './components/AdminPanel.vue' 


// --- 1. 基础工具配置 ---
marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (content: string) => {
  return marked.parse(content || '')
}

// --- 2. 状态定义 (必须放在计算属性之前) ---
const isLoggedIn = ref(false)
const isRegistering = ref(false)
const showDocs = ref(false)
const showMap = ref(false)
const isLoading = ref(false)
const isStreaming = ref(false)
const currentUser = ref('')
const loginForm = ref({ username: '', password: '' })
const loginError = ref('')
const selectedAppId = ref('activitydiary')
const appList = ref([])
const sessions = ref([])
const currentSessionId = ref('')
const inputMsg = ref('')
const chatInput = ref<HTMLTextAreaElement | null>(null)
const messageScroll = ref(null)

const MAX_CHAT_INPUT_LINES = 6

const textareaLineHeightPx = (el: HTMLTextAreaElement) => {
  const lh = getComputedStyle(el).lineHeight
  if (lh === 'normal') {
    const fs = parseFloat(getComputedStyle(el).fontSize) || 15
    return fs * 1.35
  }
  const n = parseFloat(lh)
  return Number.isFinite(n) && n > 0 ? n : 24
}

const adjustChatInputHeight = () => {
  const el = chatInput.value
  if (!el) return
  el.style.height = '0px'
  el.style.overflowY = 'hidden'
  const lineH = textareaLineHeightPx(el)
  const padY =
    (parseFloat(getComputedStyle(el).paddingTop) || 0) +
    (parseFloat(getComputedStyle(el).paddingBottom) || 0)
  const maxH = lineH * MAX_CHAT_INPUT_LINES + padY
  const natural = el.scrollHeight
  const nextH = Math.min(Math.max(natural, lineH + padY), maxH)
  el.style.height = `${nextH}px`
  el.style.overflowY = natural > maxH ? 'auto' : 'hidden'
}
const docsContent = ref('正在加载手册...')
const showAdmin = ref(false) // 控制中台显示的“开关”
const isAdmin = ref(true)    // 权限标记

type AttachedIssue = { number: number; title: string; body: string }
const MAX_ATTACHED_ISSUES = 5
const ISSUE_BODY_MAX = 6000
const attachedIssues = ref<AttachedIssue[]>([])
const showIssuePicker = ref(false)
const issueCatalog = ref<
  { id: number; number: number; title: string; state: string; body: string | null }[]
>([])
const issuePickerLoading = ref(false)

const issuePickerHint = computed(() => {
  if (attachedIssues.value.length >= MAX_ATTACHED_ISSUES) {
    return `最多附加 ${MAX_ATTACHED_ISSUES} 个 Issue`
  }
  return ''
})

type AttachedMap = { appId: string; content: string }
const attachedMap = ref<AttachedMap | null>(null)
const mapAttachLoading = ref(false)
const MAP_BODY_MAX = 16000

const mapAttachHint = computed(() => {
  if (mapAttachLoading.value) return '正在加载 UI Map…'
  if (attachedMap.value) return 'UI Map 已附加'
  return ''
})

// Tool-loop control (when backend reaches tool-call limit)
const toolLoopLimitReached = ref(false)
const lastApiTextBySession = ref<Record<string, string>>({})
const lastToolRoundsBySession = ref<Record<string, number>>({})

// --- 3. 计算属性 (核心修复：确保渲染实例能找到) ---
const currentMessages = computed(() => {
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  return session ? session.messages : []
})

/** 与 backend/data/app_list.yml 中当前选中项对应（name 为展示名，id 为数据/接口用标识） */
const currentAppMeta = computed(() => {
  const list = appList.value as {
    id: string
    name?: string
    description?: string
    repo_url?: string
  }[]
  return list.find((a) => a.id === selectedAppId.value) ?? null
})

// --- 4. 彻底去掉硬编码的 API 地址推导 (核心修复) ---
const getApiBase = () => {
  // 1. 优先检查环境变量（用于 Docker Compose 环境变量或生产配置）
  const envBase = import.meta.env.VITE_API_BASE
  if (envBase) return envBase
  
  // 2. 自动推导逻辑：
  // 无论你在浏览器输入的是 localhost、局域网 IP 还是公网 IP
  // hostname 都会自动捕获当前访问的域名，protocol 会自动获取 http 或 https
  const protocol = window.location.protocol
  const hostname = window.location.hostname
  
  // 默认后端端口为 8002。这种写法保证了前后端只要部署在同一台机器，就能自动连接
  return `${protocol}//${hostname}:8002/api`
}

const API_BASE = getApiBase()

// --- 5. 健壮的 Fetch 封装 ---
const safeFetch = async (url: string, options?: RequestInit) => {
  try {
    const res = await fetch(url, options)
    const contentType = res.headers.get('content-type')
    
    if (!res.ok) {
      if (contentType && contentType.includes('text/html')) {
        throw new Error(`API 响应异常: 服务器返回了 HTML (可能是 404)。请确认后端 8002 端口是否正常开启。`)
      }
      const errData = await res.json().catch(() => ({ detail: '未知错误' }))
      throw new Error(errData.detail || `请求失败 (${res.status})`)
    }
    return res
  } catch (e: any) {
    throw new Error(`连接失败: ${e.message}`)
  }
}

// --- 6. 业务逻辑方法 ---
const openDocs = async () => {
  showDocs.value = true
  docsContent.value = '正在检索分析手册...'
  try {
    const res = await safeFetch(`${API_BASE}/docs`)
    const data = await res.json()
    docsContent.value = data.content
  } catch (e: any) {
    docsContent.value = `# ⚠️ 错误\n无法加载内容：${e.message}`
  }
}

const initData = async () => {
  try {
    const appRes = await safeFetch(`${API_BASE}/apps`)
    appList.value = await appRes.json()
    const histRes = await safeFetch(`${API_BASE}/history/${currentUser.value}`)
    const raw = await histRes.json()
    // 最近会话在上：按会话 id（时间戳字符串）降序
    sessions.value = (raw as any[]).slice().sort((a, b) => {
      const na = parseInt(String(a.id), 10)
      const nb = parseInt(String(b.id), 10)
      if (!Number.isNaN(na) && !Number.isNaN(nb)) return nb - na
      return String(b.id).localeCompare(String(a.id))
    })
    
    if (sessions.value.length > 0) {
      const first = sessions.value[0]
      currentSessionId.value = first.id
      selectedAppId.value = first.app_id || 'activitydiary'
    } else {
      createNewChat()
    }
  } catch (e: any) {
    console.error('Initialization failed:', e.message)
  }
}

const handleLogin = async () => {
  loginError.value = ''
  try {
    const res = await safeFetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm.value)
    })
    const data = await res.json()
    currentUser.value = data.username
    isLoggedIn.value = true
    localStorage.setItem('gui_user', data.username)
    await initData()
  } catch (e: any) {
    loginError.value = e.message
  }
}

const handleRegister = async () => {
  loginError.value = ''
  try {
    await safeFetch(`${API_BASE}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm.value)
    })
    isRegistering.value = false
    loginError.value = '注册成功，请登录'
  } catch (e: any) {
    loginError.value = e.message
  }
}

const createNewChat = () => {
  const id = Date.now().toString()
  const entry = {
    id,
    title: '新审计会话',
    app_id: selectedAppId.value,
    messages: [{ role: 'assistant', content: '您好！GUI-Anything 审计助手已就绪。' }]
  }
  sessions.value = [entry, ...sessions.value]
  currentSessionId.value = id
}

const switchSession = (s: any) => {
  currentSessionId.value = s.id
  selectedAppId.value = s.app_id
}

const deleteSession = (id: string) => {
  const idx = sessions.value.findIndex((s: any) => s.id === id)
  if (idx < 0) return
  const wasCurrent = currentSessionId.value === id
  sessions.value.splice(idx, 1)
  delete lastApiTextBySession.value[id]
  delete lastToolRoundsBySession.value[id]
  if (!wasCurrent) return
  if (sessions.value.length > 0) {
    const next = sessions.value[0]
    currentSessionId.value = next.id
    selectedAppId.value = next.app_id
  } else {
    createNewChat()
  }
}

const onAppChange = () => { createNewChat() }

const buildMessageForApi = (userText: string) => {
  const userPart =
    userText ||
    '请结合上述 GitHub Issue 进行静态分析与审计，并给出结论或修复思路。'
  if (!attachedIssues.value.length && !attachedMap.value) return userPart
  const blocks = attachedIssues.value.map((i) => {
    let body = (i.body || '').trim() || '（无正文）'
    if (body.length > ISSUE_BODY_MAX) {
      body = `${body.slice(0, ISSUE_BODY_MAX)}\n\n…（正文已截断）`
    }
    return `### 附件：GitHub Issue #${i.number}\n**标题：** ${i.title}\n\n${body}`
  })

  if (attachedMap.value) {
    let m = (attachedMap.value.content || '').trim()
    if (m.length > MAP_BODY_MAX) {
      m = `${m.slice(0, MAP_BODY_MAX)}\n\n…（图谱内容已截断）`
    }
    blocks.push(`### 附件：UI Map 摘要 (${attachedMap.value.appId})\n\n${m}`)
  }

  return `${blocks.join('\n\n---\n\n')}\n\n---\n\n### 用户指令\n${userPart}`
}

const buildMessageForDisplay = (userText: string) => {
  const line =
    userText ||
    '请结合附件中的 Issue 给出分析与审计建议。'
  if (!attachedIssues.value.length && !attachedMap.value) return line
  const parts: string[] = []
  if (attachedIssues.value.length) {
    parts.push(attachedIssues.value.map((i) => `Issue #${i.number}`).join('、'))
  }
  if (attachedMap.value) {
    parts.push(`UI Map 摘要(${attachedMap.value.appId})`)
  }
  const head = `📎 已附加 ${parts.join('、')}`
  return `${head}\n\n${line}`
}

const openIssuePicker = async () => {
  showIssuePicker.value = true
  issuePickerLoading.value = true
  try {
    const res = await safeFetch(`${API_BASE}/issues/${selectedAppId.value}`)
    issueCatalog.value = await res.json()
  } catch {
    issueCatalog.value = []
  } finally {
    issuePickerLoading.value = false
  }
}

const removeAttachedMap = () => {
  attachedMap.value = null
}

const toggleAttachMap = async () => {
  if (mapAttachLoading.value) return
  if (attachedMap.value) {
    removeAttachedMap()
    return
  }
  mapAttachLoading.value = true
  try {
    const res = await safeFetch(`${API_BASE}/map_summary/${selectedAppId.value}`)
    const data = await res.json()
    attachedMap.value = {
      appId: selectedAppId.value,
      content: (data.summary || '').trim()
    }
  } catch (e: any) {
    console.error('Map attach failed:', e.message)
  } finally {
    mapAttachLoading.value = false
  }
}

const isIssueAttached = (num: number) => attachedIssues.value.some((i) => i.number === num)

const toggleAttachIssue = (issue: {
  number: number
  title: string
  body: string | null
}) => {
  if (isIssueAttached(issue.number)) {
    removeAttachedIssue(issue.number)
    return
  }
  if (attachedIssues.value.length >= MAX_ATTACHED_ISSUES) return
  attachedIssues.value.push({
    number: issue.number,
    title: issue.title,
    body: issue.body || ''
  })
}

const removeAttachedIssue = (num: number) => {
  attachedIssues.value = attachedIssues.value.filter((i) => i.number !== num)
}

const TOOL_LOOP_MARKER = '[[TOOL_LOOP_LIMIT_REACHED]]'

const continueToolLoop = async () => {
  const sid = currentSessionId.value
  const apiText = lastApiTextBySession.value[sid]
  if (!apiText) return
  const rounds = (lastToolRoundsBySession.value[sid] || 6) + 6
  lastToolRoundsBySession.value[sid] = rounds
  toolLoopLimitReached.value = false
  await sendMessageWithOverrides(apiText, { tool_rounds: rounds, force_no_tools: false })
}

const forceOutput = async () => {
  const sid = currentSessionId.value
  const apiText = lastApiTextBySession.value[sid]
  if (!apiText) return
  toolLoopLimitReached.value = false
  await sendMessageWithOverrides(apiText, { tool_rounds: 0, force_no_tools: true })
}

const sendMessageWithOverrides = async (
  apiText: string,
  overrides: { tool_rounds?: number; force_no_tools?: boolean }
) => {
  if (isLoading.value) return
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  if (!session) return

  isLoading.value = true
  const assistantMsg = { role: 'assistant', content: '' }
  session.messages.push(assistantMsg)
  isStreaming.value = true

  try {
    const res = await safeFetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: apiText,
        session_id: currentSessionId.value,
        username: currentUser.value,
        app_id: selectedAppId.value,
        ...overrides
      })
    })

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) throw new Error('读取器初始化失败')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      if (chunk.includes(TOOL_LOOP_MARKER)) {
        toolLoopLimitReached.value = true
        assistantMsg.content += chunk.replaceAll(TOOL_LOOP_MARKER, '')
      } else {
        assistantMsg.content += chunk
      }
      await nextTick()
      if (messageScroll.value) {
        messageScroll.value.scrollTop = messageScroll.value.scrollHeight
      }
    }
  } catch (e: any) {
    assistantMsg.content = `**Error:** ${e.message}`
  } finally {
    isLoading.value = false
    isStreaming.value = false
  }
}

const sendMessage = async () => {
  if (isLoading.value) return
  const trimmed = inputMsg.value.trim()
  if (!trimmed && !attachedIssues.value.length && !attachedMap.value) return
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  if (!session) return

  const displayText = buildMessageForDisplay(trimmed)
  const apiText = buildMessageForApi(trimmed)
  const titleSeed = trimmed || attachedIssues.value.map((i) => `#${i.number}`).join(' ')

  toolLoopLimitReached.value = false
  lastApiTextBySession.value[currentSessionId.value] = apiText
  lastToolRoundsBySession.value[currentSessionId.value] = 6

  session.messages.push({ role: 'user', content: displayText })
  attachedIssues.value = []
  attachedMap.value = null
  inputMsg.value = ''
  await nextTick()
  adjustChatInputHeight()
  await sendMessageWithOverrides(apiText, { tool_rounds: 6, force_no_tools: false })
  if (session.title === '新审计会话') {
    session.title = titleSeed.substring(0, 10)
  }
}

const handleLogout = () => {
  isLoggedIn.value = false
  localStorage.removeItem('gui_user')
}

const formatId = (id: string) => {
  const num = parseInt(id)
  if (isNaN(num)) return id
  return new Date(num).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

watch(inputMsg, () => {
  nextTick(() => adjustChatInputHeight())
})

watch(isLoggedIn, (loggedIn) => {
  if (loggedIn) nextTick(() => adjustChatInputHeight())
})

watch(selectedAppId, () => {
  attachedIssues.value = []
  issueCatalog.value = []
  attachedMap.value = null
})

onMounted(() => {
  const saved = localStorage.getItem('gui_user')
  if (saved) {
    currentUser.value = saved
    isLoggedIn.value = true
    initData()
  }
  nextTick(() => adjustChatInputHeight())
})
</script>

<style scoped>
/* 让控制台按钮与其他侧边栏按钮保持风格一致 */
.admin-entry-btn {
  width: 100%;
  background: none;
  border: none;
  color: #9ca3af; /* 与“使用手册”一样的灰色 */
  text-align: left;
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px; /* 图标与文字的间距 */
  transition: color 0.2s;
}

.admin-entry-btn:hover {
  color: #10b981; /* 悬停时变为绿色，增加点仪式感 */
}
.auth-container {
  position: fixed;
  inset: 0;
  background: #020617; /* 深色背景 */
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  font-family: 'Inter', system-ui, sans-serif;
}

/* 背景装饰光晕 */
.auth-bg-glow {
  position: absolute;
  width: 100%;
  height: 100%;
  z-index: 0;
}
.glow-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.2;
}
.glow-1 {
  width: 400px; height: 400px;
  background: #10b981;
  top: -100px; left: -100px;
}
.glow-2 {
  width: 300px; height: 300px;
  background: #3b82f6;
  bottom: -50px; right: -50px;
}

/* 登录卡片：毛玻璃效果 */
.auth-card {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 420px;
  padding: 48px 40px;
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 28px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}

.auth-header { text-align: center; margin-bottom: 36px; }
.auth-icon-wrapper { font-size: 48px; margin-bottom: 16px; }
.auth-header h1 { 
  color: #f8fafc; font-size: 28px; font-weight: 800; 
  letter-spacing: -1px; margin-bottom: 8px; 
}
.auth-header p { color: #94a3b8; font-size: 14px; }

/* 输入框组合 */
.input-group { margin-bottom: 24px; text-align: left; }
.input-group label { 
  display: block; font-size: 11px; font-weight: 700; 
  color: #10b981; text-transform: uppercase; 
  margin-bottom: 8px; letter-spacing: 1.2px; 
}
.input-group input {
  width: 100%; background: rgba(0, 0, 0, 0.3); 
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 14px 16px; border-radius: 12px; 
  color: #f1f5f9; outline: none; transition: all 0.3s;
}
.input-group input:focus { 
  border-color: #10b981; 
  background: rgba(0, 0, 0, 0.4);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1); 
}

/* 按钮 */
.auth-btn {
  width: 100%; padding: 16px; background: #10b981; color: #ffffff; 
  border: none; border-radius: 12px; font-weight: 700; font-size: 15px;
  cursor: pointer; transition: all 0.3s; margin-top: 12px;
}
.auth-btn:hover { background: #059669; transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3); }
.auth-btn:active { transform: translateY(0); }
.auth-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* 底部链接 */
.auth-footer { margin-top: 32px; text-align: center; }
.toggle-link { color: #64748b; font-size: 13px; cursor: pointer; transition: color 0.2s; }
.toggle-link:hover { color: #f1f5f9; }
.auth-error-hint { margin-top: 16px; color: #f87171; font-size: 13px; text-align: center; }

/* 加载动画 */
.auth-loader {
  display: inline-block; width: 18px; height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-radius: 50%; border-top-color: #fff;
  animation: auth-spin 0.8s linear infinite;
}
@keyframes auth-spin { to { transform: rotate(360deg); } }
/* 原有样式完全保持一致，未做改动 */
.app-layout { display: flex; width: 100vw; height: 100vh; background: #ffffff; color: #1a1a1a; overflow: hidden; }
.app-sidebar { width: 280px; background: #0b0d11; color: white; display: flex; flex-direction: column; padding: 16px; flex-shrink: 0;}
.logo-text { 
  font-size: 20px; font-weight: 800; margin-bottom: 24px; display: flex; align-items: center; gap: 8px;
  background: linear-gradient(to right, #ffffff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.logo-icon { -webkit-text-fill-color: initial; font-size: 24px; }
.btn-new-chat-fancy {
  width: 100%; padding: 12px; background: #1f2937; border: 1px solid #374151; color: white; 
  border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  font-size: 14px; font-weight: 600; transition: all 0.3s;
}
.btn-new-chat-fancy:hover { background: #374151; transform: translateY(-1px); }
.session-list { flex: 1; overflow-y: auto; margin-top: 16px; }
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 10px 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: 0.2s;
}
.session-item:hover { background: #1f2937; }
.session-item.active { background: #1f2937; border: 1px solid #374151; }
.session-item-main { flex: 1; min-width: 0; }
.session-delete {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.session-delete:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}
.s-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.s-meta { font-size: 11px; color: #6b7280; margin-top: 4px; }
.sidebar-bottom { border-top: 1px solid #1f2937; padding-top: 16px; }
.project-picker label { font-size: 11px; color: #6b7280; display: block; margin-bottom: 8px; text-transform: uppercase; }
.project-picker select { width: 100%; background: #111827; border: 1px solid #374151; color: white; padding: 10px; border-radius: 6px; margin-bottom: 8px; }
.project-picker-meta {
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 8px;
  font-size: 11px;
  line-height: 1.45;
  color: #9ca3af;
}
.pp-desc { margin: 0 0 6px; color: #d1d5db; }
.pp-desc:last-child { margin-bottom: 0; }
.pp-repo {
  margin: 0;
  word-break: break-all;
  color: #6b7280;
  font-size: 10px;
}
.footer-nav button { width: 100%; background: none; border: none; color: #9ca3af; text-align: left; padding: 10px; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 10px; }
.footer-nav button:hover { color: white; }
.chat-main { flex: 1; display: flex; flex-direction: column; background: #f9fafb; min-width: 0; }
.chat-scroller { flex: 1; overflow-y: auto; }
.chat-content { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
.msg-row { display: flex; gap: 16px; margin-bottom: 32px; width: 100%; }
.msg-row.assistant { align-items: flex-start; justify-content: flex-start; }
.msg-row.user { align-items: flex-start; justify-content: flex-end; }
.avatar { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; flex-shrink: 0; margin-top: 4px; }
.avatar.ai { background: #10a37f; color: white; order: 1; }
.avatar.user { background: #6366f1; color: white; order: 2; }
.msg-bubble { max-width: 80%; position: relative; }
.assistant .msg-bubble { order: 2; }
.user .msg-bubble { order: 1; }
.msg-content { padding: 14px 18px; border-radius: 16px; font-size: 15px; line-height: 1.6; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.assistant .msg-content { background: #ffffff; color: #1f2937; border: 1px solid #e5e7eb; border-top-left-radius: 4px; }
.assistant :deep(.markdown-body) h1, .assistant :deep(.markdown-body) h2 { font-size: 1.2rem; margin: 1rem 0 0.5rem; border-bottom: 1px solid #eee; padding-bottom: 4px;}
.assistant :deep(.markdown-body) ul, .assistant :deep(.markdown-body) ol { padding-left: 1.5rem; margin: 0.5rem 0; }
.assistant :deep(.markdown-body) li { margin: 0.3rem 0; }
.assistant :deep(.markdown-body) p { margin-bottom: 0.5rem; }
.assistant :deep(.markdown-body) blockquote { border-left: 4px solid #10a37f; background: #f0fdf4; padding: 8px 12px; margin: 0.5rem 0; color: #166534; }
.assistant :deep(.markdown-body) code { background: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-family: monospace; }
.user .msg-content { background: #111827; color: #ffffff; border-top-right-radius: 4px; white-space: pre-wrap;}
.input-area { padding: 24px 20px 40px; background: #f3f4f6; }
.composer-card {
  max-width: 800px;
  margin: 0 auto;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}
.composer-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px 0;
  border-bottom: 1px solid #e8edf3;
}
.issue-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 6px 4px 10px;
  font-size: 12px;
  color: #0f172a;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 999px;
}
.chip-icon { flex-shrink: 0; color: #4f46e5; }
.chip-label { font-weight: 700; color: #4338ca; flex-shrink: 0; }
.chip-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  max-width: 220px;
  color: #475569;
}
.chip-remove {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #64748b;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.chip-remove:hover { background: rgba(99, 102, 241, 0.15); color: #312e81; }
.input-container {
  position: relative;
  background: #fafbfc;
  padding: 12px 16px 14px;
}
.input-container textarea {
  width: 100%;
  display: block;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 1.5;
  background: transparent;
  padding: 4px 48px 4px 4px;
  min-height: calc(1.5em + 8px);
  box-sizing: border-box;
  overflow-x: hidden;
}
.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 12px 10px;
  background: #f1f5f9;
  border-top: 1px solid #e2e8f0;
}

.tool-loop-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.toolbar-attach {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  color: #475569;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.toolbar-attach:hover {
  color: #0f172a;
  border-color: #cbd5e1;
  background: #f8fafc;
}
.toolbar-hint { font-size: 12px; color: #94a3b8; }
.issue-picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.issue-picker {
  width: 100%;
  max-width: 480px;
  max-height: min(70vh, 520px);
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.issue-picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}
.issue-picker-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.issue-picker-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}
.issue-picker-close:hover { background: #f1f5f9; color: #0f172a; }
.issue-picker-status {
  margin: 0;
  padding: 20px 16px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.issue-picker-list {
  list-style: none;
  margin: 0;
  padding: 8px;
  overflow-y: auto;
  flex: 1;
}
.issue-picker-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  border: 1px solid transparent;
}
.issue-picker-item:hover { background: #f8fafc; }
.issue-picker-item.attached {
  background: #eef2ff;
  border-color: #c7d2fe;
}
.ip-num {
  flex-shrink: 0;
  font-weight: 800;
  font-family: ui-monospace, monospace;
  color: #4f46e5;
}
.ip-title {
  flex: 1;
  min-width: 0;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ip-state {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}
.send-btn { position: absolute; right: 12px; bottom: 12px; background: #111827; color: white; border: none; padding: 8px; border-radius: 10px; cursor: pointer; }
.drawer { position: absolute; top: 0; right: 0; width: 42%; height: 100%; background: white; box-shadow: -10px 0 30px rgba(0,0,0,0.05); z-index: 100; display: flex; flex-direction: column; }
.drawer-header { padding: 16px 20px; border-bottom: 1px solid #f3f4f6; display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.drawer-view { flex: 1; overflow-y: auto; padding: 20px; }

/* Docs drawer: dark (non-black) theme */
.docs-drawer {
  background: #0f172a;
  box-shadow: -12px 0 40px rgba(2, 6, 23, 0.35);
}
.docs-drawer .drawer-header {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  color: #e5e7eb;
  background: rgba(15, 23, 42, 0.7);
}
.docs-drawer .drawer-view {
  background: radial-gradient(1200px 600px at 10% 0%, rgba(56, 189, 248, 0.10), transparent 55%),
    radial-gradient(900px 500px at 90% 10%, rgba(16, 185, 129, 0.10), transparent 55%),
    #0f172a;
}
.docs-drawer :deep(.docs-markdown) {
  --md-text: #e5e7eb;
  --md-muted: #9ca3af;
  --md-border: rgba(148, 163, 184, 0.22);
  --md-bg-soft: rgba(15, 23, 42, 0.55);
  --md-code-bg: rgba(148, 163, 184, 0.14);
  --md-code-text: #e5e7eb;
  --md-link: #60a5fa;
  --md-codeblock-bg: rgba(2, 6, 23, 0.8);
  --md-codeblock-text: #e5e7eb;
  --md-codeblock-border: rgba(148, 163, 184, 0.2);
}
.docs-drawer :deep(.docs-markdown h1),
.docs-drawer :deep(.docs-markdown h2),
.docs-drawer :deep(.docs-markdown h3) {
  color: #f8fafc;
}

.docs-drawer :deep(.docs-markdown code) {
  color: var(--md-code-text);
}
.docs-drawer :deep(.docs-markdown table) {
  background: rgba(2, 6, 23, 0.35);
}
.docs-drawer :deep(.docs-markdown th) {
  background: rgba(2, 6, 23, 0.55);
  color: #cbd5e1;
}
.login-wrapper { position: fixed; inset: 0; background: #0b0d11; display: flex; align-items: center; justify-content: center; }
.login-panel { background: white; padding: 48px; border-radius: 20px; width: 400px; text-align: center; }
.panel-logo { font-size: 24px; font-weight: 800; margin-bottom: 24px; }
.primary-action { width: 100%; padding: 14px; background: #111827; color: white; border: none; border-radius: 10px; margin-top: 24px; cursor: pointer; }
</style>