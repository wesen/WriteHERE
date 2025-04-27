import React, { useState, useRef, useEffect } from 'react';
import { useGetEventsQuery, ConnectionStatus, AgentEvent, KnownEventType } from '../features/events/eventsApi';
import { Table, Spinner, Alert, Form, Button, Badge, ButtonGroup } from 'react-bootstrap';
import { isEventType } from '../helpers/eventType'; // Import the type guard
import './styles.css'; // We'll add a separate styles file
import { useAppDispatch, useAppSelector } from '../store';
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

// Event types categories for filtering
const EVENT_CATEGORIES = {
    STEPS: ['step_started', 'step_finished'],
    NODES: ['node_created', 'node_status_changed', 'node_result_available', 'node_added'],
    GRAPH: ['plan_received', 'edge_added', 'inner_graph_built'],
    LLM: ['llm_call_started', 'llm_call_completed'],
    TOOLS: ['tool_invoked', 'tool_returned']
};

// All known event types
const ALL_EVENT_TYPES: KnownEventType[] = [
    'step_started', 'step_finished',
    'node_created', 'node_status_changed', 'node_result_available', 'node_added',
    'plan_received', 'edge_added', 'inner_graph_built',
    'llm_call_started', 'llm_call_completed',
    'tool_invoked', 'tool_returned'
];

