import React from 'react';
import { Card, Badge } from 'react-bootstrap'; // Keep only necessary imports
import { AgentEvent, LlmMessage } from '../features/events/eventsApi';
import { isEventType } from '../helpers/eventType';
import { ArrowRight } from 'lucide-react';
import CodeHighlighter from './SyntaxHighlighter';

// --- Copied & Adapted from EventDetailModal.tsx --- 

// Status color mapping (using Bootstrap text colors)
const statusColorMap: { [key: string]: string } = {
  NOT_READY: 'text-secondary',
  READY: 'text-primary',
  PLANNING: 'text-info',
  PLANNING_POST_REFLECT: 'text-info',
  DOING: 'text-warning',
  FINISH: 'text-success',
  FAILED: 'text-danger',
};

// Helper to format and truncate text previews
const formatPreview = (text: string, maxLength: number = 500): string => {
  if (!text) return '';
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
};

// Render the LLM prompt messages (removed outer div and adjusted styling)
const renderPromptMessages = (messages: LlmMessage[]) => {
  return (
    <>
      {messages.map((message, index) => (
        <div key={index} className={`message message-${message.role} mb-2 p-2 rounded border`}>
          <div className="message-header mb-1">
            <Badge bg={message.role === 'system' ? 'secondary' : message.role === 'assistant' ? 'success' : 'primary'} className="text-uppercase">
              {message.role}
            </Badge>
          </div>
          <div className="message-content">
            <CodeHighlighter
              code={message.content}
              language="markdown"
              maxHeight="300px"
              showLineNumbers={false}
            />
          </div>
        </div>
      ))}
    </>
  );
};

