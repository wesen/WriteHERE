import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import {
  nodeAdded as graphNodeAdded,
  nodeUpdated as graphNodeUpdated,
  edgeAdded as graphEdgeAdded,
} from "../graph/graphSlice"; // Import graph actions

// Define the structure for a single message in the prompt
export interface LlmMessage {
  role: "system" | "user" | "assistant" | string; // Allow other roles potentially
  content: string;
}

// Define the shape of an event based on the documentation
export interface StepStartedPayload {
  step: number;
  node_id: string;
  node_goal: string;
  root_id: string;
}

export interface StepFinishedPayload {
  step: number;
  node_id: string;
  action_name: string;
  status_after: string;
  duration_seconds: number;
}

export interface NodeStatusChangePayload {
  node_id: string;
  node_goal: string; // Note: Not strictly needed for rendering but present in python
  old_status: string;
  new_status: string;
  step?: number | null;
}

export interface LlmCallStartedPayload {
  agent_class: string;
  model: string;
  prompt: LlmMessage[]; // Changed to array of messages
  prompt_preview: string;
  step?: number | null; // Added optional step
  node_id?: string | null;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  error?: string | null; // Optional
  node_id?: string | null; // Optional
  token_usage?: TokenUsage | null; // Optional
}

export interface LlmCallCompletedPayload {
  agent_class: string;
  model: string;
  duration_seconds: number;
  response: string; // Changed to full response content
  result_summary: string;
  error?: string | null; // Optional
  step?: number | null; // Added optional step
  node_id?: string | null; // Optional
  token_usage?: TokenUsage | null; // Optional
}

export interface ToolInvokedPayload {
  tool_name: string;
  api_name: string;
  args_summary: string;
  node_id?: string | null; // Optional
}

export interface ToolReturnedPayload {
  tool_name: string;
  api_name: string;
  state: string;
  duration_seconds: number;
  result_summary: string;
  error?: string | null; // Optional
  node_id?: string | null; // Optional
}

// New Node/Graph Event Payloads

export interface NodeCreatedPayload {
  node_id: string;
  node_nid: string;
  node_type: string;
  task_type: string;
  task_goal: string;
  layer: number;
  outer_node_id?: string | null;
  root_node_id: string;
  initial_parent_nids: string[];
  step?: number | null;
}

export interface PlanReceivedPayload {
  node_id: string;
  raw_plan: any[]; // Using any[] since plan structure can vary
  step?: number | null;
}

export interface NodeAddedPayload {
  graph_owner_node_id: string;
  added_node_id: string;
  added_node_nid: string;
  step?: number | null;
}

export interface EdgeAddedPayload {
  graph_owner_node_id: string;
  parent_node_id: string;
  child_node_id: string;
  parent_node_nid: string;
  child_node_nid: string;
  step?: number | null;
}

export interface InnerGraphBuiltPayload {
  node_id: string;
  node_count: number;
  edge_count: number;
  node_ids: string[];
  step?: number | null;
}

export interface NodeResultAvailablePayload {
  node_id: string;
  action_name: string;
  result_summary: string;
  step?: number | null;
}

// Define a union of known event type strings
export type KnownEventType =
  | "step_started"
  | "step_finished"
  | "node_status_changed"
  | "llm_call_started"
  | "llm_call_completed"
  | "tool_invoked"
  | "tool_returned"
  | "node_created"
  | "plan_received"
  | "node_added"
  | "edge_added"
  | "inner_graph_built"
  | "node_result_available";

// Discriminated Union for all possible events
export type AgentEvent =
  | {
      event_id: string;
      timestamp: string;
      event_type: "step_started";
      run_id?: string | null;
      payload: StepStartedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "step_finished";
      run_id?: string | null;
      payload: StepFinishedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "node_status_changed";
      run_id?: string | null;
      payload: NodeStatusChangePayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "llm_call_started";
      run_id?: string | null;
      payload: LlmCallStartedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "llm_call_completed";
      run_id?: string | null;
      payload: LlmCallCompletedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "tool_invoked";
      run_id?: string | null;
      payload: ToolInvokedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "tool_returned";
      run_id?: string | null;
      payload: ToolReturnedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "node_created";
      run_id?: string | null;
      payload: NodeCreatedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "plan_received";
      run_id?: string | null;
      payload: PlanReceivedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "node_added";
      run_id?: string | null;
      payload: NodeAddedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "edge_added";
      run_id?: string | null;
      payload: EdgeAddedPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "inner_graph_built";
      run_id?: string | null;
      payload: InnerGraphBuiltPayload;
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "node_result_available";
      run_id?: string | null;
      payload: NodeResultAvailablePayload;
    }
  // Fallback for unknown event types, ensuring it doesn't overlap with known types
  | {
      event_id: string;
      timestamp: string;
      run_id?: string | null; // Add run_id for consistency
      event_type: Exclude<string, KnownEventType>; // Use Exclude here
      payload: Record<string, unknown>;
    };

// Interface for the data received from the WebSocket API (used by RTK Query)
export interface EventsApiResponse {
  status: ConnectionStatus;
  events: AgentEvent[];
}

