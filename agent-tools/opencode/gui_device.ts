import { tool } from "@opencode-ai/plugin"

// The session identity comes from OpenCode, never from model-provided arguments.
export default tool({
  description: "Observe or operate the Android device explicitly bound by the user to this conversation. Use exact UI selectors from observe, respect action budgets, and verify coverage/business results independently. launch is only for the app launcher/exported activity; navigate to internal activities through UI controls. A rejected action is recoverable: observe and retry with a better selector. No task binding means no device access.",
  args: {
    operation: tool.schema.enum(["observe", "act", "baseline", "after", "assertions", "status"]),
    action: tool.schema.object({
      kind: tool.schema.enum(["tap", "long_press", "key", "text", "scroll", "launch"]),
      selector: tool.schema.object({
        resource_id: tool.schema.string().optional(),
        text: tool.schema.string().optional(),
        description: tool.schema.string().optional(),
        target: tool.schema.enum(["self", "nearest_clickable_ancestor", "list_item"]).optional(),
      }).optional(),
      within: tool.schema.string().optional(),
      reason: tool.schema.string(),
      evidence: tool.schema.array(tool.schema.object({file_path: tool.schema.string(), line: tool.schema.number()})).optional(),
      key: tool.schema.number().optional(),
      text: tool.schema.string().optional(),
      direction: tool.schema.enum(["up", "down"]).optional(),
      component: tool.schema.string().optional(),
    }).optional().describe("For act only. Use selectors copied exactly from observe. launch requires component; key requires key; text requires text; scroll requires direction."),
  },
  async execute(args, context) {
    const token = process.env.GUI_AGENT_BRIDGE_TOKEN
    if (!token) throw new Error("GUI-Anything device bridge is not configured")
    const response = await fetch(`${process.env.GUI_AGENT_BRIDGE_URL || "http://127.0.0.1:8002"}/api/agent-tools`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-GUI-Agent-Token": token },
      body: JSON.stringify({session_id: context.sessionID, operation: args.operation,
        action: args.action || null}),
      signal: context.abort,
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Device operation rejected")
    return JSON.stringify(result)
  },
})