const EventTable: React.FC = () => {
    const { data, error, isLoading } = useGetEventsQuery(undefined, {
        // pollingInterval: 30000, 
    });
    const dispatch = useAppDispatch();
    const events = data?.events ?? [];
    const status = data?.status ?? ConnectionStatus.Connecting;
    
    // Get current event from modal stack
    const modalStack = useAppSelector(state => state.modalStack.stack);
    const currentEventId = modalStack.length > 0 && modalStack[modalStack.length - 1].type === 'event' 
        ? modalStack[modalStack.length - 1].params.eventId
        : null;
    
    // Add state for auto-scroll toggle
    const [autoScroll, setAutoScroll] = useState(false);
    // Add state for event type filtering
    const [activeEventTypes, setActiveEventTypes] = useState<KnownEventType[]>(ALL_EVENT_TYPES);
    const tableEndRef = useRef<HTMLDivElement>(null);
    const highlightedRowRef = useRef<HTMLTableRowElement>(null);
    
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
    
    // Scroll to highlighted row when it changes
    useEffect(() => {
        if (currentEventId && highlightedRowRef.current) {
            highlightedRowRef.current.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }
    }, [currentEventId]);

    // Handle toggling a specific event type
    const toggleEventType = (eventType: KnownEventType) => {
        if (activeEventTypes.includes(eventType)) {
            setActiveEventTypes(activeEventTypes.filter(type => type !== eventType));
        } else {
            setActiveEventTypes([...activeEventTypes, eventType]);
        }
    };

    // Handle toggling all event types in a category
    const toggleCategory = (category: KnownEventType[]) => {
        // Check if all types in this category are currently active
        const allActive = category.every(type => activeEventTypes.includes(type));
        
        if (allActive) {
            // Remove all types in this category
            setActiveEventTypes(activeEventTypes.filter(type => !category.includes(type)));
        } else {
            // Add all types in this category that aren't already active
            const typesToAdd = category.filter(type => !activeEventTypes.includes(type));
            setActiveEventTypes([...activeEventTypes, ...typesToAdd]);
        }
    };

    // Toggle all event types
    const toggleAllEventTypes = () => {
        if (activeEventTypes.length === ALL_EVENT_TYPES.length) {
            setActiveEventTypes([]);
        } else {
            setActiveEventTypes([...ALL_EVENT_TYPES]);
        }
    };

    if (isLoading && !data) {
        return <Spinner animation="border" role="status" className="d-block mx-auto mt-5"><span className="visually-hidden">Loading...</span></Spinner>;
    }

    if (error) {
        const errorMessage = error instanceof Error ? error.message : JSON.stringify(error);
        return <Alert variant="danger">Error loading events: {errorMessage}. Check console.</Alert>;
    }

    // Filter events by active event types
    const filteredEvents = events.filter(event => 
        activeEventTypes.includes(event.event_type as KnownEventType)
    );

    // Get events in the correct order based on auto-scroll setting
    const displayEvents = autoScroll ? [...filteredEvents] : [...filteredEvents].reverse();

    return (
        <>
            <div className="mb-3">
                <div className="d-flex justify-content-between align-items-center mb-2">
                    <h6 className="mb-0">Filter Event Types</h6>
                    <Button 
                        size="sm" 
                        variant="outline-secondary"
                        onClick={toggleAllEventTypes}
                    >
                        {activeEventTypes.length === ALL_EVENT_TYPES.length ? 'Clear All' : 'Select All'}
                    </Button>
                </div>
                
                <div className="d-flex flex-wrap gap-2 mb-3">
                    <div>
                        <Badge bg="secondary" className="mb-1">Steps</Badge>
                        <ButtonGroup size="sm" className="d-flex">
                            {EVENT_CATEGORIES.STEPS.map(type => (
                                <Button 
                                    key={type}
                                    variant={activeEventTypes.includes(type as KnownEventType) ? "primary" : "outline-primary"}
                                    onClick={() => toggleEventType(type as KnownEventType)}
                                    className="py-1 px-2"
                                >
                                    <EventTypeBadge eventType={type} size="sm" showIcon={false} />
                                </Button>
                            ))}
                            <Button
                                variant="outline-secondary"
                                onClick={() => toggleCategory(EVENT_CATEGORIES.STEPS as KnownEventType[])}
                                className="py-1 px-2"
                            >
                                {EVENT_CATEGORIES.STEPS.every(type => activeEventTypes.includes(type as KnownEventType)) ? 'Clear' : 'All'}
                            </Button>
                        </ButtonGroup>
                    </div>
                    
                    <div>
                        <Badge bg="secondary" className="mb-1">Nodes</Badge>
                        <ButtonGroup size="sm" className="d-flex">
                            {EVENT_CATEGORIES.NODES.map(type => (
                                <Button 
                                    key={type}
                                    variant={activeEventTypes.includes(type as KnownEventType) ? "primary" : "outline-primary"}
                                    onClick={() => toggleEventType(type as KnownEventType)}
                                    className="py-1 px-2"
                                >
                                    <EventTypeBadge eventType={type} size="sm" showIcon={false} />
                                </Button>
                            ))}
                            <Button
                                variant="outline-secondary"
                                onClick={() => toggleCategory(EVENT_CATEGORIES.NODES as KnownEventType[])}
                                className="py-1 px-2"
                            >
                                {EVENT_CATEGORIES.NODES.every(type => activeEventTypes.includes(type as KnownEventType)) ? 'Clear' : 'All'}
                            </Button>
                        </ButtonGroup>
                    </div>
                    
                    <div>
                        <Badge bg="secondary" className="mb-1">Graph</Badge>
                        <ButtonGroup size="sm" className="d-flex">
                            {EVENT_CATEGORIES.GRAPH.map(type => (
                                <Button 
                                    key={type}
                                    variant={activeEventTypes.includes(type as KnownEventType) ? "primary" : "outline-primary"}
                                    onClick={() => toggleEventType(type as KnownEventType)}
                                    className="py-1 px-2"
                                >
                                    <EventTypeBadge eventType={type} size="sm" showIcon={false} />
                                </Button>
                            ))}
                            <Button
                                variant="outline-secondary"
                                onClick={() => toggleCategory(EVENT_CATEGORIES.GRAPH as KnownEventType[])}
                                className="py-1 px-2"
                            >
                                {EVENT_CATEGORIES.GRAPH.every(type => activeEventTypes.includes(type as KnownEventType)) ? 'Clear' : 'All'}
                            </Button>
                        </ButtonGroup>
                    </div>
                    
                    <div>
                        <Badge bg="secondary" className="mb-1">LLM</Badge>
                        <ButtonGroup size="sm" className="d-flex">
                            {EVENT_CATEGORIES.LLM.map(type => (
                                <Button 
                                    key={type}
                                    variant={activeEventTypes.includes(type as KnownEventType) ? "primary" : "outline-primary"}
                                    onClick={() => toggleEventType(type as KnownEventType)}
                                    className="py-1 px-2"
                                >
                                    <EventTypeBadge eventType={type} size="sm" showIcon={false} />
                                </Button>
                            ))}
                            <Button
                                variant="outline-secondary"
                                onClick={() => toggleCategory(EVENT_CATEGORIES.LLM as KnownEventType[])}
                                className="py-1 px-2"
                            >
                                {EVENT_CATEGORIES.LLM.every(type => activeEventTypes.includes(type as KnownEventType)) ? 'Clear' : 'All'}
                            </Button>
                        </ButtonGroup>
                    </div>
                    
                    <div>
                        <Badge bg="secondary" className="mb-1">Tools</Badge>
                        <ButtonGroup size="sm" className="d-flex">
                            {EVENT_CATEGORIES.TOOLS.map(type => (
                                <Button 
                                    key={type}
                                    variant={activeEventTypes.includes(type as KnownEventType) ? "primary" : "outline-primary"}
                                    onClick={() => toggleEventType(type as KnownEventType)}
                                    className="py-1 px-2"
                                >
                                    <EventTypeBadge eventType={type} size="sm" showIcon={false} />
                                </Button>
                            ))}
                            <Button
                                variant="outline-secondary"
                                onClick={() => toggleCategory(EVENT_CATEGORIES.TOOLS as KnownEventType[])}
                                className="py-1 px-2"
                            >
                                {EVENT_CATEGORIES.TOOLS.every(type => activeEventTypes.includes(type as KnownEventType)) ? 'Clear' : 'All'}
                            </Button>
                        </ButtonGroup>
                    </div>
                </div>
            </div>
            
            <div className="d-flex justify-content-between align-items-center mb-2">
                <div>
                    <small className="text-muted">
                        Showing {displayEvents.length} of {events.length} events
                    </small>
                </div>
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
                        {displayEvents.length === 0 && events.length > 0 && (
                            <tr>
                                <td colSpan={6} className="text-center text-muted p-4">No events match the current filters</td>
                            </tr>
                        )}
                        {displayEvents.map((event) => {
                            const nodeIdInfo = getEventNodeIdInfo(event);
                            const isHighlighted = currentEventId === event.event_id;
                            
                            return (
                                <tr 
                                    key={event.event_id} 
                                    style={{ verticalAlign: 'middle', cursor: 'pointer' }}
                                    onClick={() => handleEventClick(event)}
                                    className={`event-row ${isHighlighted ? 'event-row-highlighted' : ''}`}
                                    ref={isHighlighted ? highlightedRowRef : null}
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