export enum ConnectionStatus {
  Connecting = "Connecting",
  Connected = "Connected",
  Disconnected = "Disconnected",
}

// Define a service using a base query and expected endpoints
export const eventsApi = createApi({
  reducerPath: "eventsApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/" }), // Use root base URL
  endpoints: (builder) => ({
    getEvents: builder.query<
      {
        events: AgentEvent[];
        status: ConnectionStatus;
      },
      void
    >({
      query: () => "/api/events", // Specify the full path here
      async onQueryStarted(arg, { queryFulfilled }) {
        try {
          const result = await queryFulfilled;
          console.log("[eventsApi] HTTP fetch result:", result);
        } catch (err) {
          console.error("[eventsApi] HTTP fetch error:", err);
        }
      },
      async onCacheEntryAdded(
        _,
        { updateCachedData, cacheEntryRemoved, dispatch }
      ) {
        // Set initial status
        updateCachedData((draft) => {
          draft.status = ConnectionStatus.Connecting;
          if (!draft.events) {
            draft.events = [];
          }
        });

        console.log("[eventsApi] Attempting WebSocket connection...");
        const wsProtocol =
          window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/events`; // Use host instead of hostname and port
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[eventsApi] WebSocket connection established");
          updateCachedData((draft) => {
            draft.status = ConnectionStatus.Connected;
          });
        };

        ws.onmessage = (event) => {
          let msg: AgentEvent; // Declare msg here
          try {
            msg = JSON.parse(event.data); // Assign here
            console.log("[eventsApi] Received event:", msg);

            /* 1️⃣  keep the audit log */
            updateCachedData((draft) => {
              // Prepend the new event to maintain chronological order (newest first)
              draft.events.unshift(msg);
              // Optional: Limit the number of stored events
              const maxEvents = 200;
              if (draft.events.length > maxEvents) {
                draft.events.length = maxEvents; // Keep only the latest N events
              }
            });

            /* 2️⃣  mirror graph‑relevant events */
            switch (msg.event_type) {
              case "node_created": {
                // Ensure payload is correctly typed
                const p = msg.payload as NodeCreatedPayload;
                console.log(
                  `[Graph] Dispatching nodeAdded: ${p.node_id} (${p.node_nid})`
                );
                dispatch(
                  graphNodeAdded({
                    id: p.node_id,
                    nid: p.node_nid,
                    type: p.node_type,
                    goal: p.task_goal,
                    layer: p.layer,
                    taskType: p.task_type,
                  })
                );
                break;
              }
              case "node_added": {
                // "node_added" only tells you that a *graph* gained a node.
                // If you actually know the node details from elsewhere you can
                // upsert here; otherwise ignore or dispatch a minimal add.
                // Example: dispatch(graphNodeAdded({ id: (msg.payload as NodeAddedPayload).added_node_id, ... other known defaults ... }))
                break;
              }
              case "edge_added": {
                const p = msg.payload as EdgeAddedPayload;
                const edgeId = `${p.parent_node_id}-${p.child_node_id}`;
                console.log(`[Graph] Dispatching edgeAdded: ${edgeId}`);
                dispatch(
                  graphEdgeAdded({
                    id: edgeId, // Use pre-calculated ID
                    parent: p.parent_node_id,
                    child: p.child_node_id,
                  })
                );
                break;
              }
              case "node_status_changed": {
                const p = msg.payload as NodeStatusChangePayload;
                console.log(
                  `[Graph] Dispatching nodeUpdated: ${p.node_id}, Status: ${p.new_status}`
                );
                dispatch(
                  graphNodeUpdated({
                    id: p.node_id,
                    changes: { status: p.new_status },
                  })
                );
                break;
              }
              // Handle other event types if they should affect the graph
            }
          } catch (e) {
            console.error(
              "[eventsApi] Failed to parse incoming message or dispatch graph action:",
              event.data,
              e
            );
          }
        };

        ws.onerror = (error) => {
          console.error("[eventsApi] WebSocket error:", error);
          // Status might be updated in onclose, or you can update here
          updateCachedData((draft) => {
            draft.status = ConnectionStatus.Disconnected;
          });
        };

        ws.onclose = (event) => {
          console.log(
            `[eventsApi] WebSocket connection closed (Code: ${event.code}, Reason: ${event.reason})`
          );
          updateCachedData((draft) => {
            draft.status = ConnectionStatus.Disconnected;
          });
          // Note: No automatic reconnection logic here. RTK Query will re-run
          // onCacheEntryAdded if the component re-subscribes.
        };

        // Wait for the cache entry to be removed (component unmounts)
        await cacheEntryRemoved;

        // Close the WebSocket connection when the cache entry is removed
        ws.close();
        console.log(
          "[eventsApi] WebSocket connection closed due to cache removal"
        );
      },
    }),
  }),
});

// Export hooks for usage in functional components, which are
// auto-generated based on the defined endpoints
export const { useGetEventsQuery } = eventsApi;
