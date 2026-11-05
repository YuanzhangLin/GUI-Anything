<template>
  <section class="run-workbench">
    <header><h2>代码目标工作台</h2><button @click="load">刷新</button></header>
    <p>Agent 安装状态不代表模型已登录；未配置时仍可查看源码和 Map。</p><p role="alert" v-if="error">{{ error }}</p>
    <details><summary>从 Map 选择源码依据</summary><div style="height:500px"><MapCanvas :app-id="appId" @source="openEvidence" /></div></details>
    <div class="workbench-columns">
      <aside><label>项目源码 <input v-model="filter" placeholder="按文件路径筛选"></label>
        <SourceTree :files="files" :filter="filter" :selected="source?.path" @select="openSource" />
      </aside>
      <main>
        <template v-if="source">
          <h3>{{ source.path }}</h3><small>版本 {{ source.revision.commit || '无 Git 提交（按文件哈希绑定）' }} {{ source.revision.dirty ? '· 含本地修改' : '' }}</small>
          <p>点击起始行，再按 Shift 点击结束行，或填写行范围。</p><label v-if="source.symbols.length">选择已解析的 Java 方法 <select @change="selectMethod"><option value="">选择方法…</option><option v-for="(method, index) in source.symbols" :key="index" :value="index">{{ method.signature }}</option></select></label>
          <div ref="sourcePanel" class="source-lines"><button v-for="(line, i) in lines" :key="i" :data-line="i + 1" :class="{ selected: i + 1 >= start && i + 1 <= end }" @click="selectLine(i + 1, $event)"><span>{{ i + 1 }}</span><code>{{ line || ' ' }}</code></button></div>
          <form @submit.prevent="createRun">
            <label>起始行 <input type="number" v-model.number="start" min="1" :max="lines.length"></label>
            <label>结束行 <input type="number" v-model.number="end" :min="start" :max="lines.length"></label>
            <label>任务目标 <textarea v-model="goal" required placeholder="要触发什么行为、到达哪个代码分支？"></textarea></label>
            <label>业务成功条件 <textarea v-model="business" required placeholder="例如：原记录删除，合并内容持久化"></textarea></label>
            <details><summary>页面断言（可选）</summary><p>按填写的属性精确匹配控件；填写多个属性时须同时满足。</p><label>资源 ID <input v-model="uiResource" placeholder="包名:id/控件名"></label><label>显示文本 <input v-model="uiText"></label><label>无障碍描述 <input v-model="uiDescription"></label><label>预期匹配数量 <input type="number" min="0" v-model.number="uiCount"></label></details>
            <details><summary>可执行业务断言（可选）</summary><label>已配置的数据库检查名 <input v-model="businessCheck" placeholder="例如 merged_notes"></label><label>绑定参数 JSON 数组 <textarea v-model="businessParameters"></textarea></label><label>预期查询结果 JSON 数组 <textarea v-model="businessExpected"></textarea></label></details><label>Agent <select v-model="agentProvider"><option v-for="a in agentList" :key="a.id" :value="a.id">{{ a.id }} · {{ a.available ? '已安装' : '不可用' }}</option><option value="manual">CLI 手动执行</option></select></label><label>执行设备 <select v-model="serial"><option value="">暂不选择</option><option v-for="d in deviceList" :key="d.serial" :value="d.serial" :disabled="d.state !== 'device'">{{ d.serial }} · {{ d.state }}</option></select></label><label>操作预算 <input type="number" v-model.number="budget" min="1" max="1000"></label>
            <label>时间预算（秒）<input type="number" v-model.number="timeBudget" min="30" max="14400"></label>
            <button :disabled="busy">保存 Run 目标</button>
          </form>
        </template>
        <p v-else>从左侧打开源码，选择本次测试目标。</p>
      </main>
      <aside><h3>已保存的 Run</h3><ul><li v-for="run in runs" :key="run.id"><button @click="openRun(run.id)">{{ run.goal }}</button></li></ul>
        <article v-if="active"><h3>{{ active.goal }}</h3><p>{{ active.target.path }} : {{ active.target.start_line }}–{{ active.target.end_line }}</p>
          <details v-if="active.map_snapshot"><summary>创建时的 Map 快照</summary><p>该图谱固定于 Run 创建时，后续重新出图不会改变它。源码链接打开当前文件，请核对版本。</p><div style="height:420px"><MapCanvas :key="active.id" :app-id="appId" :snapshot="active.map_snapshot" @source="openEvidence" /></div></details><p v-else>创建时未保存 Map 快照。</p>
          <p :class="{ mismatch: !active.source_check?.matches }">{{ active.source_check?.matches ? '源码版本匹配' : '源码已变化或不可用；不可按原目标直接执行' }}</p>
          <pre>{{ active.target.excerpt }}</pre><button @click="openSavedTarget">查看目标源码</button><p>覆盖：{{ active.results.coverage }} · 业务：{{ active.results.business }} · 页面：{{ active.results.ui }}</p><p>状态：{{ active.status }}</p>
          <h4>保存的成功条件</h4><ul><li v-for="(condition, index) in active.conditions" :key="index"><strong>{{ condition.kind }}</strong>：{{ condition.description }}<span> · {{ active.condition_results?.[index]?.status || 'not_checked' }}</span><pre v-if="condition.selector">{{ JSON.stringify(condition.selector, null, 2) }}
