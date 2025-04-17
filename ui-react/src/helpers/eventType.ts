import { AgentEvent, KnownEventType } from "../features/events/eventsApi";

// Type guard to check for a specific event type and narrow down the AgentEvent type.
export function isEventType<T extends KnownEventType>(type: T) {
  return (e: AgentEvent): e is Extract<AgentEvent, { event_type: T }> =>
    e.event_type === type;
}
