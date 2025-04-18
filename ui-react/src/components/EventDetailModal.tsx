import React, { useState } from 'react';
import { Modal, Tab, Nav, Button, Badge } from 'react-bootstrap';
import { AgentEvent, LlmMessage } from '../features/events/eventsApi';
import { isEventType } from '../helpers/eventType';
import { ArrowRight } from 'lucide-react';

// Event type to badge variant mapping
const eventTypeBadgeVariant: Record<string, string> = {
  step_started: 'primary',
  step_finished: 'success',
  node_status_changed: 'info',
  llm_call_started: 'warning',
  llm_call_completed: 'warning',
  tool_invoked: 'secondary',
  tool_returned: 'secondary',
  default: 'light'
};

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

interface EventDetailModalProps {
  show: boolean;
  onHide: () => void;
  event: AgentEvent | null;
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({ show, onHide, event }) => {
  const [activeTab, setActiveTab] = useState('summary');
  
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
      console.error("Error formatting timestamp:", isoString, e);
      return isoString;
    }
  };

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
              <pre style={{ maxHeight: '300px', overflowY: 'auto', whiteSpace: 'pre-wrap', margin: 0 }}>
                {message.content}
              </pre>
            </div>
          </div>
        ))}
      </div>
    );
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
                  <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>
                </div>
                <div className="col-md-6">
                  <p className="mb-1"><strong>Root ID:</strong> {event.payload.root_id}</p>
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
                <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>
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
                <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>
                <p className="mb-1"><strong>Node Goal:</strong> {event.payload.node_goal}</p>
              </div>
              <div className="col-md-6">
                <p className="mb-1">
                  <strong>Status Change:</strong> 
                  <span className={statusColorMap[event.payload.old_status] || ''}> {event.payload.old_status}</span>
                  <ArrowRight size={14} className="mx-2" />
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
                  {event.payload.step !== undefined && <p className="mb-1"><strong>Step:</strong> {event.payload.step}</p>}
                  {event.payload.node_id && <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>}
                </div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Prompt Preview</strong>
            </div>
            <div className="card-body">
              <pre style={{ maxHeight: '250px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                {formatPreview(event.payload.prompt_preview)}
              </pre>
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
                  {event.payload.step !== undefined && <p className="mb-1"><strong>Step:</strong> {event.payload.step}</p>}
                  {event.payload.node_id && <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>}
                  {event.payload.token_usage && (
                    <p className="mb-1">
                      <strong>Tokens:</strong> {event.payload.token_usage.prompt_tokens} prompt + {event.payload.token_usage.completion_tokens} completion
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
              <pre style={{ maxHeight: '250px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                {formatPreview(event.payload.response)}
              </pre>
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
                {event.payload.node_id && <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>}
              </div>
            </div>
            <div className="mt-3">
              <strong>Arguments:</strong>
              <pre style={{ maxHeight: '200px', overflowY: 'auto' }}>{event.payload.args_summary}</pre>
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
                  {event.payload.node_id && <p className="mb-1"><strong>Node ID:</strong> {event.payload.node_id}</p>}
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
              <pre style={{ maxHeight: '200px', overflowY: 'auto' }}>{event.payload.result_summary}</pre>
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
          <pre style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {JSON.stringify(event.payload, null, 2)}
          </pre>
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
                  <pre style={{ maxHeight: '500px', overflowY: 'auto', whiteSpace: 'pre-wrap', margin: 0 }}>
                    {event.payload.response}
                  </pre>
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

  return (
    <Modal show={show} onHide={onHide} size="lg" aria-labelledby="event-detail-modal" centered>
      <Modal.Header closeButton>
        <Modal.Title id="event-detail-modal">
          <Badge bg={getBadgeVariant(event.event_type)} className="me-2">
            {event.event_type}
          </Badge>
          <small className="text-muted">{formatTimestamp(event.timestamp)}</small>
        </Modal.Title>
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
                {tab.content}
              </Tab.Pane>
            ))}
            <Tab.Pane eventKey="json">
              <div className="d-flex justify-content-end mb-2">
                <Button size="sm" variant="outline-secondary" onClick={copyJsonToClipboard}>
                  Copy JSON
                </Button>
              </div>
              <pre className="bg-light p-3 rounded" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {JSON.stringify(event, null, 2)}
              </pre>
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
                      {event.payload.node_id && (
                        <tr>
                          <th>Node ID</th>
                          <td>{event.payload.node_id}</td>
                        </tr>
                      )}
                      {isEventType('step_started')(event) && (
                        <tr>
                          <th>Root Node ID</th>
                          <td>{event.payload.root_id}</td>
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