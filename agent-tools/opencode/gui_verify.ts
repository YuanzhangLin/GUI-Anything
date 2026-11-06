import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Verify the bound device task independently. Use baseline before actions, after when finished, assertions for UI/business checks, and status for the current Run state.",
  args: { operation: tool.schema.enum(["baseline", "after", "assertions", "status"]) },
  async execute(args, context) {
    const token = process.env.GUI_AGENT_BRIDGE_TOKEN
    if (!token) throw new Error("GUI-Anything device bridge is not configured")
    const response = await fetch(`${process.env.GUI_AGENT_BRIDGE_URL || "http://127.0.0.1:8002"}/api/agent-tools`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-GUI-Agent-Token": token },
      body: JSON.stringify({ session_id: context.sessionID, operation: args.operation, action: null }), signal: context.abort,
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Device verification rejected")
    return JSON.stringify(result)
  },
})
