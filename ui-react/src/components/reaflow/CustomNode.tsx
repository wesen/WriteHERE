import React from 'react';
import { NodeChildProps } from 'reaflow';
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
  // parent?: string; // No longer needed for flat structure
  text?: string; // Keep text for compatibility or specific uses if needed
  width?: number;
  height?: number;
  data?: {
    type?: string;
    title?: string;
    description?: string;
    stats?: Record<string, string | number>; // Use string | number for status
    showStats?: boolean;
    showError?: boolean;
  };
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
// Changed: nodeProps: NodeChildProps; -> Add MyNodeData to node
nodeProps: NodeChildProps;
selectedNode: string | null;
// nodes: MyNodeData[]; // No longer needed for parent check
onNodeClick: (id: string) => void;
// Changed: onAddClick: (node: MyNodeData) => void; -> Make optional as per tutorial
onAddClick?: (node: MyNodeData) => void;
}

export const CustomNode: React.FC<CustomNodeProps> = ({
nodeProps,
selectedNode,
onNodeClick,
onAddClick
}) => {
const { node } = nodeProps; // x, y are provided but not used in this version
const width = node.width || NODE_WIDTH;
const height = node.height || NODE_HEIGHT;
  const isSelected = selectedNode === node.id;
  const isDisabled = false; // Add logic if needed

  // Determine if add button should be shown (e.g., hide for 'end' type)
  const showAddButton = node.data?.type !== 'end' && onAddClick; // Only show if handler provided

  return (
    <foreignObject x={0} y={0}
     width={width} height={height}
     className="node-style-reset" // Apply reset class here
     >
      {/* Wrapper div takes node-wrapper class */}
      <div className="node-wrapper">
        <NodeContent
          node={node}
          selected={isSelected}
          onClick={onNodeClick ? () => onNodeClick(node.id) : undefined}
        />

        {/* Add Button - similar structure to reachat */}
        {showAddButton && (
          <div className="add-button">
            {/* Basic button for now, can enhance with icons later */}
            <button
              disabled={isDisabled}
              // size="middle"
              // shape="circle"
              // icon={<PlusOutlined />}
              onClick={(e) => {
                e.stopPropagation(); // Prevent node click
                // Check if onAddClick exists before calling
                if (onAddClick) onAddClick(node);
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