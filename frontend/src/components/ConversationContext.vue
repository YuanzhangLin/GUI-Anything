<template>
  <aside ref="rail" class="context-rail" :style="railStyle">
    <div class="rail-resizer" aria-label="调节右侧栏宽度" @pointerdown="startWidthResize" />
    <section class="code-pane" :style="{height:`${codeHeight}px`}">
      <header><strong>项目代码</strong><span class="header-actions"><button @click="expanded=true">展开</button><button @click="loadFiles">刷新</button></span></header>
      <input v-model="filter" placeholder="搜索文件路径" aria-label="搜索源码">
      <p v-if="sourceError" role="alert">{{ sourceError }}</p>
      <SourceTree :files="files" :filter="filter" :selected="source?.path" @select="openSource"/>
      <details v-if="source" open>
        <summary>{{ source.path }}</summary>
        <div class="source-actions">
          <span>{{ startLine === endLine ? `已选第 ${startLine} 行` : `已选 ${startLine}–${endLine} 行` }}</span>
          <button @click="emit('attach', {path:source.path,text:source.text,appId})">附加全文</button>
          <button class="bind-button" :disabled="!serial" @click="bindTarget">重新绑定</button>
        </div>
        <p class="selection-help">点击行选择；按住 Shift 或拖动可选择连续代码。松开后自动绑定当前设备。</p>
        <div class="code-lines" role="listbox" aria-label="选择目标代码行" @pointerleave="finishLineSelection">
          <div v-for="line in sourceLines" :key="line.number" class="code-line" :class="{selected:isLineSelected(line.number)}" role="option" :aria-selected="isLineSelected(line.number)" @pointerdown="beginLineSelection(line.number,$event)" @pointerenter="extendLineSelection(line.number)">
            <span class="line-check" aria-hidden="true">{{ isLineSelected(line.number) ? '✓' : '' }}</span>
            <span class="line-number">{{ line.number }}</span>
            <code>{{ line.text || ' ' }}</code>
          </div>
        </div>
      </details>
    </section>
    <div class="row-resizer" aria-label="调节代码和虚拟机高度" @pointerdown="startHeightResize"><span /></div>
    <section class="device-pane">
      <header><strong>虚拟机 / 设备</strong><button :disabled="loading" @click="loadDevices">检测设备</button></header>
      <select v-model="serial" aria-label="目标设备" @change="deviceChanged">
        <option value="">选择设备</option>
        <option v-for="d in devices" :key="d.serial" :value="d.serial" :disabled="d.state !== 'device'">{{ d.serial }} · {{ d.state }}</option>
      </select>
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="devices.length" class="device-grid">
        <article v-for="device in devices" :key="device.serial" :class="['device-card',{selected:serial===device.serial,offline:device.state!=='device'}]" @click="selectDevice(device)">
          <header><div><strong>{{ device.serial }}</strong><small>{{ device.serial.startsWith('emulator-')?'虚拟机':'真实设备' }} · {{ device.state }}</small></div><span>{{ serial===device.serial?'当前对话':'' }}</span></header>
          <div class="device-screen"><img v-if="deviceViews[device.serial]?.picture" :src="deviceViews[device.serial].picture" :alt="`${device.serial} 当前截图`"><div v-else><strong>{{ deviceViews[device.serial]?.loading?'正在获取画面':device.state==='device'?'等待设备画面':'设备不可用' }}</strong></div></div>
          <footer><span>{{ deviceViews[device.serial]?.activity||'尚未获取当前 App' }}<small>{{ deviceViews[device.serial]?.observed_at?`观察于 ${formatTime(deviceViews[device.serial].observed_at)}`:'尚未观察' }}</small><small>{{ deviceViews[device.serial]?.last_action||'最近动作：无' }}</small></span><button :disabled="device.state!=='device'||deviceViews[device.serial]?.loading" @click.stop="previewDevice(device.serial)">刷新</button></footer>
        </article>
      </div>
      <div v-else class="device-screen empty"><div><strong>{{ loading?'正在检测设备':'没有连接的设备' }}</strong><p>从本机环境启动 Android 模拟器后点击「检测设备」。</p></div></div>
    </section>
  </aside>
  <Teleport to="body">
    <div v-if="expanded" class="code-dialog-backdrop" @click.self="expanded=false">
      <section class="code-dialog" role="dialog" aria-modal="true" aria-label="选择目标代码">
        <header><div><strong>选择目标代码</strong><small>{{ appId }} · {{ source?.path || '尚未选择文件' }}</small></div><button aria-label="关闭代码选择" @click="expanded=false">×</button></header>
        <div class="dialog-meta"><span>项目 / App：{{ appId }}</span><span>范围：{{ source ? `${startLine}–${endLine}` : '未选择' }}</span><span>版本：{{ source?.file_sha256?.slice(0,12) || '—' }}</span></div>
        <div class="dialog-body">
          <aside><input v-model="filter" placeholder="搜索文件路径" aria-label="搜索源码"><SourceTree :files="files" :filter="filter" :selected="source?.path" @select="openSource"/></aside>
          <main>
            <div v-if="source" class="dialog-source-head"><span>{{ source.path }}</span><button :disabled="!serial" @click="bindTarget">绑定到对话</button></div>
            <p v-if="!source" class="dialog-empty">从左侧选择一个源码文件。</p>
            <div v-else class="dialog-code-lines" role="listbox" aria-label="选择目标代码行" @pointerleave="finishLineSelection">
              <div v-for="line in sourceLines" :key="line.number" class="code-line" :class="{selected:isLineSelected(line.number)}" role="option" :aria-selected="isLineSelected(line.number)" @pointerdown="beginLineSelection(line.number,$event)" @pointerenter="extendLineSelection(line.number)"><span class="line-check">{{ isLineSelected(line.number)?'✓':'' }}</span><span class="line-number">{{ line.number }}</span><code>{{ line.text||' ' }}</code></div>
            </div>
          </main>
        </div>
        <footer><span>点击行选择；Shift 或拖动选择连续范围。关闭后会保留当前选择。</span><button :disabled="!source||!serial" @click="bindTarget();expanded=false">提交目标</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {authFetch} from '../utils/auth'
