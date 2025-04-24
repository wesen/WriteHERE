import React from 'react';
import { Button } from 'react-bootstrap';

// Utility function to format timestamp
export function formatTimestamp(isoString: string | undefined): string {
    if (!isoString) return 'N/A';
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


// Helper function to render a clickable node ID
interface RenderClickableNodeIdProps {
    nodeId: string | undefined | null;
    label?: string;
    truncate?: boolean;
    onNodeClick?: (nodeId: string) => void;
}

export const RenderClickableNodeId: React.FC<RenderClickableNodeIdProps> = ({
    nodeId,
    label,
    truncate = true,
    onNodeClick,
}) => {
    if (!nodeId) return <>N/A</>;
    
    const displayText = truncate ? `${nodeId.substring(0, 8)}...` : nodeId;
    
    return onNodeClick ? (
      <Button
        variant="link"
        className="p-0 text-decoration-none align-baseline" // Added align-baseline
        style={{ fontSize: 'inherit' }} // Ensure button text size matches surrounding text
        onClick={(e) => {
          e.stopPropagation(); // Prevent modal close or other parent clicks
          onNodeClick(nodeId);
        }}
      >
        {label || displayText}
      </Button>
    ) : (
      label || displayText
    );
}; 