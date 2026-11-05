<template>
  <component :is="admin ? 'section' : 'details'" class="model-settings" @toggle="onToggle">
    <summary v-if="!admin">选择模型 {{ selectedLabel }}</summary>
    <header v-else>
      <div><h2>OpenCode 模型服务</h2><p>密钥直接保存到这台机器上的 OpenCode，不写入项目文件。</p></div>
      <button :disabled="busy" @click="load">刷新状态</button>
    </header>
    <p v-if="!admin">选择管理控制台已配置的模型。连接状态不代表模型调用已经验证。</p>
    <p class="service-status" role="status">{{ status || '正在等待读取服务状态' }}</p>
    <label>模型供应商<select v-model="provider" @change="model = ''; emitChoice()"><option value="">使用 OpenCode 默认设置</option><option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}{{ p.connected ? '（已连接）' : '' }}</option></select></label>
    <label v-if="!admin && provider">模型<select v-model="model" @change="emitChoice"><option value="">请选择模型</option><option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }}</option></select></label>
    <form v-if="admin && provider" @submit.prevent="save">
      <div class="provider-state"><span :class="{ connected: selectedProvider?.connected }"></span>{{ selectedProvider?.connected ? '已保存认证' : '尚未连接' }}<small>{{ models.length }} 个可用模型</small></div>
      <label>API key<input v-model="key" type="password" autocomplete="new-password" spellcheck="false" placeholder="粘贴后保存；页面不会再次显示"></label>
      <button class="save-key" :disabled="busy || !key.trim()">{{ busy ? '正在配置…' : '保存并自动配置' }}</button>
      <p>保存后会自动刷新供应商和模型列表。平台不会在响应中返回密钥。</p>
      <div v-if="selectedProvider?.connected" class="connection-test">
        <label>连接测试模型<select v-model="model"><option value="">请选择一个模型</option><option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }}</option></select></label>
        <button type="button" :disabled="busy || !model" @click="testModel">{{ busy ? '正在验证…' : '验证模型连接' }}</button>
      </div>
    </form>
    <p v-else-if="admin">先选择模型供应商，再输入对应 API key。</p>
    <button v-if="!admin" :disabled="busy" @click="load">刷新连接状态</button>
  </component>
</template>
<script setup lang="ts">
import {ref,computed,onMounted} from 'vue'
import {authFetch} from '../utils/auth'
const props=defineProps<{apiBase:string;admin:boolean}>()
const emit=defineEmits<{change:[value:{providerID:string;modelID:string}|null]}>()
const providers=ref<any[]>([]),provider=ref(''),model=ref(''),key=ref(''),status=ref(''),busy=ref(false)
const models=computed(()=>providers.value.find(p=>p.id===provider.value)?.models || [])
const selectedProvider=computed(()=>providers.value.find(p=>p.id===provider.value))
const selectedLabel=computed(()=>model.value ? '· '+model.value : '')
function emitChoice(){emit('change',provider.value && model.value ? {providerID:provider.value,modelID:model.value}:null)}
async function load(){busy.value=true;try{const r=await authFetch(`${props.apiBase}/conversation-settings`);const d=await r.json();if(!r.ok)throw new Error(d.detail);providers.value=d.providers;status.value='已读取服务配置'}catch(e){status.value=String(e)}finally{busy.value=false}}
function onToggle(e:Event){if((e.target as HTMLDetailsElement).open && !providers.value.length)load();if(!(e.target as HTMLDetailsElement).open)key.value=''}
async function save(){busy.value=true;try{const value=key.value;key.value='';const r=await authFetch(`${props.apiBase}/conversation-settings/credentials`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:provider.value,api_key:value})});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'认证保存失败');await load();status.value=d.note}catch(e){status.value=String(e)}finally{busy.value=false}}
async function testModel(){busy.value=true;status.value='正在调用所选模型验证连接…';try{const r=await authFetch(`${props.apiBase}/conversation-settings/test`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:provider.value,model:model.value})});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'模型连接测试失败');status.value=d.note}catch(e){status.value=String(e)}finally{busy.value=false}}
onMounted(()=>{if(props.admin)load()})
</script>
<style scoped>
.model-settings{padding:10px 14px;border-top:1px solid #e0e7ed;font:12px 'Segoe UI','Microsoft YaHei',sans-serif;color:#526b7c}.model-settings summary{cursor:pointer}.model-settings header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;border-bottom:1px solid #dbe4e9;padding-bottom:20px;margin-bottom:22px}.model-settings h2{margin:0 0 7px;color:#263b4b;font-size:22px;font-weight:650}.model-settings header p{margin:0}.model-settings label{display:block;margin:10px 0}.model-settings select,.model-settings input{box-sizing:border-box;width:100%;padding:9px;border:1px solid #cdd9e1;border-radius:6px;background:white;color:#344b5d}.model-settings button{padding:7px 12px;background:#e7eff4;border:1px solid #cbd9e3;border-radius:6px;color:#345668;cursor:pointer}.model-settings button:disabled{opacity:.55;cursor:not-allowed}.model-settings p{font-size:11px;line-height:1.6}.model-settings[open]{max-height:340px;overflow:auto}.model-settings:not(details){max-width:720px;padding:0;border:0;font-size:13px}.model-settings:not(details) select,.model-settings:not(details) input{max-width:560px;margin-top:7px;padding:11px}.model-settings:not(details) form{margin-top:20px;padding:20px;border-left:3px solid #2c7182;background:#f2f6f8}.service-status{padding:10px 12px;background:#eef3f6;border-radius:6px}.provider-state{display:flex;align-items:center;gap:8px;margin-bottom:15px}.provider-state span{width:8px;height:8px;border-radius:50%;background:#9aa8b2}.provider-state span.connected{background:#268265}.provider-state small{margin-left:auto;color:#788a96}.save-key{margin-top:6px;background:#276d80!important;color:white!important;border-color:#276d80!important}
.connection-test{margin-top:22px;padding-top:18px;border-top:1px solid #d4e0e6}.connection-test button{background:#fff!important;color:#276d80!important;border-color:#83aab7!important}
</style>
