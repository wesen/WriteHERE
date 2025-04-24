import React, { useMemo, useState } from 'react';
import { Modal, Spinner, Card, Row, Col, Badge, ListGroup, Placeholder, Button } from 'react-bootstrap';
import { useSelector } from 'react-redux';
import { selectNodeById } from '../features/graph/selectors';
import { useGetEventsQuery, AgentEvent } from '../features/events/eventsApi';
import { RootState } from '../store';
import NodeEventDetailPane from './NodeEventDetailPane';
import { isEventType } from '../helpers/eventType';
import { ArrowLeft } from 'react-feather';
import { formatTimestamp, RenderClickableNodeId } from '../helpers/formatters';

import { statusColorMap, } from '../helpers/eventConstants';
import EventTypeBadge from './EventTypeBadge';
import EventPayloadDetails from './EventPayloadDetails';

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
      // Check payload properties safely without using 'any'
      const p = event.payload;
      if (typeof p !== 'object' || p === null) return false; // Ensure payload is an object

      // Check for specific properties before accessing them
      return (
        ('node_id' in p && p.node_id === nodeId) ||
        ('added_node_id' in p && p.added_node_id === nodeId) ||
        ('parent_node_id' in p && p.parent_node_id === nodeId) ||
        ('child_node_id' in p && p.child_node_id === nodeId) ||
        ('graph_owner_node_id' in p && p.graph_owner_node_id === nodeId)
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

  const handleEventClick = (event: AgentEvent) => {
    if (onEventClick) {
      onEventClick(event.event_id);
    } else {
      setSelectedEvent(event); // Fallback to original behavior
    }
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
            {nodeCreatedEvent && isEventType('node_created')(nodeCreatedEvent) && (
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
                          ? <RenderClickableNodeId nodeId={nodeCreatedEvent.payload.outer_node_id} onNodeClick={onNodeClick} />
                          : 'N/A'}
                      </p>
                      <p className="mb-1">
                        <strong>Root Node:</strong>{' '}
                        <RenderClickableNodeId nodeId={nodeCreatedEvent.payload.root_node_id} onNodeClick={onNodeClick} />
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
                      className="d-flex justify-content-between align-items-start p-2 event-list-item"
                    >
                      <div className="flex-grow-1 me-2" style={{ minWidth: 0 }}>
                        <div className="d-flex justify-content-between align-items-center mb-1">
                          <EventTypeBadge eventType={event.event_type} size="sm" />
                          <small className="text-muted text-nowrap ms-2">{formatTimestamp(event.timestamp)}</small>
                        </div>
                        <div className="event-details-container">
                           <EventPayloadDetails event={event} onNodeClick={onNodeClick} className="small"/>
                        </div>
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