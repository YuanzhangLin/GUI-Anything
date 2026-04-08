# 🛡️ GUI-Anything 深度分析手册

> **提示**：本工具主要用于辅助 Android 逆向工程与源码审计。所有分析结果基于静态提取的控制流图（CFG）。

---

## 1. 核心架构说明
GUI-Anything 通过解析 APK 产生的 `Activity/Fragment` 关系，构建了一个多层级的交互模型。
[Image of an architectural diagram of a static analysis tool for Android apps]

### 节点类型定义
- **Launcher Activity** (蓝色): 应用的物理入口。
- **Standard Activity** (灰色): 常规业务承载页面。
- **Exported Activity** (红色警告): 具有外部调用风险的组件。

---

## 2. 如何进行深度分析？
您可以利用 **DeepSeek-V3** 的逻辑推理能力，结合图谱进行以下操作：

### 🔍 场景 A：权限追踪
**提问示例**：
`"分析该应用在进入 Simple-Dialer 拨号页面前，是否进行了运行时权限检查？"`

### 🔗 场景 B：逻辑盲区扫描
**提问示例**：
`"图中显示 MainActivity 可以直接跳转到 PayActivity，这是否绕过了身份验证逻辑？"`

---

## 3. 常见问题 (FAQ)
| 问题 | 解决方法 |
| :--- | :--- |
| 地图显示为空 | 请确认 `backend/data/` 目录下存在对应的 JSON 文件。 |
| AI 回复超时 | DeepSeek 正在处理大规模图谱上下文，请开启流式输出。 |
| 登录失效 | 为了安全，Session 会在 24 小时后过期。 |