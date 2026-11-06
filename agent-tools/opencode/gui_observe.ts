import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Observe the Android device bound to this conversation. Call this before every action and after any rejected action. Returns the current Activity, screenshot asset and exact UI nodes/selectors. Takes no arguments.",
  args: {},
  async execute(_args, context) {
    return bridge(context, "observe")
  },
})

async function bridge(context: any, operation: string, action: any = null) {
  const token = process.env.GUI_AGENT_BRIDGE_TOKEN
  if (!token) throw new Error("GUI-Anything device bridge is not configured")
  const response = await fetch(`${process.env.GUI_AGENT_BRIDGE_URL || "http://127.0.0.1:8002"}/api/agent-tools`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-GUI-Agent-Token": token },
    body: JSON.stringify({ session_id: context.sessionID, operation, action }), signal: context.abort,
  })
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Device observation rejected")
  return JSON.stringify(result)
}