import SourceTree from './SourceTree.vue'

const props=defineProps<{appId:string;apiBase:string}>()
const emit=defineEmits<{attach:[value:{path:string;text:string;appId:string}];target:[value:any];context:[value:any]}>()
const rail=ref<HTMLElement|null>(null)
const files=ref<string[]>([]),filter=ref(''),source=ref<any>(null),devices=ref<any[]>([]),serial=ref(''),picture=ref(''),activity=ref(''),deviceViews=ref<Record<string,any>>({}),error=ref(''),sourceError=ref(''),loading=ref(false)
const startLine=ref(1),endLine=ref(1),expanded=ref(false)
const sourceLines=computed(()=>(source.value?.text||'').split(/\r?\n/).map((text:string,index:number)=>({number:index+1,text})))
function clamp(value:number,min:number,max:number){return Math.min(Math.max(value,min),max)}
const railWidth=ref(clamp(Number(localStorage.getItem('gui_context_w'))||380,280,720))
const codeHeight=ref(Math.max(180,Number(localStorage.getItem('gui_context_code_h'))||330))
const railStyle=computed(()=>({width:`${railWidth.value}px`}))

function bindTarget(){emit('target',{app_id:props.appId,device_serial:serial.value,target:{path:source.value.path,start_line:startLine.value,end_line:endLine.value,file_sha256:source.value.file_sha256}})}
let selectingLines=false,lineAnchor=1
function isLineSelected(line:number){return line>=startLine.value&&line<=endLine.value}
function beginLineSelection(line:number,event:PointerEvent){
  selectingLines=true
  if(event.shiftKey){startLine.value=Math.min(lineAnchor,line);endLine.value=Math.max(lineAnchor,line)}
  else{lineAnchor=line;startLine.value=line;endLine.value=line}
  event.preventDefault()
}
function extendLineSelection(line:number){if(!selectingLines)return;startLine.value=Math.min(lineAnchor,line);endLine.value=Math.max(lineAnchor,line)}
function finishLineSelection(){if(!selectingLines)return;selectingLines=false;if(serial.value)bindTarget()}
function publishDeviceContext(){const device=devices.value.find(d=>d.serial===serial.value);emit('context',serial.value?{serial:serial.value,state:device?.state||'device',details:device?.details||'',activity:activity.value||'',screenshot_available:Boolean(picture.value),screenshot_data_url:picture.value||null,observed_at:new Date().toISOString()}:null)}
async function get(path:string){const r=await authFetch(`${props.apiBase}/workbench${path}`);const data=await r.json();if(!r.ok)throw new Error(data.detail || '请求失败');return data}
async function loadFiles(){const app=props.appId;sourceError.value='';try{const data=await get(`/projects/${app}/files`);if(app===props.appId)files.value=data.files}catch(e){if(app===props.appId)sourceError.value=String(e)}}
async function openSource(path:string){const app=props.appId;try{const data=await get(`/projects/${app}/source?path=${encodeURIComponent(path)}`);if(app===props.appId){source.value=data;startLine.value=1;endLine.value=1}}catch(e){sourceError.value=String(e)}}
async function loadDevices(){error.value='';loading.value=true;try{const data=await get('/devices');devices.value=data.devices;serial.value=devices.value.find(d=>d.serial===serial.value&&d.state==='device')?.serial||devices.value.find(d=>d.state==='device')?.serial||'';if(!data.available)error.value=data.reason;await Promise.all(devices.value.filter(d=>d.state==='device').map(d=>previewDevice(d.serial,false)));syncSelectedContext()}catch(e){error.value=String(e);publishDeviceContext()}finally{loading.value=false}}
async function previewDevice(targetSerial:string,publish=true){deviceViews.value[targetSerial]={...(deviceViews.value[targetSerial]||{}),loading:true};try{const data=await get(`/devices/${encodeURIComponent(targetSerial)}/preview`);deviceViews.value[targetSerial]={picture:`data:image/png;base64,${data.screenshot}`,activity:data.activity||'',observed_at:new Date().toISOString(),last_action:'最近动作：刷新画面',loading:false};if(targetSerial===serial.value)syncSelectedContext(publish)}catch(e){deviceViews.value[targetSerial]={...(deviceViews.value[targetSerial]||{}),loading:false,error:String(e),observed_at:new Date().toISOString()};if(targetSerial===serial.value){error.value=String(e);syncSelectedContext(publish)}}}
function syncSelectedContext(publish=true){const view=deviceViews.value[serial.value]||{};picture.value=view.picture||'';activity.value=view.activity||'';if(publish)publishDeviceContext()}
function formatTime(value:string){return new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}
async function selectDevice(device:any){if(device.state!=='device')return;serial.value=device.serial;syncSelectedContext();if(!deviceViews.value[device.serial]?.picture)await previewDevice(device.serial);if(source.value)bindTarget()}
async function preview(){if(serial.value)await previewDevice(serial.value)}
async function deviceChanged(){syncSelectedContext();if(serial.value&&!deviceViews.value[serial.value]?.picture)await preview();if(serial.value&&source.value)bindTarget()}

