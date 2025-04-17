import React from 'react';
import { useGetEventsQuery, ConnectionStatus, AgentEvent } from '../features/events/eventsApi';
import { Table, Spinner, Alert, Badge } from 'react-bootstrap';
import { Play, CheckCircle, ArrowRight, Clock, Zap, Database, Search, AlertCircle } from 'lucide-react';

// Event type to icon/color mapping (similar to prototype)
const eventTypeConfig = {
    step_started: { icon: Play, color: 'text-blue-500', bgColor: 'bg-blue-100', bsVariant: 'primary-subtle', bsTextColor: 'primary' },
    step_finished: { icon: CheckCircle, color: 'text-green-500', bgColor: 'bg-green-100', bsVariant: 'success-subtle', bsTextColor: 'success' },
    node_status_change: { icon: ArrowRight, color: 'text-purple-500', bgColor: 'bg-purple-100', bsVariant: 'info-subtle', bsTextColor: 'info' }, // Changed to info for Bootstrap
    llm_call_started: { icon: Clock, color: 'text-yellow-500', bgColor: 'bg-yellow-100', bsVariant: 'warning-subtle', bsTextColor: 'warning' },
    llm_call_completed: { icon: Zap, color: 'text-yellow-600', bgColor: 'bg-yellow-100', bsVariant: 'warning-subtle', bsTextColor: 'warning' }, // Keep same as started for simplicity
    tool_invoked: { icon: Database, color: 'text-indigo-500', bgColor: 'bg-indigo-100', bsVariant: 'secondary-subtle', bsTextColor: 'secondary' }, // Changed to secondary
    tool_returned: { icon: Database, color: 'text-indigo-700', bgColor: 'bg-indigo-100', bsVariant: 'secondary-subtle', bsTextColor: 'secondary' }, // Keep same as invoked
    search_completed: { icon: Search, color: 'text-blue-700', bgColor: 'bg-blue-100', bsVariant: 'primary-subtle', bsTextColor: 'primary' }, // Reuse primary
    default: { icon: AlertCircle, color: 'text-gray-500', bgColor: 'bg-gray-100', bsVariant: 'light', bsTextColor: 'dark' }
};

// Status color mapping (using Bootstrap text colors)
const statusColorMap: { [key: string]: string } = {
    NOT_READY: 'text-secondary',
    READY: 'text-primary',
    DOING: 'text-warning',
    FINISH: 'text-success',
    FAILED: 'text-danger',
    PLAN_DONE: 'text-info', // Example, adjust as needed
    NEED_UPDATE: 'text-warning',
    FINAL_TO_FINISH: 'text-success',
    NEED_POST_REFLECT: 'text-primary',
};

// Utility function to format timestamp
function formatTimestamp(isoString: string): string {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString("en-US", {
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit',
            hour12: true 
        }).toLowerCase();
    } catch (e) {
        console.error("Error formatting timestamp:", isoString, e);
        return isoString; // Fallback
    }
}

