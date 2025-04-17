import React from 'react';
import { ConnectionStatus } from '../features/events/eventsApi';
import { Alert } from 'react-bootstrap';

interface StatusIndicatorProps {
    status: ConnectionStatus;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status }) => {
    let variant: string;
    let text: string;

    switch (status) {
        case ConnectionStatus.Connected:
            variant = 'success';
            text = 'Connected';
            break;
        case ConnectionStatus.Connecting:
            variant = 'warning';
            text = 'Connecting...';
            break;
        case ConnectionStatus.Disconnected:
        default:
            variant = 'danger';
            text = 'Disconnected';
            break;
    }

    return (
        <Alert variant={variant} className="mt-3 mb-3 text-center">
            {text}
        </Alert>
    );
};

export default StatusIndicator; 