预期数量：{{ condition.expected_count }}</pre></li></ul>
          <button @click="downloadRun">导出任务 JSON</button>
          <div class="run-controls"><button v-if="active.status === 'draft'" @click="control('start')">开始执行</button><button v-if="active.status === 'running'" @click="control('pause')">暂停</button><button v-if="active.status === 'paused'" @click="control('resume')">继续</button><button v-if="active.status !== 'stopped'" @click="control('stop')">停止</button><button :disabled="busy" @click="observe">观察设备</button></div>
          <button :disabled="busy" @click="coverage('baseline')">采集覆盖基线</button><button :disabled="busy" @click="coverage('after')">采集执行后覆盖</button><button v-if="active.status === 'running' && active.agent !== 'manual'" @click="launchAgent">启动 Agent</button><button :disabled="busy" @click="verifyAssertions">验证业务断言</button><RunResults :run="active" @source="openCoverageLine" /><p>已用动作 {{ active.actions }} / {{ active.action_budget }}</p><img v-if="screenshot && selectedEvent?.kind !== 'action'" :src="screenshot" alt="设备截图" class="device-shot">
          <section v-if="lastDecision"><h4>Agent 最近计划</h4><ol><li v-for="(step, index) in lastDecision.payload.plan" :key="index">{{ step }}</li></ol><p>决策：{{ lastDecision.payload.status }} · {{ lastDecision.payload.reason }}</p><p v-if="lastDecision.payload.verification">请求验证：{{ lastDecision.payload.verification }}</p></section>
          <p v-if="lastNotice" role="status">最近执行提示：{{ lastNotice.payload.reason }}</p>
          <details v-if="visibleObservation"><summary>UI 层级 · {{ visibleObservation.activity || '未知页面' }}</summary><p>节点按观察顺序显示；父节点编号用于还原层级。</p><div class="hierarchy-table"><table><thead><tr><th>节点 / 父节点</th><th>类型</th><th>资源 ID</th><th>文本 / 描述</th><th>可用</th></tr></thead><tbody><tr v-for="(node, index) in visibleObservation.nodes" :key="index"><td>{{ index }} / {{ node.parent_index ?? '根' }}</td><td>{{ node.class }}</td><td>{{ node.resource_id }}</td><td>{{ node.text }} {{ node.description }}</td><td>{{ node.enabled ? '是' : '否' }}</td></tr></tbody></table></div></details>
          <h4>执行事件</h4><button v-if="selectedEvent" @click="returnToLive">返回最新观察</button><p v-if="selectedEvent">正在回放事件 {{ selectedEvent.seq }}，截图保持在该事件。</p>
          <section v-if="selectedEvent?.kind === 'action'">
            <p>动作：{{ selectedEvent.payload.kind }} · {{ selectedEvent.payload.reason }}</p>
            <p>Map 路径：{{ selectedEvent.payload.edge_id || '未提供' }}</p>
            <p v-if="selectedEvent.payload.kind === 'key'">Android 按键：{{ selectedEvent.payload.key }}</p><p v-else-if="selectedEvent.payload.kind === 'launch'">启动组件：{{ selectedEvent.payload.component }}</p><pre v-else>定位依据：{{ JSON.stringify(selectedEvent.payload.selector || selectedEvent.payload.target, null, 2) }}</pre>
            <button v-for="(evidence, index) in selectedEvent.payload.evidence" :key="index" @click="openEvidence({ path: evidence.file_path, line: evidence.line || 1 })">源码：{{ evidence.file_path }}:{{ evidence.line }}</button>
            <div class="replay-pair"><figure><figcaption>执行前</figcaption><img v-if="screenshot" :src="screenshot" alt="执行前设备截图" class="device-shot"></figure><figure><figcaption>执行后</figcaption><img v-if="afterScreenshot" :src="afterScreenshot" alt="执行后设备截图" class="device-shot"><p v-else>尚无与该动作关联的执行后截图</p></figure></div>
          </section>
          <ol><li v-for="event in events" :key="event.seq"><button @click="inspect(event)">{{ event.seq }} · {{ event.kind }} {{ event.payload.reason || event.payload.activity || '' }}</button></li></ol><details v-if="selectedEvent"><summary>原始事件详情</summary><pre>{{ JSON.stringify(selectedEvent, null, 2) }}</pre></details>
        </article>
      </aside>
    </div>
  </section>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { authFetch } from '../utils/auth'
