# React Event Modal Implementation Guide

## Introduction

The Recursive Agent Event Logging System provides real-time visibility into the execution of the agent through a Redis-based event streaming architecture. This guide focuses on the UI component that displays detailed information about individual events through a modal interface with tabbed content.

This document serves as a comprehensive tutorial for developers who want to understand, maintain, or extend the event modal functionality in the React UI. We'll cover architecture, implementation details, and provide examples for adding new tabs and adapting the modal for new event types.

## Architecture Overview

### Event Monitoring System

Before diving into the modal implementation, it's important to understand the broader event monitoring system:

1. **Event Generation**: The agent emits events during execution (e.g., `step_started`, `llm_call_completed`)
2. **Event Streaming**: Events are published to Redis and read by the WebSocket server
3. **WebSocket API**: The client connects to a WebSocket endpoint to receive events in real-time
4. **React UI**: Events are displayed in a table and can be inspected in detail via the modal

### Modal Component Architecture

The event modal follows a component-based architecture with these key elements:

1. **EventDetailModal Component**: The main component that renders different content based on event type
2. **Tabbed Interface**: Uses React Bootstrap's `Tab` and `Nav` components for organized content
3. **Dynamic Tab Generation**: Dynamically adds tabs based on event type and available data
4. **Type-Specific Rendering**: Renders different content based on event type and schema

### Data Flow

The data flow for the modal is as follows:

1. User clicks on an event row in the EventTable component
2. EventTable sets the selected event and shows the modal
3. EventDetailModal receives the event via props and renders appropriate tabs
4. Tabs display different views of the event data (summary, JSON, special tabs, metadata)

## Implementation Details

### EventDetailModal Component

The `EventDetailModal` component is the core of this feature. Here's a simplified view of its structure:

```typescript
interface EventDetailModalProps {
  show: boolean;
  onHide: () => void;
  event: AgentEvent | null;
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({ show, onHide, event }) => {
  const [activeTab, setActiveTab] = useState('summary');
  
  if (!event) return null;

  // Helper functions for rendering
  const formatTimestamp = (isoString: string): string => {...}
  const copyJsonToClipboard = () => {...}
  const formatPreview = (text: string, maxLength: number = 500): string => {...}

  // Get special tabs based on event type
  const getSpecialTabs = () => {...}
  const specialTabs = getSpecialTabs();

  // Render event-specific content
  const renderSummaryContent = () => {...}
  const renderPromptMessages = (messages: LlmMessage[]) => {...}

  return (
    <Modal show={show} onHide={onHide} size="lg" centered>
      <Modal.Header>...</Modal.Header>
      <Modal.Body>
        <Tab.Container activeKey={activeTab} onSelect={...}>
          <Nav variant="tabs">...</Nav>
          <Tab.Content>...</Tab.Content>
        </Tab.Container>
      </Modal.Body>
    </Modal>
  );
};
```

### Standard Tabs

The modal always includes these standard tabs:

1. **Summary**: Type-specific view of event details
2. **JSON**: Raw JSON representation of the event
3. **Metadata**: Key event metadata in a table format

### Special Tabs

Special tabs are added dynamically based on event type. For example:

- `llm_call_started` events get a "Prompt" tab
- `llm_call_completed` events get a "Response" tab

This is handled by the `getSpecialTabs()` function, which returns an array of tab objects based on the event type.

## Extending the Modal for New Event Types

To add support for a new event type in the modal, follow these steps:

### 1. Update the Summary Tab Content

Modify the `renderSummaryContent()` function to handle your new event type:

```typescript
const renderSummaryContent = () => {
  // Existing cases...

  if (isEventType('your_new_event_type')(event)) {
    return (
      <div className="card">
        <div className="card-header bg-light py-2">
          <strong>Event Specific Heading</strong>
        </div>
        <div className="card-body">
          <div className="row g-2">
            <div className="col-md-6">
              <p className="mb-1"><strong>Field 1:</strong> {event.payload.field1}</p>
            </div>
            <div className="col-md-6">
              <p className="mb-1"><strong>Field 2:</strong> {event.payload.field2}</p>
            </div>
          </div>
          {/* Additional content as needed */}
        </div>
      </div>
    );
  }

  // Default case...
}
```

