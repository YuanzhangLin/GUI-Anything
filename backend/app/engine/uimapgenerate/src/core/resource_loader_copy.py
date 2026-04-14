import os
from lxml import etree

class ResourceLoader:
    def __init__(self, project_root, main_source_set=None):
        self.project_root = project_root
        self.main_source_set = main_source_set
        self.strings = {}
        self.layouts = {}
        # 修复点：直接初始化带下划线的内部变量，不要给 property 赋值
        self._manifest_activities = set() 
        self.manifest_main_entry = None  # <--- 新增：用于存储入口 Activity 名

    def load_all(self):
        res_path = os.path.join(self.project_root, self.main_source_set, "res")
        print(f"📂 [ResourceLoader] 正在检查资源路径: {res_path}")
        if not os.path.exists(res_path):
            print(f"❌ [ResourceLoader] 路径不存在，请检查 config/project.yaml 中的 main_source_set")
            return
        
        manifest_path = os.path.join(self.project_root, self.main_source_set, "AndroidManifest.xml")

        # 1. 加载 Manifest 中的 Activity 白名单
        self._parse_manifest(manifest_path)
        
        # 2. 加载 Strings
        val_path = os.path.join(res_path, "values")
        if os.path.exists(val_path):
            for f in os.listdir(val_path):
                if "strings" in f and f.endswith(".xml"):
                    self._parse_strings(os.path.join(val_path, f))

        # 3. 加载 Layouts (处理嵌套)
        lay_path = os.path.join(res_path, "layout")
        if os.path.exists(lay_path):
            # 第一遍：解析基础文件
            for f in os.listdir(lay_path):
                if f.endswith(".xml"):
                    name = f.replace(".xml", "")
                    self.layouts[name] = self._parse_layout_file(os.path.join(lay_path, f))
            
            # 第二遍：处理 <include> 嵌套（递归平铺）
            self._resolve_layout_includes()

        print(f"✅ [ResourceLoader] 加载完成。已索引布局: {list(self.layouts.keys())[:5]}... 等共 {len(self.layouts)} 个")

    def _parse_manifest(self, path):
        if not os.path.exists(path): return
        
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
        
        # 寻找所有 activity 标签
        for activity in root.findall(".//activity"):
            # 获取 activity 的名字
            name = activity.get("{http://schemas.android.com/apk/res/android}name")
            if not name: continue
            
            # 处理名字的简写，例如 .MainActivity -> com.example.MainActivity
            short_name = name.split('.')[-1]
            self.manifest_activities.add(short_name)
            
            # --- 关键逻辑：寻找入口点 ---
            # 检查是否有 <intent-filter> 包含 MAIN 和 LAUNCHER
            is_main = False
            is_launcher = False
            
            for intent_filter in activity.findall("intent-filter"):
                for action in intent_filter.findall("action"):
                    if action.get("{http://schemas.android.com/apk/res/android}name") == "android.intent.action.MAIN":
                        is_main = True
                for category in intent_filter.findall("category"):
                    if category.get("{http://schemas.android.com/apk/res/android}name") == "android.intent.category.LAUNCHER":
                        is_launcher = True
            
            if is_main and is_launcher:
                self.manifest_main_entry = short_name # 记下大老板的名字
                
    def _parse_layout_file(self, path):
        elements = []
        try:
            tree = etree.parse(path)
            for node in tree.iter():
                # 处理普通控件
                node_id = node.get("{http://schemas.android.com/apk/res/android}id")
                if node_id:
                    elements.append({
                        "tag": "element",
                        "id": node_id.split("/")[-1],
                        "type": node.tag,
                        "text": self._resolve_string(node.get("{http://schemas.android.com/apk/res/android}text"))
                    })
                # 处理 <include> 标签
                if node.tag == "include":
                    layout_ref = node.get("layout") 
                    if layout_ref:
                        elements.append({
                            "tag": "include",
                            "layout_name": layout_ref.split("/")[-1]
                        })
        except: pass
        return elements

    def _resolve_layout_includes(self):
        """递归展开 layout 中的 include 内容"""
        def flatten(elements):
            new_list = []
            for el in elements:
                if el["tag"] == "include":
                    sub_layout = self.layouts.get(el["layout_name"], [])
                    # 递归展开子布局并合并
                    new_list.extend(flatten(sub_layout))
                else:
                    new_list.append(el)
            return new_list

        for name in self.layouts:
            self.layouts[name] = flatten(self.layouts[name])

    def _resolve_string(self, val):
            if not val: return ""
            # 处理 @string/abc 或 @android:string/abc
            if val.startswith("@string/") or ":string/" in val:
                string_key = val.split("/")[-1]
                # 如果在 strings 字典里找到了就替换，找不到保留原样
                return self.strings.get(string_key, val)
            return val

    def _parse_strings(self, path):
        """解析字符串，支持普通 string 和 string-array"""
        try:
            tree = etree.parse(path)
            # 处理 <string name="xxx">内容</string>
            for node in tree.xpath("//string"):
                name = node.get("name")
                if name:
                    self.strings[name] = node.text if node.text else ""
            
            # 处理 <string-array name="xxx">... (可选，Simple-Calendar 常用)
            for node in tree.xpath("//string-array"):
                name = node.get("name")
                items = node.xpath("./item/text()")
                if name and items:
                    self.strings[name] = "|".join(items)
        except: pass

    @property
    def manifest_activities(self):
        """
        返回 Manifest 中定义的 Activity 集合。
        """
        return getattr(self, "_manifest_activities", set())

    def get_layout_elements(self, layout_name):
        """
        根据布局名称获取 UI 元素列表。
        """
        if not layout_name:
            return []
        return self.layouts.get(layout_name, [])


