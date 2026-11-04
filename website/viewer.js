(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const svgNS = 'http://www.w3.org/2000/svg';
  const statuses = { unreviewed: '待校验', confirmed: '已确认', questionable: '有疑问', incorrect: '错误' };
  let graph = null;
  let screens = new Map();
  let reviews = {};
  let storageKey = '';
  let mapFingerprint = '';
  let selected = null;
  let runtimeTrace = null;

  function node(tag, className, content) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }
  function svg(tag, attributes = {}) {
    const element = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    return element;
  }
  function shortId(id) { return String(id || '').split('.').pop(); }
  function evidenceText(item) {
    if (!item) return '无源码定位';
    return [item.file_path || '无源码定位', item.line ? `:${item.line}` : '', item.method ? ` · ${item.method}` : ''].join('');
  }
  function reviewKey(edge) { return edge.id || `${edge.from}:${edge.to}:${edge.action}`; }
  function fingerprint(data) {
    const content = JSON.stringify(data);
    let hash = 2166136261;
    for (let index = 0; index < content.length; index++) {
      hash ^= content.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, '0');
  }
  function saveReview() {
    try { localStorage.setItem(storageKey, JSON.stringify(reviews)); }
    catch (_) { /* Export remains available if storage is disabled. */ }
    renderRoutes();
  }
  function loadReview() {
    mapFingerprint = fingerprint(graph);
    storageKey = `gui-anything-review:${mapFingerprint}`;
    try { reviews = JSON.parse(localStorage.getItem(storageKey) || '{}'); }
    catch (_) { reviews = {}; }
  }
  function appendEvidence(parent, evidence) {
    for (const item of evidence || []) {
      const row = node('div', 'evidence');
      row.append(node('strong', '', evidenceText(item)));
      parent.append(row);
    }
  }
  function selectScreen(screen) {
    selected = { kind: 'screen', id: screen.id };
    markSelection();
    const inspector = $('inspector');
    inspector.replaceChildren(node('span', 'eyebrow', 'SCREEN / 页面候选'), node('h2', '', screen.title || shortId(screen.id)));
    inspector.append(node('p', '', `${screen.kind === 'screen_candidate' ? '静态识别的候选页面' : '页面'} · ${screen.entry ? '应用入口 · ' : ''}${screen.components?.[0]?.type || '未知组件'} ${shortId(screen.id)}`));
    const hosted = (graph.containments || []).filter((item) => item.parent === screen.id);
    const parents = (graph.containments || []).filter((item) => item.child === screen.id);
    if (hosted.length || parents.length) {
      inspector.append(node('h3', '', '页面包含关系'));
      const list = node('ul');
      hosted.forEach((item) => list.append(node('li', '', `承载 ${screens.get(item.child)?.title || shortId(item.child)} · ${item.kind}`)));
      parents.forEach((item) => list.append(node('li', '', `由 ${screens.get(item.parent)?.title || shortId(item.parent)} 承载 · ${item.kind}`)));
      inspector.append(list);
    }
    inspector.append(node('h3', '', '代码出处'));
    appendEvidence(inspector, [{ file_path: screen.components?.[0]?.file_path || '无源码定位' }]);
    const elements = screen.elements || [];
    inspector.append(node('h3', '', `静态识别元素 · ${elements.length}`));
    const list = node('ul');
    for (const item of elements) {
      const source = item.evidence?.file_path ? ` · ${evidenceText(item.evidence)}` : '';
      list.append(node('li', '', `${item.label || item.id} (${item.kind || item.type || 'unknown'})${source}`));
    }
    inspector.append(list);
    if (runtimeTrace?.start?.screen === screen.id && runtimeTrace.start.screenshot_data) {
      inspector.append(node('h3', '', '运行开始时的界面'));
      const shot = node('img', 'runtime-shot');
      shot.src = runtimeTrace.start.screenshot_data;
      shot.alt = '运行开始时的界面截图';
      inspector.append(shot);
    }
  }
  function selectRoute(edge) {
    selected = { kind: 'route', id: reviewKey(edge) };
    markSelection();
    const inspector = $('inspector');
    const from = screens.get(edge.from)?.title || shortId(edge.from);
    const to = screens.get(edge.to)?.title || shortId(edge.to);
    inspector.replaceChildren(node('span', 'eyebrow', 'PATH / 操作路径'), node('h2', '', `${from} → ${to}`));
    inspector.append(node('p', '', edge.action || '跳转'));
    const trigger = edge.trigger || {};
    const control = screens.get(edge.from)?.elements?.find((item) => item.id === edge.trigger_id);
    const triggerLabel = trigger.status === 'resolved'
      ? `${trigger.label || control?.label || edge.trigger_id} · 已定位静态触发点`
      : trigger.status === 'event_only'
        ? `${trigger.label || trigger.event || '事件'} · 具体控件未定位`
        : '尚未定位触发方式';
    inspector.append(node('h3', '', '怎么跳转'), node('p', '', triggerLabel));
    inspector.append(node('h3', '', '代码依据'));
    appendEvidence(inspector, edge.evidence);
    inspector.append(node('p', '', `${edge.verification || '未校验'} · 静态分析推断，仍需实际运行或人工核对。`));
    const runtimeSteps = (runtimeTrace?.steps || []).filter((step) => step.edge_id === reviewKey(edge));
    if (runtimeSteps.length) {
      inspector.append(node('h3', '', `运行时观察 · ${runtimeSteps.length} 次`));
      for (const step of runtimeSteps) {
        const observed = step.after?.screen || step.before?.screen || '无法识别';
        const detail = `${step.status} · 实际页面 ${shortId(observed)}${step.reason ? ` · ${step.reason}` : ''}${step.after?.hierarchy ? ` · 界面记录 ${step.after.hierarchy}` : ''}${step.after?.screenshot ? ` · 截图 ${step.after.screenshot}` : ''}`;
        inspector.append(node('div', `runtime-note ${step.status}`, detail));
        const screenshot = step.after?.screenshot_data || step.before?.screenshot_data;
        if (screenshot) {
          const shot = node('img', 'runtime-shot');
          shot.src = screenshot;
          shot.alt = `第 ${step.index} 步${step.after?.screenshot_data ? '执行后' : '执行前'}的界面截图`;
          inspector.append(shot);
        }
      }
    }
    const key = reviewKey(edge);
    const review = reviews[key] || {};
    inspector.append(node('h3', '', '人工校验'));
    const actions = node('div', 'review-actions');
    for (const status of Object.keys(statuses)) {
      const button = node('button', review.status === status ? 'active' : '', statuses[status]);
      button.type = 'button';
      button.addEventListener('click', () => {
        reviews[key] = { ...reviews[key], status, updated_at: new Date().toISOString() };
        saveReview();
        selectRoute(edge);
      });
      actions.append(button);
    }
    inspector.append(actions);
    const note = node('textarea', 'review-note');
    note.placeholder = '记录运行时检查结果或疑问…';
    note.value = review.note || '';
    note.setAttribute('aria-label', '校验备注');
    note.addEventListener('change', () => {
      reviews[key] = { ...reviews[key], note: note.value, updated_at: new Date().toISOString() };
      saveReview();
    });
    inspector.append(note);
  }
  function markSelection() {
    for (const item of document.querySelectorAll('.node, .edge')) item.classList.remove('selected');
    if (!selected) return;
    for (const item of document.querySelectorAll(`[data-${selected.kind}-id]`)) {
      if (item.getAttribute(`data-${selected.kind}-id`) === selected.id) item.classList.add('selected');
    }
  }
  function layout() {
    if (!graph.screens.length) return { positions: new Map(), width: 900, height: 540 };
    const depth = new Map();
    const entry = graph.screens.filter((screen) => screen.entry).map((screen) => screen.id);
    const queue = entry.length ? [...entry] : [graph.screens[0].id];
    queue.forEach((id) => depth.set(id, 0));
    for (let index = 0; index < queue.length; index++) {
      const id = queue[index];
      const outgoing = graph.transitions.filter((edge) => edge.from === id).map((edge) => edge.to);
      for (const target of outgoing) if (!depth.has(target)) { depth.set(target, Math.min((depth.get(id) || 0) + 1, 4)); queue.push(target); }
    }
    graph.screens.forEach((screen) => { if (!depth.has(screen.id)) depth.set(screen.id, 4); });
    const columns = new Map();
    for (const screen of graph.screens) {
      const column = depth.get(screen.id);
      if (!columns.has(column)) columns.set(column, []);
      columns.get(column).push(screen);
    }
    const positions = new Map();
    for (const [column, items] of columns) items.forEach((screen, row) => positions.set(screen.id, { x: 35 + column * 250, y: 35 + row * 108 }));
    return { positions, width: Math.max(900, (Math.max(...columns.keys()) + 1) * 250 + 35), height: Math.max(540, ...[...columns.values()].map((items) => items.length * 108 + 60)) };
  }
  function renderGraph() {
    const root = $('map-svg');
    root.replaceChildren();
    const { positions, width, height } = layout();
    root.setAttribute('width', width);
    root.setAttribute('height', height);
    root.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const groups = new Map();
    for (const edge of graph.transitions) {
      const key = `${edge.from}>${edge.to}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(edge);
    }
    for (const edges of groups.values()) {
      const edge = edges[0];
      const a = positions.get(edge.from), b = positions.get(edge.to);
      if (!a || !b) continue;
      const sameColumn = a.x === b.x;
      const x1 = sameColumn ? a.x + 90 : a.x + 180;
      const y1 = a.y + 35;
      const x2 = sameColumn ? b.x + 90 : b.x;
      const y2 = b.y + 35;
      const d = sameColumn ? `M${x1} ${y1} C${x1 + 95} ${y1},${x2 + 95} ${y2},${x2} ${y2}`
        : `M${x1} ${y1} C${(x1 + x2) / 2} ${y1},${(x1 + x2) / 2} ${y2},${x2} ${y2}`;
      const runtime = (runtimeTrace?.steps || []).filter((step) => edges.some((item) => reviewKey(item) === step.edge_id));
      const runtimeClass = runtime.some((step) => step.status === 'mismatch') ? ' mismatch'
        : runtime.some((step) => step.status === 'verified') ? ' verified' : '';
      const path = svg('path', { d, class: `edge${runtimeClass}`, 'data-route-id': reviewKey(edge) });
      const hit = svg('path', { d, class: 'edge-hit', tabindex: 0, role: 'button', 'aria-label': `${screens.get(edge.from)?.title} 到 ${screens.get(edge.to)?.title}，${edges.length} 种操作` });
      const open = () => {
        if (edges.length === 1) return selectRoute(edge);
        const inspector = $('inspector');
        inspector.replaceChildren(node('span', 'eyebrow', 'MULTIPLE PATHS / 多种操作'), node('h2', '', `${screens.get(edge.from)?.title} → ${screens.get(edge.to)?.title}`), node('p', '', '这两个页面间有多种静态识别的操作。请选择一条逐项校验。'));
        edges.forEach((item) => {
          const button = node('button', 'route-row', `${item.action} · ${item.trigger?.label || '触发未定位'}`);
          button.type = 'button';
          button.addEventListener('click', () => selectRoute(item));
          inspector.append(button);
        });
      };
      hit.addEventListener('click', open);
      hit.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } });
      root.append(path, hit);
    }
    for (const screen of graph.screens) {
      const { x, y } = positions.get(screen.id);
      const group = svg('g', { class: `node${screen.entry ? ' entry' : ''}`, 'data-screen-id': screen.id, tabindex: 0, role: 'button', 'aria-label': screen.title });
      group.append(svg('rect', { x, y, width: 180, height: 70, rx: 9 }));
      const kind = svg('text', { x: x + 12, y: y + 18, class: 'kind' }); kind.textContent = screen.components?.[0]?.type?.toUpperCase() || 'PAGE';
      const title = svg('text', { x: x + 12, y: y + 40, class: 'title' }); title.textContent = String(screen.title || shortId(screen.id)).slice(0, 22);
      const id = svg('text', { x: x + 12, y: y + 58, class: 'id' }); id.textContent = shortId(screen.id).slice(0, 26);
      group.append(kind, title, id);
      group.addEventListener('click', () => selectScreen(screen));
      group.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectScreen(screen); } });
      root.append(group);
    }
  }
  function renderRoutes() {
    const list = $('route-list');
    list.replaceChildren();
    const query = $('route-search').value.trim().toLowerCase();
    const filter = $('route-filter').value;
    for (const edge of graph.transitions) {
      const review = reviews[reviewKey(edge)] || {};
      const status = review.status || 'unreviewed';
      if (filter !== 'all' && filter !== status) continue;
      const label = `${screens.get(edge.from)?.title || shortId(edge.from)} → ${screens.get(edge.to)?.title || shortId(edge.to)}`;
      const searchable = `${label} ${edge.action} ${edge.trigger?.label || ''} ${(edge.evidence || []).map(evidenceText).join(' ')}`.toLowerCase();
      if (query && !searchable.includes(query)) continue;
      const button = node('button', 'route-row'); button.type = 'button';
      const text = node('span'); text.append(node('strong', '', label), node('small', '', edge.action || '跳转'));
      const runtime = (runtimeTrace?.steps || []).filter((step) => step.edge_id === reviewKey(edge));
      const runtimeLabel = runtime.some((step) => step.status === 'mismatch') ? '运行偏差'
        : runtime.some((step) => step.status === 'verified') ? '运行已验证' : '';
      const kind = node('span', 'path-kind', runtimeLabel || (edge.trigger?.status === 'resolved' ? '已定位触发点' : edge.trigger?.status === 'event_only' ? '只定位事件' : '触发未知'));
      const badge = node('span', `status ${status}`, statuses[status]);
      button.append(text, kind, badge);
      button.addEventListener('click', () => { selectRoute(edge); $('inspector').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
      list.append(button);
    }
    if (!list.children.length) list.append(node('p', '', '没有匹配的操作路径。'));
  }
  function loadMap(data) {
    if (!data || data.schema_version !== 2 || !Array.isArray(data.screens) || !Array.isArray(data.transitions)) throw new Error('需要 schema_version=2 且包含 screens、transitions 的 Map JSON');
    graph = data;
    runtimeTrace = null;
    $('trace-summary').hidden = true;
    screens = new Map(graph.screens.map((screen) => [screen.id, screen]));
    loadReview();
    $('project-title').textContent = graph.project_name || 'Android UI Map';
    $('map-meta').textContent = `${graph.source || 'unknown'} · ${graph.mode || 'unknown'} · ${graph.source_commit ? `commit ${graph.source_commit} · ` : ''}静态分析结果，校验记录单独保存`;
    $('map-counts').replaceChildren(...[[graph.screens.length, '页面'], [graph.transitions.length, '路径'], [(graph.containments || []).length, '包含关系']].map(([count, label]) => node('span', '', `${count} ${label}`)));
    $('load-error').hidden = true;
    $('workspace').hidden = false;
    $('route-card').hidden = false;
    $('export-review').disabled = false;
    selected = null;
    renderGraph();
    renderRoutes();
    if (graph.screens.length) selectScreen(graph.screens.find((screen) => screen.entry) || graph.screens[0]);
  }
  function showError(error) { $('load-error').textContent = `地图载入失败：${error.message || error}`; $('load-error').hidden = false; }
  function loadTrace(data) {
    if (!graph) throw new Error('请先载入 Map');
    if (data.schema_version !== 1 || !Array.isArray(data.steps)) throw new Error('需要包含 steps 的运行轨迹 JSON');
    if (data.project_name !== graph.project_name) throw new Error('运行轨迹与当前 Map 的项目名称不一致');
    if (data.source_commit && graph.source_commit && data.source_commit !== graph.source_commit) throw new Error('运行轨迹与当前 Map 的源码版本不一致');
    const ids = new Set(graph.transitions.map(reviewKey));
    if (data.steps.some((step) => !ids.has(step.edge_id))) throw new Error('运行轨迹包含当前 Map 中不存在的路径');
    runtimeTrace = data;
    const summary = $('trace-summary');
    const verified = data.steps.filter((step) => step.status === 'verified').length;
    const mismatches = data.steps.filter((step) => step.status === 'mismatch').length;
    summary.textContent = `运行轨迹：${data.status || '未知'} · ${verified} 步已验证 · ${mismatches} 步偏差${data.reason ? ` · ${data.reason}` : ''}`;
    summary.classList.toggle('mismatch', !!mismatches || data.status === 'needs_review' || data.status === 'error');
    summary.hidden = false;
    $('load-error').hidden = true;
    renderGraph();
    renderRoutes();
    if (selected?.kind === 'route') {
      const edge = graph.transitions.find((item) => reviewKey(item) === selected.id);
      if (edge) selectRoute(edge);
    }
  }
  $('map-file').addEventListener('change', async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try { loadMap(JSON.parse(await file.text())); }
    catch (error) { showError(error); }
  });
  $('trace-file').addEventListener('change', async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try { loadTrace(JSON.parse(await file.text())); }
    catch (error) { showError(error); }
  });
  $('route-search').addEventListener('input', () => { if (graph) renderRoutes(); });
  $('route-filter').addEventListener('change', () => { if (graph) renderRoutes(); });
  $('export-review').addEventListener('click', () => {
    if (!graph) return;
    const data = { schema_version: 1, project_name: graph.project_name || '', source_commit: graph.source_commit || null, map_fingerprint: mapFingerprint, exported_at: new Date().toISOString(), reviews };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2) + '\n'], { type: 'application/json' }));
    const link = node('a'); link.href = url; link.download = `${(graph.project_name || 'map').replace(/[^a-z0-9_-]/gi, '_')}-review.json`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  (async () => {
    try {
      const embedded = $('embedded-map').textContent.trim();
      if (embedded) {
        loadMap(JSON.parse(embedded));
        const embeddedTrace = $('embedded-trace').textContent.trim();
        if (embeddedTrace) loadTrace(JSON.parse(embeddedTrace));
        return;
      }
      const params = new URLSearchParams(location.search);
      const source = params.get('map') || './demo.json';
      const response = await fetch(source, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      loadMap(await response.json());
      const traceSource = params.get('trace');
      if (traceSource) {
        const traceResponse = await fetch(traceSource, { cache: 'no-store' });
        if (!traceResponse.ok) throw new Error(`Trace HTTP ${traceResponse.status}`);
        loadTrace(await traceResponse.json());
      }
    } catch (error) { showError(error); }
  })();
})();