### 2. Add Special Tabs (if needed)

If your event type has detailed data that deserves its own tab, extend the `getSpecialTabs()` function:

```typescript
const getSpecialTabs = () => {
  // Existing cases...
  
  if (isEventType('your_new_event_type')(event) && event.payload.special_data) {
    return [
      {
        key: 'special_tab',
        title: 'Special Tab',
        content: (
          <div className="card">
            <div className="card-header bg-light py-2">
              <strong>Special Data</strong>
            </div>
            <div className="card-body">
              {/* Render your special data here */}
              <pre style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {JSON.stringify(event.payload.special_data, null, 2)}
              </pre>
            </div>
          </div>
        )
      }
    ];
  }
  
  return [];
}
```

### 3. Update Type Definitions (if needed)

If your new event type has a unique payload structure, you'll need to update the type definitions in `eventsApi.ts`:

```typescript
export interface YourNewEventPayload {
  field1: string;
  field2: number;
  special_data?: any;
  // Other fields...
}

// Add to the AgentEvent type union
export type AgentEvent =
  | {
      event_id: string;
      timestamp: string;
      event_type: "your_new_event_type";
      run_id?: string | null;
      payload: YourNewEventPayload;
    }
  | // Other event types...
```

### 4. Add Styling (if needed)

If your event type needs special styling, add CSS rules to `styles.css`:

```css
/* Your new event type styles */
.special-data-container {
  background-color: #f8f9fa;
  border-left: 4px solid #6c757d;
}
```

## Adding Complex Visualizations

For more complex visualizations or interactive elements within a tab, you can create a dedicated component:

```typescript
// In a separate file: SpecialVisualizationComponent.tsx
import React from 'react';
import { YourNewEventPayload } from '../features/events/eventsApi';

interface Props {
  data: YourNewEventPayload;
}

const SpecialVisualizationComponent: React.FC<Props> = ({ data }) => {
  // Implement your visualization using the data
  return (
    <div className="special-visualization">
      {/* Your visualization here */}
    </div>
  );
};

export default SpecialVisualizationComponent;
```

Then import and use this component in your special tab:

```typescript
import SpecialVisualizationComponent from './SpecialVisualizationComponent';

// In getSpecialTabs()
content: (
  <div className="card">
    <div className="card-header bg-light py-2">
      <strong>Special Visualization</strong>
    </div>
    <div className="card-body">
      <SpecialVisualizationComponent data={event.payload} />
    </div>
  </div>
)
```

## Best Practices

When extending the event modal, follow these best practices:

1. **Type Safety**: Always use TypeScript's type system to ensure type safety
2. **Responsive Design**: Ensure your UI elements are responsive and accessible
3. **Performance**: Be mindful of rendering performance, especially for large data sets
4. **Error Handling**: Implement robust error handling for missing or malformed data
5. **Consistent UX**: Maintain a consistent user experience with the rest of the application
6. **Component Reuse**: Create reusable components for common patterns

## Example: Adding a Graph Visualization Tab

Let's walk through a complete example of adding a graph visualization tab for a hypothetical event type that contains graph data.

### 1. Define the Event Type

```typescript
// In eventsApi.ts
export interface GraphNode {
  id: string;
  label: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface GraphDataPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

// Add to the AgentEvent type union
export type AgentEvent =
  | {
      event_id: string;
      timestamp: string;
      event_type: "graph_data_generated";
      run_id?: string | null;
      payload: GraphDataPayload;
    }
  | // Other event types...
```

### 2. Create a Graph Visualization Component

