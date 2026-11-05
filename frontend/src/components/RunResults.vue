<template>
  <section aria-label="独立验证结果">
    <h4>目标代码覆盖</h4>
    <p>当前结论：{{ label(run.results.coverage) }}</p>
    <p v-if="run.results.coverage === 'stale'" role="alert">报告之后执行过新动作，下表仅保留历史证据，不能作为当前成功结论。</p>
    <template v-if="run.coverage_verdict">
      <p>通过条件：所选范围内每个可执行行均从基线未命中变为执行后命中。分支数展示覆盖数量变化，不代表所有分支均已覆盖。</p>
      <div class="table-scroll"><table>
        <thead><tr><th>源码行</th><th>基线已覆盖指令</th><th>执行后已覆盖指令</th><th>覆盖分支数变化</th><th>新增行命中</th></tr></thead>
        <tbody><tr v-for="row in run.coverage_verdict.lines" :key="row.line">
          <td><button @click="$emit('source', { path: run.target.path, line: row.line })">{{ row.line }}</button></td>
          <td>{{ row.before.ci }}</td><td>{{ row.after.ci }}</td><td>{{ row.before.cb }} → {{ row.after.cb }}</td><td>{{ row.newly_hit ? '是' : '否' }}</td>
        </tr></tbody>
      </table></div>
    </template>
    <h4>业务与页面断言</h4>
    <p v-if="!run.assertions?.length">尚无断言验证记录；任务描述不会自动变成验证通过。</p>
    <article v-for="result in run.assertions || []" :key="result.condition">
      <strong>{{ result.description }}</strong><p>{{ label(run.condition_results?.find((c: any) => c.condition === result.condition)?.status || result.status) }}</p>
      <p v-if="result.reason">{{ result.reason }}</p>
      <p v-if="result.expected_count !== undefined">匹配控件：预期 {{ result.expected_count }}，实际 {{ result.actual_count }}</p>
      <template v-if="result.expected_rows"><p>预期数据</p><pre>{{ JSON.stringify(result.expected_rows, null, 2) }}</pre><p>实际数据</p><pre>{{ JSON.stringify(result.actual_rows, null, 2) }}</pre></template>
    </article>
    <details v-if="run.coverage_verdict || run.assertions?.length"><summary>原始验证数据</summary><pre>{{ JSON.stringify({coverage: run.coverage_verdict, assertions: run.assertions}, null, 2) }}</pre></details>
  </section>
</template>
<script setup lang="ts">
defineProps<{ run: any }>()
defineEmits<{ source: [reference: { path: string; line: number }] }>()
function label(status: string) {
  return ({passed:'通过',failed:'未通过',not_checked:'未检查',stale:'已过期',error:'验证出错'} as Record<string,string>)[status] || status
}
</script>
<style scoped>
.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:7px;border:1px solid #dbe2ea;text-align:left}th{background:#f1f5f9}pre{overflow:auto;font-size:12px}article{padding:10px 0;border-bottom:1px solid #e2e8f0}[role=alert]{color:#b42318}button{cursor:pointer;text-decoration:underline;color:#047857;border:0;background:transparent}
</style>
