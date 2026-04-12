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

const props = defineProps(['appList', 'apiBase'])
const emit = defineEmits(['close'])

const activeTab = ref('projects')
const selectedProject = ref(null)
const logs = ref([
  '[SYSTEM] 后台管理系统初始化完成...',
  '[INFO] 已连接到后端 API: 211.71.15.39:8002'
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
/* 保持你之前喜欢的样式风格 */
.admin-screen { position: fixed; inset: 0; background: rgba(2, 6, 23, 0.9); z-index: 2000; display: flex; padding: 30px; }
.admin-layout { width: 100%; max-width: 1400px; margin: 0 auto; background: #ffffff; border-radius: 20px; display: flex; flex-direction: column; overflow: hidden; }
.admin-topbar { background: #0f172a; color: white; padding: 18px 28px; display: flex; justify-content: space-between; align-items: center; }
.brand { display: flex; align-items: center; gap: 12px; font-weight: 800; }
.admin-main { flex: 1; display: flex; overflow: hidden; }
.admin-nav { width: 240px; background: #f8fafc; border-right: 1px solid #e2e8f0; padding: 20px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-radius: 10px; cursor: pointer; color: #64748b; font-size: 14px; margin-bottom: 6px; transition: 0.2s; }
.nav-item.active { background: #10b981; color: white; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }
.admin-body { flex: 1; padding: 40px; overflow-y: auto; background: #ffffff; }
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