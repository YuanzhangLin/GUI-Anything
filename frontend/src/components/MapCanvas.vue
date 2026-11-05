<template>
  <div class="map-container">
    <div class="map-toolbar">
      <button v-if="!props.demo && !props.snapshot" class="toolbar-btn" :disabled="isGenerating || !props.appId" @click="generateMap">
        {{ isGenerating ? `生成中… ${progress}%` : 'Fast 出图' }}
      </button>
      <label v-if="edges.length">选择跳转 <select aria-label="选择图谱跳转" @change="selectTransition"><option value="">选择路径…</option><option v-for="edge in edges" :key="edge.id" :value="edge.id">{{ edge.source.split('.').pop() }} → {{ edge.target.split('.').pop() }} · {{ edge.label }}</option></select></label>
      <span v-if="errorMsg" class="toolbar-error">{{ errorMsg }}</span>
    </div>
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      @node-click="onNodeClick"
      @edge-click="onEdgeClick"
      :fit-view-on-init="true"
      :default-viewport="{ x: 0, y: 0, zoom: 0.5 }"
    >
      <Background pattern-color="#aaa" :gap="16" />
      <Controls />
    </VueFlow>
    <div v-if="selection" class="map-inspector">
      <button class="inspector-close" type="button" @click="selection = null" aria-label="关闭详情">×</button>
      <strong>{{ selection.title }}</strong>
      <p>{{ selection.detail }}</p>
      <p v-if="selection.relationship">{{ selection.relationship }}</p>
      <p v-if="selection.trigger">触发方式：{{ selection.trigger }}</p>
      <p v-if="selection.evidence">依据：{{ selection.evidence }}</p><button v-if="!props.demo && sourceReference" @click="emit('source', sourceReference)">打开对应源码</button>
      <small>{{ selection.verification }}</small>
      <div v-if="selection.elements.length" class="inspector-elements">
        <strong>静态识别元素（{{ selection.elements.length }}）</strong>
        <ul>
          <li v-for="element in selection.elements.slice(0, 12)" :key="element.id">
            <span>{{ element.label }}</span>
            <small>{{ element.type }} · {{ element.id }} · {{ element.kind === 'display_element' ? '展示' : '可操作候选' }}</small>
          </li>
        </ul>
        <small v-if="selection.elements.length > 12">另有 {{ selection.elements.length - 12 }} 个元素未在此列出</small>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { parseAndroidJson } from '../utils/parser'
import { authFetch } from '../utils/auth'

// 导入 Vue Flow 样式
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

// 接收父组件 App.vue 传过来的 appId
const props = defineProps<{
  appId: string
  demo?: boolean
  snapshot?: Record<string, any>
}>()

const emit = defineEmits<{ source: [reference: { path: string; line: number }] }>()
const sourceReference = ref<{ path: string; line: number } | null>(null)
const nodes = ref([])
const edges = ref([])
const { fitView } = useVueFlow()

const errorMsg = ref('')
const isGenerating = ref(false)
const progress = ref(0)
type MapElement = { id: string, label: string, type: string, kind: string }
const selection = ref<{ title: string, detail: string, relationship: string, evidence: string, verification: string, trigger: string, elements: MapElement[] } | null>(null)

const onNodeClick = ({ node }: any) => {
  const screen = node.data || {}
  const component = screen.components?.[0] || {}
  sourceReference.value = component.file_path ? { path: component.file_path, line: component.line || 1 } : null
  selection.value = {
    title: screen.title || node.id,
    detail: `组件：${component.type || '未知'}；布局：${(screen.layouts || []).join(', ') || '未识别'}`,
    relationship: [
      ...(screen.parent_pages || []).map((parent: any) => `由 ${parent.title} 承载（${parent.kind === 'tab_host' ? '标签页' : '导航容器'}）`),
      ...(screen.contained_pages || []).map((child: any) => `承载 ${child.title}（${child.kind === 'tab_host' ? '标签页' : '导航目的地'}）`)
    ].join('；'),
    evidence: component.file_path || '',
    verification: screen.kind === 'screen_candidate' ? '静态分析候选页面，未经运行时验证' : '',
    trigger: '',
    elements: screen.elements || []
  }
}

