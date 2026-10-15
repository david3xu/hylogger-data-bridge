// Decode observed backend return status without inferring delivery from a saved decision.
export function returnLabel(value: unknown): string {
  if (!value || typeof value !== "object" || !("phase" in value)) return "Chat status unavailable";
  const labels: Record<string, string> = {
    manual: "Chat is not connected · explicit follow-up is available",
    connected: "Chat connected · your next decision will notify Codex",
    pending: "Decision saved · preparing chat notification",
    queued: "Chat notified · waiting for the investigation to continue",
    uncertain: "Notification receipt uncertain · check the chat before retrying",
    working: "The investigation is continuing",
    failed: "Chat return failed · use explicit follow-up",
    completed: "Continuation completed · new evidence is ready",
  };
  return typeof value.phase === "string"
    ? labels[value.phase] || "Chat status unavailable"
    : "Chat status unavailable";
}
