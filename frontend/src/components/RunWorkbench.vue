<template>
  <section class="run-workbench">
    <header class="workbench-toolbar"><nav aria-label="工作区域"><button :class="{current: pane === 'source'}" @click="pane = 'source'">源码与任务</button><button :class="{current: pane === 'runs'}" @click="pane = 'runs'">执行记录 <span>{{ runs.length }}</span></button><button :class="{current: pane === 'settings'}" @click="pane = 'settings'">工具与模型</button></nav><div><button @click="load">刷新</button><button :aria-expanded="deviceOpen" aria-controls="device-drawer" @click="deviceOpen = !deviceOpen">设备面板 {{ deviceOpen ? '›' : '‹' }}</button></div></header>
    <p role="alert" v-if="error">{{ error }}</p>
    <section v-if="pane === 'settings'" class="tool-settings"><h2>执行工具与模型</h2><p>选择任务的执行工具，模型认证独立于平台登录。</p><label>执行工具<select v-model="agentProvider"><option v-for="a in agentList" :key="a.id" :value="a.id">{{ a.id }} · {{ a.available ? '已安装' : '未安装' }}</option><option value="manual">手动 / CLI</option></select></label><p class="setup-note">模型配置入口正在完善。当前尚未检查认证；请勿将 API key 填入任务描述或对话。</p></section>
    <div class="execution-layout" :class="{'device-open': deviceOpen}">
    <div class="execution-content">
    <details v-show="pane === 'source'"><summary>从 Map 选择源码依据</summary><div style="height:500px"><MapCanvas :app-id="appId" @source="openEvidence" /></div></details>
    <div class="workbench-columns" :class="{'runs-mode': pane === 'runs'}" v-show="pane !== 'settings'">
      <aside v-show="pane === 'source'" class="file-browser"><label>项目源码 <input v-model="filter" placeholder="按文件路径筛选"></label>
        <SourceTree :files="files" :filter="filter" :selected="source?.path" @select="openSource" />
      </aside>
      <main v-show="pane === 'source'" class="source-editor">
        <template v-if="source">
          <h3>{{ source.path }}</h3><small>版本 {{ source.revision.commit || '无 Git 提交（按文件哈希绑定）' }} {{ source.revision.dirty ? '· 含本地修改' : '' }}</small>
          <p>点击起始行，再按 Shift 点击结束行，或填写行范围。</p><label v-if="source.symbols.length">选择已解析的 Java 方法 <select @change="selectMethod"><option value="">选择方法…</option><option v-for="(method, index) in source.symbols" :key="index" :value="index">{{ method.signature }}</option></select></label>
          <div ref="sourcePanel" class="source-lines"><button v-for="(line, i) in lines" :key="i" :data-line="i + 1" :class="{ selected: i + 1 >= start && i + 1 <= end }" @click="selectLine(i + 1, $event)"><span>{{ i + 1 }}</span><code>{{ line || ' ' }}</code></button></div>
          <form @submit.prevent="createRun">
            <label>起始行 <input type="number" v-model.number="start" min="1" :max="lines.length"></label>
            <label>结束行 <input type="number" v-model.number="end" :min="start" :max="lines.length"></label>
            <h3>定义任务</h3><label>任务目标 <textarea v-model="goal" required placeholder="要触发什么行为、到达哪个代码分支？"></textarea></label>
            <label>业务成功条件 <textarea v-model="business" required placeholder="例如：原记录删除，合并内容持久化"></textarea></label>
            <details><summary>页面断言（可选）</summary><p>按填写的属性精确匹配控件；填写多个属性时须同时满足。</p><label>资源 ID <input v-model="uiResource" placeholder="包名:id/控件名"></label><label>显示文本 <input v-model="uiText"></label><label>无障碍描述 <input v-model="uiDescription"></label><label>预期匹配数量 <input type="number" min="0" v-model.number="uiCount"></label></details>
            <details><summary>可执行业务断言（可选）</summary><label>已配置的数据库检查名 <input v-model="businessCheck" placeholder="例如 merged_notes"></label><label>绑定参数 JSON 数组 <textarea v-model="businessParameters"></textarea></label><label>预期查询结果 JSON 数组 <textarea v-model="businessExpected"></textarea></label></details><label>Agent <select v-model="agentProvider"><option v-for="a in agentList" :key="a.id" :value="a.id">{{ a.id }} · {{ a.available ? '已安装' : '不可用' }}</option><option value="manual">CLI 手动执行</option></select></label><label>执行设备 <select v-model="serial"><option value="">暂不选择</option><option v-for="d in deviceList" :key="d.serial" :value="d.serial" :disabled="d.state !== 'device'">{{ d.serial }} · {{ d.state }}</option></select></label><label>操作预算 <input type="number" v-model.number="budget" min="1" max="1000"></label>
            <label>时间预算（秒）<input type="number" v-model.number="timeBudget" min="30" max="14400"></label>
            <button class="primary-action" :disabled="busy">保存任务</button>
          </form>
        </template>
        <div v-else class="editor-empty"><FileCode2 :size="38" :stroke-width="1.3"/><h2>从一段代码开始</h2><p>打开左侧文件，选择方法或代码行。<br>为它定义一个可执行、可验证的任务。</p><button @click="pane = 'runs'">查看已有任务</button></div>
      </main>
      <aside v-show="pane === 'runs'" class="run-history"><h3>已保存任务</h3><p v-if="!runs.length">还没有任务。先到「源码与任务」选择代码目标。</p><ul><li v-for="run in runs" :key="run.id"><button @click="openRun(run.id)">{{ run.goal }}</button></li></ul>
        <article v-if="active"><h3>{{ active.goal }}</h3><p>{{ active.target.path }} : {{ active.target.start_line }}–{{ active.target.end_line }}</p>
          <details v-if="active.map_snapshot"><summary>创建时的 Map 快照</summary><p>该图谱固定于 Run 创建时，后续重新出图不会改变它。源码链接打开当前文件，请核对版本。</p><div style="height:420px"><MapCanvas :key="active.id" :app-id="appId" :snapshot="active.map_snapshot" @source="openEvidence" /></div></details><p v-else>创建时未保存 Map 快照。</p>
          <p :class="{ mismatch: !active.source_check?.matches }">{{ active.source_check?.matches ? '源码版本匹配' : '源码已变化或不可用；不可按原目标直接执行' }}</p>
          <pre>{{ active.target.excerpt }}</pre><button @click="openSavedTarget">查看目标源码</button><p>覆盖：{{ active.results.coverage }} · 业务：{{ active.results.business }} · 页面：{{ active.results.ui }}</p><p>状态：{{ active.status }}</p>
          <h4>保存的成功条件</h4><ul><li v-for="(condition, index) in active.conditions" :key="index"><strong>{{ condition.kind }}</strong>：{{ condition.description }}<span> · {{ active.condition_results?.[index]?.status || 'not_checked' }}</span><pre v-if="condition.selector">{{ JSON.stringify(condition.selector, null, 2) }}
