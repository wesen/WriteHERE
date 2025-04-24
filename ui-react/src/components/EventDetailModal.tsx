import React, { useState } from 'react';
import { Modal, Tab, Nav, Button, Badge } from 'react-bootstrap';
import { AgentEvent, LlmMessage } from '../features/events/eventsApi';
import { isEventType } from '../helpers/eventType';
import { ArrowRight, ArrowLeft } from 'lucide-react';
import CodeHighlighter from './SyntaxHighlighter';
import { statusColorMap, eventTypeBadgeVariant } from '../helpers/eventConstants.ts';
import { formatTimestamp, RenderClickableNodeId } from '../helpers/formatters.tsx';

interface EventDetailModalProps {
  show: boolean;
  onHide: () => void;
  event: AgentEvent | null;
  onNodeClick?: (nodeId: string) => void;
  hasPrevious?: boolean;
  onBack?: () => void;
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({ 
  show, 
  onHide, 
  event, 
  onNodeClick,
  hasPrevious = false,
  onBack
}) => {
  const [activeTab, setActiveTab] = useState('summary');
  
  if (!event) return null;

  const copyJsonToClipboard = () => {
    navigator.clipboard.writeText(JSON.stringify(event, null, 2))
      .then(() => {
        alert('JSON copied to clipboard');
      })
      .catch(err => {
        console.error('Failed to copy JSON: ', err);
      });
  };

  const getBadgeVariant = (eventType: string): string => {
    return eventTypeBadgeVariant[eventType] || eventTypeBadgeVariant.default;
  };

  // Helper to format and truncate text previews
  const formatPreview = (text: string, maxLength: number = 500): string => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  // Render the LLM prompt messages
  const renderPromptMessages = (messages: LlmMessage[]) => {
    return (
      <div className="prompt-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message message-${message.role} mb-3 p-3 rounded`}>
            <div className="message-header mb-2">
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
      </div>
    );
  };

  const handleBackClick = () => {
    if (onBack) {
      onBack();
    }
  };

  // Render the summary tab content based on event type
  const renderSummaryContent = () => {
    if (isEventType('step_started')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>Step Information</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1"><strong>Step:</strong> {event.payload.step}</p>
                  <p className="mb-1">
                    <strong>Node ID:</strong> 
                    <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                  </p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>Root ID:</strong> 
                    <RenderClickableNodeId nodeId={event.payload.root_id} onNodeClick={onNodeClick} />
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Node Goal</strong>
            </div>
            <div className="card-body">
              <p>{event.payload.node_goal}</p>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('step_finished')(event)) {
      return (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Step Details</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <p className="mb-1"><strong>Step:</strong> {event.payload.step}</p>
                <p className="mb-1">
                  <strong>Node ID:</strong> 
                  <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                </p>
                <p className="mb-1"><strong>Action:</strong> {event.payload.action_name}</p>
              </div>
              <div className="col-md-6">
                <p className="mb-1"><strong>Status After:</strong> <span className={statusColorMap[event.payload.status_after] || ''}>{event.payload.status_after}</span></p>
                <p className="mb-1"><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (isEventType('node_status_changed')(event)) {
      return (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Status Change Details</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Node ID:</strong> 
                  <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                </p>
                <p className="mb-1"><strong>Node Goal:</strong> {event.payload.node_goal}</p>
              </div>
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Status Change:</strong>
                  <span className={statusColorMap[event.payload.old_status] || ''}> {event.payload.old_status}</span>
                  <ArrowRight size={16} className="mx-1" />
                  <span className={statusColorMap[event.payload.new_status] || ''}>{event.payload.new_status}</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (isEventType('llm_call_started')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>LLM Call Information</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1"><strong>Agent Class:</strong> {event.payload.agent_class}</p>
                  <p className="mb-1"><strong>Model:</strong> {event.payload.model}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Action:</strong> {event.payload.action_name || 'N/A'}</p>
                  {event.payload.node_id && (
                    <p className="mb-1">
                      <strong>Node ID:</strong> 
                      <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Prompt Preview</strong>
            </div>
            <div className="card-body">
              <CodeHighlighter
                code={formatPreview(event.payload.prompt_preview)}
                language="markdown"
                maxHeight="250px"
              />
              {event.payload.prompt && (
                <div className="text-end mt-2">
                  <Button size="sm" variant="outline-primary" onClick={() => setActiveTab('prompt')}>
                    View Full Prompt
                  </Button>
                </div>
              )}
            </div>
          </div>
        </>
      );
    }

    if (isEventType('llm_call_completed')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>LLM Response Information</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1"><strong>Agent Class:</strong> {event.payload.agent_class}</p>
                  <p className="mb-1"><strong>Model:</strong> {event.payload.model}</p>
                  <p className="mb-1"><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Action:</strong> {event.payload.action_name || 'N/A'}</p>
                  {event.payload.node_id && (
                    <p className="mb-1">
                      <strong>Node ID:</strong> 
                      <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                    </p>
                  )}
                  {event.payload.token_usage && (
                    <p className="mb-1">
                      <strong>Tokens:</strong> {event.payload.token_usage.prompt_tokens} / {event.payload.token_usage.completion_tokens}
                    </p>
                  )}
                </div>
              </div>
              {event.payload.error && (
                <div className="alert alert-danger mt-2">
                  <strong>Error:</strong> {event.payload.error}
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Response Preview</strong>
            </div>
            <div className="card-body">
              <CodeHighlighter
                code={formatPreview(event.payload.response)}
                language="markdown"
                maxHeight="250px"
              />
              <div className="text-end mt-2">
                <Button size="sm" variant="outline-primary" onClick={() => setActiveTab('response')}>
                  View Full Response
                </Button>
              </div>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('tool_invoked')(event)) {
      return (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Tool Invocation Details</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <p className="mb-1"><strong>Tool Name:</strong> {event.payload.tool_name}</p>
                <p className="mb-1"><strong>API:</strong> {event.payload.api_name}</p>
              </div>
              <div className="col-md-6">
                {event.payload.node_id && (
                  <p className="mb-1">
                    <strong>Node ID:</strong> 
                    <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                  </p>
                )}
              </div>
            </div>
            <div className="mt-3">
              <strong>Arguments:</strong>
              <CodeHighlighter
                code={event.payload.args_summary}
                language="json"
                maxHeight="200px"
              />
            </div>
          </div>
        </div>
      );
    }

    if (isEventType('tool_returned')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>Tool Return Details</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1"><strong>Tool Name:</strong> {event.payload.tool_name}</p>
                  <p className="mb-1"><strong>API:</strong> {event.payload.api_name}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>State:</strong> 
                    <span className={event.payload.state === 'SUCCESS' ? 'text-success' : 'text-danger'}> {event.payload.state}</span>
                  </p>
                  <p className="mb-1"><strong>Duration:</strong> {event.payload.duration_seconds.toFixed(2)}s</p>
                  {event.payload.node_id && (
                    <p className="mb-1">
                      <strong>Node ID:</strong> 
                      <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                    </p>
                  )}
                </div>
              </div>
              {event.payload.error && (
                <div className="alert alert-danger mt-2">
                  <strong>Error:</strong> {event.payload.error}
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Result</strong>
            </div>
            <div className="card-body">
              <CodeHighlighter
                code={event.payload.result_summary}
                language="json"
                maxHeight="200px"
              />
            </div>
          </div>
        </>
      );
    }

    if (isEventType('node_created')(event)) {
      return (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Node Creation Details</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Node ID:</strong> 
                  <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} truncate={false} />
                </p>
                <p className="mb-1"><strong>Node NID:</strong> {event.payload.node_nid}</p>
                <p className="mb-1"><strong>Node Type:</strong> {event.payload.node_type}</p>
                <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type}</p>
              </div>
              <div className="col-md-6">
                <p className="mb-1"><strong>Layer:</strong> {event.payload.layer}</p>
                <p className="mb-1">
                  <strong>Outer Node ID:</strong>{' '}
                  {event.payload.outer_node_id 
                    ? <RenderClickableNodeId nodeId={event.payload.outer_node_id} onNodeClick={onNodeClick} />
                    : 'N/A'}
                </p>
                <p className="mb-1">
                  <strong>Root Node ID:</strong>{' '}
                  <RenderClickableNodeId nodeId={event.payload.root_node_id} onNodeClick={onNodeClick} />
                </p>
              </div>
            </div>
            <div className="mt-3">
              <p className="mb-1"><strong>Goal:</strong> {event.payload.task_goal}</p>
              <p className="mb-1"><strong>Initial Parent NIDs:</strong> {event.payload.initial_parent_nids?.join(', ') || 'None'}</p>
            </div>
          </div>
        </div>
      );
    }

    if (isEventType('plan_received')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>Plan Information</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>Node ID:</strong> 
                    <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                  </p>
                  <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Plan Items:</strong> {event.payload.raw_plan?.length || 0}</p>
                  <p className="mb-1"><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Plan Structure</strong>
            </div>
            <div className="card-body">
              <CodeHighlighter
                code={JSON.stringify(event.payload.raw_plan, null, 2)}
                language="json"
                maxHeight="300px"
                showLineNumbers={true}
              />
            </div>
          </div>
        </>
      );
    }

    if (isEventType('node_added')(event)) {
      return (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Node Added Details</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Graph Owner Node:</strong>{' '}
                  <RenderClickableNodeId nodeId={event.payload.graph_owner_node_id} onNodeClick={onNodeClick} />
                </p>
                <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</p>
                <p className="mb-1"><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</p>
              </div>
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Added Node ID:</strong>{' '}
                  <RenderClickableNodeId nodeId={event.payload.added_node_id} onNodeClick={onNodeClick} />
                </p>
                <p className="mb-1"><strong>Added Node NID:</strong> {event.payload.added_node_nid}</p>
                <p className="mb-1"><strong>Step:</strong> {event.payload.step || 'N/A'}</p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (isEventType('edge_added')(event)) {
      return (
        <>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Edge Creation Details</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>Graph Owner Node:</strong>{' '}
                    <RenderClickableNodeId nodeId={event.payload.graph_owner_node_id} onNodeClick={onNodeClick} />
                  </p>
                  <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</p>
                  <p className="mb-1"><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Step:</strong> {event.payload.step || 'N/A'}</p>
                </div>
              </div>
              
              <div className="edge-visualization mt-4 p-3 border rounded bg-light">
                <div className="d-flex align-items-center justify-content-center">
                  <div className="node-box border rounded p-2 bg-white">
                    <p className="mb-0"><strong>Parent:</strong> {event.payload.parent_node_nid}</p>
                    <p className="mb-0 small text-muted">
                      <RenderClickableNodeId nodeId={event.payload.parent_node_id} onNodeClick={onNodeClick} />
                    </p>
                  </div>
                  <ArrowRight size={30} className="mx-3 text-primary" />
                  <div className="node-box border rounded p-2 bg-white">
                    <p className="mb-0"><strong>Child:</strong> {event.payload.child_node_nid}</p>
                    <p className="mb-0 small text-muted">
                      <RenderClickableNodeId nodeId={event.payload.child_node_id} onNodeClick={onNodeClick} />
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('inner_graph_built')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>Graph Construction Completed</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>Owner Node ID:</strong>{' '}
                    <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                  </p>
                  <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</p>
                  <p className="mb-1"><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Node Count:</strong> <Badge bg="primary">{event.payload.node_count}</Badge></p>
                  <p className="mb-1"><strong>Edge Count:</strong> <Badge bg="info">{event.payload.edge_count}</Badge></p>
                  <p className="mb-1"><strong>Step:</strong> {event.payload.step || 'N/A'}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Graph Node IDs</strong>
            </div>
            <div className="card-body">
              <div className="node-id-list">
                {event.payload.node_ids?.map((nodeId: string, index: number) => (
                  <Badge key={index} bg="light" text="dark" className="me-2 mb-2 p-2">
                    <RenderClickableNodeId nodeId={nodeId} onNodeClick={onNodeClick} />
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </>
      );
    }

    if (isEventType('node_result_available')(event)) {
      return (
        <>
          <div className="card mb-3">
            <div className="card-header bg-light py-2">
              <strong>Node Result Information</strong>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <p className="mb-1">
                    <strong>Node ID:</strong>{' '}
                    <RenderClickableNodeId nodeId={event.payload.node_id} onNodeClick={onNodeClick} />
                  </p>
                  <p className="mb-1"><strong>Action Name:</strong> {event.payload.action_name}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Task Type:</strong> {event.payload.task_type || 'N/A'}</p>
                  <p className="mb-1"><strong>Task Goal:</strong> {event.payload.task_goal || 'N/A'}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Result Content</strong>
            </div>
            <div className="card-body">
              <CodeHighlighter
                code={event.payload.result_summary}
                language="markdown"
                maxHeight="300px"
              />
            </div>
          </div>
        </>
      );
    }

    // Default case for unknown event types
    return (
      <div className="card">
        <div className="card-header bg-light py-2">
          <strong>Event Details</strong>
        </div>
        <div className="card-body">
          <CodeHighlighter 
            code={JSON.stringify(event.payload, null, 2)}
            language="json"
            maxHeight="300px"
          />
        </div>
      </div>
    );
  };

  // Define special tabs based on event type
  const getSpecialTabs = () => {
    if (isEventType('llm_call_started')(event) && event.payload.prompt) {
      return [
        {
          key: 'prompt',
          title: 'Prompt',
          content: (
            <div className="card">
              <div className="card-header bg-light py-2">
                <strong>Full Prompt</strong>
              </div>
              <div className="card-body">
                {renderPromptMessages(event.payload.prompt)}
              </div>
            </div>
          )
        }
      ];
    }
    
    if (isEventType('llm_call_completed')(event) && event.payload.response) {
      return [
        {
          key: 'response',
          title: 'Response',
          content: (
            <div className="card">
              <div className="card-header bg-light py-2">
                <strong>Full Response</strong>
              </div>
              <div className="card-body">
                <div className="message message-assistant p-3 rounded">
                  <CodeHighlighter
                    code={event.payload.response}
                    language="markdown"
                    maxHeight="500px"
                  />
                </div>
              </div>
            </div>
          )
        }
      ];
    }
    
    return [];
  };

  const specialTabs = getSpecialTabs();

  // Render special tab content based on active tab
  const renderSpecialTabContent = () => {
    if (activeTab === 'prompt' && isEventType('llm_call_started')(event)) {
      return (
        <div className="p-3">
          <h5>Full Prompt</h5>
          {Array.isArray(event.payload.prompt) ? (
            event.payload.prompt.map((message: LlmMessage, index: number) => (
              <div key={index} className="mb-3">
                <div className="fw-bold">{message.role}</div>
                <CodeHighlighter
                  code={message.content}
                  language="markdown"
                  maxHeight="400px"
                />
              </div>
            ))
          ) : (
            <div className="alert alert-warning">
              Prompt is not in expected format
            </div>
          )}
        </div>
      );
    }

    if (activeTab === 'response' && isEventType('llm_call_completed')(event)) {
      return (
        <div className="p-3">
          <h5>Full Response</h5>
          <CodeHighlighter
            code={event.payload.response}
            language="markdown"
            maxHeight="400px"
          />
        </div>
      );
    }

    if (activeTab === 'plan' && isEventType('plan_received')(event)) {
      return (
        <div className="p-3">
          <h5>Raw Plan</h5>
          <CodeHighlighter
            code={JSON.stringify(event.payload.raw_plan, null, 2)}
            language="json"
            maxHeight="400px"
            showLineNumbers={true}
          />
        </div>
      );
    }

    if (activeTab === 'result') {
      if (isEventType('tool_returned')(event)) {
        return (
          <div className="p-3">
            <h5>Tool Result</h5>
            <CodeHighlighter
              code={event.payload.result_summary}
              language="json"
              maxHeight="400px"
            />
          </div>
        );
      }

      if (isEventType('node_result_available')(event)) {
        return (
          <div className="p-3">
            <h5>Node Result</h5>
            <CodeHighlighter
              code={event.payload.result_summary}
              language="markdown"
              maxHeight="400px"
            />
          </div>
        );
      }
    }

    return null;
  };

  return (
    <Modal show={show} onHide={onHide} size="lg" aria-labelledby="event-detail-modal" centered>
      <Modal.Header closeButton>
        <div className="d-flex align-items-center w-100">
          {hasPrevious && (
            <Button variant="link" className="p-0 me-2" onClick={handleBackClick}>
              <ArrowLeft size={20} />
            </Button>
          )}
          <Modal.Title className="flex-grow-1">
            <Badge bg={getBadgeVariant(event.event_type)} className="me-2">
              {event.event_type}
            </Badge>
            <small className="text-muted">{formatTimestamp(event.timestamp)}</small>
          </Modal.Title>
        </div>
      </Modal.Header>
      <Modal.Body className="p-0">
        <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k || 'summary')}>
          <Nav variant="tabs" className="px-3 pt-3">
            <Nav.Item>
              <Nav.Link eventKey="summary">Summary</Nav.Link>
            </Nav.Item>
            {specialTabs.map(tab => (
              <Nav.Item key={tab.key}>
                <Nav.Link eventKey={tab.key}>{tab.title}</Nav.Link>
              </Nav.Item>
            ))}
            <Nav.Item>
              <Nav.Link eventKey="json">JSON</Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link eventKey="metadata">Metadata</Nav.Link>
            </Nav.Item>
          </Nav>
          <Tab.Content className="p-3">
            <Tab.Pane eventKey="summary">
              {renderSummaryContent()}
            </Tab.Pane>
            {specialTabs.map(tab => (
              <Tab.Pane key={tab.key} eventKey={tab.key}>
                {activeTab === tab.key && renderSpecialTabContent()}
              </Tab.Pane>
            ))}
            <Tab.Pane eventKey="json">
              <div className="d-flex justify-content-end mb-2">
                <Button size="sm" variant="outline-secondary" onClick={copyJsonToClipboard}>
                  Copy JSON
                </Button>
              </div>
              <CodeHighlighter
                code={JSON.stringify(event, null, 2)}
                language="json"
                maxHeight="400px"
                showLineNumbers={true}
              />
            </Tab.Pane>
            <Tab.Pane eventKey="metadata">
              <div className="card">
                <div className="card-header bg-light py-2">
                  <strong>Event Metadata</strong>
                </div>
                <div className="card-body">
                  <table className="table table-sm table-hover">
                    <tbody>
                      <tr>
                        <th style={{ width: '180px' }}>Event ID</th>
                        <td>{event.event_id}</td>
                      </tr>
                      <tr>
                        <th>Event Type</th>
                        <td>{event.event_type}</td>
                      </tr>
                      <tr>
                        <th>Timestamp</th>
                        <td>{formatTimestamp(event.timestamp)}</td>
                      </tr>
                      <tr>
                        <th>Run ID</th>
                        <td>{event.run_id || 'N/A'}</td>
                      </tr>
                      {typeof event.payload === 'object' && event.payload !== null && 'node_id' in event.payload && (
                        <tr>
                          <th>Node ID</th>
                          <td><RenderClickableNodeId nodeId={(event.payload as { node_id: string }).node_id} onNodeClick={onNodeClick} truncate={false} /></td>
                        </tr>
                      )}
                      {isEventType('step_started')(event) && (
                        <tr>
                          <th>Root Node ID</th>
                          <td><RenderClickableNodeId nodeId={event.payload.root_id} onNodeClick={onNodeClick} /></td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </Tab.Pane>
          </Tab.Content>
        </Tab.Container>
      </Modal.Body>
    </Modal>
  );
};

export default EventDetailModal; 