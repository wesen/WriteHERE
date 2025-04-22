import React, { useMemo, useState } from 'react';
import { Modal, Spinner, Card, Row, Col, Badge, ListGroup, Placeholder } from 'react-bootstrap';
import { useSelector } from 'react-redux';
import { selectNodeById } from '../features/graph/selectors';
import { useGetEventsQuery, AgentEvent } from '../features/events/eventsApi';
import { RootState } from '../app/store';
import NodeEventDetailPane from './NodeEventDetailPane';

interface NodeDetailModalProps {
  show: boolean;
  onHide: () => void;
  nodeId: string;
}

const NodeDetailModal: React.FC<NodeDetailModalProps> = ({ show, onHide, nodeId }) => {
  // Initially, just display the node ID to confirm it works
  // We will add more details in the next steps

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

  return (
    <Modal show={show} onHide={onHide} size="lg" centered scrollable>
      <Modal.Header closeButton>
        <Modal.Title>
          Node Details: {node ? `${node.type} (${node.nid})` : nodeId.substring(0, 8) + '...'}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {!node ? (
          <div className="text-center">
            <Spinner animation="border" size="sm" /> Loading node data...
          </div>
        ) : (
          <Card className="mb-3">
            <Card.Header>Metadata</Card.Header>
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
                    <Badge bg={statusColorMap[node.status] || 'light'} className="ms-2">
                      {node.status}
                    </Badge>
                  </p>
                </Col>
              </Row>
              <hr />
              <p><strong>Goal:</strong></p>
              <pre className="bg-light p-2 rounded small">{node.goal || 'No goal specified'}</pre>
            </Card.Body>
          </Card>
        )}

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
                  key={event.id}
                  action
                  onClick={() => setSelectedEvent(event)}
                  active={selectedEvent?.id === event.id}
                  className="d-flex justify-content-between align-items-center"
                >
                  <div>
                    <Badge bg={getBadgeVariant(event.event_type)} className="me-2">
                      {event.event_type}
                    </Badge>
                    <small className="text-muted">{formatTimestamp(event.timestamp)}</small>
                  </div>
                  {/* Add more summary info if needed */}
                </ListGroup.Item>
              ))
            )}
          </ListGroup>
        </Card>

        {/* Event Detail Pane Section */}
        {selectedEvent && (
          <div className="mt-3">
            <NodeEventDetailPane event={selectedEvent} />
          </div>
        )}

      </Modal.Body>
    </Modal>
  );
};

export default NodeDetailModal; 