<template>
  <aside ref="rail" class="context-rail" :style="railStyle">
    <div class="rail-resizer" aria-label="调节右侧栏宽度" @pointerdown="startWidthResize" />
    <section class="code-pane" :style="{height:`${codeHeight}px`}">
      <header><strong>项目代码</strong><button @click="loadFiles">刷新</button></header>
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
      <div class="device-screen">
        <img v-if="picture" :src="picture" alt="目标设备当前截图">
        <div v-else><strong>{{ loading ? '正在获取画面' : serial ? '等待设备画面' : '没有连接的设备' }}</strong><p>启动 Android 模拟器后点击「检测设备」。</p></div>
      </div>
      <footer><span>{{ activity || '尚未获取当前 App' }}<small v-if="serial">已作为默认对话上下文</small></span><button :disabled="!serial || loading" @click="preview">刷新画面</button></footer>
    </section>
  </aside>
</template>

<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {authFetch} from '../utils/auth'
import SourceTree from './SourceTree.vue'

const props=defineProps<{appId:string;apiBase:string}>()
const emit=defineEmits<{attach:[value:{path:string;text:string;appId:string}];target:[value:any];context:[value:any]}>()
const rail=ref<HTMLElement|null>(null)
const files=ref<string[]>([]),filter=ref(''),source=ref<any>(null),devices=ref<any[]>([]),serial=ref(''),picture=ref(''),activity=ref(''),error=ref(''),sourceError=ref(''),loading=ref(false)
const startLine=ref(1),endLine=ref(1)
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
let generation=0
async function get(path:string){const r=await authFetch(`${props.apiBase}/workbench${path}`);const data=await r.json();if(!r.ok)throw new Error(data.detail || '请求失败');return data}
async function loadFiles(){const app=props.appId;sourceError.value='';try{const data=await get(`/projects/${app}/files`);if(app===props.appId)files.value=data.files}catch(e){if(app===props.appId)sourceError.value=String(e)}}
async function openSource(path:string){const app=props.appId;try{const data=await get(`/projects/${app}/source?path=${encodeURIComponent(path)}`);if(app===props.appId){source.value=data;startLine.value=1;endLine.value=1}}catch(e){sourceError.value=String(e)}}
async function loadDevices(){error.value='';try{const data=await get('/devices');devices.value=data.devices;serial.value=devices.value.find(d=>d.serial===serial.value&&d.state==='device')?.serial||devices.value.find(d=>d.state==='device')?.serial||'';if(!data.available)error.value=data.reason;if(serial.value)await preview();else{picture.value='';activity.value='';publishDeviceContext()}}catch(e){error.value=String(e);publishDeviceContext()}}
async function preview(){const id=++generation;picture.value='';activity.value='';if(!serial.value){publishDeviceContext();return}loading.value=true;error.value='';try{const data=await get(`/devices/${encodeURIComponent(serial.value)}/preview`);if(id===generation){picture.value=`data:image/png;base64,${data.screenshot}`;activity.value=data.activity||'';publishDeviceContext()}}catch(e){if(id===generation){error.value=String(e);publishDeviceContext()}}finally{if(id===generation)loading.value=false}}
async function deviceChanged(){await preview();if(serial.value&&source.value)bindTarget()}

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
watch(()=>props.appId,()=>{source.value=null;files.value=[];loadFiles()})
</script>

<style scoped>
.context-rail{position:relative;flex:none;display:flex;flex-direction:column;height:100%;min-width:280px;max-width:min(720px,55vw);border-left:1px solid #cfd9df;background:#f1f5f7;color:#344b5c;font:12px 'Segoe UI','Microsoft YaHei',sans-serif}.rail-resizer{position:absolute;z-index:3;top:0;bottom:0;left:-5px;width:10px;cursor:col-resize}.rail-resizer:hover,.rail-resizer:active{background:rgba(44,113,130,.16)}.row-resizer{height:8px;flex:none;display:flex;align-items:center;justify-content:center;cursor:row-resize;border-top:1px solid #cfd9df;border-bottom:1px solid #cfd9df;background:#e5ecef}.row-resizer span{width:36px;height:2px;border-radius:2px;background:#8fa4b0}.row-resizer:hover{background:#d7e3e7}.code-pane,.device-pane{box-sizing:border-box;padding:14px 16px;min-height:0;overflow:auto}.code-pane{flex:none;min-height:180px}.context-rail header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.context-rail button{border:1px solid #c5d3dc;background:white;border-radius:5px;padding:5px 9px;color:#3f6072;cursor:pointer}.context-rail button:disabled{opacity:.45;cursor:default}.context-rail input,.context-rail select{width:100%;box-sizing:border-box;padding:8px;border:1px solid #c5d3dc;border-radius:5px;background:white;margin-bottom:8px}.context-rail summary{overflow-wrap:anywhere;cursor:pointer}.source-actions{position:sticky;top:-14px;z-index:2;display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0 0;padding:8px 0;background:#f1f5f7}.source-actions span{margin-right:auto;color:#526d7e}.source-actions .bind-button{background:#2c7182;color:white;border-color:#2c7182}.selection-help{margin:4px 0 8px;color:#718793;font-size:10px}.code-lines{overflow:auto;max-height:300px;border:1px solid #cbd7de;background:#fff;font:11px/1.55 Consolas,monospace;user-select:none}.code-line{display:grid;grid-template-columns:20px 42px minmax(0,1fr);min-height:18px;cursor:default}.code-line:hover{background:#edf5f7}.code-line.selected{background:#d8ebef}.line-check{display:flex;align-items:center;justify-content:center;color:#256b7d;background:#eef3f5}.line-number{padding:1px 7px;text-align:right;color:#82939d;border-right:1px solid #e0e7eb}.code-line code{padding:1px 8px;white-space:pre;overflow:visible;color:#263f4e}.device-pane{flex:1;min-height:220px;display:flex;flex-direction:column;background:#edf2f4}.device-screen{min-height:150px;flex:1;display:flex;justify-content:center;align-items:center;background:#dfe7eb;border:1px solid #d2dde3;border-radius:6px;overflow:hidden;text-align:center;color:#6c818e}.device-screen img{width:100%;height:100%;object-fit:contain}.device-screen p{font-size:11px;padding:0 20px}.device-pane footer{display:flex;align-items:center;gap:10px;margin-top:10px}.device-pane footer span{flex:1;display:flex;flex-direction:column;overflow-wrap:anywhere;font-size:10px}.device-pane footer small{margin-top:3px;color:#477486}.device-pane footer button{flex-shrink:0}[role=alert]{color:#a44332;font-size:11px}.code-pane :deep(.source-tree){max-height:180px}@media(max-width:850px){.context-rail{max-width:48vw;min-width:260px}}
</style>
