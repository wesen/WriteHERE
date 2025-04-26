import React, { useState, useRef, useEffect } from 'react';
import { useGetEventsQuery, ConnectionStatus, AgentEvent } from '../features/events/eventsApi';
import { Table, Spinner, Alert, Form } from 'react-bootstrap';
import { isEventType } from '../helpers/eventType'; // Import the type guard
import './styles.css'; // We'll add a separate styles file
import { useAppDispatch } from '../store';
import { pushModal } from '../features/ui/modalStackSlice';
import { formatTimestamp, RenderClickableNodeId } from '../helpers/formatters.tsx'; // Use shared formatter
import EventTypeBadge from './EventTypeBadge.tsx'; // Use shared badge
import EventPayloadDetails from './EventPayloadDetails.tsx'; // Use shared details renderer

// Helper function to extract common IDs or return N/A
const getEventStep = (event: AgentEvent): number | string => {
    if (isEventType('step_started')(event) || 
        isEventType('step_finished')(event) ||
        isEventType('node_created')(event) ||
        isEventType('plan_received')(event) ||
        isEventType('llm_call_started')(event) ||
        isEventType("llm_call_completed")(event) ||
        isEventType('node_status_changed')(event) ||
        isEventType('node_added')(event) ||
        isEventType('edge_added')(event) ||
        isEventType('inner_graph_built')(event) ||
        isEventType('tool_invoked')(event) ||
        isEventType('tool_returned')(event) ||
        isEventType('node_result_available')(event)) {

        return event.payload.step ?? 'N/A';
    }
    return 'N/A';
}

const getEventNodeIdInfo = (event: AgentEvent): { id: string | null, text: string } => {
    if (isEventType('step_started')(event) || 
        isEventType('step_finished')(event) ||
        isEventType('node_status_changed')(event) ||
        isEventType('llm_call_started')(event) ||
        isEventType("llm_call_completed")(event) ||
        isEventType("tool_invoked")(event) ||
        isEventType("tool_returned")(event) ||
        isEventType("node_created")(event) ||
        isEventType("plan_received")(event) ||
        isEventType("node_result_available")(event)) {
        const id = event.payload.node_id;
        return { id: id ?? null, text: id ? id.substring(0, 8) : 'N/A' };
    }
    
    if (isEventType("node_added")(event)) {
        const id = event.payload.added_node_id;
        return { id: id, text: id ? id.substring(0, 8) : 'N/A' };
    }
    
    if (isEventType("edge_added")(event)) {
        // For edges, maybe return the owner or null, display simplified text
        return { id: event.payload.graph_owner_node_id, text: `${event.payload.parent_node_nid}→${event.payload.child_node_nid}` };
    }
    
    if (isEventType("inner_graph_built")(event)) {
         const id = event.payload.node_id;
        return { id: id, text: id ? id.substring(0, 8) : 'N/A' };
    }
    
    return { id: null, text: 'N/A' };
}

const EventTable: React.FC = () => {
    const { data, error, isLoading } = useGetEventsQuery(undefined, {
        // pollingInterval: 30000, 
    });
    const dispatch = useAppDispatch();
    const events = data?.events ?? [];
    const status = data?.status ?? ConnectionStatus.Connecting;
    
    // Add state for auto-scroll toggle
    const [autoScroll, setAutoScroll] = useState(false);
    const tableEndRef = useRef<HTMLDivElement>(null);
    
    // Handle opening the modal with a specific event
    const handleEventClick = (event: AgentEvent) => {
        dispatch(pushModal({ type: 'event', params: { eventId: event.event_id } }));
    };

    const handleNodeClick = (nodeId: string) => {
        dispatch(pushModal({ type: 'node', params: { nodeId } }));
    };
    
    // Auto-scroll effect
    useEffect(() => {
        if (autoScroll && tableEndRef.current) {
            tableEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [events, autoScroll]);

    if (isLoading && !data) {
        return <Spinner animation="border" role="status" className="d-block mx-auto mt-5"><span className="visually-hidden">Loading...</span></Spinner>;
    }

    if (error) {
        const errorMessage = error instanceof Error ? error.message : JSON.stringify(error);
        return <Alert variant="danger">Error loading events: {errorMessage}. Check console.</Alert>;
    }

    // Get events in the correct order based on auto-scroll setting
    const displayEvents = autoScroll ? [...events] : [...events].reverse();

    return (
        <>
            <div className="d-flex justify-content-end mb-2">
                <Form>
                    <Form.Check 
                        type="switch"
                        id="auto-scroll-switch"
                        label="Auto-scroll to new events"
                        checked={autoScroll}
                        onChange={(e) => setAutoScroll(e.target.checked)}
                    />
                </Form>
            </div>
            <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                <Table hover responsive size="sm" className="mt-0 mb-0 table-fixed">
                    <colgroup>
                        <col style={{ width: '10%' }} />
                        <col style={{ width: '12%' }} />
                        <col style={{ width: '10%' }} />
                        <col style={{ width: '5%' }} />
                        <col style={{ width: '10%' }} />
                        <col style={{ width: '53%' }} />
                    </colgroup>
                    <thead className="table-light border-bottom" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                        <tr>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Timestamp</th>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Type</th>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small text-nowrap">Run ID</th>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small text-nowrap">Step #</th>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small text-nowrap">Node ID</th>
                            <th className="px-3 py-2 text-muted fw-medium text-uppercase small text-start">Payload / Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayEvents.length === 0 && status === ConnectionStatus.Connected && (
                            <tr>
                                <td colSpan={6} className="text-center text-muted p-4">Waiting for events...</td>
                            </tr>
                        )}
                        {displayEvents.map((event) => {
                            const nodeIdInfo = getEventNodeIdInfo(event);
                            
                            return (
                                <tr 
                                    key={event.event_id} 
                                    style={{ verticalAlign: 'middle', cursor: 'pointer' }}
                                    onClick={() => handleEventClick(event)}
                                    className="event-row"
                                >
                                    <td className="px-3 py-2 text-muted small text-nowrap">{formatTimestamp(event.timestamp)}</td>
                                    <td className="px-3 py-2">
                                        <EventTypeBadge eventType={event.event_type} />
                                    </td>
                                    <td className="px-3 py-2 text-muted small font-monospace text-nowrap">{event.run_id?.substring(0, 8) || 'N/A'}</td>
                                    <td className="px-3 py-2 text-muted small text-center">{getEventStep(event)}</td>
                                    <td className="px-3 py-2 text-muted small font-monospace text-nowrap">
                                        <RenderClickableNodeId 
                                            nodeId={nodeIdInfo.id} 
                                            label={nodeIdInfo.text} 
                                            truncate={false}
                                            onNodeClick={handleNodeClick} 
                                        />
                                    </td>
                                    <td className="px-3 py-2 text-muted small text-start">
                                        <EventPayloadDetails event={event} onNodeClick={handleNodeClick} showCallIds={true} />
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </Table>
                <div ref={tableEndRef} />
            </div>
        </>
    );
};

export default EventTable; 