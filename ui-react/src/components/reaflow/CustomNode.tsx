import React from 'react';
import { NodeChildProps } from 'reaflow';
// Removed: import { MyNodeData } from './App'; -> This type will be defined in reaflowAdapter
import { nodeConfig } from './nodeConfig';
import './ReaflowCanvas.css'; // Make sure CSS is imported

// Define node dimensions directly here or import if needed elsewhere
const NODE_WIDTH = 260;
const NODE_HEIGHT = 164; // Matches reachat-codesandbox including button space
// Removed unused: const NODE_BUTTON_SIZE = 32; // From reachat style

// --- Helper Components (can remain as they are type/data driven) ---

interface NodeStatsProps {
showStats?: boolean;
// Changed: stats?: Record<string, number>; -> Use string | number for status
stats?: Record<string, string | number>;
}

// Explicitly type MyNodeData inline based on usage and tutorial
export interface MyNodeData {
  id: string;
  width?: number; // Make optional
  height?: number; // Make optional
  data: {
    type: string; // Added 'container' as a possible type
    title: string;
    description: string;
    stats: { // Make stats optional for container
      status?: string;
    } | Record<string, never>; // Allow empty object for container
    showStats: boolean;
    showError: boolean;
  };
  parent?: string; // Change to optional string (undefined)
  className?: string; // Added for container styling
}


const NodeStats: React.FC<NodeStatsProps> = ({ showStats, stats }) =>
showStats && stats ? (
  <ul className="node-stats">
    {Object.entries(stats).map(([label, count]) => (
      <li key={label}>
        <span>{label}</span>
        <strong>{count}</strong>
      </li>
    ))}
  </ul>
) : null;

interface NodeContentProps {
// Changed: node: MyNodeData; -> Use the inline defined type
node: MyNodeData;
selected?: boolean;
onClick?: () => void;
}

const NodeContent: React.FC<NodeContentProps> = ({ node, selected, onClick }) => {
// Ensure data exists before accessing properties
const nodeData = node.data || {} as MyNodeData['data'];
const type = nodeData.type || 'default'; // Handle potentially missing type
const title = nodeData.title || 'Node Title';
const description = nodeData.description || 'Node Description';
const showError = nodeData.showError;

// Handle case where stats might be empty object for container
const stats = typeof nodeData.stats === 'object' && nodeData.stats !== null ? nodeData.stats : {};

const { color, icon, backgroundColor } = nodeConfig(type);

// Use inline styles derived from nodeConfig for simplicity
const nodeContentStyle: React.CSSProperties = {
  borderLeft: `4px solid ${color}`,
  backgroundColor: backgroundColor,
  color: '#333' // Default text color
};

const nodeIconStyle: React.CSSProperties = {
  color: color // Use the node's primary color for the icon
};

return (
  <div
    className="node-content"
    style={nodeContentStyle}
    onClick={onClick}
    aria-selected={selected ? 'true' : 'false'} // Ensure aria-selected is string 'true'/'false'
  >
    {showError && <div className="node-error-badge"></div>}
    <div className="node-icon" style={nodeIconStyle}>{icon}</div>
    <div className="node-details">
      <h1>{title}</h1> {/* Removed ID from title here */}
      <p>{description}</p>
    </div>
    <NodeStats stats={stats as Record<string, string | number>} showStats={nodeData.showStats} />
  </div>
);
};

// --- Main CustomNode Component ---

export interface CustomNodeProps {
  nodeProps: {
    node: MyNodeData;
    x?: number;
    y?: number;
  };
  selectedNode: string | null;
  onNodeClick?: (id: string) => void;
  onAddClick?: (node: MyNodeData) => void;
}

export const CustomNode: React.FC<CustomNodeProps> = ({
  nodeProps,
  selectedNode,
  onNodeClick,
  onAddClick
}) => {
  const { node } = nodeProps; // node here is NodeChildProps['node'], which includes calculated x, y, width, height
  const width = node.width ?? NODE_WIDTH; // Use calculated width, fallback to default
  const height = node.height ?? NODE_HEIGHT; // Use calculated height, fallback to default
  const isSelected = selectedNode === node.id;
  const isDisabled = false;
  const isContainer = node.data?.type === 'container';

  // Ensure node.data exists before accessing its properties
  const nodeInternalData = node.data || {} as MyNodeData['data'];

  // Determine if add button should be shown
  const showAddButton = !isContainer && nodeInternalData.type !== 'end' && onAddClick;

  return (
    <foreignObject x={0} y={0}
     width={width} height={height}
     className="node-style-reset"
     >
      {/* Render container node differently */}
      {isContainer ? (
         <div className={`node-container-wrapper ${node.className || ''}`} />
      ) : (
        <div className={`node-wrapper ${node.parent ? 'node-nested-content' : ''}`}>
          <NodeContent
            node={node as MyNodeData}
            selected={isSelected}
            onClick={onNodeClick ? () => onNodeClick(node.id) : undefined}
          />

          {showAddButton && (
            <div className="add-button">
              <button
                disabled={isDisabled}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onAddClick) onAddClick(node as MyNodeData);
                }}
              >
                +
              </button>
            </div>
          )}
        </div>
      )}
    </foreignObject>
  );
}; 