预期数量：{{ condition.expected_count }}</pre></li></ul>
          <button @click="downloadRun">导出任务 JSON</button>
          <div class="run-controls"><button v-if="active.status === 'draft'" @click="control('start')">开始执行</button><button v-if="active.status === 'running'" @click="control('pause')">暂停</button><button v-if="active.status === 'paused'" @click="control('resume')">继续</button><button v-if="active.status !== 'stopped'" @click="control('stop')">停止</button><button :disabled="busy" @click="observe">观察设备</button></div>
          <button :disabled="busy" @click="coverage('baseline')">采集覆盖基线</button><button :disabled="busy" @click="coverage('after')">采集执行后覆盖</button><button v-if="active.status === 'running' && active.agent !== 'manual'" @click="launchAgent">启动 Agent</button><button :disabled="busy" @click="verifyAssertions">验证业务断言</button><RunResults :run="active" @source="openCoverageLine" /><p>已用动作 {{ active.actions }} / {{ active.action_budget }}</p>
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
    </div>
    <aside v-if="deviceOpen" id="device-drawer" class="device-drawer" aria-label="虚拟机与设备" @keydown.esc="deviceOpen = false">
      <header><h3><Smartphone :size="18"/> 设备</h3><button aria-label="收起设备面板" @click="deviceOpen = false"><PanelRightClose :size="17"/></button></header>
      <label>目标虚拟机 / 手机<select v-model="serial"><option value="">选择连接设备</option><option v-for="d in deviceList" :key="d.serial" :value="d.serial" :disabled="d.state !== 'device'">{{ d.serial }} · {{ d.state }}</option></select></label>
      <div class="connection-state"><i :class="{connected: deviceList.some(d => d.serial === serial && d.state === 'device')}"/>{{ deviceList.some(d => d.serial === serial && d.state === 'device') ? '设备已连接' : '等待设备连接' }}</div>
      <div class="phone-display"><img v-if="screenshot" :src="screenshot" alt="所选任务的设备观察截图"/><div v-else class="phone-placeholder"><Smartphone :size="42" :stroke-width="1"/><strong>{{ serial ? '等待屏幕画面' : '尚未连接设备' }}</strong><p>{{ serial ? '打开或保存任务后，点击刷新画面。' : '启动 Android 模拟器，或通过 USB 连接手机。' }}</p><button @click="load">重新检测设备</button></div></div>
      <p class="screen-caption">{{ selectedEvent ? '历史回放 · 事件 ' + selectedEvent.seq : '最近一次任务观察（非视频流）' }}</p>
      <dl><dt>画面所属设备</dt><dd>{{ active?.device_serial || '未选择任务' }}</dd><dt>当前观察页面</dt><dd>{{ visibleObservation?.activity || '尚未观察' }}</dd></dl>
      <button class="refresh-screen" :disabled="busy || !active || active.status === 'stopped'" @click="observe">刷新任务设备画面</button>
      <p class="device-help">画面来自已保存任务绑定的设备。切换上方设备用于新建任务，不改变历史任务。</p>
    </aside>
    </div>
  </section>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { FileCode2, Smartphone, PanelRightClose } from 'lucide-vue-next'
