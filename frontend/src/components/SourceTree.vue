<template>
  <nav aria-label="项目源码目录" class="source-tree">
    <p v-if="!rows.length">没有匹配的源码文件。</p>
    <ul>
      <li v-for="row in rows" :key="row.path" :style="{ paddingLeft: `${row.depth * 12}px` }">
        <button v-if="row.directory" :aria-expanded="isOpen(row.path)" :title="row.path" @click="toggle(row.path)">{{ isOpen(row.path) ? '▾' : '▸' }} {{ row.name }}/</button>
        <button v-else :aria-current="selected === row.path ? 'true' : undefined" :title="row.path" @click="$emit('select', row.path)">{{ row.name }}</button>
      </li>
    </ul>
  </nav>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
const props = defineProps<{ files: string[]; filter: string; selected?: string }>()
defineEmits<{ select: [path: string] }>()
const expanded = ref(new Set<string>())
const isOpen = (path: string) => Boolean(props.filter.trim()) || expanded.value.has(path)
function toggle(path: string) {
  if (expanded.value.has(path)) expanded.value.delete(path)
  else expanded.value.add(path)
}
const rows = computed(() => {
  const entries = new Map<string, { path: string; name: string; directory: boolean; depth: number }>()
  for (const file of props.files) {
    if (!file.toLowerCase().includes(props.filter.trim().toLowerCase())) continue
    const parts = file.split('/')
    for (let i = 0; i < parts.length; i++) {
      const path = parts.slice(0, i + 1).join('/')
      entries.set(path, { path, name: parts[i], directory: i < parts.length - 1, depth: i })
      if (i < parts.length - 1 && !isOpen(path)) break
    }
  }
  return [...entries.values()].sort((a, b) => {
    const left = a.path.split('/'), right = b.path.split('/')
    for (let i = 0; i < Math.min(left.length, right.length); i++) {
      if (left[i] === right[i]) continue
      const leftDirectory = i < left.length - 1 || a.directory
      const rightDirectory = i < right.length - 1 || b.directory
      if (leftDirectory !== rightDirectory) return leftDirectory ? -1 : 1
      return left[i].localeCompare(right[i])
    }
    return left.length - right.length
  })
})
watch(() => props.selected, path => {
  if (!path) return
  const parts = path.split('/')
  for (let i = 1; i < parts.length; i++) expanded.value.add(parts.slice(0, i).join('/'))
}, { immediate: true })
</script>
<style scoped>
.source-tree{max-height:550px;overflow:auto}.source-tree ul{list-style:none;padding:0;margin:0}.source-tree li{margin:2px 0}.source-tree button{max-width:100%;border:0;background:transparent;text-align:left;padding:5px;overflow-wrap:anywhere;cursor:pointer}.source-tree button[aria-current=true]{background:#ccefe3;font-weight:600}@media(max-width:1000px){.source-tree{max-height:220px}}
</style>
