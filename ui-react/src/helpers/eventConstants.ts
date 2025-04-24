// Event type to badge variant mapping
export const eventTypeBadgeVariant: Record<string, string> = {
  step_started: "primary",
  step_finished: "success",
  node_status_changed: "info",
  llm_call_started: "warning",
  llm_call_completed: "warning",
  tool_invoked: "secondary",
  tool_returned: "secondary",
  node_created: "info", // Changed from purple-subtle for consistency
  plan_received: "info",
  node_added: "success",
  edge_added: "secondary",
  inner_graph_built: "primary",
  node_result_available: "warning",
  default: "light",
};

// Status color mapping (using Bootstrap text colors)
export const statusColorMap: { [key: string]: string } = {
  NOT_READY: "text-secondary",
  READY: "text-primary",
  PLANNING: "text-info",
  PLANNING_POST_REFLECT: "text-info",
  DOING: "text-warning",
  FINISH: "text-success",
  FAILED: "text-danger",
  // Add any other potential statuses seen
};
