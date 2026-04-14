import re
from . import parser_engine

class CodeScanner:
    def __init__(self):
        # 1. 扩展函数匹配
        self.kt_extension_pattern = re.compile(r"fun\s+([\w\d]+)\.([\w\d]+)\s*\(")
        # 2. 交互识别关键词（增加了菜单和 ID 相关的词）
        self.keywords = [
            "Intent", "startActivity", "setOnClickListener", 
            "setOnMenuItemClickListener", "itemId", "R.id.", 
            "show(", "inflate(", "launch", "start"
        ]

    def scan_file(self, file_path):
        """
        修复版扫描方法：
        1. 收集所有可能的布局文件（列表形式）
        2. 保留源代码 raw_code 供 Analyzer 深度分析
        3. 整合交互追踪和扩展函数
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. 提取类基本信息
        info = self._extract_class_info(content, file_path)
        if not info:
            info = {"class_name": None, "super_class": None}

        # 2. 核心修复：收集所有关联的布局（不再是单个字符串，而是列表）
        # 这样可以同时抓到 activity_main 和 bottom_tablayout_item
        info["layout"] = self._discover_layouts(content)
        
        # 3. 核心修复：保留源代码，这对 ProjectAnalyzer 的补丁逻辑至关重要
        info["raw_code"] = content

        # 4. 提取增强型交互逻辑（含函数追踪）
        info["interactions"] = self._extract_interactions_enhanced(content)

        # 5. 提取 Kotlin 扩展函数
        extensions = []
        for match in self.kt_extension_pattern.finditer(content):
            start_pos = match.start()
            extensions.append({
                "receiver_class": match.group(1),
                "func_name": match.group(2),
                # 抓取较长的片段确保逻辑完整
                "code_snippet": content[start_pos : start_pos + 1000] 
            })
        info["extensions"] = extensions
        
        return info

    def _discover_layouts(self, code_str):
        """
        不再使用简单的提前返回逻辑。
        现在会扫描全文，抓取所有 R.layout 和 ViewBinding 引用。
        """
        found_layouts = set()

        # 线索 1: 标准 R.layout.xxx
        r_layout_matches = re.findall(r'R\.layout\.(\w+)', code_str)
        for l in r_layout_matches:
            found_layouts.add(l)

        # 线索 2: ViewBinding (例如 ActivityMainBinding -> activity_main)
        # 匹配 XXXBinding
        binding_matches = re.findall(r'([A-Z][\w\d]+)Binding', code_str)
        for name in binding_matches:
            # 排除干扰项
            if name in ["View", "Item", "Data", "ViewBinding"]: 
                continue 
            
            # 将 ActivityMain 转换为 activity_main
            # 这里的正则处理：在每个大写字母前加下划线（除了开头）
            s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
            layout_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
            
            # 清理可能的 binding 后缀
            layout_name = layout_name.replace("_binding", "")
            
            if layout_name:
                found_layouts.add(layout_name)

        # 返回列表
        return list(found_layouts)

    def _extract_interactions_enhanced(self, code):
        """
        增强版切片提取：关键词感应 + 深度函数追踪
        """
        lines = code.split('\n')
        snippets = []
        processed_lines = set()

        for i, line in enumerate(lines):
            # 发现交互关键词
            if any(k in line for k in self.keywords):
                if i in processed_lines: continue
                
                # 策略：遇到 setOnMenuItemClickListener 等复杂块，直接抓取 40 行，确保 when 块完整
                window = 40 if "MenuItem" in line or "when" in line else 12
                start = max(0, i - 2)
                end = min(len(lines), i + window)
                
                snippet_text = "\n".join(lines[start:end])
                snippets.append({"line": i + 1, "code_snippet": snippet_text})
                
                # 尝试追踪该代码块中调用的本地私有函数
                # 寻找形如 xxxDialog() 或 launchXxx() 的调用
                potential_calls = re.findall(r'(\w+Dialog|\w+Intent|launch\w+|show\w+)\s*\(', snippet_text)
                for func_name in set(potential_calls):
                    if func_name not in ["getString", "inflate", "apply", "setResult"]:
                        traced_code = self._find_function_definition(code, func_name)
                        if traced_code:
                            snippets.append({
                                "line": "traced",
                                "source_func": func_name,
                                "code_snippet": f"/* 追踪到的函数定义: {func_name} */\n{traced_code}"
                            })

                for j in range(start, end): processed_lines.add(j)
        return snippets

    def _extract_class_info(self, code, path):
        """解析类名和父类名 (增强版)"""
        res = {"class_name": None, "super_class": None}

        # 优先使用正则表达式，因为它在处理复杂的 Kotlin 语法（如构造函数、修饰符）时最稳
        # 匹配: class Name ... : Super 或 class Name ... extends Super
        kt_class_regex = r"class\s+([\w\d]+)(?:[\s\S]*?):\s*([\w\d\.]+)"
        java_class_regex = r"class\s+([\w\d]+)(?:[\s\S]*?)extends\s+([\w\d\.]+)"
        
        regex = kt_class_regex if path.endswith(".kt") else java_class_regex
        match = re.search(regex, code)
        
        if match:
            res["class_name"] = match.group(1)
            res["super_class"] = match.group(2)
        else:
            # 保底：匹配没有继承关系的普通类
            simple_match = re.search(r"class\s+([\w\d]+)", code)
            if simple_match:
                res["class_name"] = simple_match.group(1)

        # 如果正则抓到了，直接返回，避免 Tree-sitter 的环境差异导致失败
        if res["class_name"]:
            return res

        # --- 以下是 Tree-sitter 备选方案 (如果正则失败) ---
        try:
            if not getattr(parser_engine, "AVAILABLE", False):
                return None

            parser_engine.set_language(path)
            tree = parser_engine.parser.parse(bytes(code, "utf8"))
            
            # 使用最简单的标识符查询
            query_str = "(class_declaration [(type_identifier) (identifier)] @name)"
            lang = parser_engine.JAVA_LANG if path.endswith(".java") else parser_engine.KOTLIN_LANG
            query = lang.query(query_str)
            captures = query.captures(tree.root_node)
            
            for node, tag in captures:
                if tag == "name":
                    # 处理 bytes 转换
                    text = node.text.decode('utf-8') if hasattr(node, 'text') else ""
                    res["class_name"] = text
                    break 
            return res if res["class_name"] else None
        except:
            return None

    def _discover_layout(self, code_str):
            """
            通过多种线索寻找布局 ID，增加对 ViewBinding 的支持
            """
            # 线索 1: 标准 R.layout.xxx
            r_layout_match = re.findall(r'R\.layout\.(\w+)', code_str)
            if r_layout_match:
                for l in r_layout_match:
                    if any(x in l for x in ["activity", "fragment", "dialog", "layout"]):
                        return l
                return r_layout_match[0]

            # 线索 2: ViewBinding (例如 ActivityMainBinding -> activity_main)
            # 匹配 XXXBinding，但排除常见的系统词
            binding_matches = re.findall(r'(\w+)Binding', code_str)
            for name in binding_matches:
                if name in ["View", "Item", "Data"]: continue # 排除干扰项
                
                # 将 ActivityMain 转换为 activity_main
                # 逻辑：在每个大写字母前加下划线，然后转小写
                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
                layout_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
                
                # 过滤掉常见的无用后缀
                layout_name = layout_name.replace("_binding", "")
                
                # 验证：如果转换后的名字出现在资源库中，就采用它
                # 注意：这里我们无法直接访问 loader，所以先返回名字，让 Analyzer 去校验
                return layout_name

            return None

    def _discover_menu(self, code_str):
        """检测代码中 inflate 了哪个菜单"""
        # 匹配 R.menu.xxxx
        match = re.search(r'R\.menu\.(\w+)', code_str)
        return match.group(1) if match else None


    def _extract_interactions(self, code):
        """
        增强版切片提取：支持简单的同文件函数追踪
        """
        keywords = ["Intent", "startActivity", "setOnClickListener", "setOnMenuItemClickListener", "show(", "inflate("]
        lines = code.split('\n')
        snippets = []
        
        # 1. 第一遍扫描：找出直接交互点
        for i, line in enumerate(lines):
            if any(k in line for k in keywords):
                # 记录这一块切片
                start = max(0, i - 2)
                end = min(len(lines), i + 10)
                snippets.append({
                    "line": i + 1,
                    "code_snippet": "\n".join(lines[start:end])
                })
                
                # 2. 函数追踪：寻找形如 -> launchAbout() 的本地函数调用
                # 匹配：字母开头跟括号，且不在关键词列表里
                call_match = re.search(r'([\w\d]+)\s*\((?!.*{)', line)
                if call_match:
                    func_name = call_match.group(1)
                    if func_name not in ["if", "when", "let", "apply", "run"] + keywords:
                        # 在当前文件中寻找该函数的定义: fun func_name(
                        trace_snippet = self._find_function_definition(code, func_name)
                        if trace_snippet:
                            snippets.append({
                                "line": "traced",
                                "source_func": func_name,
                                "code_snippet": f"/* Traced Definition of {func_name} */\n{trace_snippet}"
                            })
        return snippets


    def _find_function_definition(self, code, func_name):
        """在当前文件中寻找函数定义"""
        # 匹配 fun funcName( 或 void funcName(
        pattern = rf"(fun|void|private|public)\s+{func_name}\s*\("
        match = re.search(pattern, code)
        if match:
            start_idx = match.start()
            # 抓取函数开始后的 25 行（足以覆盖大多数跳转逻辑）
            lines = code[start_idx:].split('\n')
            return "\n".join(lines[:25])
        return None

