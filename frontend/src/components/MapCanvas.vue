<template>
  <div class="map-container">
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

const fetchMapData = async (id: string) => {
  if (!id) return
  try {
    console.log(`正在加载项目地图: ${id}`)
    // 修正后的接口地址：后面带上项目 ID
    const response = await fetch(`http://211.71.15.39:8002/api/map/${id}`);
    if (!response.ok) throw new Error('后端返回 404');
    
    const data = await response.json();
    const { nodes: pNodes, edges: pEdges } = parseAndroidJson(data);
    
    nodes.value = pNodes;
    edges.value = pEdges;
    
    // 异步等待 DOM 更新后自动缩放地图
    setTimeout(() => { fitView() }, 100)
  } catch (e) {
    console.error("加载地图数据失败", e);
  }
}

// 初始化加载
onMounted(() => {
  fetchMapData(props.appId)
})

// 监听项目 ID 变化，用户切换下拉框时自动重绘地图
watch(() => props.appId, (newId) => {
  fetchMapData(newId)
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  background-color: #f8fafc;
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