import MapCanvas from './MapCanvas.vue'
import SourceTree from './SourceTree.vue'
import RunResults from './RunResults.vue'
const props = defineProps<{ appId: string; apiBase: string }>()
const files = ref<string[]>([]), filter = ref(''), source = ref<any>(null), runs = ref<any[]>([]), active = ref<any>(null)
const businessCheck = ref(''), businessParameters = ref('[]'), businessExpected = ref('[]')
const uiResource = ref(''), uiText = ref(''), uiDescription = ref(''), uiCount = ref(1)
const sourcePanel = ref<HTMLElement | null>(null)
const agentProvider = ref('opencode')
const timeBudget = ref(1800)
const agentList = ref<any[]>([])
const deviceList = ref<any[]>([]), serial = ref(''), events = ref<any[]>([]), selectedEvent = ref<any>(null), screenshot = ref('')
const afterScreenshot = ref('')
let lastImageEvent: number | undefined
let runRequest = 0, imageRequest = 0, sourceRequest = 0
let polling = false
let requestedRun: string | null = null
let timer: ReturnType<typeof setInterval> | undefined
const error = ref(''), busy = ref(false), start = ref(1), end = ref(1), goal = ref(''), business = ref(''), budget = ref(60)
const base = computed(() => `${props.apiBase}/workbench`)
const lines = computed<string[]>(() => source.value ? source.value.text.replace(/\r\n/g, '\n').replace(/\n$/, '').split('\n') : [])
const lastDecision = computed(() => [...events.value].reverse().find(event => event.kind === 'agent_decision'))
const lastNotice = computed(() => [...events.value].reverse().find(event => ['blocked', 'agent_blocked', 'agent_error', 'verification_required', 'recovery', 'agent_decision_discarded', 'agent_request_cancelled'].includes(event.kind)))
const visibleObservation = computed(() => {
  if (selectedEvent.value) {
    const event = selectedEvent.value
    return event.kind === 'observation' ? event.payload : event.payload.before || event.payload.after || null
  }
  return [...events.value].reverse().find(event => event.kind === 'observation')?.payload
})
async function request(path: string, options: RequestInit = {}) {
  const r = await authFetch(`${base.value}${path}`, options)
  const body = await r.json()
  if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
  return body
}
async function load() {
  error.value = ''
  try { const [tree, saved] = await Promise.all([request(`/projects/${props.appId}/files`), request(`/projects/${props.appId}/runs`)])
    files.value = tree.files; runs.value = saved
    deviceList.value = (await request('/devices')).devices
    agentList.value = await request('/agents')
    if (tree.truncated) error.value = '文件列表超过上限，仅显示前 20000 项'
  } catch (e) { error.value = String(e) }
}
async function openSource(path: string) {
  const generation = ++sourceRequest
  error.value = ''
  try { const result = await request(`/projects/${props.appId}/source?path=${encodeURIComponent(path)}`)
    if (generation !== sourceRequest) return
    source.value = result; start.value = end.value = 1 }
  catch (e) { if (generation === sourceRequest) error.value = String(e) }
}
async function openEvidence(reference: { path: string; line: number }) {
  await openSource(reference.path)
  if (source.value?.path === reference.path) { start.value = end.value = Math.max(1, Math.min(reference.line, lines.value.length)); await revealSelection() }
}
async function openSavedTarget() {
  const target = active.value?.target
  if (!target) return
  await openSource(target.path)
  if (source.value?.path !== target.path) return
  if (source.value.file_sha256 !== target.file_sha256) {
    error.value = '当前文件与保存的目标版本不同；请核对冻结代码片段，不能沿用旧行号。'
    return
  }
  start.value = Math.max(1, Math.min(target.start_line, lines.value.length))
  end.value = Math.max(start.value, Math.min(target.end_line, lines.value.length))
  await revealSelection()
}
async function openCoverageLine(reference: { path: string; line: number }) {
  const runId = active.value?.id
  await openSavedTarget()
  if (active.value?.id !== runId || source.value?.file_sha256 !== active.value?.target.file_sha256) return
  start.value = end.value = reference.line
  await revealSelection()
}
async function revealSelection() {
  await nextTick()
  sourcePanel.value?.querySelector(`[data-line="${start.value}"]`)?.scrollIntoView({ block: 'center', inline: 'nearest' })
}
function selectMethod(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value === '') return
  const method = source.value.symbols[Number(value)]
  start.value = method.start_line; end.value = method.end_line
  revealSelection()
}
function selectLine(line: number, event: MouseEvent) {
  if (event.shiftKey) { const anchor = start.value; start.value = Math.min(anchor, line); end.value = Math.max(anchor, line) }
  else start.value = end.value = line
}
async function openRun(id: string) {
  const generation = ++runRequest
  if (requestedRun !== id) {
    requestedRun = id; active.value = null; events.value = []; selectedEvent.value = null
    lastImageEvent = undefined; clearImage()
  }
  try { const [run, history] = await Promise.all([request(`/runs/${id}`), request(`/runs/${id}/events`)])
    if (generation !== runRequest) return
    active.value = run; events.value = history
    const latest = [...history].reverse().find(e => e.kind === 'observation')
    if (!selectedEvent.value && latest?.seq !== lastImageEvent) { lastImageEvent = latest?.seq; await showImage(latest?.payload.screenshot, id) }
  } catch (e) { if (generation === runRequest) error.value = String(e) }
}
async function createRun() {
  busy.value = true; error.value = ''
  try {
    const selector = Object.fromEntries(Object.entries({ resource_id: uiResource.value, text: uiText.value, description: uiDescription.value }).filter(([, value]) => value !== ''))
    const conditions: any[] = [{ kind: 'coverage', description: 'Selected executable lines newly covered' }, { kind: 'business', description: business.value, check: businessCheck.value || null, parameters: JSON.parse(businessParameters.value), expected_rows: businessCheck.value ? JSON.parse(businessExpected.value) : null }]
    if (Object.keys(selector).length) conditions.push({ kind: 'ui', description: '页面控件精确匹配', selector, expected_count: uiCount.value })
    const run = await request(`/projects/${props.appId}/runs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      goal: goal.value, target: { path: source.value.path, start_line: start.value, end_line: end.value, file_sha256: source.value.file_sha256 },
      agent: agentProvider.value, device_serial: serial.value || null, action_budget: budget.value, time_budget_seconds: timeBudget.value, conditions
    }) })
    await load(); await openRun(run.id)
  } catch (e) { error.value = String(e) } finally { busy.value = false }
}
function downloadRun() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(active.value, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a'); a.href = url; a.download = `run-${active.value.id}.json`; a.click(); URL.revokeObjectURL(url)
}
async function verifyAssertions() {
  busy.value = true
  try { await request(`/runs/${active.value.id}/assertions`, { method: 'POST' }); await openRun(active.value.id) } catch (e) { error.value = String(e) } finally { busy.value = false }
}
async function launchAgent() {
  try { await request(`/runs/${active.value.id}/agent`, { method: 'POST' }); await openRun(active.value.id) } catch (e) { error.value = String(e) }
}
async function coverage(label: string) {
  busy.value = true
  try { await request(`/runs/${active.value.id}/coverage/${label}`, { method: 'POST' }); await openRun(active.value.id) }
  catch (e) { error.value = String(e) } finally { busy.value = false }
}
async function control(command: string) {
  try { await request(`/runs/${active.value.id}/control/${command}`, { method: 'POST' }); await openRun(active.value.id) } catch (e) { error.value = String(e) }
}
function clearImage() {
  ++imageRequest
  if (screenshot.value) URL.revokeObjectURL(screenshot.value)
  screenshot.value = ''
  if (afterScreenshot.value) URL.revokeObjectURL(afterScreenshot.value)
  afterScreenshot.value = ''
}
async function showImage(name: string | null, runId = active.value?.id) {
  clearImage()
  const generation = imageRequest
  if (!name) return
  const r = await authFetch(`${base.value}/runs/${runId}/assets/${name}`)
  if (!r.ok) throw new Error('截图读取失败')
  const blob = await r.blob()
  if (generation === imageRequest && active.value?.id === runId) screenshot.value = URL.createObjectURL(blob)
}
async function observe() {
  busy.value = true
  try { const observation = await request(`/runs/${active.value.id}/observe`, { method: 'POST' }); await showImage(observation.screenshot); await openRun(active.value.id) }
  catch (e) { error.value = String(e) } finally { busy.value = false }
}
async function inspect(event: any) {
  selectedEvent.value = event
  const runId = active.value.id
  try {
    await showImage(event.payload.screenshot || event.payload.before?.screenshot || event.payload.after?.screenshot, runId)
    if (selectedEvent.value?.seq !== event.seq || active.value?.id !== runId) return
    const generation = imageRequest
    const completion = events.value.find(e => e.kind === 'action_completed' && e.payload.action_seq === event.seq)
    if (!completion?.payload.after?.screenshot) return
    const r = await authFetch(`${base.value}/runs/${runId}/assets/${completion.payload.after.screenshot}`)
    if (!r.ok) throw new Error('执行后截图读取失败')
    const blob = await r.blob()
    if (generation === imageRequest) afterScreenshot.value = URL.createObjectURL(blob)
  } catch (e) { if (active.value?.id === runId) error.value = String(e) }
}
async function returnToLive() {
  selectedEvent.value = null; lastImageEvent = undefined
  if (active.value) await openRun(active.value.id)
}
onMounted(() => { load(); timer = setInterval(async () => {
  if (active.value?.status !== 'running' || busy.value || polling) return
  polling = true
  try { await openRun(active.value.id) } finally { polling = false }
}, 2000) })
onUnmounted(() => { if (timer) clearInterval(timer); ++runRequest; ++sourceRequest; clearImage() })
watch(() => props.appId, () => {
  ++runRequest; ++sourceRequest; requestedRun = null; selectedEvent.value = null
  source.value = active.value = null; events.value = []; clearImage(); load()
})
</script>
<style scoped>
.hierarchy-table{overflow:auto;max-height:320px}.hierarchy-table table{border-collapse:collapse;font-size:12px}.hierarchy-table th,.hierarchy-table td{padding:6px;border:1px solid #cbd5e1;overflow-wrap:anywhere;min-width:70px}
.replay-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.replay-pair figure{margin:0;min-width:0}
.run-workbench h3,.run-workbench small{overflow-wrap:anywhere}.run-workbench select{max-width:100%;width:100%}.run-workbench input,.run-workbench textarea{box-sizing:border-box}
.device-shot{width:100%;max-height:450px;object-fit:contain}.run-controls{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.run-workbench{margin-top:24px;padding:20px;border:1px solid #ccd5df;border-radius:12px;background:white;color:#172338}.run-workbench header{display:flex;align-items:center;justify-content:space-between}.workbench-columns{display:grid;grid-template-columns:minmax(150px,1fr) minmax(300px,3fr) minmax(180px,1fr);gap:18px}.workbench-columns>*{min-width:0}.run-workbench ul{list-style:none;padding:0;max-height:550px;overflow:auto}.run-workbench li button{text-align:left;overflow-wrap:anywhere;width:100%;margin-bottom:6px}.run-workbench button{cursor:pointer;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:#f8fafc}.run-workbench label{display:block;margin:10px 0}.run-workbench input,.run-workbench textarea{width:100%;padding:7px;border:1px solid #ccd5df;border-radius:4px}.source-lines{max-height:480px;overflow:auto;margin-top:12px;background:#f8fafc}.source-lines button{display:flex;width:100%;border:0;border-radius:0;text-align:left;white-space:pre;min-width:max-content}.source-lines span{display:inline-block;width:45px;color:#64748b;flex-shrink:0}.source-lines .selected{background:#ccefe3}.run-workbench pre{overflow:auto;font-size:12px}.mismatch,[role=alert]{color:#b42318}@media(max-width:1000px){.workbench-columns{grid-template-columns:1fr}.run-workbench ul{max-height:150px}}
</style>
