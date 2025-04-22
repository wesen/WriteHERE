import React from 'react';
import { Canvas, Node, Edge, ElkCanvasLayoutOptions } from 'reaflow';
import { useSelector } from 'react-redux';
import { selectReaflowGraph } from '../features/graph/reaflowAdapter';
import { CustomNode } from './reaflow/CustomNode';
import './reaflow/ReaflowCanvas.css';

const layout: ElkCanvasLayoutOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.spacing.nodeNode': '80',
  'elk.layered.spacing.nodeNodeBetweenLayers': '80'
};

export const GraphCanvas: React.FC = () => {
  const { nodes, edges } = useSelector(selectReaflowGraph);
  const [selected, setSelected] = React.useState<string | null>(null);

  const onNodeClick = (id: string | undefined) => {
    if (id) {
        setSelected(id);
    }
  }

  return (
    <div style={{ width: '100%', height: '80vh' }}>
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