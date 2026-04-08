export const parseAndroidJson = (json: any) => {
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