```typescript
// GraphVisualization.tsx
import React, { useEffect, useRef } from 'react';
import { GraphDataPayload } from '../features/events/eventsApi';
import ForceGraph2D from 'react-force-graph-2d';

interface Props {
  data: GraphDataPayload;
}

const GraphVisualization: React.FC<Props> = ({ data }) => {
  const graphRef = useRef<any>(null);
  
  useEffect(() => {
    if (graphRef.current) {
      // Configure the graph once it's mounted
      graphRef.current.d3Force('charge').strength(-120);
    }
  }, []);
  
  // Convert our data format to what the graph component expects
  const graphData = {
    nodes: data.nodes.map(node => ({ id: node.id, name: node.label })),
    links: data.edges.map(edge => ({ 
      source: edge.source, 
      target: edge.target,
      label: edge.label
    }))
  };
  
  return (
    <div style={{ height: '500px', width: '100%' }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeLabel="name"
        linkLabel="label"
        nodeColor={() => '#1E88E5'}
        linkColor={() => '#757575'}
      />
    </div>
  );
};

export default GraphVisualization;
```

### 3. Update Event Detail Modal

```typescript
// In EventDetailModal.tsx

import GraphVisualization from './GraphVisualization';

// In getSpecialTabs()
if (isEventType('graph_data_generated')(event) && event.payload.nodes?.length > 0) {
  return [
    {
      key: 'graph',
      title: 'Graph Visualization',
      content: (
        <div className="card">
          <div className="card-header bg-light py-2">
            <strong>Graph Visualization</strong>
            <span className="ms-2 badge bg-secondary">
              {event.payload.nodes.length} nodes, {event.payload.edges.length} edges
            </span>
          </div>
          <div className="card-body p-0">
            <GraphVisualization data={event.payload} />
          </div>
        </div>
      )
    }
  ];
}
```

### 4. Add Summary Content

```typescript
// In renderSummaryContent()
if (isEventType('graph_data_generated')(event)) {
  return (
    <>
      <div className="card mb-3">
        <div className="card-header bg-light py-2">
          <strong>Graph Data Information</strong>
        </div>
        <div className="card-body">
          <div className="row g-2">
            <div className="col-md-6">
              <p className="mb-1"><strong>Nodes:</strong> {event.payload.nodes.length}</p>
              <p className="mb-1"><strong>Edges:</strong> {event.payload.edges.length}</p>
            </div>
            <div className="col-md-6">
              {event.payload.metadata && (
                <>
                  <p className="mb-1"><strong>Algorithm:</strong> {event.payload.metadata.algorithm || 'N/A'}</p>
                  <p className="mb-1"><strong>Source:</strong> {event.payload.metadata.source || 'N/A'}</p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-header bg-light py-2">
          <strong>Graph Preview</strong>
        </div>
        <div className="card-body">
          <p className="mb-1">
            <strong>Node Examples:</strong>{' '}
            {event.payload.nodes.slice(0, 3).map(n => n.label).join(', ')}
            {event.payload.nodes.length > 3 ? ', ...' : ''}
          </p>
          <p className="mb-2">
            <strong>Edge Examples:</strong>{' '}
            {event.payload.edges.slice(0, 3).map(e => `${e.source} → ${e.target}`).join(', ')}
            {event.payload.edges.length > 3 ? ', ...' : ''}
          </p>
          <div className="text-end mt-3">
            <Button size="sm" variant="outline-primary" onClick={() => setActiveTab('graph')}>
              View Graph Visualization
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
```

## Tutorial: Creating a Mock Event

For testing purposes, you might want to create mock events to test your UI components. Here's how to create and use mock events:

### 1. Create a Mock Event Factory

