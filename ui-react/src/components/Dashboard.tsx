import React, { useState } from 'react';
import { Card, ListGroup, Badge, Spinner, Col, Row, Alert, ProgressBar, Button, Modal } from 'react-bootstrap';
import { AgentEvent, useGetEventsQuery } from '../features/events/eventsApi';
import { formatTimestamp } from '../helpers/formatters';
import { isEventType } from '../helpers/eventType';
import { ChevronUp, ChevronDown, Info } from 'lucide-react';

// CSS for fixed-size items
const listItemStyle = {
  height: '60px',
  overflow: 'hidden',
  cursor: 'pointer',
  padding: '10px 15px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between'
};

const titleStyle = {
  width: '70%',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis'
};

const Dashboard: React.FC = () => {
  const { data, isLoading, error } = useGetEventsQuery();
  const [showCompletedLlm, setShowCompletedLlm] = useState(false);
  const [showCompletedTool, setShowCompletedTool] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<AgentEvent | null>(null);
  const [showEventModal, setShowEventModal] = useState(false);

  const handleEventClick = (event: AgentEvent) => {
    setSelectedEvent(event);
    setShowEventModal(true);
  };

  const closeEventModal = () => {
    setShowEventModal(false);
    setSelectedEvent(null);
  };

  if (isLoading) {
    return <div className="text-center p-5"><Spinner animation="border" /></div>;
  }

  if (error) {
    return <Alert variant="danger">Error loading event data</Alert>;
  }

  if (!data || !data.events || data.events.length === 0) {
    return <Alert variant="info">No events available</Alert>;
  }

  // Get the most recent events (newest first)
  const events = data.events;

  // Calculate summary statistics
  const totalSteps = new Set(events
    .filter(event => event.event_type === 'step_started' || event.event_type === 'step_finished')
    .map(event => event.payload.step)
  ).size;

  const totalLlmCalls = events.filter(event => event.event_type === 'llm_call_started').length;
  const totalToolCalls = events.filter(event => event.event_type === 'tool_invoked').length;
  const totalNodes = new Set(events
    .filter(isEventType('node_created'))
    .map(event => event.payload.node_id)
  ).size;

  const completedNodes = new Set(events
    .filter(isEventType('node_status_changed'))
    .filter(event => 
      event.payload.new_status === 'FINISH'
    )
    .map(event => event.payload.node_id)
  ).size;

  // Find active steps (started but not finished)
  const activeSteps = new Map();
  const finishedSteps = new Set();

  events.forEach(event => {
    if (event.event_type === 'step_finished') {
      finishedSteps.add(event.payload.step);
    } else if (event.event_type === 'step_started') {
      if (!finishedSteps.has(event.payload.step)) {
        activeSteps.set(event.payload.step, event);
      }
    }
  });

  // --- Process Events for Active and Completed Calls ---

  const activeLlmCalls = new Map<string, AgentEvent>();
  const completedLlmCalls: AgentEvent[] = [];
  const llmCallStartedMap = new Map<string, AgentEvent>();

  const activeToolCalls = new Map<string, AgentEvent>();
  const completedToolCalls: AgentEvent[] = [];
  const toolCallInvokedMap = new Map<string, AgentEvent>();

  // Iterate once to map starts/invokes and identify completed calls
  // First, process all started/invoked events
  events.forEach(event => {
    if (isEventType('llm_call_started')(event) && event.payload.call_id) {
      llmCallStartedMap.set(event.payload.call_id, event);
    } else if (isEventType('tool_invoked')(event) && event.payload.tool_call_id) {
      toolCallInvokedMap.set(event.payload.tool_call_id, event);
    }
  });

  // Then, process all completed/returned events
  events.forEach(event => {
    if (isEventType('llm_call_completed')(event) && event.payload.call_id) {
      const startedEvent = llmCallStartedMap.get(event.payload.call_id);
      if (startedEvent && isEventType('llm_call_started')(startedEvent)) {
        completedLlmCalls.push(event);
        llmCallStartedMap.delete(event.payload.call_id); // Remove from started map
      }
    } else if (isEventType('tool_returned')(event) && event.payload.tool_call_id) {
      const invokedEvent = toolCallInvokedMap.get(event.payload.tool_call_id);
      if (invokedEvent && isEventType('tool_invoked')(invokedEvent)) {
        completedToolCalls.push(event);
        toolCallInvokedMap.delete(event.payload.tool_call_id); // Remove from invoked map
      }
    }
  });
  // Any remaining entries in the started/invoked maps are active calls
  llmCallStartedMap.forEach((event, call_id) => activeLlmCalls.set(call_id, event));
  toolCallInvokedMap.forEach((event, tool_call_id) => activeToolCalls.set(tool_call_id, event));

  // Sort completed calls by end time (newest first)
  completedLlmCalls.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  completedToolCalls.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  // Convert active maps to arrays for rendering
  const activeStepsArray = Array.from(activeSteps.values());
  const activeLlmCallsArray = Array.from(activeLlmCalls.values());
  const activeToolCallsArray = Array.from(activeToolCalls.values());

  // Get run start time (if available)
  const runStartEvent = events.find(event => event.event_type === 'run_started');
  const runStartTime = runStartEvent ? formatTimestamp(runStartEvent.timestamp) : 'N/A';

  // Render event details in modal based on event type
  const renderEventDetails = () => {
    if (!selectedEvent) return null;

    if (isEventType('step_started')(selectedEvent)) {
      return (
        <>
          <Modal.Header closeButton>
            <Modal.Title>Step {selectedEvent.payload.step} Details</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
            <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
            <div className="mb-2"><strong>Node ID:</strong> {selectedEvent.payload.node_id}</div>
            <div className="mb-2"><strong>Goal:</strong> {selectedEvent.payload.node_goal}</div>
            <div className="mb-2"><strong>Status:</strong> <Badge bg="primary">In Progress</Badge></div>
          </Modal.Body>
        </>
      );
    } else if (isEventType('llm_call_started')(selectedEvent)) {
      return (
        <>
          <Modal.Header closeButton>
            <Modal.Title>LLM Call Details</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
            <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
            <div className="mb-2"><strong>Model:</strong> {selectedEvent.payload.model}</div>
            <div className="mb-2"><strong>Agent:</strong> {selectedEvent.payload.agent_class}</div>
            {selectedEvent.payload.node_id && (
              <div className="mb-2"><strong>Node ID:</strong> {selectedEvent.payload.node_id}</div>
            )}
            <div className="mb-2"><strong>Call ID:</strong> {selectedEvent.payload.call_id}</div>
            <div className="mb-2"><strong>Status:</strong> <Badge bg="primary">In Progress</Badge></div>
            <div className="mb-3">
              <strong>Prompt Preview:</strong>
              <div className="border rounded p-2 mt-1 bg-light">
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem' }}>
                  {selectedEvent.payload.prompt_preview}
                </pre>
              </div>
            </div>
          </Modal.Body>
        </>
      );
    } else if (isEventType('tool_invoked')(selectedEvent)) {
      return (
        <>
          <Modal.Header closeButton>
            <Modal.Title>Tool Call Details</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
            <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
            <div className="mb-2"><strong>Tool:</strong> {selectedEvent.payload.tool_name}.{selectedEvent.payload.api_name}</div>
            {selectedEvent.payload.node_id && (
              <div className="mb-2"><strong>Node ID:</strong> {selectedEvent.payload.node_id}</div>
            )}
            <div className="mb-2"><strong>Tool Call ID:</strong> {selectedEvent.payload.tool_call_id}</div>
            <div className="mb-2"><strong>Status:</strong> <Badge bg="primary">In Progress</Badge></div>
            <div className="mb-3">
              <strong>Arguments:</strong>
              <div className="border rounded p-2 mt-1 bg-light">
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem' }}>
                  {selectedEvent.payload.args_summary}
                </pre>
              </div>
            </div>
          </Modal.Body>
        </>
      );
    } else if (isEventType('llm_call_completed')(selectedEvent)) {
      return (
        <>
          <Modal.Header closeButton>
            <Modal.Title>Completed LLM Call</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
            <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
            <div className="mb-2"><strong>Duration:</strong> {selectedEvent.payload.duration_seconds.toFixed(2)}s</div>
            <div className="mb-2"><strong>Model:</strong> {selectedEvent.payload.model}</div>
            <div className="mb-2"><strong>Agent:</strong> {selectedEvent.payload.agent_class}</div>
            {selectedEvent.payload.node_id && (
              <div className="mb-2"><strong>Node ID:</strong> {selectedEvent.payload.node_id}</div>
            )}
            {selectedEvent.payload.token_usage && (
              <div className="mb-2">
                <strong>Tokens:</strong> {selectedEvent.payload.token_usage.prompt_tokens} prompt + {selectedEvent.payload.token_usage.completion_tokens} completion
              </div>
            )}
            <div className="mb-2">
              <strong>Status:</strong> 
              <Badge bg={selectedEvent.payload.error ? "danger" : "success"} className="ms-2">
                {selectedEvent.payload.error ? "Error" : "Success"}
              </Badge>
            </div>
            {selectedEvent.payload.error && (
              <div className="mb-3">
                <strong>Error:</strong>
                <div className="border rounded p-2 mt-1 bg-light text-danger">
                  {selectedEvent.payload.error}
                </div>
              </div>
            )}
          </Modal.Body>
        </>
      );
    } else if (isEventType('tool_returned')(selectedEvent)) {
      return (
        <>
          <Modal.Header closeButton>
            <Modal.Title>Completed Tool Call</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
            <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
            <div className="mb-2"><strong>Duration:</strong> {selectedEvent.payload.duration_seconds.toFixed(2)}s</div>
            <div className="mb-2"><strong>Tool:</strong> {selectedEvent.payload.tool_name}.{selectedEvent.payload.api_name}</div>
            {selectedEvent.payload.node_id && (
              <div className="mb-2"><strong>Node ID:</strong> {selectedEvent.payload.node_id}</div>
            )}
            <div className="mb-2">
              <strong>Status:</strong> 
              <Badge bg={selectedEvent.payload.state === 'SUCCESS' ? "success" : "danger"} className="ms-2">
                {selectedEvent.payload.state}
              </Badge>
            </div>
            {selectedEvent.payload.error && (
              <div className="mb-3">
                <strong>Error:</strong>
                <div className="border rounded p-2 mt-1 bg-light text-danger">
                  {selectedEvent.payload.error}
                </div>
              </div>
            )}
          </Modal.Body>
        </>
      );
    }

    return (
      <>
        <Modal.Header closeButton>
          <Modal.Title>Event Details</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="mb-2"><strong>Event Type:</strong> {selectedEvent.event_type}</div>
          <div className="mb-2"><strong>Timestamp:</strong> {formatTimestamp(selectedEvent.timestamp)}</div>
          <div>
            <strong>Payload:</strong>
            <pre className="border rounded p-2 mt-1 bg-light">
              {JSON.stringify(selectedEvent.payload, null, 2)}
            </pre>
          </div>
        </Modal.Body>
      </>
    );
  };

  return (
    <div className="dashboard-container">
      {/* Summary Card */}
      <Row className="mb-4">
        <Col>
          <Card>
            <Card.Header>Run Summary</Card.Header>
            <Card.Body>
              <Row>
                <Col md={3} className="mb-3 mb-md-0">
                  <div className="text-center">
                    <h2 className="mb-0">{totalSteps}</h2>
                    <div className="text-muted">Steps</div>
                  </div>
                </Col>
                <Col md={3} className="mb-3 mb-md-0">
                  <div className="text-center">
                    <h2 className="mb-0">{totalNodes}</h2>
                    <div className="text-muted">Nodes</div>
                  </div>
                </Col>
                <Col md={3} className="mb-3 mb-md-0">
                  <div className="text-center">
                    <h2 className="mb-0">{totalLlmCalls}</h2>
                    <div className="text-muted">LLM Calls</div>
                  </div>
                </Col>
                <Col md={3}>
                  <div className="text-center">
                    <h2 className="mb-0">{totalToolCalls}</h2>
                    <div className="text-muted">Tool Calls</div>
                  </div>
                </Col>
              </Row>
              <hr />
              <Row>
                <Col md={6} className="d-flex justify-content-between">
                  <span><strong>Run Started:</strong></span>
                  <span>{runStartTime}</span>
                </Col>
                <Col md={6} className="d-flex justify-content-between">
                  <span><strong>Completed Nodes:</strong></span>
                  <span>{completedNodes} / {totalNodes}</span>
                </Col>
              </Row>
              {totalNodes > 0 && (
                <Row className="mt-2">
                  <Col>
                    <ProgressBar 
                      now={totalNodes > 0 ? (completedNodes / totalNodes) * 100 : 0} 
                      variant="success" 
                      label={`${Math.round((completedNodes / totalNodes) * 100)}%`}
                    />
                  </Col>
                </Row>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Activity Cards Row */}
      <Row className="mb-4">
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Active Steps</span>
              <Badge bg="primary">{activeStepsArray.length}</Badge>
            </Card.Header>
            <ListGroup variant="flush" style={{ height: '300px', overflowY: 'auto' }}>
              {activeStepsArray.length > 0 ? (
                activeStepsArray.map(event => (
                  <ListGroup.Item 
                    key={event.event_id} 
                    style={listItemStyle}
                    onClick={() => handleEventClick(event)}
                  >
                    <div style={titleStyle}>
                      <Badge bg="secondary" className="me-2">Step {event.payload.step}</Badge>
                      {event.payload.node_goal ? event.payload.node_goal.substring(0, 30) + '...' : 'Step in progress'}
                    </div>
                    <div className="d-flex align-items-center">
                      <Spinner animation="border" size="sm" className="me-2" />
                      <Info size={16} />
                    </div>
                  </ListGroup.Item>
                ))
              ) : (
                <ListGroup.Item className="text-center text-muted">No active steps</ListGroup.Item>
              )}
            </ListGroup>
          </Card>
        </Col>

        <Col md={4}>
          <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Active LLM Calls</span>
              <Badge bg="info">{activeLlmCallsArray.length}</Badge>
            </Card.Header>
            <ListGroup variant="flush" style={{ height: '300px', overflowY: 'auto' }}>
              {activeLlmCallsArray.length > 0 ? (
                activeLlmCallsArray.map((event: AgentEvent) => {
                  if (!isEventType('llm_call_started')(event)) {
                    return null;
                  }
                  return (
                    <ListGroup.Item 
                      key={event.event_id} 
                      style={listItemStyle}
                      onClick={() => handleEventClick(event)}
                    >
                      <div style={titleStyle}>
                        <span className="me-2">{event.payload.model}</span>
                        {event.payload.prompt_preview ? event.payload.prompt_preview.substring(0, 30) + '...' : 'LLM call in progress'}
                      </div>
                      <div className="d-flex align-items-center">
                        <Spinner animation="border" size="sm" className="me-2" />
                        <Info size={16} />
                      </div>
                    </ListGroup.Item>
                  );
                })
              ) : (
                <ListGroup.Item className="text-center text-muted">No active LLM calls</ListGroup.Item>
              )}
            </ListGroup>
          </Card>
        </Col>

        <Col md={4}>
          <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Active Tool Calls</span>
              <Badge bg="warning">{activeToolCallsArray.length}</Badge>
            </Card.Header>
            <ListGroup variant="flush" style={{ height: '300px', overflowY: 'auto' }}>
              {activeToolCallsArray.length > 0 ? (
                activeToolCallsArray.map(event => {
                  if (!isEventType('tool_invoked')(event)) {
                    return null;
                  }
                  return (
                    <ListGroup.Item 
                      key={event.event_id} 
                      style={listItemStyle}
                      onClick={() => handleEventClick(event)}
                    >
                      <div style={titleStyle}>
                        <span className="me-2">{event.payload.tool_name}.{event.payload.api_name}</span>
                        {event.payload.args_summary ? event.payload.args_summary.substring(0, 30) + '...' : 'Tool call in progress'}
                      </div>
                      <div className="d-flex align-items-center">
                        <Spinner animation="border" size="sm" className="me-2" />
                        <Info size={16} />
                      </div>
                    </ListGroup.Item>
                  );
                })
              ) : (
                <ListGroup.Item className="text-center text-muted">No active tool calls</ListGroup.Item>
              )}
            </ListGroup>
          </Card>
        </Col>
      </Row>

      {/* Completed LLM Calls */}
      <Row>
        <Col md={6}>
          <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Completed LLM Calls</span>
              <Button 
                variant="link" 
                size="sm" 
                onClick={() => setShowCompletedLlm(!showCompletedLlm)}
                className="p-0 d-flex align-items-center"
              >
                <Badge bg="secondary" className="me-2">{completedLlmCalls.length}</Badge>
                {showCompletedLlm ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
              </Button>
            </Card.Header>
            {showCompletedLlm && (
              <ListGroup variant="flush" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {completedLlmCalls.length > 0 ? (
                  completedLlmCalls.map((call) => {
                    if (!isEventType('llm_call_completed')(call)) {
                      return null;
                    }
                    return (
                      <ListGroup.Item 
                        key={call.payload.call_id} 
                        style={listItemStyle}
                        onClick={() => handleEventClick(call)}
                      >
                        <div style={titleStyle}>
                          <Badge bg={call.payload.error ? "danger" : "success"} className="me-2">
                            {call.payload.error ? "Error" : "Success"}
                          </Badge>
                          <span>{call.payload.model}</span>
                        </div>
                        <div className="d-flex align-items-center">
                          <small className="text-muted me-2">{call.payload.duration_seconds.toFixed(1)}s</small>
                          <Info size={16} />
                        </div>
                      </ListGroup.Item>
                    );
                  })
                ) : (
                  <ListGroup.Item className="text-center text-muted">No completed LLM calls</ListGroup.Item>
                )}
              </ListGroup>
            )}
          </Card>
        </Col>

        {/* Completed Tool Calls */}
        <Col md={6}>
          <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Completed Tool Calls</span>
               <Button 
                variant="link" 
                size="sm" 
                onClick={() => setShowCompletedTool(!showCompletedTool)}
                className="p-0 d-flex align-items-center"
              >
                <Badge bg="secondary" className="me-2">{completedToolCalls.length}</Badge>
                {showCompletedTool ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
              </Button>
            </Card.Header>
            {showCompletedTool && (
              <ListGroup variant="flush" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {completedToolCalls.length > 0 ? (
                  completedToolCalls.map(call => {
                    if (!isEventType('tool_returned')(call)) {
                      return null;
                    }
                    return (
                      <ListGroup.Item 
                        key={call.payload.tool_call_id} 
                        style={listItemStyle}
                        onClick={() => handleEventClick(call)}
                      >
                        <div style={titleStyle}>
                          <Badge bg={call.payload.state === 'SUCCESS' ? "success" : "danger"} className="me-2">
                            {call.payload.state}
                          </Badge>
                          <span>{call.payload.tool_name}.{call.payload.api_name}</span>
                        </div>
                        <div className="d-flex align-items-center">
                          <small className="text-muted me-2">{call.payload.duration_seconds.toFixed(1)}s</small>
                          <Info size={16} />
                        </div>
                      </ListGroup.Item>
                    );
                  })
                ) : (
                  <ListGroup.Item className="text-center text-muted">No completed tool calls</ListGroup.Item>
                )}
              </ListGroup>
            )}
          </Card>
        </Col>
      </Row>

      {/* Event Details Modal */}
      <Modal show={showEventModal} onHide={closeEventModal} size="lg">
        {renderEventDetails()}
        <Modal.Footer>
          <Button variant="secondary" onClick={closeEventModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};
export default Dashboard; 

