export type Page =
  | { id: "overview" }
  | { id: "new-evaluation" }
  | { id: "result"; runId: string }
  | { id: "history" }
  | { id: "analytics" }
  | { id: "providers" };
