export const parseAndroidJson = (json: any) => {
  if (json?.schema_version === 2 && Array.isArray(json.screens) && Array.isArray(json.transitions)) {
    const screens = json.screens as any[]
    const transitions = json.transitions as any[]
    const containments = Array.isArray(json.containments) ? json.containments as any[] : []
    const screenById = new Map(screens.map((screen) => [screen.id, screen]))
    const ids = new Set(screens.map((screen) => screen.id))
    const outgoing = new Map<string, string[]>()
    for (const edge of transitions) {
      if (!ids.has(edge.from) || !ids.has(edge.to)) continue
      outgoing.set(edge.from, [...(outgoing.get(edge.from) || []), edge.to])
    }

    // Place reachable screens by distance from an entry screen. Isolated screens
    // stay visible in a separate final column rather than disappearing.
    const depth = new Map<string, number>()
    const queue = screens.filter((screen) => screen.entry).map((screen) => screen.id)
    for (const id of queue) depth.set(id, 0)
    for (let i = 0; i < queue.length; i++) {
      for (const next of outgoing.get(queue[i]) || []) {
        if (!depth.has(next)) {
          depth.set(next, (depth.get(queue[i]) || 0) + 1)
          queue.push(next)
        }
      }
    }
    const maxDepth = Math.max(0, ...depth.values())
    const columnCounts = new Map<number, number>()
    const nodes = screens.map((screen) => {
      const column = depth.get(screen.id) ?? maxDepth + 1
      const row = columnCounts.get(column) || 0
      columnCounts.set(column, row + 1)
      return {
        id: screen.id,
        label: screen.title,
        position: { x: column * 300 + 40, y: row * 150 + 40 },
        data: {
          ...screen,
          contained_pages: containments.filter((relation) => relation.parent === screen.id).map((relation) => ({ title: screenById.get(relation.child)?.title || relation.child, kind: relation.kind })),
          parent_pages: containments.filter((relation) => relation.child === screen.id).map((relation) => ({ title: screenById.get(relation.parent)?.title || relation.parent, kind: relation.kind }))
        },
        style: {
          background: screen.entry ? '#ecfdf5' : '#fff',
          border: `2px solid ${screen.entry ? '#0d9488' : '#94a3b8'}`,
          borderRadius: '12px', padding: '14px', width: '220px',
          color: '#0f172a', fontWeight: '600'
        }
      }
    })
    const edges = transitions.filter((edge) => ids.has(edge.from) && ids.has(edge.to)).map((edge) => ({
      id: edge.id,
      source: edge.from,
      target: edge.to,
      label: edge.action,
      data: { ...edge, containment: containments.find((relation) => relation.parent === edge.from && relation.child === edge.to) },
      animated: false,
      style: { stroke: ['source_rule', 'decompiled_rule'].includes(edge.verification) ? '#0d9488' : '#94a3b8', strokeWidth: 2 },
      labelStyle: { fill: '#475569', fontSize: '11px' }
    }))
    return { nodes, edges }
  }

  const nodes: any[] = [];
  const edges: any[] = [];

  // 定义颜色配置
  const colors = {
    Activity: '#3b82f6', // 蓝色
    Fragment: '#10b981', // 绿色
    Dialog: '#f59e0b',   // 橙色
    Other: '#94a3b8'     // 灰色
  };

  json.units.forEach((unit: any, idx: number) => {
    // 简单的行列布局：每行 3 个
    const row = Math.floor(idx / 2);
    const col = idx % 2;

    nodes.push({
      id: unit.unit_id,
      label: unit.unit_id,
      position: { x: col * 350 + 50, y: row * 200 + 50 },
      data: { ...unit },
      style: {
        background: unit.is_entry_point ? '#eff6ff' : '#fff',
        border: `2px solid ${colors[unit.unit_type] || colors.Other}`,
        borderRadius: '12px',
        padding: '15px',
        width: '220px',
        textAlign: 'center',
        fontWeight: '600',
        color: '#1e293b'
      }
    });

    // 提取跳转关系
    unit.ui_elements?.forEach((el: any) => {
      if (el.interaction?.type === 'NAVIGATE_TO' && el.interaction.target_unit) {
        edges.push({
          id: `e-${unit.unit_id}-${el.interaction.target_unit}-${el.id}`,
          source: unit.unit_id,
          target: el.interaction.target_unit,
          label: el.text || el.id.split('.').pop(), // 取 ID 的最后一段
          animated: true,
          style: { stroke: colors.Activity, strokeWidth: 2 },
          labelStyle: { fill: '#64748b', fontSize: '10px', fontWeight: 'bold' }
        });
      }
    });
  });

  return { nodes, edges };
};
