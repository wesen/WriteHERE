import React, { useState, useCallback } from 'react';
import { Canvas, Node, Edge, ElkCanvasLayoutOptions } from 'reaflow';
import { useSelector } from 'react-redux';
import { selectReaflowGraph } from '../features/graph/reaflowAdapter';
import { CustomNode } from './reaflow/CustomNode';
import './reaflow/ReaflowCanvas.css';
import { RootState } from '../store';
import Spinner from 'react-bootstrap/Spinner';
import Alert from 'react-bootstrap/Alert';
import NodeDetailModal from './NodeDetailModal.tsx';

const layout: ElkCanvasLayoutOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.spacing.nodeNode': '100',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
};

export const GraphCanvas: React.FC = () => {
  const { nodes, edges } = useSelector(selectReaflowGraph);
  const { loading, initialized, error } = useSelector((state: RootState) => ({
    loading: state.graph.loading,
    initialized: state.graph.initialized,
    error: state.graph.error
  }));
  
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [showNodeModal, setShowNodeModal] = useState(false);

  const onNodeClick = useCallback((id: string) => {
    console.log("Node clicked:", id);
    setSelectedNodeId(id);
    setShowNodeModal(true);
  }, []);

  // Clear selection when clicking on canvas
  const onCanvasClick = useCallback(() => {
    // Optionally: keep track of selection for visual highlight separately
    // Or hide the modal if clicked outside
    // setShowNodeModal(false); // Consider if this is desired behavior
  }, []);

  // Show loading indicator
  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '300px' }}>
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading graph...</span>
        </Spinner>
        <span className="ms-2">Loading graph state from server...</span>
      </div>
    );
  }

  // Show error if present
  if (error) {
    return (
      <Alert variant="danger">
        <Alert.Heading>Error Loading Graph State</Alert.Heading>
        <p>{error}</p>
      </Alert>
    );
  }

  // Show empty state if no nodes
  if (!initialized || nodes.length === 0) {
    return (
      <div className="text-center p-5">
        <p className="text-muted">No graph nodes available. Start an agent run to visualize the graph.</p>
      </div>
    );
  }

  return (
    <div style={{ userSelect: 'none' }} onClick={onCanvasClick}>
      <Canvas
        direction="DOWN"
        fit
        pannable
        zoomable
        nodes={nodes}
        edges={edges}
        layoutOptions={layout}
        node={
          <Node>
            {(p) => (
              <CustomNode
                nodeProps={p}
                selectedNode={selectedNodeId}
                onNodeClick={onNodeClick}
              />
            )}
          </Node>
        }
        edge={<Edge />}
      />
      {/* Render the modal */}
      {selectedNodeId && (
        <NodeDetailModal
          show={showNodeModal}
          onHide={() => {
            setShowNodeModal(false);
            setSelectedNodeId(null); // Clear selection when modal closes
          }}
          nodeId={selectedNodeId}
        />
      )}
    </div>
  );
}; 