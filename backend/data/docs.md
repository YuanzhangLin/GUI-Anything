# GUI-Anything 使用手册

## 产品目标

图谱以用户能看见的页面和操作路径为主体。Activity、Fragment、布局文件和导航 XML 是静态证据。Fast 生成的页面属于候选页面，未经运行时验证；不要把静态推断说成真实用户操作已被确认。

## 查看 Demo

登录页可直接打开固定 Demo。图来自 Activity Diary 源码的一次 Fast 静态扫描；它只包含图谱和证据位置，不包含 APK、反编译文件、Issue 或对话结果。官网选取其中部分路径展示。

## 分析真实项目

1. 管理员在控制台下载已配置的 Android 仓库，或上传 APK。APK 由后端 JADX 反编译。
2. 打开地图，点击「Fast 出图」。此模式不调用大模型；当前识别 Manifest Activity、Navigation XML 与部分标签页 Fragment、显式 Intent 路径，以及布局和菜单 XML 中的元素候选。
3. 点击页面查看按钮、菜单项、输入框、列表、展示元素，以及它承载/被承载的页面；点击路径查看触发元素（若已定位）、代码位置及规则来源。`containments` 是承载关系，`transitions` 是用户可走的路径，二者不等同。没有路径或元素不代表运行时不存在。
4. 需要解释业务逻辑时，在对话区选用 OpenCode、内置 Agent 或已配置的自定义 Agent。平台会把当前图摘要传给 Agent。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| 地图为空 | 先确认项目源码或 APK 已就绪，再点击「Fast 出图」。 |
| APK 导入失败 | 检查文件是否为含 Manifest 和 DEX 的 APK；后台需要 JADX。 |
| Agent 不可用 | 检查后端是否安装对应 Agent，以及模型凭证和环境变量。Fast 出图仍可使用。 |
| 静态图缺少页面 | 当前规则只覆盖能从 Manifest、Navigation XML 和显式 Intent 识别的路径。 |
