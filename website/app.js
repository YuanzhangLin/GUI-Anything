// A readable excerpt of the real Fast map. The JSON contains the full graph.
const positions = {
  MainActivity: [25, 195],
  ManageActivity: [220, 40],
  HistoryActivity: [220, 150],
  DetailStatFragement: [220, 270],
  DetailNoteFragment: [220, 375],
  EditActivity: [425, 40],
  HistoryDetailActivity: [425, 150],
};
const visibleRoutes = new Set([
  'MainActivity>ManageActivity',
  'MainActivity>HistoryActivity',
  'MainActivity>DetailStatFragement',
  'MainActivity>DetailNoteFragment',
  'ManageActivity>EditActivity',
  'HistoryActivity>HistoryDetailActivity',
]);
const ns = 'http://www.w3.org/2000/svg';
const inspector = document.getElementById('map-inspector');
const nodesRoot = document.getElementById('map-nodes');
const linesRoot = document.getElementById('map-lines');
let selected = null;

function shortId(id) { return id.split('.').pop(); }

function select(element, title, description, kind, evidence, elements = []) {
  if (selected) selected.classList.remove('selected');
  selected = element;
  element.classList.add('selected');
  inspector.replaceChildren();
  const kicker = document.createElement('span');
  kicker.className = 'inspector-kicker';
  kicker.textContent = kind === 'screen' ? 'SCREEN / 页面' : 'PATH / 操作路径';
  const heading = document.createElement('h3');
  heading.textContent = title;
  const paragraph = document.createElement('p');
  paragraph.textContent = description;
  const detail = document.createElement('div');
  detail.className = 'inspector-evidence';
  const detailLabel = document.createElement('span');
  detailLabel.textContent = 'SOURCE EVIDENCE / 代码依据';
  const detailValue = document.createElement('code');
  detailValue.textContent = evidence || '静态规则识别';
  detail.append(detailLabel, detailValue);
  inspector.append(kicker, heading, paragraph, detail);
  if (kind === 'screen') {
    const section = document.createElement('div');
    section.className = 'inspector-elements';
    const label = document.createElement('span');
    label.textContent = `UI ELEMENTS / 静态识别 ${elements.length} 个`;
    section.appendChild(label);
    const list = document.createElement('ul');
    for (const item of elements.slice(0, 8)) {
      const row = document.createElement('li');
      const name = document.createElement('strong');
      name.textContent = item.label;
      const type = document.createElement('small');
      type.textContent = `${item.type} · ${item.kind === 'display_element' ? '展示' : '可操作候选'}`;
      row.append(name, type);
      list.appendChild(row);
    }
    section.appendChild(list);
    if (elements.length > 8) {
      const more = document.createElement('small');
      more.textContent = `另有 ${elements.length - 8} 个元素，完整图数据中可查看。`;
      section.appendChild(more);
    }
    inspector.appendChild(section);
  }
}

function connect(from, to) {
  const [fx, fy] = positions[shortId(from)];
  const [tx, ty] = positions[shortId(to)];
  const x1 = fx + 145;
  const y1 = fy + 35;
  const x2 = tx;
  const y2 = ty + 35;
  const mid = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
}

async function renderMap() {
  try {
    const response = await fetch('./demo.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Demo map is unavailable');
    const graph = await response.json();
    const screens = new Map(graph.screens.map((screen) => [screen.id, screen]));
    const summary = document.getElementById('map-summary');
    const containments = graph.containments || [];
    summary.textContent = `${graph.screens.length} PAGES · ${graph.transitions.length} PATHS · ${containments.length} HOSTED`;

    const routeGroups = new Map();
    for (const edge of graph.transitions) {
      if (!visibleRoutes.has(`${shortId(edge.from)}>${shortId(edge.to)}`)) continue;
      if (!screens.has(edge.from) || !screens.has(edge.to)) continue;
      const key = `${edge.from}>${edge.to}`;
      if (!routeGroups.has(key)) routeGroups.set(key, []);
      routeGroups.get(key).push(edge);
    }
    for (const group of routeGroups.values()) {
      const edge = group[0];
      const pathData = connect(edge.from, edge.to);
      const path = document.createElementNS(ns, 'path');
      path.setAttribute('d', pathData);
      linesRoot.appendChild(path);
      const hit = document.createElementNS(ns, 'path');
      hit.setAttribute('d', pathData);
      hit.setAttribute('class', 'edge-hit');
      hit.setAttribute('role', 'button');
      hit.setAttribute('tabindex', '0');
      hit.setAttribute('aria-label', `${screens.get(edge.from).title}到${screens.get(edge.to).title}：${group.length}种操作`);
      const routeDetails = group.map((route, index) => {
        const evidence = route.evidence?.[0];
        const pointer = evidence?.file_path ? `${evidence.file_path}${evidence.line ? `:${evidence.line}` : ''}` : '无源码定位';
        const control = screens.get(route.from).elements?.find((item) => item.id === route.trigger_id);
        const trigger = route.trigger?.status === 'resolved'
          ? `触发：${control?.label || route.trigger?.label || route.trigger_id}`
          : route.trigger?.status === 'event_only'
            ? `触发动作：${route.trigger?.label || route.action}；具体控件未定位`
            : '触发方式尚未定位';
        return `${index + 1}. ${route.action}；${trigger}；依据 ${pointer}`;
      }).join('\n');
      const hosting = containments.find((item) => item.parent === edge.from && item.child === edge.to);
      const hostingText = hosting ? '两页之间同时存在承载关系：目标页是当前页中的标签或导航目的地。' : '';
      const action = () => select(path, `${screens.get(edge.from).title} → ${screens.get(edge.to).title}`, `${group.length} 种静态识别的操作路径。${hostingText}\n${routeDetails}\n尚未经运行时验证。`, 'path', '每种操作的依据见上方');
      hit.addEventListener('click', action);
      hit.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); }
      });
      linesRoot.appendChild(hit);
    }

    for (const screen of graph.screens) {
      const position = positions[shortId(screen.id)];
      if (!position) continue;
      const node = document.createElement('button');
      node.type = 'button';
      node.className = `map-node${screen.entry ? ' entry' : ''}`;
      node.style.left = `${position[0]}px`;
      node.style.top = `${position[1]}px`;
      const type = document.createElement('span');
      type.className = 'node-type';
      type.textContent = `${screen.entry ? 'ENTRY ' : ''}${screen.components?.[0]?.type?.toUpperCase() || 'PAGE'}`;
      const title = document.createElement('strong');
      title.textContent = screen.title;
      const detail = document.createElement('small');
      detail.textContent = shortId(screen.id);
      node.append(type, title, detail);
      node.addEventListener('click', () => {
        const hosted = containments.filter((item) => item.parent === screen.id).map((item) => screens.get(item.child)?.title).filter(Boolean);
        const parents = containments.filter((item) => item.child === screen.id).map((item) => screens.get(item.parent)?.title).filter(Boolean);
        const relationText = [hosted.length ? `承载页面：${hosted.join('、')}。` : '', parents.length ? `由 ${parents.join('、')} 承载。` : ''].join('');
        select(node, screen.title, `静态分析识别的候选页面。对应组件：${screen.components?.[0]?.type || '未知'} ${shortId(screen.id)}。${relationText}`, 'screen', screen.components?.[0]?.file_path, screen.elements || []);
      });
      nodesRoot.appendChild(node);
    }
  } catch (error) {
    inspector.querySelector('h3').textContent = '示例图暂时无法加载';
    inspector.querySelector('p').textContent = '请刷新页面重试，或到 GitHub 查看项目源码。';
  }
}

renderMap();
