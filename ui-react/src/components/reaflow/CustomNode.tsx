import React from 'react';
// Removed: import { MyNodeData } from './App'; -> This type will be defined in reaflowAdapter
import { nodeConfig } from './nodeConfig';

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
    type: string;
    title: string;
    description: string;
    stats: {
      status: string;
    };
    showStats: boolean;
    showError: boolean;
  };
  parent?: string; // Change to optional string (undefined)
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
const nodeData = node.data || {};
const type = nodeData.type || 'default';
const title = nodeData.title || 'Node Title';
const description = nodeData.description || 'Node Description';
const showError = nodeData.showError;

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
      {/* Added fallback for node.id */}
      <h1>{title} (ID: {node.id || 'N/A'})</h1>
      <p>{description}</p>
    </div>
    <NodeStats stats={nodeData.stats} showStats={nodeData.showStats} />
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
  // Check parent using the node passed in props
  const isNested = node.parent !== undefined;

  // Ensure node.data exists before accessing its properties
  const nodeInternalData = node.data || {} as MyNodeData['data']; // Use type assertion for safety

  // Determine if add button should be shown (e.g., hide for 'end' type)
  const showAddButton = nodeInternalData.type !== 'end' && onAddClick;

  return (
    <foreignObject x={0} y={0}
     width={width} height={height}
     className="node-style-reset"
     >
      {/* Use the node from props which has the necessary layout info and data */}
      <div className={`node-wrapper ${isNested ? 'node-nested' : ''}`}>
        <NodeContent
          node={node as MyNodeData} // Assert type for NodeContent which expects our defined MyNodeData
          selected={isSelected}
          onClick={onNodeClick ? () => onNodeClick(node.id) : undefined}
        />

        {showAddButton && (
          <div className="add-button">
            <button
              disabled={isDisabled}
              onClick={(e) => {
                e.stopPropagation();
                if (onAddClick) onAddClick(node as MyNodeData); // Assert type here too
              }}
            >
              +
            </button>
          </div>
        )}
      </div>
    </foreignObject>
  );
}; 