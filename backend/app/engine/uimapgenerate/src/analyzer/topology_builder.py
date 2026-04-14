import json
import copy
import time
from ..llm.prompts.element_semantic_prompt import SYSTEM_PROMPT, build_element_semantic_prompt
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

class TopologyBuilder:
    def __init__(self, all_units_list, llm_client):
        self.units_map = {u['unit_id']: u for u in all_units_list}
        self.llm = llm_client
        self.visited = set()
        # 全局语义注册表：存储已分析类的“能力零件”
        self.semantic_registry = {} 
        self.inventory = list(self.units_map.keys())
        self.lock = Lock() # 确保线程安全地更新注册表和已访问集合
        # 添加调试计数器
        self.debug_counter = 0
        self.max_debug_depth = 0

    def build_parallel(self, sorted_unit_ids, max_workers=5):
        """
        按照层级，在每一层内部实行并行分析
        """
        # 1. 按照继承深度对 ID 进行分组
        # 例如: {0: ['BaseActivity'], 1: ['SimpleActivity'], 2: ['MainActivity', 'EventActivity']}
        levels = {}
        
        # 首先打印所有组件信息
        print(f"\n📊 [Debug] 开始分析，共有 {len(sorted_unit_ids)} 个组件")
        print("组件列表:")
        for uid in sorted_unit_ids[:20]:  # 只打印前20个
            unit = self.units_map.get(uid, {})
            parent = unit.get('super_class', 'None')
            print(f"  - {uid} (父类: {parent})")
        
        # 分组前先检查循环
        print("\n🔍 [Debug] 检查继承链...")
        for uid in sorted_unit_ids:
            depth = self._get_depth(uid)
            print(f"  {uid}: 深度 {depth}")
            if depth > 10:  # 深度异常时详细检查
                print(f"   警告: {uid} 继承深度异常 ({depth})")
        
        # 正常分组逻辑
        for uid in sorted_unit_ids:
            depth = self._get_depth(uid)
            if depth not in levels: levels[depth] = []
            levels[depth].append(uid)

        total_start = time.time()

        # 2. 逐层处理
        for depth in sorted(levels.keys()):
            uids_in_level = levels[depth]
            print(f"\n🌊 [Parallel Level {depth}] 正在并行处理 {len(uids_in_level)} 个组件...")
            
            # 打印该层的组件
            for uid in uids_in_level:
                unit = self.units_map.get(uid, {})
                parent = unit.get('super_class', 'None')
                print(f"  - {uid} (继承自: {parent})")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                future_to_uid = {
                    executor.submit(self._analyze_single_task, uid): uid 
                    for uid in uids_in_level
                }
                
                for future in as_completed(future_to_uid):
                    uid = future_to_uid[future]
                    try:
                        future.result()
                    except RecursionError as e:
                        print(f"   🔴 组件 {uid} 递归错误: {e}")
                        # 尝试获取更多信息
                        unit = self.units_map.get(uid, {})
                        print(f"     父类: {unit.get('super_class')}")
                        print(f"     元素数: {len(unit.get('ui_elements', []))}")
                    except Exception as e:
                        print(f"   ❌ 组件 {uid} 分析过程中崩溃: {e}")
                        
        print(f"\n📊 [Debug Summary]")
        print(f"  深度计算总次数: {self.debug_counter}")
        print(f"  最大继承深度: {self.max_debug_depth}")
        print(f"⏱️ LLM 语义注入总耗时: {time.time() - total_start:.2f} 秒")

    def _get_depth(self, unit_id):
        """安全计算继承深度，避免循环引用"""
        depth = 0
        curr = unit_id
        visited = set()  # 添加已访问集合防止循环
        max_depth = 50  # 设置最大深度限制
        
        # 调试：记录调用
        self.debug_counter += 1
        if self.debug_counter % 100 == 0:
            print(f"  🔍 [Depth Check] 已计算 {self.debug_counter} 次深度")
        
        while curr in self.units_map and depth < max_depth:
            if curr in visited:
                print(f"⚠️  检测到循环继承: {unit_id} -> {curr}")
                print(f"   循环路径: {' -> '.join(visited)} -> {curr}")
                break
            visited.add(curr)
            
            parent = self.units_map[curr].get('super_class')
            if not parent or parent not in self.units_map: 
                break
            depth += 1
            curr = parent
            
            # 更新最大深度记录
            if depth > self.max_debug_depth:
                self.max_debug_depth = depth
                if depth > 10:  # 深度过大时记录
                    print(f"  ⚠️ 继承链深度异常: {depth} 在 {unit_id}")
        
        if depth >= max_depth:
            print(f"🔴 达到最大深度限制: {unit_id}")
            print(f"   当前路径: {' -> '.join(visited)}")
            
        return depth

    # def _analyze_single_task(self, unit_id):
    #     """线程安全的单个分析任务"""
    #     unit = self.units_map[unit_id]
        
    #     # A. 处理继承逻辑 (读注册表)
    #     with self.lock:
    #         parent_class = unit.get('super_class')
    #         if parent_class in self.semantic_registry:
    #             self._inherit_semantics(unit, parent_class)
    #         self.visited.add(unit_id)

    #     # B. 调用 LLM (耗时操作，在锁外进行)
    #     prompt = build_element_semantic_prompt(unit, self.inventory)
    #     if 'adpter' in prompt.lower():
    #         print(prompt)  # 调试输出提示词
    #     try:
    #         res_text = self.llm.call_chat(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
    #         if 'adapter' in res_text.lower():
    #             print(f"   LLM返回: {res_text[:200]}...")  # 调试输出部分结果
    #         semantic_updates = json.loads(res_text)
            
    #         # C. 回填数据并归档 (写注册表)
    #         with self.lock:
    #             self._process_updates(unit, semantic_updates)
    #             self._archive_semantics(unit_id)
    #             print(f"   ✅ [Done] {unit_id}")
    #     except Exception as e:
    #         print(f"   ⚠️ [Error] {unit_id}: {e}")

    def _analyze_single_task(self, unit_id):
        """线程安全的单个分析任务"""
        unit = self.units_map[unit_id]
        
        # 打开日志文件（追加模式）
        with open('debug_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} 分析 {unit_id} ===\n")
        
        # A. 处理继承逻辑 (读注册表)
        with self.lock:
            parent_class = unit.get('super_class')
            if parent_class in self.semantic_registry:
                self._inherit_semantics(unit, parent_class)
            self.visited.add(unit_id)

        # B. 调用 LLM (耗时操作，在锁外进行)
        prompt = build_element_semantic_prompt(unit, self.inventory)
        
        # 记录包含"adapter"的提示词
        temp = False 
        if 'mainactivity' in prompt.lower() or 'mainactivity' in prompt.lower():
            temp = True
            with open('debug_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n【PROMPT】{unit_id}\n")
                f.write(prompt)
                f.write("\n【END PROMPT】\n")
        
        try:
            res_text = self.llm.call_chat(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
            
            # 记录包含"adapter"的返回结果
            if temp:
                with open('debug_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"\n【RESPONSE】{unit_id}\n")
                    f.write(res_text)
                    f.write("\n【END RESPONSE】\n")
            
            semantic_updates = json.loads(res_text)
            
            # C. 回填数据并归档 (写注册表)
            with self.lock:
                self._process_updates(unit, semantic_updates)
                self._archive_semantics(unit_id)
                print(f"   ✅ [Done] {unit_id}")
        except Exception as e:
            print(f"   ⚠️ [Error] {unit_id}: {e}")
            with open('debug_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n【ERROR】{unit_id}: {e}\n")

    def build_with_inheritance(self, sorted_unit_ids):
        """按继承深度顺序执行语义流水线"""
        for unit_id in sorted_unit_ids:
            if unit_id in self.visited:
                continue
            
            unit = self.units_map[unit_id]
            print(f"\n🧬 [Semantic Workflow] 处理组件: {unit_id}")

            # 1. 语义继承：从父类克隆已识别的功能
            parent_class = unit.get('super_class')
            if parent_class in self.semantic_registry:
                print(f"   ⬆️ 继承父类语义: 从 {parent_class} 继承了功能元素")
                self._inherit_semantics(unit, parent_class)

            # 2. LLM 分析：注入业务逻辑并发现新元素
            self.analyze_single_unit(unit_id)

            # 3. 语义归档：存入注册表供子类继承
            self._archive_semantics(unit_id)

    def analyze_single_unit(self, unit_id):
        try:
            print(f"  🐛 [DEBUG] 开始分析单元: {unit_id}")
            print(f"    visited集合大小: {len(self.visited)}")
            print(f"    当前在分析的单位: {[u for u in self.visited if u == unit_id]}")
            
            if unit_id in self.visited:
                print(f"  🔴 [ERROR] 检测到重复分析: {unit_id}")
                print(f"    调用栈:")
                import traceback
                traceback.print_stack(limit=10)
                return
            
            unit = self.units_map.get(unit_id)
            if not unit:
                print(f"  🔴 [ERROR] 找不到单元: {unit_id}")
                return
                
            self.visited.add(unit_id)
            print(f"  ✅ 已添加到visited: {unit_id}")

            # 确保静态解析出的元素默认 location 为 layout
            ui_elements = unit.get('ui_elements', [])
            print(f"  📊 UI元素数量: {len(ui_elements)}")
            
            for el in ui_elements:
                if 'location' not in el:
                    el['location'] = 'layout'
                    print(f"    ➕ 设置默认location: {el.get('id')}")

            print(f"  🤖 构建提示词...")
            # 添加安全检查
            try:
                prompt = build_element_semantic_prompt(unit, self.inventory)
                print(f"  ✅ 提示词构建完成，长度: {len(prompt)}")
                
                # 限制prompt长度避免问题
                if len(prompt) > 10000:
                    print(f"  ⚠️ 提示词过长，截断...")
                    prompt = prompt[:10000] + "..."
            except Exception as prompt_error:
                print(f"  🔴 构建提示词失败: {prompt_error}")
                import traceback
                traceback.print_exc()
                return

            print(f"  📞 调用LLM...")
            try:
                res_text = self.llm.call_chat(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
                print(f"  ✅ LLM返回，长度: {len(res_text)}")
                
                # 检查返回结果
                if not res_text or len(res_text) < 10:
                    print(f"  ⚠️ LLM返回结果过短")
                    return
                    
                semantic_updates = json.loads(res_text)
                print(f"  ✅ JSON解析完成，更新项: {len(semantic_updates)}")
                
                # 调用更新处理函数
                print(f"  🔧 处理更新...")
                self._process_updates(unit, semantic_updates)
                print(f"  ✅ 更新处理完成")
                
            except json.JSONDecodeError as e:
                print(f"  🔴 JSON解析失败: {e}")
                print(f"    LLM返回: {res_text[:200]}...")
            except Exception as e:
                print(f"  🔴 LLM调用或处理失败: {e}")
                import traceback
                traceback.print_exc()
                
        except RecursionError as e:
            print(f"  🔴 🔴 🔴 递归错误在 analyze_single_unit: {unit_id}")
            print(f"    错误详情: {e}")
            print(f"    当前调用栈:")
            import traceback
            traceback.print_stack(limit=15)
            # 记录到文件以便后续分析
            with open("recursion_error.log", "a") as f:
                f.write(f"\n=== RecursionError at {time.time()} ===\n")
                f.write(f"Unit ID: {unit_id}\n")
                traceback.print_exc(file=f)
            raise
        except Exception as e:
            print(f"  🔴 分析单元 {unit_id} 时发生未知错误: {e}")
            import traceback
            traceback.print_exc()

    def _process_updates(self, unit, semantic_updates):
        print(f"    🐛 [DEBUG _process_updates] 开始处理更新")
        print(f"      单元: {unit.get('unit_id')}")
        print(f"      更新数量: {len(semantic_updates)}")
        
        try:
            ui_dict = {str(e['id']): e for e in unit['ui_elements']}
            print(f"      现有UI元素字典大小: {len(ui_dict)}")
            
            for i, update in enumerate(semantic_updates[:5]):  # 只处理前5个避免size过大
                print(f"      处理更新 {i+1}/{len(semantic_updates)}: {update.get('id', 'No ID')}")
                
                raw_id = update.get('id', '').replace('binding.', '').strip()
                if not raw_id: 
                    print(f"        ⚠️ 跳过空ID")
                    continue

                # 检查这个ID是否已经在处理中（避免循环）
                if hasattr(self, '_processing_ids'):
                    if raw_id in self._processing_ids:
                        print(f"        🔴 检测到循环处理: {raw_id}")
                        continue
                    self._processing_ids.add(raw_id)
                else:
                    self._processing_ids = {raw_id}
                
                # 逻辑增强：符号补全
                logic = update.get('business_logic')
                interaction = update.get('interaction') or {}
                
                # 如果 LLM 没给 target_unit，但业务逻辑里提到了函数，
                # 或者我们想让它更稳，可以在这里做一个简单的正则二次提取（可选）
                target = interaction.get('target_unit', '')
                
                # 统一清理 target_unit：去掉可能存在的 this. 前缀
                if target:
                    target = target.replace('this.', '').strip()
                    interaction['target_unit'] = target

                # 位置修正逻辑
                inferred_type = update.get('inferred_type', 'Component')
                location = update.get('location', 'layout')
                if inferred_type == "MenuItem" or "menu" in str(raw_id).lower():
                    location = "menu"
                
                print(f"        ID: {raw_id}, 位置: {location}, 目标: {target}")
                
                if raw_id in ui_dict:
                    print(f"        ✅ 更新现有元素")
                    ui_dict[raw_id]['business_logic'] = logic
                    ui_dict[raw_id]['interaction'] = interaction
                    ui_dict[raw_id]['location'] = location
                else:
                    print(f"        ➕ 添加新元素")
                    unit['ui_elements'].append({
                        "id": raw_id,
                        "location": location,
                        "type": inferred_type,
                        "text": update.get('text') or update.get('display_text', ''),
                        "source": "code_discovery",
                        "business_logic": logic,
                        "interaction": interaction
                    })
                    
            # 清理处理ID集合
            if hasattr(self, '_processing_ids'):
                self._processing_ids.clear()
                
        except Exception as e:
            print(f"    🔴 _process_updates 失败: {e}")
            import traceback
            traceback.print_exc()

    def _inherit_semantics(self, unit, parent_class):
        parent_elements = self.semantic_registry[parent_class]
        existing_ids = {e['id'] for e in unit['ui_elements']}
        for p_el in parent_elements:
            if p_el['id'] not in existing_ids:
                inherited_el = copy.deepcopy(p_el)
                inherited_el['source'] = f"inherited_from_{parent_class}"
                unit['ui_elements'].append(inherited_el)

    def _archive_semantics(self, unit_id):
        unit = self.units_map[unit_id]
        active_elements = [
            e for e in unit['ui_elements'] 
            if e.get('business_logic') or e.get('interaction')
        ]
        self.semantic_registry[unit_id] = active_elements