const onEdgeClick = ({ edge }: any) => {
  const transition = edge.data || {}
  const evidence = transition.evidence?.[0] || {}
  sourceReference.value = evidence.file_path ? { path: evidence.file_path, line: evidence.line || 1 } : null
  const origin = nodes.value.find((node: any) => node.id === edge.source)?.data || {}
  const trigger = (origin.elements || []).find((element: MapElement) => element.id === transition.trigger_id)
  selection.value = {
    title: `${edge.source} → ${edge.target}`,
    detail: transition.action || edge.label || '跳转',
    relationship: transition.containment ? `同时存在承载关系：${transition.containment.kind === 'tab_host' ? '标签页' : '导航容器'}` : '',
    evidence: [evidence.file_path, evidence.line].filter(Boolean).join(':'),
    verification: transition.verification === 'demo' ? '固定示例关系' : transition.verification === 'source_rule' ? '由源码规则识别' : transition.verification === 'decompiled_rule' ? '由反编译代码规则识别' : '尚未校验',
    trigger: transition.trigger?.status === 'resolved'
      ? `${transition.trigger?.label || trigger?.label || transition.trigger_id}（静态识别）`
      : transition.trigger?.status === 'event_only'
        ? `${transition.trigger?.label || transition.action}；具体控件未定位`
        : '尚未定位',
    elements: []
  }
}
function selectTransition(event: Event) {
  const id = (event.target as HTMLSelectElement).value
  const edge = edges.value.find((item: any) => item.id === id)
  if (edge) onEdgeClick({ edge })
}

const getApiBase = () => {
  const envBase = import.meta.env.VITE_API_BASE
  if (envBase) return envBase
  return '/api'
}

const API_BASE = getApiBase()

const fetchMapData = async (id: string) => {
  if (!id) return
  try {
    errorMsg.value = ''
    let data = props.snapshot
    if (!data) {
      const response = await authFetch(props.demo ? `${API_BASE}/demo/map` : `${API_BASE}/map/${id}`)
      if (!response.ok) throw new Error(`加载失败 (${response.status})`)
      data = await response.json()
    }
    const { nodes: pNodes, edges: pEdges } = parseAndroidJson(data)

    nodes.value = pNodes
    edges.value = pEdges
    selection.value = null

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
    const res = await authFetch(`${API_BASE}/map/${props.appId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'fast' })
    })
    if (!res.ok) throw new Error(`任务创建失败 (${res.status})`)
    const { task_id } = await res.json()
    if (!task_id) throw new Error('后端未返回 task_id')

    for (let i = 0; i < 120; i++) {
      const st = await authFetch(`${API_BASE}/map/tasks/${task_id}`)
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
  selection.value = null
  errorMsg.value = ''
  isGenerating.value = false
  progress.value = 0
  fetchMapData(newId)
})
watch(() => props.snapshot, () => fetchMapData(props.appId))
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  background-color: #f8fafc;
  position: relative;
}
.map-inspector { position: absolute; z-index: 30; right: 16px; bottom: 16px; width: min(360px, calc(100% - 32px)); max-height: min(580px, calc(100% - 32px)); overflow-y: auto; padding: 16px; background: white; border: 1px solid #cbd5e1; border-radius: 12px; box-shadow: 0 12px 32px #0f172a24; color: #0f172a; font-size: 13px; }
.map-inspector p { margin: 8px 0; overflow-wrap: anywhere; }
.map-inspector small { color: #64748b; }
.inspector-elements { border-top: 1px solid #e2e8f0; margin-top: 12px; padding-top: 12px; }
.inspector-elements ul { list-style: none; padding: 0; margin: 8px 0; }
.inspector-elements li { padding: 7px 0; border-bottom: 1px solid #f1f5f9; }
.inspector-elements li span, .inspector-elements li small { display: block; }
.inspector-close { float: right; border: 0; background: none; font-size: 20px; cursor: pointer; }

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
