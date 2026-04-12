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
          <div class="s-title">{{ s.title }}</div>
          <div class="s-meta">{{ s.app_id }}</div>
        </div>
      </div>

      <div class="sidebar-bottom">
        <div class="project-picker">
          <label>当前目标</label>
          <select v-model="selectedAppId" @change="onAppChange">
            <option v-for="app in appList" :key="app.id" :value="app.id">{{ app.name }}</option>
          </select>
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
        <div class="input-container">
          <textarea 
            v-model="inputMsg" 
            @keyup.enter.exact.prevent="sendMessage"
            placeholder="输入审计指令..."
            rows="1"
          ></textarea>
          <button class="send-btn" @click="sendMessage" :disabled="isLoading">
            <Send :size="18" />
          </button>
        </div>
      </footer>
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
        <div class="markdown-body" v-html="renderMarkdown(docsContent)"></div>
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
import { ref, computed, onMounted, nextTick } from 'vue'
import { Plus, Send, Activity, X, BookOpen, LogOut,Settings } from 'lucide-vue-next'
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
const messageScroll = ref(null)
const docsContent = ref('正在加载手册...')
const showAdmin = ref(false) // 控制中台显示的“开关”
const isAdmin = ref(true)    // 权限标记


// --- 3. 计算属性 (核心修复：确保渲染实例能找到) ---
const currentMessages = computed(() => {
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  return session ? session.messages : []
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
    sessions.value = await histRes.json()
    
    if (sessions.value.length > 0) {
      const last = sessions.value[sessions.value.length - 1]
      currentSessionId.value = last.id
      selectedAppId.value = last.app_id || 'activitydiary'
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
  sessions.value.push({ 
    id, 
    title: '新审计会话', 
    app_id: selectedAppId.value, 
    messages: [{ role: 'assistant', content: '您好！GUI-Anything 审计助手已就绪。' }] 
  })
  currentSessionId.value = id
}

const switchSession = (s: any) => {
  currentSessionId.value = s.id
  selectedAppId.value = s.app_id
}

const onAppChange = () => { createNewChat() }

const sendMessage = async () => {
  if (!inputMsg.value.trim() || isLoading.value) return
  const text = inputMsg.value
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  if (!session) return

  session.messages.push({ role: 'user', content: text })
  inputMsg.value = ''
  isLoading.value = true
  
  const assistantMsg = { role: 'assistant', content: '' }
  session.messages.push(assistantMsg)
  isStreaming.value = true

  try {
    const res = await safeFetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: text, 
        session_id: currentSessionId.value, 
        username: currentUser.value, 
        app_id: selectedAppId.value 
      })
    })

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) throw new Error('读取器初始化失败')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      assistantMsg.content += decoder.decode(value, { stream: true })
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
    if (session.title === '新审计会话') {
      session.title = text.substring(0, 10)
    }
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

onMounted(() => {
  const saved = localStorage.getItem('gui_user')
  if (saved) {
    currentUser.value = saved
    isLoggedIn.value = true
    initData()
  }
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
.session-item { padding: 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px; transition: 0.2s; }
.session-item:hover { background: #1f2937; }
.session-item.active { background: #1f2937; border: 1px solid #374151; }
.s-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.s-meta { font-size: 11px; color: #6b7280; margin-top: 4px; }
.sidebar-bottom { border-top: 1px solid #1f2937; padding-top: 16px; }
.project-picker label { font-size: 11px; color: #6b7280; display: block; margin-bottom: 8px; text-transform: uppercase; }
.project-picker select { width: 100%; background: #111827; border: 1px solid #374151; color: white; padding: 10px; border-radius: 6px; margin-bottom: 12px; }
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
.input-area { padding: 24px 20px 48px; background: #f9fafb; }
.input-container { max-width: 800px; margin: 0 auto; position: relative; background: white; border: 1px solid #e5e7eb; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); padding: 12px 16px; }
.input-container textarea { width: 100%; border: none; outline: none; resize: none; font-size: 15px; background: transparent; padding: 4px 40px 4px 0; min-height: 24px; }
.send-btn { position: absolute; right: 12px; bottom: 12px; background: #111827; color: white; border: none; padding: 8px; border-radius: 10px; cursor: pointer; }
.drawer { position: absolute; top: 0; right: 0; width: 42%; height: 100%; background: white; box-shadow: -10px 0 30px rgba(0,0,0,0.05); z-index: 100; display: flex; flex-direction: column; }
.drawer-header { padding: 16px 20px; border-bottom: 1px solid #f3f4f6; display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.drawer-view { flex: 1; overflow-y: auto; padding: 20px; }
.login-wrapper { position: fixed; inset: 0; background: #0b0d11; display: flex; align-items: center; justify-content: center; }
.login-panel { background: white; padding: 48px; border-radius: 20px; width: 400px; text-align: center; }
.panel-logo { font-size: 24px; font-weight: 800; margin-bottom: 24px; }
.primary-action { width: 100%; padding: 14px; background: #111827; color: white; border: none; border-radius: 10px; margin-top: 24px; cursor: pointer; }
</style>