import { authFetch } from '../utils/auth'
import MapCanvas from './MapCanvas.vue'
import SourceTree from './SourceTree.vue'
import RunResults from './RunResults.vue'
const props = defineProps<{ appId: string; apiBase: string }>()
const files = ref<string[]>([]), filter = ref(''), source = ref<any>(null), runs = ref<any[]>([]), active = ref<any>(null)
const businessCheck = ref(''), businessParameters = ref('[]'), businessExpected = ref('[]')
const uiResource = ref(''), uiText = ref(''), uiDescription = ref(''), uiCount = ref(1)
const sourcePanel = ref<HTMLElement | null>(null)
const pane = ref('source'), deviceOpen = ref(true)
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
  pane.value = 'source'
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
.setup-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin:16px 0}.setup-overview section{padding:18px;border:1px solid #cbd5e1;border-radius:12px;background:white}.setup-overview h3{margin-top:0}.setup-overview p{color:#475569;line-height:1.6}

.hierarchy-table{overflow:auto;max-height:320px}.hierarchy-table table{border-collapse:collapse;font-size:12px}.hierarchy-table th,.hierarchy-table td{padding:6px;border:1px solid #cbd5e1;overflow-wrap:anywhere;min-width:70px}
.replay-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.replay-pair figure{margin:0;min-width:0}
.run-workbench h3,.run-workbench small{overflow-wrap:anywhere}.run-workbench select{max-width:100%;width:100%}.run-workbench input,.run-workbench textarea{box-sizing:border-box}
.device-shot{width:100%;max-height:450px;object-fit:contain}.run-controls{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.run-workbench{margin-top:24px;padding:20px;border:1px solid #ccd5df;border-radius:12px;background:white;color:#172338}.run-workbench header{display:flex;align-items:center;justify-content:space-between}.workbench-columns{display:grid;grid-template-columns:minmax(150px,1fr) minmax(300px,3fr) minmax(180px,1fr);gap:18px}.workbench-columns>*{min-width:0}.run-workbench ul{list-style:none;padding:0;max-height:550px;overflow:auto}.run-workbench li button{text-align:left;overflow-wrap:anywhere;width:100%;margin-bottom:6px}.run-workbench button{cursor:pointer;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:#f8fafc}.run-workbench label{display:block;margin:10px 0}.run-workbench input,.run-workbench textarea{width:100%;padding:7px;border:1px solid #ccd5df;border-radius:4px}.source-lines{max-height:480px;overflow:auto;margin-top:12px;background:#f8fafc}.source-lines button{display:flex;width:100%;border:0;border-radius:0;text-align:left;white-space:pre;min-width:max-content}.source-lines span{display:inline-block;width:45px;color:#64748b;flex-shrink:0}.source-lines .selected{background:#ccefe3}.run-workbench pre{overflow:auto;font-size:12px}.mismatch,[role=alert]{color:#b42318}@media(max-width:1000px){.workbench-columns{grid-template-columns:1fr}.run-workbench ul{max-height:150px}}

/* Workspace surfaces: quiet chrome, a focused editor, and a dedicated device rail. */
.run-workbench{margin:0;padding:0;border:0;border-radius:0;background:transparent;font-size:13px;color:#283747}
.run-workbench h2{font-size:20px;font-weight:600}.run-workbench h3{font-size:14px;font-weight:600}
.run-workbench button{padding:8px 12px;border-radius:6px;background:#fff;color:#344658;font:inherit;transition:background .15s}
.run-workbench button:hover{background:#edf3f6}.run-workbench button:disabled{cursor:not-allowed;opacity:.45}
.run-workbench :is(button,input,select,textarea):focus-visible{outline:2px solid #287e91;outline-offset:2px}
.run-workbench select,.run-workbench input,.run-workbench textarea{padding:9px 10px;border:1px solid #d7e0e5;border-radius:6px;background:#fff;color:#283747;font:inherit}.run-workbench textarea{min-height:85px;resize:vertical}
.workbench-toolbar{padding:0 0 16px;border-bottom:1px solid #dde4e9;gap:12px;flex-wrap:wrap}.workbench-toolbar nav,.workbench-toolbar>div{display:flex;gap:6px}.workbench-toolbar nav button{border-color:transparent;background:transparent}.workbench-toolbar nav button.current{background:#e0eef1;color:#15566a;font-weight:600}.workbench-toolbar nav span{margin-left:6px;font-size:11px;opacity:.65}
.execution-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:22px;padding-top:20px;align-items:start}.execution-layout.device-open{grid-template-columns:minmax(0,1fr) 300px}.execution-content{min-width:0}
.workbench-columns{grid-template-columns:210px minmax(0,1fr);gap:0;min-height:560px;border:1px solid #dde4e9;border-radius:9px;overflow:hidden;background:#fff;margin-top:14px}.workbench-columns.runs-mode{display:block}.file-browser{padding:16px;background:#f6f8fa;border-right:1px solid #e2e8ed}.source-editor,.run-history{padding:22px}.source-editor>h3{font:12px Consolas,monospace}.source-editor>small{color:#73808e;font-size:11px}.source-editor form{border-top:1px solid #e2e8ed;margin-top:20px;padding-top:12px}
.editor-empty{min-height:470px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#78909c}.editor-empty h2{color:#344658;margin:20px 0 8px}.editor-empty p{line-height:1.9;margin-bottom:24px}
.run-workbench .source-lines{background:#f8fafc;border:1px solid #e3e9ee;border-radius:6px}.run-workbench .source-lines button{border-radius:0;padding:3px 8px;font:12px/1.65 Consolas,monospace;background:transparent}.run-workbench .source-lines button.selected{background:#dceff0}
.run-workbench details{padding:12px 0;border-bottom:1px solid #e5ebef}.run-workbench summary{cursor:pointer;color:#506679}.run-workbench .primary-action{background:#216e83;color:white;border-color:#216e83;padding:10px 18px;margin-top:16px}
.device-drawer{position:sticky;top:0;background:#eef2f5;border:1px solid #dbe3e8;border-radius:10px;padding:16px;animation:drawer-enter .18s ease-out}.device-drawer header h3{display:flex;align-items:center;gap:8px;margin:0}.device-drawer header button{padding:5px;border:0;background:transparent}.device-drawer label{font-size:12px;color:#617484}.device-drawer select{margin-top:7px}.connection-state{display:flex;align-items:center;gap:7px;font-size:12px;margin:14px 0;color:#617484}.connection-state i{width:6px;height:6px;background:#9aa7b1;border-radius:50%}.connection-state i.connected{background:#318c70}
.phone-display{aspect-ratio:9/17;border:6px solid #334452;border-radius:24px;overflow:hidden;background:#e2e8ed;box-shadow:0 8px 20px #33445214;display:flex;align-items:center;justify-content:center}.phone-display img{width:100%;height:100%;object-fit:contain;background:#111}.phone-placeholder{display:flex;flex-direction:column;align-items:center;gap:18px;padding:18px;text-align:center;color:#738492}.phone-placeholder strong{font-size:14px;color:#475e70}.phone-placeholder p{font-size:12px;line-height:1.8;margin:0}.phone-placeholder button{font-size:12px}.screen-caption{text-align:center;color:#748595;font-size:11px;margin:12px 0 18px}.device-drawer dl{font-size:11px}.device-drawer dt{color:#8493a0;margin-top:10px}.device-drawer dd{margin:4px 0;color:#43586a;overflow-wrap:anywhere}.refresh-screen{width:100%;margin-top:12px}.device-help{font-size:11px;line-height:1.7;color:#7a8b99}.tool-settings{max-width:650px;padding:24px 0}.setup-note{padding:16px;background:#f5f0e3;color:#756331;line-height:1.8}
@keyframes drawer-enter{from{opacity:0;transform:translateX(15px)}to{opacity:1;transform:none}}
@media(max-width:1250px){.workbench-columns{grid-template-columns:1fr}.file-browser{border-right:0;border-bottom:1px solid #e2e8ed}.execution-layout.device-open{grid-template-columns:minmax(0,1fr) 270px}}
@media(max-width:850px){.execution-layout.device-open{grid-template-columns:1fr}.device-drawer{position:fixed;right:12px;top:20px;bottom:20px;width:min(300px,calc(100vw - 56px));overflow:auto;z-index:100;box-shadow:-12px 0 40px #25384b30}.phone-display{max-height:480px}.source-editor,.run-history{padding:14px}}
@media(prefers-reduced-motion:reduce){.device-drawer{animation:none}.run-workbench button{transition:none}}
</style>
