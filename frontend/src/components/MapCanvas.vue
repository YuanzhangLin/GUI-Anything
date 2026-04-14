<template>
  <div class="map-container">
    <div class="map-toolbar">
      <button class="toolbar-btn" :disabled="isGenerating || !props.appId" @click="generateMap">
        {{ isGenerating ? `生成中… ${progress}%` : '生成 UI Map' }}
      </button>
      <span v-if="errorMsg" class="toolbar-error">{{ errorMsg }}</span>
    </div>
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :fit-view-on-init="true"
      :default-viewport="{ x: 0, y: 0, zoom: 0.5 }"
    >
      <Background pattern-color="#aaa" :gap="16" />
      <Controls />
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { parseAndroidJson } from '../utils/parser'

// 导入 Vue Flow 样式
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

// 接收父组件 App.vue 传过来的 appId
const props = defineProps<{
  appId: string
}>()

const nodes = ref([])
const edges = ref([])
const { fitView } = useVueFlow()

const errorMsg = ref('')
const isGenerating = ref(false)
const progress = ref(0)

const getApiBase = () => {
  const envBase = import.meta.env.VITE_API_BASE
  if (envBase) return envBase
  const protocol = window.location.protocol
  const hostname = window.location.hostname
  return `${protocol}//${hostname}:8002/api`
}

const API_BASE = getApiBase()

const fetchMapData = async (id: string) => {
  if (!id) return
  try {
    errorMsg.value = ''
    const response = await fetch(`${API_BASE}/map/${id}`)
    if (!response.ok) throw new Error(`加载失败 (${response.status})`)

    const data = await response.json()
    const { nodes: pNodes, edges: pEdges } = parseAndroidJson(data)

    nodes.value = pNodes
    edges.value = pEdges

    // 异步等待 DOM 更新后自动缩放地图
    setTimeout(() => { fitView() }, 100)
  } catch (e) {
    console.error("加载地图数据失败", e)
    errorMsg.value = '加载地图失败（可能尚未生成 UI Map）'
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const generateMap = async () => {
  if (!props.appId || isGenerating.value) return
  isGenerating.value = true
  progress.value = 0
  errorMsg.value = ''
  try {
    const res = await fetch(`${API_BASE}/map/${props.appId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'real' })
    })
    if (!res.ok) throw new Error(`任务创建失败 (${res.status})`)
    const { task_id } = await res.json()
    if (!task_id) throw new Error('后端未返回 task_id')

    for (let i = 0; i < 120; i++) {
      const st = await fetch(`${API_BASE}/map/tasks/${task_id}`)
      if (!st.ok) throw new Error(`任务状态查询失败 (${st.status})`)
      const data = await st.json()
      progress.value = Number(data.progress ?? progress.value)
      if (data.status === 'success') {
        await fetchMapData(props.appId)
        return
      }
      if (data.status === 'error') {
        throw new Error(data.message || '生成失败')
      }
      await sleep(800)
    }
    throw new Error('生成超时')
  } catch (e: any) {
    console.error(e)
    errorMsg.value = e?.message || '生成失败'
  } finally {
    isGenerating.value = false
  }
}

// 初始化加载
onMounted(() => {
  fetchMapData(props.appId)
})

// 监听项目 ID 变化，用户切换下拉框时自动重绘地图
watch(() => props.appId, (newId) => {
  errorMsg.value = ''
  isGenerating.value = false
  progress.value = 0
  fetchMapData(newId)
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  background-color: #f8fafc;
  position: relative;
}

.map-toolbar {
  position: absolute;
  z-index: 20;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  backdrop-filter: blur(10px);
}

.toolbar-btn {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #10b981;
  background: #10b981;
  color: #fff;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
}

.toolbar-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.toolbar-error {
  color: #ef4444;
  font-size: 12px;
}

:deep(.vue-flow__node) {
  font-size: 12px;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}

:deep(.vue-flow__edge-path) {
  stroke-width: 2.5;
  stroke: #94a3b8;
}
</style>