// Render the summary content based on event type (mostly copied, removed some outer cards)
const renderSummaryContent = (event: AgentEvent) => {
  // ... (Keep all the `if (isEventType(...))` blocks from EventDetailModal.tsx)
  // --- Start of copied content --- 
    if (isEventType('step_started')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>Step Information</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Step:</strong> {event.payload.step}</small></p>
                <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>
              </div>
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Root ID:</strong> {event.payload.root_id}</small></p>
              </div>
            </div>
          </div>
          <div>
            <strong>Node Goal</strong>
            <pre className="bg-light p-2 rounded small mt-1">{event.payload.node_goal}</pre>
          </div>
        </>
      );
    }

    if (isEventType('step_finished')(event)) {
      return (
        <>
          <strong>Step Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Step:</strong> {event.payload.step}</small></p>
              <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>
              <p className="mb-1"><small><strong>Action:</strong> {event.payload.action_name}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Status After:</strong> <span className={statusColorMap[event.payload.status_after] || ''}>{event.payload.status_after}</span></small></p>
              <p className="mb-1"><small><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</small></p>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('node_status_changed')(event)) {
      return (
        <>
          <strong>Status Change Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>
              <p className="mb-1"><small><strong>Node Goal:</strong> {event.payload.node_goal}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Status Change:</strong> 
                <span className={statusColorMap[event.payload.old_status] || ''}> {event.payload.old_status}</span>
                <ArrowRight size={12} className="mx-1" />
                <span className={statusColorMap[event.payload.new_status] || ''}>{event.payload.new_status}</span></small>
              </p>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('llm_call_started')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>LLM Call Information</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Agent Class:</strong> {event.payload.agent_class}</small></p>
                <p className="mb-1"><small><strong>Model:</strong> {event.payload.model}</small></p>
              </div>
              <div className="col-md-6">
                {event.payload.step !== undefined && <p className="mb-1"><small><strong>Step:</strong> {event.payload.step}</small></p>}
                {event.payload.node_id && <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>}
              </div>
            </div>
          </div>
          <div>
            <strong>Prompt Preview</strong>
            <CodeHighlighter
              code={formatPreview(event.payload.prompt_preview)}
              language="markdown"
              maxHeight="250px"
              className="mt-1"
            />
            {/* TODO: Add button/logic to show full prompt if needed */}
          </div>
        </>
      );
    }

    if (isEventType('llm_call_completed')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>LLM Response Information</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Agent Class:</strong> {event.payload.agent_class}</small></p>
                <p className="mb-1"><small><strong>Model:</strong> {event.payload.model}</small></p>
                <p className="mb-1"><small><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</small></p>
              </div>
              <div className="col-md-6">
                {event.payload.step !== undefined && <p className="mb-1"><small><strong>Step:</strong> {event.payload.step}</small></p>}
                {event.payload.node_id && <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>}
                {event.payload.token_usage && (
                  <p className="mb-1">
                    <small><strong>Tokens:</strong> {event.payload.token_usage.prompt_tokens} prompt + {event.payload.token_usage.completion_tokens} completion</small>
                  </p>
                )}
              </div>
            </div>
            {event.payload.error && (
              <div className="alert alert-danger mt-2 small">
                <strong>Error:</strong> {event.payload.error}
              </div>
            )}
          </div>
          <div>
            <strong>Response Preview</strong>
            <CodeHighlighter
              code={formatPreview(event.payload.response)}
              language="markdown"
              maxHeight="250px"
              className="mt-1"
            />
            {/* TODO: Add button/logic to show full response if needed */}
          </div>
        </>
      );
    }

    if (isEventType('tool_invoked')(event)) {
      return (
        <>
          <strong>Tool Invocation Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Tool Name:</strong> {event.payload.tool_name}</small></p>
              <p className="mb-1"><small><strong>API:</strong> {event.payload.api_name}</small></p>
            </div>
            <div className="col-md-6">
              {event.payload.node_id && <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>}
            </div>
          </div>
          <div className="mt-2">
            <strong>Arguments:</strong>
            <CodeHighlighter
              code={event.payload.args_summary}
              language="json"
              maxHeight="200px"
              className="mt-1"
            />
          </div>
        </>
      );
    }

    if (isEventType('tool_returned')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>Tool Return Details</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Tool Name:</strong> {event.payload.tool_name}</small></p>
                <p className="mb-1"><small><strong>API:</strong> {event.payload.api_name}</small></p>
              </div>
              <div className="col-md-6">
                <p className="mb-1">
                  <small><strong>State:</strong> 
                  <span className={event.payload.state === 'SUCCESS' ? 'text-success' : 'text-danger'}> {event.payload.state}</span></small>
                </p>
                <p className="mb-1"><small><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</small></p>
                {event.payload.node_id && <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>}
              </div>
            </div>
            {event.payload.error && (
              <div className="alert alert-danger mt-2 small">
                <strong>Error:</strong> {event.payload.error}
              </div>
            )}
          </div>
          <div>
            <strong>Result</strong>
            <CodeHighlighter
              code={event.payload.result_summary}
              language="json"
              maxHeight="200px"
              className="mt-1"
            />
          </div>
        </>
      );
    }

    if (isEventType('node_created')(event)) {
      return (
        <>
          <strong>Node Creation Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>
              <p className="mb-1"><small><strong>Node NID:</strong> {event.payload.node_nid}</small></p>
              <p className="mb-1"><small><strong>Node Type:</strong> {event.payload.node_type}</small></p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Layer:</strong> {event.payload.layer}</small></p>
              <p className="mb-1"><small><strong>Outer Node ID:</strong> {event.payload.outer_node_id || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Root Node ID:</strong> {event.payload.root_node_id}</small></p>
            </div>
          </div>
          <div className="mt-2">
            <p className="mb-1"><small><strong>Goal:</strong> {event.payload.task_goal}</small></p>
            <p className="mb-1"><small><strong>Initial Parent NIDs:</strong> {event.payload.initial_parent_nids?.join(', ') || 'None'}</small></p>
          </div>
        </>
      );
    }

    if (isEventType('plan_received')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>Plan Information</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Node ID:</strong> {event.payload.node_id}</small></p>
                <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              </div>
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Plan Items:</strong> {event.payload.raw_plan?.length || 0}</small></p>
                <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
              </div>
            </div>
          </div>

          <div>
            <strong>Plan Structure</strong>
            <CodeHighlighter
              code={JSON.stringify(event.payload.raw_plan, null, 2)}
              language="json"
              maxHeight="300px"
              showLineNumbers={true}
              className="mt-1"
            />
          </div>
        </>
      );
    }

    if (isEventType('node_added')(event)) {
      return (
        <>
          <strong>Node Added Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Graph Owner Node:</strong> {event.payload.graph_owner_node_id?.substring(0, 8) || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Added Node ID:</strong> {event.payload.added_node_id?.substring(0, 8) || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Added Node NID:</strong> {event.payload.added_node_nid}</small></p>
              <p className="mb-1"><small><strong>Step:</strong> {event.payload.step || 'N/A'}</small></p>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('edge_added')(event)) {
      return (
        <>
          <strong>Edge Creation Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Graph Owner Node:</strong> {event.payload.graph_owner_node_id?.substring(0, 8) || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Step:</strong> {event.payload.step || 'N/A'}</small></p>
            </div>
          </div>
          
          <div className="edge-visualization mt-2 p-2 border rounded bg-light">
            <div className="d-flex align-items-center justify-content-center">
              <div className="node-box border rounded p-1 bg-white">
                <p className="mb-0"><small><strong>Parent:</strong> {event.payload.parent_node_nid}</small></p>
                <p className="mb-0 small text-muted">{event.payload.parent_node_id?.substring(0, 8)}</p>
              </div>
              <ArrowRight size={20} className="mx-2 text-primary" />
              <div className="node-box border rounded p-1 bg-white">
                <p className="mb-0"><small><strong>Child:</strong> {event.payload.child_node_nid}</small></p>
                <p className="mb-0 small text-muted">{event.payload.child_node_id?.substring(0, 8)}</p>
              </div>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('inner_graph_built')(event)) {
      return (
        <>
          <div className="mb-3">
            <strong>Graph Construction Completed</strong>
            <div className="row g-2 mt-1">
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Owner Node ID:</strong> {event.payload.node_id?.substring(0, 8) || 'N/A'}</small></p>
                <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
              </div>
              <div className="col-md-6">
                <p className="mb-1"><small><strong>Nodes:</strong> {event.payload.num_nodes}</small></p>
                <p className="mb-1"><small><strong>Edges:</strong> {event.payload.num_edges}</small></p>
              </div>
            </div>
          </div>
        </>
      );
    }

    // Fallback for unknown event types
    return <p>Details for event type {event.event_type} not yet implemented.</p>;
  // --- End of copied content ---
};

// --- End Copied & Adapted --- 

interface NodeEventDetailPaneProps {
  event: AgentEvent;
}

const NodeEventDetailPane: React.FC<NodeEventDetailPaneProps> = ({ event }) => {
  if (!event) return null;

  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
    } catch (e) {
      return isoString;
    }
  };

  return (
    <Card>
      <Card.Header className="d-flex justify-content-between align-items-center">
        <span>Event Details: <strong>{event.event_type}</strong></span>
        <small className="text-muted">{formatTimestamp(event.timestamp)}</small>
      </Card.Header>
      <Card.Body>
        {renderSummaryContent(event)}
        {/* Consider adding tabs for full prompt/response/raw JSON later if needed */}
      </Card.Body>
    </Card>
  );
};

export default NodeEventDetailPane; 