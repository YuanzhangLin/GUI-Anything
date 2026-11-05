import { tool } from "@opencode-ai/plugin"

// The session identity comes from OpenCode, never from model-provided arguments.
export default tool({
  description: "Observe or operate the Android device explicitly bound by the user to this conversation. Use exact UI selectors from observe, respect action budgets, and verify coverage/business results independently. No task binding means no device access.",
  args: {
    operation: tool.schema.enum(["observe", "act", "baseline", "after", "assertions", "status"]),
    action: tool.schema.string().optional().describe("For act only: a JSON action object accepted by GUI-Anything (tap, long_press, key, text, scroll, launch); never raw shell commands."),
  },
  async execute(args, context) {
    const token = process.env.GUI_AGENT_BRIDGE_TOKEN
    if (!token) throw new Error("GUI-Anything device bridge is not configured")
    const response = await fetch(`${process.env.GUI_AGENT_BRIDGE_URL || "http://127.0.0.1:8002"}/api/agent-tools`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-GUI-Agent-Token": token },
      body: JSON.stringify({session_id: context.sessionID, operation: args.operation,
        action: args.action ? JSON.parse(args.action) : null}),
      signal: context.abort,
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Device operation rejected")
    return JSON.stringify(result)
  },
})
