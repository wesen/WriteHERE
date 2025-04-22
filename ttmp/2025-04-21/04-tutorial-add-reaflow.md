Below is a “drop‑in” guide that shows how to bolt your **normalized Redux graph slice** onto the **Reaflow** canvas, *reuse* the custom‑styled node prototype you already built, and keep the diagram in‑sync with the live WebSocket stream.

---

### 0  Prerequisites & one‑line install

```bash
# in ui-react/
npm i reaflow
```

> You already depend on React 19 and Vite, so no extra setup is needed. Reaflow bundles the ELK layout engine and TypeScript types.citeturn1search0turn1search1

---

## 1  Copy the prototype pieces into **ui‑react**

1.  **Copy files**  
    from the prototype repo into `src/components/reaflow/` inside *ui‑react*  

    ```
    CustomNode.tsx
    nodeConfig.ts
    App.css      → Re‑name to ReaflowCanvas.css (only the node/edge styles)
    ```

2.  **Adjust imports** so they resolve relative to `ui‑react/src/components/reaflow/…`.

3.  **Delete** the stateful logic in the prototype’s `App.tsx`; we’ll feed data from Redux instead.

---

## 2  Create a selector that converts slice data ⇒ Reaflow shapes

```ts
// src/features/graph/reaflowAdapter.ts
import { MyNodeData } from '../../components/reaflow/CustomNode';
import { createSelector } from '@reduxjs/toolkit';
import {
  selectAllNodesData,
  selectAllEdgesData
} from './selectors';         // ← already in your codebase

const NODE_W = 260;
const NODE_H = 164;

export const selectReaflowGraph = createSelector(
  [selectAllNodesData, selectAllEdgesData],
  (nodes, edges) => {
    const rNodes: MyNodeData[] = nodes.map((n) => ({
      id: n.id,
      width: NODE_W,
      height: NODE_H,
      data: {
        type: n.taskType === 'COMPOSITION' ? 'goal'
            : n.layer === 0             ? 'goal'
            : n.layer === 1             ? 'subtask'
            : 'action',
        title: n.goal,
        description: `(${n.type})`,
        // decorate with live status
        stats: { status: n.status ?? 'N/A' },
        showStats: true,
        showError: n.status === 'FAILED'
      }
    }));

    const rEdges = edges.map((e) => ({
      id: e.id,
      from: e.parent,
      to:   e.child,
      className: 'edge-hierarchy'
    }));

    return { nodes: rNodes, edges: rEdges };
  }
);
```

*Why a selector?*  
It memo‑caches the transformation, so **Reaflow re-renders only when the slice actually changes**, not on every Redux update.

---

## 3  A dedicated `<GraphCanvas>` component

```tsx
// src/components/GraphCanvas.tsx
import React from 'react';
import { Canvas, Node, Edge, ElkCanvasLayoutOptions } from 'reaflow';
import { useAppSelector } from '../store';
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
  const { nodes, edges } = useAppSelector(selectReaflowGraph);
  const [selected, setSelected] = React.useState<string | null>(null);

  const onNodeClick = (id: string) => setSelected(id);

  return (
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
              onAddClick={() => { /* optional – future feature */ }}
            />
          )}
        </Node>
      }
      edge={<Edge />}
    />
  );
};
```

*Why this works:* every time `nodeAdded`, `edgeAdded`, or `nodeUpdated` is dispatched by the WebSocket handler, the slice mutates → the selector recomputes → React re‑renders `<GraphCanvas>` with the new arrays → Reaflow performs an internal diff and patches the SVG.

---

## 4  Surface the diagram in the main UI

Add Bootstrap tabs (or your preferred layout) in `src/App.tsx`:

```tsx
import Tabs from 'react-bootstrap/Tabs';
import Tab from 'react-bootstrap/Tab';
import EventTable from './components/EventTable';
import { GraphCanvas } from './components/GraphCanvas';

export default function App() {
  return (
    <Container fluid className="pt-4">
      <h1 className="text-center mb-4">Recursive Agent — Live Monitor</h1>
      <Tabs defaultActiveKey="events" id="main-tabs">
        <Tab eventKey="events"      title="Events"><EventTable /></Tab>
        <Tab eventKey="task-graph"  title="Task Graph"><GraphCanvas /></Tab>
      </Tabs>
    </Container>
  );
}
```

---

## 5  Color & status mapping (optional polish)

If you want node borders to reflect **live status** instead of task type:

1.  Extend `nodeConfig.ts` with a `statusColors` map.
2.  In the selector, *override* `color` / `backgroundColor` based on `n.status`.
3.  Reaflow will update the node because its `data` object is shallow‑compared.

---

## 6  Performance checklist

| Concern | Solution |
|---------|----------|
| **Large graphs** | Keep `maxEvents` trimming in the WebSocket handler so the slice doesn’t balloon. |
| **Layout thrash** | The layered ELK algorithm is fast, but for > 1 000 nodes switch to `'elk.algorithm': 'mrtree'`. |
| **React re‑renders** | The `createSelector` memo keeps `nodes` / `edges` referentially stable unless something truly changed. |

---

## 7  Testing the live update

1.  Run backend + frontend as usual.  
2.  Trigger an event that creates a new node (e.g., `node_created`).  
   *You should see the node appear instantly in the “Task Graph” tab.*  
3.  Force a status change (`node_status_changed`) and watch the color swap.

If you do **not** see an update:

* Verify the WebSocket console logs.  
* Confirm your slice receives the action (`redux‑devtools`).  
* Ensure the selector’s arrays actually gain/patch items (log length).

---

### What you achieved

* **Single source‑of‑truth:** the normalized graph slice is now powering both the data table *and* an interactive DAG.  
* **Zero extra network calls:** all updates piggy‑back on the existing WebSocket.  
* **Design consistency:** you reused the rich node card styling and button affordances from your prototype with no duplication.

You can now iterate on richer interactions—inline editing, status legends, zoom‑to‑selection—without touching the back end. Happy hacking! 🚀