// Utility to render payload details nicely using the discriminated union
function renderPayloadDetails(event: AgentEvent): React.ReactNode {
    switch (event.event_type) {
        case 'step_started':
            return <span className="text-muted text-truncate d-inline-block" style={{ maxWidth: '500px' }}>{event.payload.node_goal}</span>;
        case 'step_finished': {
            const statusClass = statusColorMap[event.payload.status_after] || 'text-dark';
            return (
                <div>
                    Action: <span className="fw-medium">{event.payload.action_name}</span>,
                    Status: <span className={`fw-medium ${statusClass}`}>{event.payload.status_after}</span>,
                    Duration: <span className="fw-medium">{event.payload.duration_seconds?.toFixed(2)}s</span>
                </div>
            );
        }
        case 'node_status_change': {
            const oldStatusClass = statusColorMap[event.payload.old_status] || 'text-dark';
            const newStatusClass = statusColorMap[event.payload.new_status] || 'text-dark';
            return (
                <div className="d-flex align-items-center">
                    <span className={oldStatusClass}>{event.payload.old_status}</span>
                    <ArrowRight size={14} className="mx-2 text-muted" />
                    <span className={newStatusClass}>{event.payload.new_status}</span>
                </div>
            );
        }
        case 'llm_call_started':
            return (
                <div className="text-truncate" style={{ maxWidth: '500px' }}>
                    Agent: <span className="fw-medium">{event.payload.agent_class}</span>,
                    Model: <span className="fw-medium">{event.payload.model}</span>
                </div>
            );
        case 'llm_call_completed':
            return (
                <div className="text-truncate" style={{ maxWidth: '500px' }}>
                    Model: <span className="fw-medium">{event.payload.model}</span>,
                    Agent: <span className="fw-medium">{event.payload.agent_class}</span>,
                    Duration: <span className="fw-medium">{event.payload.duration_seconds?.toFixed(2)}s</span>
                    {event.payload.token_usage && (
                        <span className="ms-2 small text-muted">
                            (Tokens: {event.payload.token_usage.prompt_tokens}p + {event.payload.token_usage.completion_tokens}c)
                        </span>
                    )}
                    {event.payload.error && <div className="text-danger small mt-1">Error: {event.payload.error}</div>}
                </div>
            );
        case 'tool_invoked':
            return (
                <div className="text-truncate" style={{ maxWidth: '500px' }}>
                    Tool: <span className="fw-medium">{event.payload.tool_name}</span>,
                    API: <span className="fw-medium">{event.payload.api_name}</span>
                </div>
            );
        case 'tool_returned':
             return (
                <div className="text-truncate" style={{ maxWidth: '500px' }}>
                    Tool: <span className="fw-medium">{event.payload.tool_name}</span>,
                    API: <span className="fw-medium">{event.payload.api_name}</span>,
                    State: <span className={`fw-medium ${event.payload.state === 'SUCCESS' ? 'text-success' : 'text-danger'}`}>{event.payload.state}</span>,
                    Duration: <span className="fw-medium">{event.payload.duration_seconds?.toFixed(2)}s</span>
                    {event.payload.error && <div className="text-danger small mt-1">Error: {event.payload.error}</div>}
                </div>
            );
        default:
            const payload = event.payload as Record<string, unknown>;
            return (
                <pre style={{ maxHeight: '100px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.85em', margin: 0 }}>
                    {JSON.stringify(payload, null, 2)}
                </pre>
            );
    }
}

const EventTable: React.FC = () => {
    const { data, error, isLoading } = useGetEventsQuery(undefined, {
        // pollingInterval: 30000, 
    });

    const events = data?.events ?? [];
    const status = data?.status ?? ConnectionStatus.Connecting;

    if (isLoading && !data) {
        return <Spinner animation="border" role="status" className="d-block mx-auto mt-5"><span className="visually-hidden">Loading...</span></Spinner>;
    }

    if (error) {
        const errorMessage = error instanceof Error ? error.message : JSON.stringify(error);
        return <Alert variant="danger">Error loading events: {errorMessage}. Check console.</Alert>;
    }

    const reversedEvents = [...events].reverse();

    return (
        <>
            <Table hover responsive size="sm" className="mt-0 mb-0 table-fixed">
                <colgroup>
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '15%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '65%' }} />
                </colgroup>
                <thead className="table-light border-bottom" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <tr>
                        <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Timestamp</th>
                        <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Type</th>
                        <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Run ID</th>
                        <th className="px-3 py-2 text-muted fw-medium text-uppercase small">Payload / Details</th>
                    </tr>
                </thead>
                <tbody>
                    {reversedEvents.length === 0 && status === ConnectionStatus.Connected && (
                        <tr>
                            <td colSpan={4} className="text-center text-muted p-4">Waiting for events...</td>
                        </tr>
                    )}
                    {reversedEvents.map((event) => {
                        const eventTypeKey = event.event_type as keyof typeof eventTypeConfig;
                        const config = eventTypeConfig.hasOwnProperty(eventTypeKey) 
                            ? eventTypeConfig[eventTypeKey] 
                            : eventTypeConfig.default;
                        const IconComponent = config.icon;
                        
                        return (
                            <tr key={event.event_id} style={{ verticalAlign: 'middle' }}>
                                <td className="px-3 py-2 text-muted small text-nowrap">{formatTimestamp(event.timestamp)}</td>
                                <td className="px-3 py-2">
                                    <Badge pill bg={config.bsVariant} text={config.bsTextColor as any} className="d-inline-flex align-items-center fw-medium">
                                        <IconComponent size={12} className="me-1" />
                                        {event.event_type.toLowerCase().replace(/_/g, ' ')}
                                    </Badge>
                                </td>
                                <td className="px-3 py-2 text-muted small font-monospace">{event.run_id?.substring(0, 8) || 'N/A'}</td>
                                <td className="px-3 py-2 text-muted small">
                                    {renderPayloadDetails(event)}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </Table>
        </>
    );
};

export default EventTable; 