import React, { useState } from 'react';
import { Card, Tab, Nav, Badge } from 'react-bootstrap';
import { AgentEvent, LlmMessage } from '../features/events/eventsApi';
import { isEventType } from '../helpers/eventType';
import { ArrowRight } from 'lucide-react';
import CodeHighlighter from './SyntaxHighlighter';
import { statusColorMap } from '../helpers/eventConstants.ts';

import { RenderClickableNodeId } from '../helpers/formatters.tsx';

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

interface NodeEventDetailPaneProps {
  event: AgentEvent;
  onNodeClick?: (nodeId: string) => void;
}

const NodeEventDetailPane: React.FC<NodeEventDetailPaneProps> = ({ event, onNodeClick }) => {
  const [activeTab, setActiveTab] = useState('details');

  const hasEventSpecificData = isEventType('llm_call_completed')(event) ||
    isEventType('plan_received')(event) ||
    isEventType('tool_returned')(event);

  const renderSummaryContent = (event: AgentEvent) => {
    if (isEventType('step_started')(event)) {
      return (
        <>
          <strong>Step Information</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Step:</strong> {event.payload.step}</small></p>
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
              </p>
            </div>
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Root ID:</strong> <RenderClickableNodeId nodeId={event.payload.root_id} onNodeClick={onNodeClick} /></small>
              </p>
            </div>
          </div>
          <div className="mt-2">
            <p className="mb-1"><small><strong>Node Goal:</strong> {event.payload.node_goal}</small></p>
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
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
              </p>
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
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
              </p>
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
          <strong>LLM Call Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Agent:</strong> {event.payload.agent_class}</small></p>
              <p className="mb-1"><small><strong>Model:</strong> {event.payload.model}</small></p>
            </div>
            <div className="col-md-6">
              {event.payload.action_name && <p className="mb-1"><small><strong>Action:</strong> {event.payload.action_name}</small></p>}
              {event.payload.node_id && (
                <p className="mb-1">
                  <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
                </p>
              )}
            </div>
          </div>
        </>
      );
    }

    if (isEventType('llm_call_completed')(event)) {
      return (
        <>
          <strong>LLM Call Results</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Agent:</strong> {event.payload.agent_class}</small></p>
              <p className="mb-1"><small><strong>Model:</strong> {event.payload.model}</small></p>
              <p className="mb-1"><small><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Tokens:</strong> {event.payload.token_usage?.prompt_tokens || 0} / {event.payload.token_usage?.completion_tokens || 0}</small></p>
              {event.payload.node_id && (
                <p className="mb-1">
                  <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
                </p>
              )}
            </div>
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
              {event.payload.node_id && (
                <p className="mb-1">
                  <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
                </p>
              )}
            </div>
          </div>
          <div className="mt-2">
            <strong>Arguments:</strong>
            <CodeHighlighter
              code={event.payload.args_summary}
              language="json"
              maxHeight="200px"
            />
          </div>
        </>
      );
    }

    if (isEventType('tool_returned')(event)) {
      return (
        <>
          <strong>Tool Return Results</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Tool Name:</strong> {event.payload.tool_name}</small></p>
              <p className="mb-1"><small><strong>API:</strong> {event.payload.api_name}</small></p>
              <p className="mb-1">
                <small><strong>Status:</strong> <span className={event.payload.state === 'SUCCESS' ? 'text-success' : 'text-danger'}>{event.payload.state}</span></small>
              </p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</small></p>
              {event.payload.node_id && (
                <p className="mb-1">
                  <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
                </p>
              )}
            </div>
          </div>
          {event.payload.error && (
            <div className="alert alert-danger small mt-2 py-1">
              <strong>Error:</strong> {event.payload.error}
            </div>
          )}
        </>
      );
    }

    if (isEventType('node_created')(event)) {
      return (
        <>
          <strong>Node Creation Details</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
              </p>
              <p className="mb-1"><small><strong>Node NID:</strong> {event.payload.node_nid}</small></p>
              <p className="mb-1"><small><strong>Node Type:</strong> {event.payload.node_type}</small></p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Layer:</strong> {event.payload.layer}</small></p>
              <p className="mb-1">
                <small><strong>Outer Node ID:</strong> {event.payload.outer_node_id 
                  ? <RenderClickableNodeId nodeId={event.payload.outer_node_id} onNodeClick={onNodeClick} /> 
                  : 'N/A'}</small>
              </p>
              <p className="mb-1">
                <small><strong>Root Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.root_node_id} onNodeClick={onNodeClick} /></small>
              </p>
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
          <strong>Plan Information</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} /></small>
              </p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Plan Items:</strong> {event.payload.raw_plan?.length || 0}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
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
              <p className="mb-1">
                <small><strong>Graph Owner Node:</strong> <RenderClickableNodeId nodeId={event.payload.graph_owner_node_id} onNodeClick={onNodeClick} /></small>
              </p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Added Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.added_node_id} onNodeClick={onNodeClick} /></small>
              </p>
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
              <p className="mb-1">
                <small><strong>Graph Owner Node:</strong> <RenderClickableNodeId nodeId={event.payload.graph_owner_node_id} onNodeClick={onNodeClick} /></small>
              </p>
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
                <p className="mb-0 small text-muted">
                  <RenderClickableNodeId nodeId={event.payload.parent_node_id} onNodeClick={onNodeClick} />
                </p>
              </div>
              <ArrowRight size={20} className="mx-2 text-primary" />
              <div className="node-box border rounded p-1 bg-white">
                <p className="mb-0"><small><strong>Child:</strong> {event.payload.child_node_nid}</small></p>
                <p className="mb-0 small text-muted">
                  <RenderClickableNodeId nodeId={event.payload.child_node_id} onNodeClick={onNodeClick} />
                </p>
              </div>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('inner_graph_built')(event)) {
      return (
        <>
          <strong>Graph Construction Completed</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Owner Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} /></small>
              </p>
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Node Count:</strong> <Badge bg="primary">{event.payload.node_count}</Badge></small></p>
              <p className="mb-1"><small><strong>Edge Count:</strong> <Badge bg="info">{event.payload.edge_count}</Badge></small></p>
              <p className="mb-1"><small><strong>Step:</strong> {event.payload.step || 'N/A'}</small></p>
            </div>
          </div>
          <div className="mt-2">
            <small><strong>Graph Nodes:</strong></small>
            <div className="mt-1">
              {event.payload.node_ids?.map((nodeId: string, index: number) => (
                <Badge key={index} bg="light" text="dark" className="me-1 mb-1 p-1">
                  <RenderClickableNodeId nodeId={nodeId} onNodeClick={onNodeClick} truncate={true} />
                </Badge>
              ))}
            </div>
          </div>
        </>
      );
    }

    if (isEventType('node_result_available')(event)) {
      return (
        <>
          <strong>Node Result Information</strong>
          <div className="row g-2 mt-1">
            <div className="col-md-6">
              <p className="mb-1">
                <small><strong>Node ID:</strong> <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} /></small>
              </p>
              <p className="mb-1"><small><strong>Action Name:</strong> {event.payload.action_name}</small></p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><small><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</small></p>
              <p className="mb-1"><small><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</small></p>
            </div>
          </div>
        </>
      );
    }

    // Default case for unknown event types
    return (
      <div className="small">
        <strong>Event Payload</strong>
        <CodeHighlighter
          code={JSON.stringify(event.payload, null, 2)}
          language="json"
          maxHeight="200px"
        />
      </div>
    );
  };

  const renderEventResponse = (event: AgentEvent) => {
    if (isEventType('llm_call_completed')(event)) {
      return (
        <div className="p-3">
          <h6>LLM Response</h6>
          <div className="bg-light p-2 rounded mt-2 mb-2">
            <CodeHighlighter
              code={event.payload.response}
              language="markdown"
              maxHeight="300px"
            />
          </div>
        </div>
      );
    }

    if (isEventType('plan_received')(event)) {
      return (
        <div className="p-3">
          <h6>Raw Plan</h6>
          <div className="bg-light p-2 rounded mt-2 mb-2">
            <CodeHighlighter
              code={JSON.stringify(event.payload.raw_plan, null, 2)}
              language="json"
              maxHeight="300px"
              showLineNumbers={true}
            />
          </div>
        </div>
      );
    }

    if (isEventType('tool_returned')(event)) {
      return (
        <div className="p-3">
          <h6>Tool Result</h6>
          <div className="bg-light p-2 rounded mt-2 mb-2">
            <CodeHighlighter
              code={event.payload.result_summary}
              language="json"
              maxHeight="300px"
            />
          </div>
        </div>
      );
    }

    if (isEventType('node_result_available')(event)) {
      return (
        <div className="p-3">
          <h6>Result Content</h6>
          <div className="bg-light p-2 rounded mt-2 mb-2">
            <CodeHighlighter
              code={event.payload.result_summary}
              language="markdown"
              maxHeight="300px"
            />
          </div>
        </div>
      );
    }

    return null;
  };

  const renderRawJson = (event: AgentEvent) => {
    return (
      <div className="p-3">
        <h6>Raw JSON</h6>
        <div className="bg-light p-2 rounded mt-2">
          <CodeHighlighter
            code={JSON.stringify(event, null, 2)}
            language="json"
            maxHeight="300px"
            showLineNumbers={true}
          />
        </div>
      </div>
    );
  };

  return (
    <Card>
      <Card.Header className="bg-light py-2">
        <strong>Event Detail</strong>
      </Card.Header>
      <Card.Body className="p-0">
        <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k || 'details')}>
          <Nav variant="tabs" className="px-3 pt-3">
            <Nav.Item>
              <Nav.Link eventKey="details">Details</Nav.Link>
            </Nav.Item>
            {hasEventSpecificData && (
              <Nav.Item>
                <Nav.Link eventKey="response">Response</Nav.Link>
              </Nav.Item>
            )}
            <Nav.Item>
              <Nav.Link eventKey="json">JSON</Nav.Link>
            </Nav.Item>
          </Nav>
          <Tab.Content>
            <Tab.Pane eventKey="details">
              <div className="p-3">
                {renderSummaryContent(event)}
              </div>
            </Tab.Pane>
            {hasEventSpecificData && (
              <Tab.Pane eventKey="response">
                {renderEventResponse(event)}
              </Tab.Pane>
            )}
            <Tab.Pane eventKey="json">
              {renderRawJson(event)}
            </Tab.Pane>
          </Tab.Content>
        </Tab.Container>
      </Card.Body>
    </Card>
  );
};

export default NodeEventDetailPane; 