```typescript
// mockEvents.ts
import { AgentEvent } from '../features/events/eventsApi';

export const createMockGraphEvent = (): AgentEvent => {
  return {
    event_id: `mock-${Date.now()}`,
    timestamp: new Date().toISOString(),
    event_type: "graph_data_generated",
    run_id: "mock-run-123",
    payload: {
      nodes: [
        { id: "n1", label: "Node 1" },
        { id: "n2", label: "Node 2" },
        { id: "n3", label: "Node 3" },
        { id: "n4", label: "Node 4" },
        { id: "n5", label: "Node 5" },
      ],
      edges: [
        { source: "n1", target: "n2", label: "connects to" },
        { source: "n1", target: "n3", label: "depends on" },
        { source: "n2", target: "n4", label: "creates" },
        { source: "n3", target: "n5", label: "influences" },
        { source: "n4", target: "n5", label: "affects" },
      ],
      metadata: {
        algorithm: "force-directed",
        source: "task_dependency_analyzer",
        created_at: new Date().toISOString(),
      }
    }
  };
};

export const createMockLlmCallStartedEvent = (): AgentEvent => {
  return {
    event_id: `mock-${Date.now()}`,
    timestamp: new Date().toISOString(),
    event_type: "llm_call_started",
    run_id: "mock-run-123",
    payload: {
      agent_class: "MockAgent",
      model: "gpt-4o-mini",
      step: 3,
      node_id: "node-xyz-123",
      prompt_preview: "Analyze the following data and provide insights...",
      prompt: [
        {
          role: "system",
          content: "You are a helpful data analysis assistant."
        },
        {
          role: "user",
          content: "Analyze the following data and provide insights:\n\n```\nuser_id,purchase_amount,date\n1,120.50,2023-04-15\n2,45.20,2023-04-15\n3,200.00,2023-04-16\n```"
        }
      ]
    }
  };
};

// Add more mock event factories as needed
```

### 2. Use Mock Events for Testing

```typescript
// In a test component
import React, { useState } from 'react';
import { Button } from 'react-bootstrap';
import EventDetailModal from './EventDetailModal';
import { createMockGraphEvent, createMockLlmCallStartedEvent } from '../utils/mockEvents';

const EventModalTester: React.FC = () => {
  const [mockEvent, setMockEvent] = useState<AgentEvent | null>(null);
  const [showModal, setShowModal] = useState(false);
  
  const showGraphEvent = () => {
    setMockEvent(createMockGraphEvent());
    setShowModal(true);
  };
  
  const showLlmEvent = () => {
    setMockEvent(createMockLlmCallStartedEvent());
    setShowModal(true);
  };
  
  const handleCloseModal = () => {
    setShowModal(false);
  };
  
  return (
    <div className="p-3">
      <h2>Event Modal Tester</h2>
      <div className="mb-3">
        <Button variant="primary" className="me-2" onClick={showGraphEvent}>
          Show Graph Event
        </Button>
        <Button variant="info" onClick={showLlmEvent}>
          Show LLM Call Event
        </Button>
      </div>
      
      <EventDetailModal 
        show={showModal}
        onHide={handleCloseModal}
        event={mockEvent}
      />
    </div>
  );
};

export default EventModalTester;
```

### 3. Quick-Test in the Browser Console

You can also test directly in the browser console if the application is running:

```javascript
// In browser console
const mockEvent = {
  event_id: "mock-123",
  timestamp: new Date().toISOString(),
  event_type: "llm_call_started",
  run_id: "mock-run-123",
  payload: {
    agent_class: "TestAgent",
    model: "gpt-4o",
    prompt_preview: "Test prompt",
    prompt: [
      { role: "system", content: "You are a test assistant" },
      { role: "user", content: "This is a test" }
    ]
  }
};

// Assuming there's a way to access the React component instance
// This depends on how your app is structured
window.__setMockEvent(mockEvent);
```

## Conclusion

This guide provided a comprehensive overview of the event modal implementation, including:

1. Understanding the architecture and data flow
2. Implementing event type-specific rendering
3. Adding special tabs for detailed data visualization
4. Following best practices for extensibility and performance
5. Creating mock events for testing

By following these patterns, you can extend the event modal to handle new event types and create rich, interactive visualizations that provide deeper insights into the agent's behavior and performance.

Remember that this UI component is part of a larger event monitoring system, and changes should be coordinated with the backend event generation and data structures to ensure consistency and compatibility. 