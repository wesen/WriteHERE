import React from 'react';
import { Canvas, Node, Edge, ElkCanvasLayoutOptions } from 'reaflow';
import { useSelector } from 'react-redux';
import { selectReaflowGraph } from '../features/graph/reaflowAdapter';
import { CustomNode } from './reaflow/CustomNode';
import './reaflow/ReaflowCanvas.css';
import { RootState } from '../app/store';
import Spinner from 'react-bootstrap/Spinner';
import Alert from 'react-bootstrap/Alert';

const layout: ElkCanvasLayoutOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.spacing.nodeNode': '100',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
};

const noSelectStyle = { userSelect: 'none' };

export const GraphCanvas: React.FC = () => {
  const { nodes, edges } = useSelector(selectReaflowGraph);
  const { loading, initialized, error } = useSelector((state: RootState) => ({
    loading: state.graph.loading,
    initialized: state.graph.initialized,
    error: state.graph.error
  }));
  
  const [selected, setSelected] = React.useState<string | null>(null);

  const onNodeClick = React.useCallback((e: React.MouseEvent, data: any) => {
    e.stopPropagation();
    if (data.node) {
      setSelected(data.node.id);
    }
  }, []);

  // Clear selection when clicking on canvas
  const onCanvasClick = React.useCallback(() => {
    setSelected(null);
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
    <div style={noSelectStyle} onClick={onCanvasClick}>
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
                selectedNode={selected}
                onNodeClick={onNodeClick}
              />
            )}
          </Node>
        }
        edge={<Edge />}
      />
    </div>
  );
}; 