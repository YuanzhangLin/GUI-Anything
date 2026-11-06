import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Perform exactly one action on the Android device bound to this conversation. First call gui_observe and copy an exact selector. Example tap: {kind:'tap',selector:{text:'About',target:'nearest_clickable_ancestor'},reason:'Open About through visible navigation'}. Key uses key 4, 66, or 82. Text requires a focused editor. Launch is only for the exported launcher Activity.",
  args: {
    kind: tool.schema.enum(["tap", "long_press", "key", "text", "scroll", "launch"]),
    selector: tool.schema.object({
      resource_id: tool.schema.string().optional(), text: tool.schema.string().optional(),
      description: tool.schema.string().optional(),
      target: tool.schema.enum(["self", "nearest_clickable_ancestor", "list_item"]).optional(),
    }).optional(),
    within: tool.schema.string().optional(), reason: tool.schema.string(),
    evidence: tool.schema.array(tool.schema.object({ file_path: tool.schema.string(), line: tool.schema.number() })).optional(),
    key: tool.schema.number().optional(), text: tool.schema.string().optional(),
    direction: tool.schema.enum(["up", "down"]).optional(), component: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const token = process.env.GUI_AGENT_BRIDGE_TOKEN
    if (!token) throw new Error("GUI-Anything device bridge is not configured")
    const response = await fetch(`${process.env.GUI_AGENT_BRIDGE_URL || "http://127.0.0.1:8002"}/api/agent-tools`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-GUI-Agent-Token": token },
      body: JSON.stringify({ session_id: context.sessionID, operation: "act", action: args }), signal: context.abort,
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Device action rejected")
    return JSON.stringify(result)
  },
})