let resizeMode:''|'width'|'height'='',originX=0,originY=0,originWidth=0,originHeight=0
function startWidthResize(event:PointerEvent){resizeMode='width';originX=event.clientX;originWidth=railWidth.value;event.preventDefault()}
function startHeightResize(event:PointerEvent){resizeMode='height';originY=event.clientY;originHeight=codeHeight.value;event.preventDefault()}
function resize(event:PointerEvent){
  if(resizeMode==='width'){
    railWidth.value=clamp(originWidth+(originX-event.clientX),280,Math.min(720,window.innerWidth-420))
    localStorage.setItem('gui_context_w',String(railWidth.value))
  }
  if(resizeMode==='height'){
    const max=Math.max(180,(rail.value?.clientHeight||window.innerHeight)-228)
    codeHeight.value=clamp(originHeight+(event.clientY-originY),180,max)
    localStorage.setItem('gui_context_code_h',String(codeHeight.value))
  }
}
function stopResize(){resizeMode=''}

onMounted(()=>{window.addEventListener('pointermove',resize);window.addEventListener('pointerup',stopResize);window.addEventListener('pointerup',finishLineSelection);loadFiles();loadDevices()})
onBeforeUnmount(()=>{window.removeEventListener('pointermove',resize);window.removeEventListener('pointerup',stopResize);window.removeEventListener('pointerup',finishLineSelection)})
watch(()=>props.appId,()=>{source.value=null;files.value=[];expanded.value=false;loadFiles()})
</script>

