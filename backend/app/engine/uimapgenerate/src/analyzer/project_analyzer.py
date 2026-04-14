import os
import json
import yaml
import re
from ..core.resource_loader import ResourceLoader
from ..core.code_scanner import CodeScanner

class ProjectAnalyzer:
    def __init__(self, config_file=None, project_config=None):
        # 兼容两种初始化方式
        if project_config:
            self.cfg = project_config
        elif config_file:
            with open(config_file, "r") as f:
                self.cfg = yaml.safe_load(f)["project"]
        
        # 现在可以直接用 self.cfg 了
        self.project_path = self.cfg["root"]
        self.loader = ResourceLoader(
            self.project_path, 
            main_source_set=self.cfg.get("main_source_set")
        )
        self.scanner = CodeScanner()
        self.results = []
        
        # 核心索引库
        self.class_index = {}      # 存储类名 -> 类详情的映射
        self.extension_pool = {}   # 存储类名 -> 该类扩展函数代码块的映射

    def analyze(self):
        """
        核心执行流：扫描 -> 索引 -> 过滤 -> 平铺合并
        """
        print(f"--- 🚀 开始分析项目: {self.project_path} ---")
        
        # 0. 预加载资源 (Manifest, Strings, Layouts)
        self.loader.load_all()
        entry_class = self.loader.manifest_main_entry 

        # --- PASS 1: 全量扫描，建立全局知识库 ---
        for root, _, files in os.walk(self.project_path):
            # 过滤无关目录
            if any(x in root for x in ['build', 'test', 'res', '.git']): 
                continue 
                
            for f in files:
                if f.endswith((".java", ".kt")):
                    file_path = os.path.join(root, f)
                    info = self.scanner.scan_file(file_path)
                    
                    # A. 记录类定义
                    class_name = info.get("class_name")
                    if class_name:
                        info["file_path"] = os.path.relpath(file_path, self.project_path)
                        self.class_index[str(class_name)] = info
                    
                    # B. 记录扩展函数 (关键：即使该文件没有类定义，也可能包含扩展函数)
                    for ext in info.get("extensions", []):
                        receiver = str(ext["receiver_class"])
                        if receiver not in self.extension_pool:
                            self.extension_pool[receiver] = []
                        self.extension_pool[receiver].append({
                            "origin_file": f,
                            "code_snippet": ext["code_snippet"]
                        })

        print(f"📊 [PASS 1] 扫描完成: 索引了 {len(self.class_index)} 个类, {len(self.extension_pool)} 个类的扩展函数。")

        # --- PASS 2: 实体过滤与逻辑合并 ---
        final_units = []
        manifest_set = self.loader.manifest_activities 

        for class_name, info in self.class_index.items():
            # 1. 判定类身份 (Activity, Fragment, Dialog)
            unit_type = self._resolve_final_type(class_name)
            
            # --- 调试打印：只看包含 Dialog 字样的类 ---
            if "dialog" in class_name.lower():
                 print(f"  🔍 诊断 Dialog 类: {class_name} -> 识别为: {unit_type}")

            is_valid_activity = (unit_type == "Activity" and class_name in manifest_set)
            is_sub_unit = (unit_type in ["Fragment", "Dialog"])
            # 调试信息：如果类在 Manifest 中，观察它为何被保留或丢弃
            if class_name in manifest_set:
                print(f"  🔍 检查 Manifest 类: {class_name} -> 识别身份: {unit_type}")

            # 2. 判定逻辑：
            # (1) 如果是 Activity，必须在 Manifest 白名单中
            # (2) 如果是 Fragment/Dialog，直接保留
            is_valid_activity = (unit_type == "Activity" and class_name in manifest_set)
            is_sub_unit = (unit_type in ["Fragment", "Dialog"])

            if is_valid_activity or is_sub_unit:
                # 3. 执行“平铺合并”：收集继承链上的布局、元素、以及父类/扩展的代码逻辑
                merged_node = self._flatten_unit_with_extensions(class_name, unit_type)
                # --- 新增标记 ---
                if class_name == entry_class:
                    merged_node["is_entry_point"] = True
                else:
                    merged_node["is_entry_point"] = False
                final_units.append(merged_node)
        
        self.results = final_units
        print(f"--- ✅ 分析完成: 共发现 {len(self.results)} 个有效交互单元 ---")
        return self.results

    def _resolve_final_type(self, class_name):
        """
        修正后的身份判定：
        由于很多 Dialog 继承自 DialogFragment，
        如果我们先判断 Fragment，Dialog 就会被"截胡"。
        """
        # 添加递归深度跟踪和循环检测
        return self._resolve_final_type_recursive(class_name, visited=set(), depth=0)

    def _resolve_final_type_recursive(self, class_name, visited, depth):
        """
        递归实现的内部方法，带有安全保护
        """
        if not class_name:
            return "Unknown"
        
        # 1. 安全检查：防止循环继承
        if class_name in visited:
            print(f"  ⚠️ [_resolve_final_type] 检测到循环继承: {' -> '.join(visited)} -> {class_name}")
            return "Unknown"
        
        # 2. 安全检查：防止递归过深
        MAX_DEPTH = 20
        if depth > MAX_DEPTH:
            print(f"  ⚠️ [_resolve_final_type] 继承链过深 ({depth}层): {' -> '.join(visited)}")
            return "Unknown"
        
        visited.add(class_name)
        
        name_str = str(class_name)
        
        # 调试：打印深层递归
        if depth > 5:
            print(f"  🔍 [_resolve_final_type] 深度{depth}: 检查 {class_name}")

        # 1. 优先级最高：如果类名里直接带了 Dialog，那它 99% 就是个对话框
        if "Dialog" in name_str:
            print(f"  ✅ [_resolve_final_type] 深度{depth}: {class_name} -> Dialog (直接匹配)")
            return "Dialog"
        
        # 2. 递归查找继承链
        if class_name in self.class_index:
            parent = self.class_index[class_name].get("super_class")
            if parent:
                # 检查自继承
                if parent == class_name:
                    print(f"  ⚠️ [_resolve_final_type] 自继承: {class_name}")
                    return "Unknown"
                    
                # 递归向上找
                res = self._resolve_final_type_recursive(parent, visited, depth + 1)
                # 如果父类被判定为 Dialog，子类也是
                if res != "Unknown":
                    print(f"  ✅ [_resolve_final_type] 深度{depth}: {class_name} -> {res} (继承自父类)")
                    return res
        
        # 3. 启发式保底判定
        # 注意：这里要最后判断 Fragment，因为 DialogFragment 包含 Fragment 字符
        if "Activity" in name_str: 
            print(f"  ✅ [_resolve_final_type] 深度{depth}: {class_name} -> Activity (启发式匹配)")
            return "Activity"
        if "Fragment" in name_str: 
            print(f"  ✅ [_resolve_final_type] 深度{depth}: {class_name} -> Fragment (启发式匹配)")
            return "Fragment"
        
        print(f"  ❓ [_resolve_final_type] 深度{depth}: {class_name} -> Unknown")
        return "Unknown"
        
    def _flatten_unit_with_extensions(self, class_name, unit_type):
        """
        向上收集继承链的同时，横向收集该类及其所有父类关联的扩展函数代码。
        支持从多个布局文件（ViewBinding 和 R.layout）中合并 UI 元素，并处理菜单属性。
        """
        curr = class_name
        all_elements = []
        all_interactions = []
        all_discovered_layouts = set() # 存储所有发现的布局名
        visited = set()
        
        while curr:
            if curr in visited: break
            visited.add(curr)
            
            if curr in self.class_index:
                node = self.class_index[curr]
                raw_code = node.get("raw_code", "")
                
                # --- 1. 收集布局 (多源合并) ---
                
                # A. 来自 CodeScanner 扫描到的布局列表 (包含 R.layout 和识别到的 Binding)
                scanned_layouts = node.get("layout", [])
                if isinstance(scanned_layouts, list):
                    all_discovered_layouts.update(scanned_layouts)
                elif isinstance(scanned_layouts, str):
                    all_discovered_layouts.add(scanned_layouts)

                # B. 再次通过 Analyzer 补丁确保识别 ViewBinding (双重保险)
                binding_layout = self._infer_layout_from_binding(raw_code)
                if binding_layout:
                    all_discovered_layouts.add(binding_layout)

                # C. 针对 MainActivity 等核心类，如果还没找到 activity_ 布局，尝试猜测
                if not any(l.startswith("activity_") for l in all_discovered_layouts):
                    guessed = self._guess_layout_by_name(curr)
                    if guessed:
                        all_discovered_layouts.add(guessed)

                # --- 2. 遍历所有发现的布局，利用 ResourceLoader 抓取元素 ---
                for layout_name in all_discovered_layouts:
                    # 获取该布局下的所有元素 (ResourceLoader 会自动展开关联的 Menu)
                    res_elements = self.loader.get_layout_elements(layout_name)
                    for re_el in res_elements:
                        # 标记来源，方便后续合并去重
                        re_el["source"] = "resource_file"
                        re_el["from_layout"] = layout_name
                        all_elements.append(re_el)

                # --- 3. 收集交互逻辑 ---
                if node.get("interactions"):
                    for inter in node["interactions"]:
                        all_interactions.append(inter)
                        # 如果代码中提到了具体的 ID，尝试加入元素池，稍后合并
                        if "id" in inter:
                            clean_id = inter["id"].replace("R.id.", "")
                            all_elements.append({
                                "id": clean_id,
                                "tag": "element",
                                "type": "Unknown",
                                "source": "code_discovery",
                                "text": ""
                            })
                
                parent = node.get("super_class")
            else:
                parent = None

            # --- 4. 收集扩展函数 ---
            if curr in self.extension_pool:
                for ext in self.extension_pool[curr]:
                    all_interactions.append({
                        "source": f"Extension of {curr}",
                        "code_snippet": ext["code_snippet"]
                    })
            
            curr = parent

        # 选出一个最优的“主布局”用于展示
        primary_layout = self._pick_primary_layout(class_name, all_discovered_layouts)

        return {
            "unit_id": class_name,
            "unit_type": unit_type,
            "layout": primary_layout,
            "all_layouts": list(all_discovered_layouts),
            "ui_elements": self._deduplicate_and_merge_elements(all_elements),
            "interactions": all_interactions,
            "file_path": self.class_index.get(class_name, {}).get("file_path", "Unknown")
        }

    def _guess_layout_by_name(self, class_name):
        """
        根据类名猜测布局。
        例如: MainActivity -> activity_main
        SettingsActivity -> activity_settings
        """
        if "Activity" in class_name:
            base_name = class_name.replace("Activity", "")
            # CamelCase to snake_case
            snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', base_name).lower()
            return f"activity_{snake_name}"
        elif "Fragment" in class_name:
            base_name = class_name.replace("Fragment", "")
            snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', base_name).lower()
            return f"fragment_{snake_name}"
        return None

    def _pick_primary_layout(self, class_name, layout_set):
        """
        从布局集合中选出一个最像主布局的显示在 JSON 顶层。
        优先逻辑: activity_ > fragment_ > 其他
        """
        if not layout_set: return None
        layouts = sorted(list(layout_set))
        
        # 针对类名寻找最匹配的
        target = class_name.lower().replace("activity", "").replace("fragment", "")
        for l in layouts:
            if target in l and (l.startswith("activity_") or l.startswith("fragment_")):
                return l
        
        # 通用优先
        for l in layouts:
            if l.startswith("activity_"): return l
        for l in layouts:
            if l.startswith("fragment_"): return l
            
        return layouts[0]

    def _infer_layout_from_binding(self, raw_code):
        """
        从源码中提取 ViewBinding 类名并转换为布局文件名。
        例如: ActivityMainBinding -> activity_main
        """
        if not raw_code: return None
        # 匹配诸如 ActivityMainBinding, FragmentClockBinding 的模式
        match = re.search(r"([A-Z][a-zA-Z0-9]+)Binding", raw_code)
        if match:
            binding_class = match.group(1) # 获取 ActivityMain
            # 大驼峰转下划线
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', binding_class)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return None

    def _deduplicate_and_merge_elements(self, elements):
        """
        去重并合并元素。
        核心逻辑：当资源解析（XML）和代码扫描冲突时，优先保留含有 showAsAction 等属性的 XML 条目。
        """
        merged = {}
        for el in elements:
            eid = el['id']
            if eid not in merged:
                merged[eid] = el
            else:
                # 如果新找到的是资源文件，而旧的是代码发现，直接覆盖以获取 XML 属性 (show_as_action等)
                if el.get("source") == "resource_file":
                    # 覆盖前把代码中可能存在的 business_logic 转移过来
                    if "business_logic" in merged[eid]:
                        el["business_logic"] = merged[eid]["business_logic"]
                    if "interaction" in merged[eid]:
                        el["interaction"] = merged[eid]["interaction"]
                    merged[eid] = el
                # 反之，如果是代码发现遇到了已有的 XML 条目，只补充逻辑
                elif merged[eid].get("source") == "resource_file":
                    if "business_logic" in el:
                        merged[eid]["business_logic"] = el["business_logic"]
                    if "interaction" in el:
                        merged[eid]["interaction"] = el["interaction"]
        
        return list(merged.values())

    @property
    def units(self):
        return self.results

    def save_json(self, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)