import React from 'react';
import { Badge } from 'react-bootstrap';
import { Play, CheckCircle, ArrowRight, Clock, Zap, Database, Search, AlertCircle, GitCommit, FileCode, Network, PlusCircle, GitFork, FileText, Icon } from 'lucide-react';
import { eventTypeBadgeVariant } from '../helpers/eventConstants'; // Import shared constant

// Map event types to icons and colors (consolidated from EventTable)
const eventTypeConfig: { [key: string]: { icon: Icon, bsTextColor: string } } = {
    step_started: { icon: Play, bsTextColor: 'primary' },
    step_finished: { icon: CheckCircle, bsTextColor: 'success' },
    node_status_changed: { icon: ArrowRight, bsTextColor: 'info' },
    llm_call_started: { icon: Clock, bsTextColor: 'warning' },
    llm_call_completed: { icon: Zap, bsTextColor: 'warning' }, 
    tool_invoked: { icon: Database, bsTextColor: 'secondary' }, 
    tool_returned: { icon: Database, bsTextColor: 'secondary' }, 
    search_completed: { icon: Search, bsTextColor: 'primary' }, 
    node_created: { icon: GitCommit, bsTextColor: 'info' },
    plan_received: { icon: FileCode, bsTextColor: 'info' },
    node_added: { icon: PlusCircle, bsTextColor: 'success' },
    edge_added: { icon: GitFork, bsTextColor: 'secondary' },
    inner_graph_built: { icon: Network, bsTextColor: 'primary' },
    node_result_available: { icon: FileText, bsTextColor: 'warning' },
    default: { icon: AlertCircle, bsTextColor: 'dark' }
};

interface EventTypeBadgeProps {
    eventType: string;
    showIcon?: boolean;
    size?: "sm";
}

const EventTypeBadge: React.FC<EventTypeBadgeProps> = ({ eventType, showIcon = true, size }) => {
    const eventTypeKey = eventType as keyof typeof eventTypeConfig;
    const config = Object.prototype.hasOwnProperty.call(eventTypeConfig, eventTypeKey)
        ? eventTypeConfig[eventTypeKey]
        : eventTypeConfig.default;
    
    const badgeVariantKey = eventType as keyof typeof eventTypeBadgeVariant;
    const bsVariant = Object.prototype.hasOwnProperty.call(eventTypeBadgeVariant, badgeVariantKey)
        ? eventTypeBadgeVariant[badgeVariantKey] + '-subtle'
        : eventTypeBadgeVariant.default;

    const IconComponent = config.icon;

    return (
        <Badge 
            pill 
            bg={bsVariant as any} // Cast needed as TS struggles with constructed string types
            text={config.bsTextColor as any} // Cast needed
            className={`d-inline-flex align-items-center fw-medium ${size === 'sm' ? 'py-1 px-2' : ''}`}
            style={size === 'sm' ? { fontSize: '0.8em' } : {}}
        >
            {showIcon && <IconComponent size={size === 'sm' ? 10 : 12} className="me-1" />}
            {eventType.toLowerCase().replace(/_/g, ' ')}
        </Badge>
    );
};

export default EventTypeBadge; 