<style scoped>
.context-rail{position:relative;flex:none;display:flex;flex-direction:column;height:100%;min-width:280px;max-width:min(720px,55vw);border-left:1px solid #cfd9df;background:#f1f5f7;color:#344b5c;font:12px 'Segoe UI','Microsoft YaHei',sans-serif}.rail-resizer{position:absolute;z-index:3;top:0;bottom:0;left:-5px;width:10px;cursor:col-resize}.rail-resizer:hover,.rail-resizer:active{background:rgba(44,113,130,.16)}.row-resizer{height:8px;flex:none;display:flex;align-items:center;justify-content:center;cursor:row-resize;border-top:1px solid #cfd9df;border-bottom:1px solid #cfd9df;background:#e5ecef}.row-resizer span{width:36px;height:2px;border-radius:2px;background:#8fa4b0}.row-resizer:hover{background:#d7e3e7}.code-pane,.device-pane{box-sizing:border-box;padding:14px 16px;min-height:0;overflow:auto}.code-pane{flex:none;min-height:180px}.context-rail header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.header-actions{display:flex;gap:5px}.context-rail button{border:1px solid #c5d3dc;background:white;border-radius:5px;padding:5px 9px;color:#3f6072;cursor:pointer}.context-rail button:disabled{opacity:.45;cursor:default}.context-rail input,.context-rail select{width:100%;box-sizing:border-box;padding:8px;border:1px solid #c5d3dc;border-radius:5px;background:white;margin-bottom:8px}.context-rail summary{overflow-wrap:anywhere;cursor:pointer}.source-actions{position:sticky;top:-14px;z-index:2;display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0 0;padding:8px 0;background:#f1f5f7}.source-actions span{margin-right:auto;color:#526d7e}.source-actions .bind-button{background:#2c7182;color:white;border-color:#2c7182}.selection-help{margin:4px 0 8px;color:#718793;font-size:10px}.code-lines{overflow:auto;max-height:300px;border:1px solid #cbd7de;background:#fff;font:11px/1.55 Consolas,monospace;user-select:none}.code-line{display:grid;grid-template-columns:20px 42px minmax(0,1fr);min-height:18px;cursor:default}.code-line:hover{background:#edf5f7}.code-line.selected{background:#d8ebef}.line-check{display:flex;align-items:center;justify-content:center;color:#256b7d;background:#eef3f5}.line-number{padding:1px 7px;text-align:right;color:#82939d;border-right:1px solid #e0e7eb}.code-line code{padding:1px 8px;white-space:pre;overflow:visible;color:#263f4e}.device-pane{flex:1;min-height:220px;display:flex;flex-direction:column;background:#edf2f4}.device-screen{min-height:150px;flex:1;display:flex;justify-content:center;align-items:center;background:#dfe7eb;border:1px solid #d2dde3;border-radius:6px;overflow:hidden;text-align:center;color:#6c818e}.device-screen img{width:100%;height:100%;object-fit:contain}.device-screen p{font-size:11px;padding:0 20px}.device-pane footer{display:flex;align-items:center;gap:10px;margin-top:10px}.device-pane footer span{flex:1;display:flex;flex-direction:column;overflow-wrap:anywhere;font-size:10px}.device-pane footer small{margin-top:3px;color:#477486}.device-pane footer button{flex-shrink:0}[role=alert]{color:#a44332;font-size:11px}.code-pane :deep(.source-tree){max-height:180px}.code-dialog-backdrop{position:fixed;z-index:3000;inset:0;display:grid;place-items:center;padding:28px;background:#10202bb8}.code-dialog{width:min(1380px,96vw);height:min(880px,92vh);display:flex;flex-direction:column;overflow:hidden;border-radius:12px;background:#f7fafb;box-shadow:0 30px 90px #09151e66;font:13px 'Segoe UI','Microsoft YaHei',sans-serif;color:#344b5c}.code-dialog>header{display:flex;align-items:center;justify-content:space-between;padding:17px 20px;background:#1e3442;color:white}.code-dialog>header div{display:flex;flex-direction:column;gap:3px}.code-dialog>header small{color:#a9bec9}.code-dialog button{padding:7px 12px;border:1px solid #bdcdd5;border-radius:5px;background:white;color:#345a6c;cursor:pointer}.code-dialog>header button{border:0;background:transparent;color:white;font-size:24px}.dialog-meta{display:flex;gap:24px;padding:10px 20px;border-bottom:1px solid #d4dfe4;background:#edf3f5;color:#5b7280}.dialog-body{display:grid;grid-template-columns:320px minmax(0,1fr);flex:1;min-height:0}.dialog-body>aside{padding:15px;border-right:1px solid #d2dee4;overflow:auto}.dialog-body>aside input{box-sizing:border-box;width:100%;padding:9px;border:1px solid #bdcdd5;border-radius:5px}.dialog-body>main{display:flex;flex-direction:column;min-width:0;min-height:0;background:white}.dialog-source-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 16px;border-bottom:1px solid #d8e1e5}.dialog-source-head span{overflow-wrap:anywhere}.dialog-code-lines{flex:1;overflow:auto;font:12px/1.55 Consolas,monospace;user-select:none}.dialog-empty{margin:auto;color:#748995}.code-dialog>footer{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;border-top:1px solid #d4dfe4}.code-dialog>footer button{background:#2c7182;color:white;border-color:#2c7182}@media(max-width:850px){.context-rail{max-width:48vw;min-width:260px}.dialog-body{grid-template-columns:240px 1fr}}
.device-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:9px;overflow:auto}.device-card{min-width:0;padding:8px;border:1px solid #cbd8de;border-radius:8px;background:#f7fafb;cursor:pointer}.device-card.selected{border-color:#2c7182;box-shadow:0 0 0 2px #2c718226}.device-card.offline{opacity:.65;cursor:default}.device-card>header{margin:0 0 7px}.device-card>header div{display:flex;min-width:0;flex-direction:column}.device-card>header strong{overflow:hidden;text-overflow:ellipsis}.device-card>header small,.device-card>header span{font-size:9px;color:#67808d}.device-card>header span{color:#216b7d}.device-card .device-screen{height:180px;min-height:0;flex:none}.device-screen.empty{flex:1}.device-card footer{margin-top:8px}.device-card footer span{min-width:0}
</style>
