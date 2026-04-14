import os
from lxml import etree
import xml.etree.ElementTree as ET

class ResourceLoader:
    def __init__(self, project_root, main_source_set=None):
        self.project_root = project_root
        self.main_source_set = main_source_set
        self.strings = {}
        self.layouts = {}
        self.menus = {} 
        self._manifest_activities = set() 
        self.manifest_main_entry = None

        # --- 修复点：修正 Android 命名空间的 URI (必须是 res/android) ---
        self.NS_ANDROID = "http://schemas.android.com/apk/res/android"
        self.NS_APP = "http://schemas.android.com/apk/res-auto"

    def load_all(self):
        res_path = os.path.join(self.project_root, self.main_source_set, "res")
        print(f"📂 [ResourceLoader] 正在检查资源路径: {res_path}")
        if not os.path.exists(res_path):
            print(f"❌ [ResourceLoader] 路径不存在，请检查配置")
            return
        
        manifest_path = os.path.join(self.project_root, self.main_source_set, "AndroidManifest.xml")

        # 1. 加载 Manifest
        self._parse_manifest(manifest_path)
        
        # 2. 加载 Strings
        val_path = os.path.join(res_path, "values")
        if os.path.exists(val_path):
            for f in os.listdir(val_path):
                if "strings" in f and f.endswith(".xml"):
                    self._parse_strings(os.path.join(val_path, f))

        # 3. 加载 Menus
        menu_path = os.path.join(res_path, "menu")
        if os.path.exists(menu_path):
            for f in os.listdir(menu_path):
                if f.endswith(".xml"):
                    name = f.replace(".xml", "")
                    self.menus[name] = self._parse_menu_file(os.path.join(menu_path, f))
        print(f"✅ [ResourceLoader] 菜单加载完成。已索引菜单: {list(self.menus.keys())[:5]}... 等共 {len(self.menus)} 个")


        
        # 4. 加载 Layouts
        lay_path = os.path.join(res_path, "layout")
        if os.path.exists(lay_path):
            # 第一遍：解析基础文件
            for f in os.listdir(lay_path):
                if f.endswith(".xml"):
                    name = f.replace(".xml", "")
                    self.layouts[name] = self._parse_layout_file(os.path.join(lay_path, f))
            
            # 第二遍：递归处理 <include> 嵌套
            self._resolve_layout_includes()

        print(f"✅ [ResourceLoader] 加载完成。")
        print(f"   - 活动 (Activities): {len(self._manifest_activities)} 个")
        print(f"   - 布局 (Layouts): {len(self.layouts)} 个")
        print(f"   - 菜单 (Menus): {len(self.menus)} 个")

    def _parse_manifest(self, path):
        if not os.path.exists(path): return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            for activity in root.findall(".//activity"):
                # 使用正确的命名空间获取 android:name
                name = activity.get(f"{{{self.NS_ANDROID}}}name")
                if not name: continue
                
                short_name = name.split('.')[-1]
                self._manifest_activities.add(short_name)
                
                # 寻找入口点
                is_main = False
                is_launcher = False
                for intent_filter in activity.findall("intent-filter"):
                    for action in intent_filter.findall("action"):
                        if action.get(f"{{{self.NS_ANDROID}}}name") == "android.intent.action.MAIN":
                            is_main = True
                    for category in intent_filter.findall("category"):
                        if category.get(f"{{{self.NS_ANDROID}}}name") == "android.intent.category.LAUNCHER":
                            is_launcher = True
                
                if is_main and is_launcher:
                    self.manifest_main_entry = short_name
        except Exception as e:
            print(f"⚠️ 解析 Manifest 出错: {e}")

    def _parse_menu_file(self, path):
        """解析菜单文件，确保捕获 showAsAction"""
        items = []
        try:
            tree = etree.parse(path)
            for node in tree.xpath("//item"):
                item_id = node.get(f"{{{self.NS_ANDROID}}}id")
                item_title = node.get(f"{{{self.NS_ANDROID}}}title")
                
                # 关键：showAsAction 可能在 android: 下，也可能在 app: 下
                show_as_action = node.get(f"{{{self.NS_APP}}}showAsAction") or \
                                 node.get(f"{{{self.NS_ANDROID}}}showAsAction") or \
                                 "never" # 默认值
                
                if item_id:
                    items.append({
                        "tag": "menu_item",
                        "id": item_id.split("/")[-1],
                        "type": "MenuItem",
                        "text": self._resolve_string(item_title),
                        # 确保这个字段被存入字典
                        "showAsAction": show_as_action, 
                        "is_action_button": "always" in show_as_action or "ifRoom" in show_as_action
                    })
        except: pass
        return items

    def _parse_layout_file(self, path):
        elements = []
        try:
            tree = etree.parse(path)
            for node in tree.iter():
                # 处理 ID
                node_id = node.get(f"{{{self.NS_ANDROID}}}id")
                node_text = node.get(f"{{{self.NS_ANDROID}}}text")
                # 关联 Menu
                menu_ref = node.get(f"{{{self.NS_APP}}}menu")
                
                if node_id:
                    element_data = {
                        "tag": "element",
                        "id": node_id.split("/")[-1],
                        "type": str(node.tag),
                        "text": self._resolve_string(node_text)
                    }
                    if menu_ref:
                        element_data["associated_menu"] = menu_ref.split("/")[-1]
                    
                    elements.append(element_data)

                # 处理 <include>
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
        def flatten(elements, depth=0):
            if depth > 10: return elements 
            new_list = []
            for el in elements:
                if el.get("tag") == "include":
                    sub_layout = self.layouts.get(el["layout_name"], [])
                    new_list.extend(flatten(sub_layout, depth + 1))
                else:
                    new_list.append(el)
            return new_list

        for name in list(self.layouts.keys()):
            self.layouts[name] = flatten(self.layouts[name])

    def _resolve_string(self, val):
        if not val: return ""
        if val.startswith("@string/") or ":string/" in val:
            string_key = val.split("/")[-1]
            return self.strings.get(string_key, val)
        return val

    def _parse_strings(self, path):
        try:
            tree = etree.parse(path)
            for node in tree.xpath("//string"):
                name = node.get("name")
                if name:
                    self.strings[name] = node.text if node.text else ""
            
            for node in tree.xpath("//string-array"):
                name = node.get("name")
                items = node.xpath("./item/text()")
                if name and items:
                    self.strings[name] = "|".join(items)
        except: pass

    @property
    def manifest_activities(self):
        return self._manifest_activities

    def get_layout_elements(self, layout_name):
        """
        获取布局元素。
        当展开 MenuItem 时，确保所有捕获到的属性都传递下去。
        """
        if not layout_name or layout_name not in self.layouts:
            return []
        
        base_elements = self.layouts[layout_name]
        final_elements = []
        
        for el in base_elements:
            final_elements.append(el)
            
            if "associated_menu" in el:
                menu_name = el["associated_menu"]
                menu_items = self.menus.get(menu_name, [])
                for mi in menu_items:
                    # 使用 .copy() 确保 mi 里的所有 key (包括 showAsAction) 都被复制
                    menu_el = mi.copy()
                    menu_el["parent_id"] = el["id"]
                    # 这里的 location 可以根据你的需要设置
                    menu_el["location"] = "menu"
                    final_elements.append(menu_el)
                    
        return final_elements