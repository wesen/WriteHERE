import React, { useMemo, useState } from 'react';
import { Modal, Spinner, Card, Row, Col, Badge, ListGroup, Placeholder, Button } from 'react-bootstrap';
import { useSelector } from 'react-redux';
import { selectNodeById } from '../features/graph/selectors';
import { useGetEventsQuery, AgentEvent } from '../features/events/eventsApi';
import { RootState } from '../store';
import NodeEventDetailPane from './NodeEventDetailPane';
import { isEventType } from '../helpers/eventType';
import { ArrowLeft } from 'react-feather';

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

interface NodeDetailModalProps {
  show: boolean;
  onHide: () => void;
  nodeId: string;
  onNodeClick?: (nodeId: string) => void;
  onEventClick?: (eventId: string) => void;
  hasPrevious?: boolean;
  onBack?: () => void;
}

const NodeDetailModal: React.FC<NodeDetailModalProps> = ({ 
  show, 
  onHide, 
  nodeId, 
  onNodeClick,
  onEventClick,
  hasPrevious = false,
  onBack
}) => {
  const node = useSelector((state: RootState) => selectNodeById(state, nodeId));
  const { data: eventsData, isLoading: isLoadingEvents } = useGetEventsQuery();
  const [selectedEvent, setSelectedEvent] = useState<AgentEvent | null>(null);

  // Filter events related to this node
  const nodeEvents = useMemo(() => {
    if (!eventsData || !nodeId) return [];
    return eventsData.events.filter(event => {
      const p = event.payload as any; // Use 'any' for easier access, ensure type safety if needed
      return (
        p.node_id === nodeId ||
        p.added_node_id === nodeId ||
        p.parent_node_id === nodeId ||
        p.child_node_id === nodeId ||
        p.graph_owner_node_id === nodeId
      );
    }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()); // Sort newest first
  }, [eventsData, nodeId]);

  // Find the node_created event for this node
  const nodeCreatedEvent = useMemo(() => {
    if (!nodeEvents) return null;
    return nodeEvents.find(event => 
      isEventType('node_created')(event) && 
      event.payload.node_id === nodeId
    );
  }, [nodeEvents, nodeId]);

  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
        month: 'short',
        day: 'numeric',
      });
    } catch (e) {
      console.error(`[NodeDetailModal] Error formatting timestamp: ${e}`);
      return isoString;
    }
  };

  const getBadgeVariant = (eventType: string): string => {
    return eventTypeBadgeVariant[eventType] || eventTypeBadgeVariant.default;
  };

  // Status color mapping (copied from EventDetailModal for consistency)
  const statusColorMap: { [key: string]: string } = {
    NOT_READY: 'secondary',
    READY: 'primary',
    PLANNING: 'info',
    PLANNING_POST_REFLECT: 'info',
    DOING: 'warning',
    FINISH: 'success',
    FAILED: 'danger',
  };

  const handleEventClick = (event: AgentEvent) => {
    if (onEventClick) {
      onEventClick(event.event_id);
    } else {
      setSelectedEvent(event); // Fallback to original behavior
    }
  };

  // Render a clickable node ID
  const renderClickableNodeId = (nodeId: string, label?: string, truncate: boolean = true) => {
    const displayText = truncate ? `${nodeId.substring(0, 8)}...` : nodeId;
    
    return onNodeClick ? (
      <Button
        variant="link"
        className="p-0 text-decoration-none" 
        onClick={() => onNodeClick(nodeId)}
      >
        {label || displayText}
      </Button>
    ) : (
      label || displayText
    );
  };

  const handleBackClick = () => {
    if (onBack) {
      onBack();
    }
  };

  return (
    <Modal show={show} onHide={onHide} size="lg" centered scrollable>
      <Modal.Header closeButton>
        <div className="d-flex align-items-center w-100">
          {hasPrevious && (
            <Button variant="link" className="p-0 me-2" onClick={handleBackClick}>
              <ArrowLeft size={20} />
            </Button>
          )}
          <Modal.Title className="flex-grow-1">
            Node Details: {node ? `${node.type} (${node.nid})` : nodeId.substring(0, 8) + '...'}
          </Modal.Title>
        </div>
      </Modal.Header>
      <Modal.Body>
        {!node ? (
          <div className="text-center">
            <Spinner animation="border" size="sm" /> Loading node data...
          </div>
        ) : (
          <>
            {/* Node Creation Details */}
            {nodeCreatedEvent && (
              <Card className="mb-3">
                <Card.Header className="bg-light">
                  <div className="d-flex justify-content-between align-items-center">
                    <strong>Node Creation Details</strong>
                    <small className="text-muted">{formatTimestamp(nodeCreatedEvent.timestamp)}</small>
                  </div>
                </Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <p className="mb-1"><strong>Node Type:</strong> {nodeCreatedEvent.payload.node_type}</p>
                      <p className="mb-1"><strong>Task Type:</strong> {nodeCreatedEvent.payload.task_type}</p>
                      <p className="mb-1"><strong>Layer:</strong> {nodeCreatedEvent.payload.layer}</p>
                      <p className="mb-1">
                        <strong>Initial Parent NIDs:</strong>{' '}
                        {nodeCreatedEvent.payload.initial_parent_nids?.length 
                          ? nodeCreatedEvent.payload.initial_parent_nids.join(', ') 
                          : 'None'}
                      </p>
                    </Col>
                    <Col md={6}>
                      <p className="mb-1">
                        <strong>Outer Node:</strong>{' '}
                        {nodeCreatedEvent.payload.outer_node_id 
                          ? renderClickableNodeId(nodeCreatedEvent.payload.outer_node_id)
                          : 'N/A'}
                      </p>
                      <p className="mb-1">
                        <strong>Root Node:</strong>{' '}
                        {renderClickableNodeId(nodeCreatedEvent.payload.root_node_id)}
                      </p>
                    </Col>
                  </Row>
                  <hr />
                  <p><strong>Original Goal:</strong></p>
                  <pre className="bg-light p-2 rounded small">{nodeCreatedEvent.payload.task_goal}</pre>
                </Card.Body>
              </Card>
            )}

            {/* Current Node State */}
            <Card className="mb-3">
              <Card.Header>Current Node State</Card.Header>
              <Card.Body>
                <Row>
                  <Col md={6}>
                    <p><strong>ID:</strong> <code>{node.id}</code></p>
                    <p><strong>NID:</strong> {node.nid}</p>
                    <p><strong>Type:</strong> {node.type}</p>
                  </Col>
                  <Col md={6}>
                    <p><strong>Task Type:</strong> {node.taskType || 'N/A'}</p>
                    <p><strong>Layer:</strong> {node.layer}</p>
                    <p>
                      <strong>Status:</strong> 
                      <Badge bg={statusColorMap[node.status || 'N/A'] || 'light'} className="ms-2">
                        {node.status}
                      </Badge>
                    </p>
                  </Col>
                </Row>
                <hr />
                <p><strong>Current Goal:</strong></p>
                <pre className="bg-light p-2 rounded small">{node.goal || 'No goal specified'}</pre>
              </Card.Body>
            </Card>

            {/* Event List Section */}
            <Card className="mt-3">
              <Card.Header>Related Events ({nodeEvents.length})</Card.Header>
              <ListGroup variant="flush" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {isLoadingEvents ? (
                  <ListGroup.Item>
                    <Placeholder as="p" animation="glow">
                      <Placeholder xs={12} />
                    </Placeholder>
                  </ListGroup.Item>
                ) : nodeEvents.length === 0 ? (
                  <ListGroup.Item>No events found for this node.</ListGroup.Item>
                ) : (
                  nodeEvents.map(event => (
                    <ListGroup.Item
                      key={event.event_id}
                      action
                      onClick={() => handleEventClick(event)}
                      active={selectedEvent?.event_id === event.event_id}
                      className="d-flex justify-content-between align-items-center"
                    >
                      <div>
                        <Badge bg={getBadgeVariant(event.event_type)} className="me-2">
                          {event.event_type}
                        </Badge>
                        <small className="text-muted">{formatTimestamp(event.timestamp)}</small>
                      </div>
                    </ListGroup.Item>
                  ))
                )}
              </ListGroup>
            </Card>

            {/* Event Detail Pane Section */}
            {selectedEvent && !onEventClick && (
              <div className="mt-3">
                <NodeEventDetailPane 
                  event={selectedEvent} 
                  onNodeClick={onNodeClick}
                />
              </div>
            )}
          </>
        )}
      </Modal.Body>
    </Modal>
  );
};

export default NodeDetailModal; 