/* The authored copy is Chinese. English is the default; both views use the same map data. */
(() => {
  'use strict';
  const copy = {
    'GUI-Anything 将 Android 应用的页面与操作路径整理成可追溯的地图。': 'GUI-Anything turns Android screens and user paths into a traceable map.',
    '跳到正文': 'Skip to content', 'GUI-Anything 首页': 'GUI-Anything home', '主导航': 'Main navigation',
    '交互示例': 'Interactive demo', '地图校验器': 'Map reviewer', '覆盖案例': 'Coverage case', '工作方式': 'How it works',
    '看懂一个 App，': 'Understand an app,', '先看它的路径。': 'start with its paths.',
    '把 Android 应用里的页面、跳转和操作线索整理成一张图。用 Map 规划路径，执行时逐步核对界面；遇到疑点，就回到 Activity、Fragment 和源码查证。': 'Turn Android screens, transitions, and action clues into a map. Plan with the map, check the live UI step by step, and trace uncertain paths back to Activities, Fragments, and source code.',
    '打开地图校验器': 'Open map reviewer', '查看源代码': 'View source code', '兼容 Agent': 'Agent compatible',
    'Fast 出图无需模型': 'Fast mapping without a model', '独立网页校验': 'Standalone review page',
    '首页': 'Home', '操作': 'Action', '目标页': 'Destination',
    'LIVE EXAMPLE / 只含图谱': 'LIVE EXAMPLE / MAP ONLY', '点开一条路径，看看依据。': 'Open a path. Inspect the evidence.',
    '基于 Activity Diary 源码的真实 Fast 结果。下方选取其中几条路径展示；网站不提供源码副本或对话记录。': 'A real Fast result from Activity Diary source. This excerpt shows selected paths; the site does not publish a source copy or conversations.',
    '可交互的应用页面地图': 'Interactive app screen map', '页面之间的操作路径': 'Actions between screens',
    '从首页开始': 'Start at the home screen', '点击页面或连接线，查看 Fast 从哪一处源码识别出它。': 'Select a screen or connection to see where Fast found it in the source.',
    '图谱来源': 'Map source', '真实源码扫描': 'Real source scan', '起始页面': 'Entry screen',
    '展示部分路径 · 静态证据，未经运行时验证': 'Selected paths · static evidence, not verified at runtime',
    'INSTRUMENTED CASE / AGENT 辅助实验': 'INSTRUMENTED CASE / AGENT-ASSISTED EXPERIMENT',
    '操作之后，目标代码真的执行了吗？': 'Did the target code actually run?',
    'OmniNotes 6.1.0 · Android API 25。一次本地实验，分别检查 JaCoCo 新增覆盖与数据库中的实际结果。': 'OmniNotes 6.1.0 · Android API 25. One local experiment checks new JaCoCo coverage and the actual database result.',
    'App：OmniNotes 6.1.0': 'App: OmniNotes 6.1.0', '包名：': 'Package: ', '· Android API 25 · 插装 APK': '· Android API 25 · instrumented APK',
    '01 / 对应代码': '01 / TARGET CODE', '保存合并结果后，删除原笔记': 'Delete original notes after saving the merge',
    '· 第 1627–1637 行': '· lines 1627–1637',
    'OmniNotes 代码节选 · © 2013–2020 Federico Iosue · GPL-3.0-or-later。行号对应本次测试源码。': 'OmniNotes code excerpt · © 2013–2020 Federico Iosue · GPL-3.0-or-later. Line numbers refer to the source used in this test.',
    '02 / 代码分析 → TASK': '02 / CODE ANALYSIS → TASK', '为什么要“多选 → 合并 → 保存”？': 'Why select → merge → save?',
    '发布': 'emits', '；事件处理器将选中笔记 ID 写入': '; the event handler writes the selected note IDs to',
    '，然后打开合并编辑页。保存后的': ', then opens the merge editor. After saving,',
    '才会调用上面的删除方法。普通保存传入空列表引用，不会命中循环体。': 'calls the deletion method above. An ordinary save passes a null list and does not enter the loop.',
    '创建两条可区分的测试笔记，选中并合并，保存合并笔记，使两条原记录被删除。确认新笔记保留两段正文，并通过 JaCoCo 验证循环体和删除调用新增覆盖。只操作本次创建的测试笔记；预算 60 次 UI 操作、30 分钟。': 'Create two distinct test notes, select and merge them, then save the merged note so both originals are deleted. Confirm the new note contains both bodies and use JaCoCo to verify new coverage of the loop and deletion call. Touch only notes created for this test; budget: 60 UI actions and 30 minutes.',
    '以上为执行前冻结任务的中文整理，不是运行器自动生成的原始输出。': 'This is an edited summary of the task frozen before execution, not raw runner output.',
    '03 / 实际执行步骤': '03 / EXECUTION STEPS', '从准备数据到保存结果': 'From test data to saved result',
    '动作': 'Step', '执行内容': 'Action', '观察 / 检查': 'Observation / check',
    '启动 OmniNotes': 'Launch OmniNotes', '进入 Notes 列表': 'Open the Notes list',
    '新建 GUIA_Merge_A；填写正文 GUIA alpha merge payload；返回收起键盘，再返回保存': 'Create GUIA_Merge_A; enter GUIA alpha merge payload; Back to dismiss the keyboard, then Back to save',
    '列表出现 A': 'A appears in the list', '同样新建 GUIA_Merge_B，正文为 GUIA beta merge payload': 'Likewise create GUIA_Merge_B with body GUIA beta merge payload',
    '列表出现 A、B': 'A and B appear in the list', '基线': 'Baseline', '采集 JaCoCo，重置探针；不计 UI 动作': 'Collect JaCoCo data and reset probes; not counted as UI actions',
    '五条目标行覆盖指令均为 0': 'Zero covered instructions on all five target lines',
    '长按 A 所在列表行': 'Long-press row A', '进入多选，已选 1 条': 'Selection mode, one item selected',
    '点击 B 所在列表行': 'Tap row B', '已选 2 条': 'Two items selected',
    '打开多选栏的 More options': 'Open More options in the selection bar',
    '限定 action_mode_bar，排除普通工具栏的同名菜单': 'Target action_mode_bar, excluding the identically named menu in the normal toolbar',
    '点击 Merge': 'Tap Merge', '编辑页展示 A、B 两段正文': 'The editor shows both A and B bodies',
    '按返回，保存合并笔记': 'Press Back to save the merged note', '列表只剩一条合并笔记': 'Only one merged note remains',
    '验证': 'Verify', '再次采集 JaCoCo，读取数据库': 'Collect JaCoCo data again and inspect the database',
    '检查新增覆盖、原 ID 删除和正文持久化': 'Check new coverage, deletion of original IDs, and persisted text',
    '04 / 覆盖与业务结果': '04 / COVERAGE AND APP RESULT', '5 / 5 目标行新增命中': '5 / 5 target lines newly covered',
    '的循环体与删除调用：1630、1631、1632、1633、1635 行，操作前覆盖指令为 0，操作后全部命中。': ' loop and deletion call: lines 1630, 1631, 1632, 1633, and 1635 had zero covered instructions before the operation and were all hit afterward.',
    '方法覆盖：9/9 行 · 35/35 条指令 · 3/4 分支。普通保存也会调用该方法，所以单看方法覆盖不足以判定成功。': 'Method coverage: 9/9 lines · 35/35 instructions · 3/4 branches. Ordinary saving also calls this method, so method coverage alone cannot prove success.',
    '两条原记录 → 一条合并记录': 'Two originals → one merged record',
    '数据库验证两条原笔记 ID 已删除，新笔记同时保留两段正文，无关记录未变。': 'The database confirms both original note IDs were deleted, the new note retains both bodies, and unrelated records were unchanged.',
    '含数据准备共 20 次 UI 操作，预算为 60 次。APK 哈希一致，JaCoCo 未报告 class 不匹配；每次采集重置探针后比较新增覆盖。': 'Including data setup, the run used 20 UI actions out of a budget of 60. The APK hash matched, JaCoCo reported no class mismatch, and probes were reset between coverage captures.',
    '能力边界：由 Agent 阅读源码、观察实时 UI，并使用本地 ADB 脚本执行。此案例不是现有导航器的端到端自动化基准，也不代表成功率或全分支覆盖。仅发布整理后的说明，原始实验数据、截图、APK、数据库及执行脚本不上传。': 'Scope: an Agent read source, observed the live UI, and executed local ADB scripts. This case is not an end-to-end benchmark of the current navigator and does not establish a success rate or full branch coverage. Only this edited account is published; raw data, screenshots, APKs, databases, and execution scripts are not uploaded.',
    '两种速度，同一张图。': 'Two speeds. One map.', '给它一个应用': 'Provide an app',
    '从 Android 源码仓库开始，或导入 APK 并在后端反编译。': 'Start with an Android source repository, or import an APK for backend decompilation.',
    '先看到路径': 'See the paths first', '无需模型，提取候选页面与显式跳转。只想要图，就停在这里。': 'Extract candidate screens and explicit transitions without a model. Stop here if you only need the map.',
    '边走边看': 'Observe as you go', '在连接的 Android 设备上逐步观察与核对；把实际轨迹载入校验器，对照 Map 和源码依据。': 'Observe and verify each step on a connected Android device. Load the trace into the reviewer to compare it with the map and source evidence.',
    '让代码里的界面，': 'Turn interfaces in code', '变成能讨论的路径。': 'into paths you can discuss.', '在 GitHub 查看项目': 'View on GitHub',
    '载入 Map JSON': 'Load Map JSON', '载入运行轨迹': 'Load runtime trace', '导出校验记录': 'Export reviews',
    '正在加载地图': 'Loading map', '可导入本地 JSON，或通过 URL 的 ?map= 参数自动载入。': 'Import local JSON or load a hosted map with the ?map= URL parameter.',
    '页面和操作路径地图': 'Screen and action path map', '页面地图': 'Screen map', '点击页面或路径查看依据': 'Select a screen or path to inspect evidence',
    '静态分析 · 待人工核对': 'Static analysis · awaiting human review', '页面关系图': 'Screen relationship graph',
    'INSPECTOR / 依据': 'INSPECTOR / EVIDENCE', '选择页面或路径': 'Select a screen or path',
    '逐条检查触发方式和源码出处。校验记录保存在当前浏览器，并可导出 JSON。': 'Inspect triggers and source locations one path at a time. Reviews stay in this browser and can be exported as JSON.',
    'PATHS / 操作路径': 'PATHS / ACTIONS', '逐条校验': 'Review each path',
    '搜索页面、动作、源码…': 'Search screens, actions, source…', '搜索路径': 'Search paths', '筛选校验状态': 'Filter review status',
    '全部路径': 'All paths', '待校验': 'Unreviewed', '已确认': 'Confirmed', '有疑问': 'Questionable', '错误': 'Incorrect',
    '无源码定位': 'No source location', 'SCREEN / 页面候选': 'SCREEN / CANDIDATE', '静态识别的候选页面': 'Statically identified candidate screen',
    '页面': 'Screen', '应用入口 · ': 'App entry · ', '未知组件': 'Unknown component', '页面包含关系': 'Screen containment',
    '代码出处': 'Source location', '运行开始时的界面': 'Screen at run start', '运行开始时的界面截图': 'Screenshot at run start',
    'PATH / 操作路径': 'PATH / ACTION', '跳转': 'Transition', '事件': 'Event', '尚未定位触发方式': 'Trigger not located',
    '怎么跳转': 'How it transitions', '代码依据': 'Source evidence', '未校验': 'Unverified', '无法识别': 'Unrecognized',
    '展开菜单 / 准备操作': 'Open menu / prepare action', '页面跳转': 'Screen transition', '人工校验': 'Human review',
    '记录运行时检查结果或疑问…': 'Record runtime checks or questions…', '校验备注': 'Review note',
    'MULTIPLE PATHS / 多种操作': 'MULTIPLE PATHS / ACTIONS', '这两个页面间有多种静态识别的操作。请选择一条逐项校验。': 'Multiple actions were identified between these screens. Choose one to review.',
    '触发未定位': 'Trigger not located', '运行偏差': 'Runtime mismatch', '运行已验证': 'Verified at runtime',
    '已定位触发点': 'Trigger located', '只定位事件': 'Event only', '触发未知': 'Unknown trigger',
    '没有匹配的操作路径。': 'No matching paths.', '静态分析结果，校验记录单独保存': 'Static analysis; reviews are saved separately',
    '路径': 'Paths', '包含关系': 'Containments', '请先载入 Map': 'Load a map first', '未知': 'Unknown',
    'SCREEN / 页面': 'SCREEN', 'SOURCE EVIDENCE / 代码依据': 'SOURCE EVIDENCE',
    '每种操作的依据见上方': 'Evidence for each action appears above',
    '示例图暂时无法加载': 'Demo map is temporarily unavailable', '请刷新页面重试，或到 GitHub 查看项目源码。': 'Refresh and try again, or view the source on GitHub.',
  };
  const patterns = [
    [/^(\d+) 种静态识别的操作路径。/, (_, n) => `${n} statically identified action ${n === '1' ? 'path' : 'paths'}. `],
    [/^(\d+) 页面$/, (_, n) => `${n} screens`],
    [/^(\d+) 路径$/, (_, n) => `${n} paths`],
    [/^(\d+) 包含关系$/, (_, n) => `${n} containments`],
    [/^(.+)到(.+)：(\d+)种操作$/, (_, from, to, n) => `${from} to ${to}: ${n} ${n === '1' ? 'action' : 'actions'}`],
    [/^(.+) 到 (.+)，(\d+) 种操作$/, (_, from, to, n) => `${from} to ${to}: ${n} ${n === '1' ? 'action' : 'actions'}`],
    [/^静态识别元素 · (\d+)$/, (_, n) => `Statically identified elements · ${n}`],
    [/^运行时观察 · (\d+) 次$/, (_, n) => `Runtime observations · ${n}`],
    [/^另有 (\d+) 个元素，完整图数据中可查看。$/, (_, n) => `${n} more elements are available in the full map data.`],
    [/^UI ELEMENTS \/ 静态识别 (\d+) 个$/, (_, n) => `UI ELEMENTS / ${n} IDENTIFIED`],
    [/^地图载入失败：(.+)$/, (_, message) => `Map failed to load: ${translate(message)}`],
    [/^运行轨迹：(.+) · (\d+) 步已验证 · (\d+) 步偏差(.*)$/, (_, status, ok, bad, reason) => `Runtime trace: ${translate(status)} · ${ok} verified · ${bad} mismatches${reason}`],
    [/^第 (\d+) 步(执行前|执行后)的界面截图$/, (_, n, when) => `Screenshot ${when === '执行后' ? 'after' : 'before'} step ${n}`],
  ];
  const fragments = [
    ['静态分析结果，校验记录单独保存', 'Static analysis; reviews are saved separately'],
    ['切换到“', 'Switch to “'], ['”标签', '” tab'],
    ['点击“', 'Tap “'], ['”菜单项', '” menu item'],
    ['点击列表项', 'Tap list item'], ['点击控件', 'Tap control'],
    ['长按列表项', 'Long-press list item'], ['长按控件', 'Long-press control'],
    ['代码跳转', 'Code transition'], ['导航菜单：', 'Navigation menu: '],
    ['静态识别的候选页面', 'Statically identified candidate screen'],
    [' · 应用入口 · ', ' · app entry · '], ['未知组件', 'Unknown component'],
    [' · 触发未定位', ' · trigger not located'],
    ['具体控件未定位', 'control not located'],
    ['· 已定位静态触发点', '· static trigger located'], ['· 具体控件未定位', '· control not located'],
    ['· 静态分析推断，仍需实际运行或人工核对。', '· inferred from static analysis; verify at runtime or by review.'],
    [' · 实际页面 ', ' · observed screen '], [' · 界面记录 ', ' · UI hierarchy '], [' · 截图 ', ' · screenshot '],
    ['承载页面：', 'Hosted screens: '], ['承载。', ' hosts it.'], ['承载 ', 'Hosts '], ['由 ', 'Hosted by '],
    [' · 已定位静态触发点', ' · static trigger located'],
    ['静态分析识别的候选页面。对应组件：', 'Candidate screen identified by static analysis. Component: '],
    ['对应组件：', 'Component: '], ['未知', 'Unknown'],
    ['种静态识别的操作路径。', ' statically identified paths.'], ['尚未经运行时验证。', 'Not verified at runtime.'],
    ['两页之间同时存在承载关系：目标页是当前页中的标签或导航目的地。', 'The destination is also hosted by this screen as a tab or navigation destination.'],
    ['触发动作：', 'Action: '], ['触发：', 'Trigger: '], ['；具体控件未定位', '; control not located'],
    ['；依据 ', '; evidence '], ['；', '; '], ['种操作', ' actions'], ['操作路径', 'action paths'],
    ['静态规则识别', 'Identified by static rules'], ['可操作候选', 'Action candidate'], ['展示', 'Display'],
    ['运行轨迹与当前 Map 的项目名称不一致', 'Trace project name does not match this map'],
    ['运行轨迹与当前 Map 的源码版本不一致', 'Trace source commit does not match this map'],
    ['运行轨迹包含当前 Map 中不存在的路径', 'Trace contains paths absent from this map'],
    ['需要包含 steps 的运行轨迹 JSON', 'Trace JSON must contain steps'],
    ['需要 schema_version=2 且包含 screens、transitions 的 Map JSON', 'Map JSON must have schema_version=2, screens, and transitions'],
    ['。', '. '], ['、', ', '],
  ];
  function translate(value) {
    if (copy[value] !== undefined) return copy[value];
    let result = value;
    for (const [pattern, replace] of patterns) result = result.replace(pattern, replace);
    if (!/[\u3400-\u9fff。、；：]/u.test(result)) return result;
    for (const [from, to] of fragments) result = result.replaceAll(from, to);
    return result;
  }
  let language = 'en';
  try { language = new URLSearchParams(location.search).get('lang') || localStorage.getItem('gui-anything-language') || 'en'; } catch (_) { /* file URLs can restrict storage */ }
  language = language === 'zh' || language === 'zh-CN' ? 'zh' : 'en';
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  const meta = document.querySelector('meta[name="description"]');
  const metaOriginal = meta?.content;
  if (meta) meta.content = language === 'en' ? translate(metaOriginal) : metaOriginal;
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'language-switch';
  toggle.textContent = language === 'en' ? '中文' : 'English';
  toggle.setAttribute('aria-label', language === 'en' ? 'Switch to Chinese' : '切换到英文');
  toggle.addEventListener('click', () => {
    language = language === 'en' ? 'zh' : 'en';
    try { localStorage.setItem('gui-anything-language', language); } catch (_) { /* file URLs can restrict storage */ }
    try {
      const url = new URL(location.href);
      url.searchParams.set('lang', language);
      history.replaceState(null, '', url.href);
    } catch (_) { /* standalone file URLs may reject history changes */ }
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    toggle.textContent = language === 'en' ? '中文' : 'English';
    toggle.setAttribute('aria-label', language === 'en' ? 'Switch to Chinese' : '切换到英文');
    if (meta) meta.content = language === 'en' ? translate(metaOriginal) : metaOriginal;
    localize(document.body);
  });
  const header = document.querySelector('.site-header nav, .topbar');
  if (header) header.append(toggle);
  const textOriginals = new WeakMap();
  const attributeOriginals = new WeakMap();
  function localize(root) {
    if (root.nodeType === Node.TEXT_NODE) {
      if (root.parentElement?.closest('pre, script, style')) return;
      const value = root.nodeValue;
      const previous = textOriginals.get(root);
      const priorEnglish = previous?.replace(previous.trim(), translate(previous.trim()));
      const original = previous !== undefined && (value === previous || value === priorEnglish) ? previous : value;
      textOriginals.set(root, original);
      const trimmed = original.trim();
      if (!trimmed) return;
      const desired = language === 'en' ? original.replace(trimmed, translate(trimmed)) : original;
      if (value !== desired) root.nodeValue = desired;
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    if (root.matches('pre, script, style')) return;
    const originals = attributeOriginals.get(root) || {};
    for (const name of ['aria-label', 'placeholder', 'title']) {
      const value = root.getAttribute(name);
      if (!value) continue;
      const original = originals[name] !== undefined && value === translate(originals[name]) ? originals[name] : value;
      originals[name] = original;
      const desired = language === 'en' ? translate(original) : original;
      if (value !== desired) root.setAttribute(name, desired);
    }
    attributeOriginals.set(root, originals);
    for (const child of root.childNodes) localize(child);
  }
  localize(document.body);
  new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === 'characterData') localize(record.target);
      else for (const added of record.addedNodes) localize(added);
    }
  }).observe(document.body, { childList: true, characterData: true, subtree: true });
})();
