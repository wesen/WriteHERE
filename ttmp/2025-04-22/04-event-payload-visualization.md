# Event Payload Visualization Improvements

## Overview

This document outlines a plan to enhance the visualization of event payloads in our event logging system. Based on the analysis of new event types and their payloads, we need to update both the event table summary view and the detailed modal view to better present this information.

## Current Implementation Analysis

Our current implementation in `EventTable.tsx` already supports basic display of the new event types (node_created, plan_received, node_added, edge_added, inner_graph_built, node_result_available), but there are several areas for improvement:

1. **Payload Field Truncation**: Many fields are truncated with ellipsis (...) which loses valuable information
2. **Contextual Information**: Most events contain contextual fields (node_id, task_type, step, etc.) that could be displayed more clearly
3. **Relationship Visualization**: Edge events show relationships that could be better visualized
4. **Code/Response Formatting**: Long text blocks like LLM responses or plans are not well-formatted

## Improvement Goals

1. **Enhance Summary Display**: Improve the compact representation of events in the main table
2. **Upgrade Detail Modal**: Create a more structured, context-aware detail view for each event type
3. **Add Visual Elements**: Incorporate appropriate visualizations for different event types
4. **Improve Readability**: Format code, JSON, and text content for better readability

## Specific Updates Needed

### Event Table Improvements

#### 1. Node Creation Events

Current display is basic and truncated. We should:

- Show node hierarchy information (layer, outer_node_id)
- Display node type with an appropriate icon/badge
- Highlight the node's position in the execution graph

#### 2. Edge Events

Current display shows parent → child relationship in basic text. We should:

- Use a small visual diagram showing the connection
- Color-code edges based on their status or type
- Show more context about what the connection represents

#### 3. Graph Building Events

Current representation is very minimal. We should:

- Show a small preview of the graph structure
- Include statistics about nodes/edges in a more readable format
- Indicate the context of the graph (e.g., planning, execution)

#### 4. LLM Call Events

Currently shows basic info about model and duration. We should:

- Better format token usage with visual indicators
- Show prompt type/template rather than truncated content
- Include clearer error state visualization when applicable

### Detail Modal Improvements

The current modal implementation is basic. For each event type, we should create specialized panels:

#### 1. Node Creation/Added Panel

- Show full node details in a structured format
- Include hierarchy information with visual representation
- Display relationships to parent/child nodes

#### 2. Edge Added Panel

- Include a visual representation of the nodes being connected
- Show the full context of both parent and child nodes
- Explain the dependency relationship

#### 3. Plan Received Panel

- Format the raw plan as a readable, syntax-highlighted JSON
- Include a visual representation of the plan structure
- Show dependencies between plan elements

#### 4. Inner Graph Built Panel

- Include a small graph visualization of the built structure
- Show full statistics about the graph
- List all nodes with their types and relationships

#### 5. LLM Call Panels

- Format the prompt and response with proper syntax highlighting
- Include collapsible sections for long content
- Show detailed token usage statistics
- Implement diffing for before/after in updates

## Implementation Considerations

### 1. Code Organization

- Create specialized renderer components for each event type
- Extract common functionality into utility functions
- Implement proper TypeScript interfaces for all event payloads

### 2. UI Components Needed

- Syntax highlighter for code/JSON content
- Collapsible panels for long content
- Small graph visualization for nodes/edges
- Progress bars or gauges for numerical data
- Badges and icons for status indicators

## Next Steps

1. Update TypeScript interfaces for all event types
2. Create specialized renderers for each event type's summary view
3. Implement detailed modal views for each event type
4. Add visualization components for graph structures
5. Improve the formatting of code and JSON content

## Example Mockups

### Node Creation Event Summary

```
NODE CREATED | Layer 1 | Type: PLAN_NODE | NID: "1"
Task: REASONING | Goal: "Design the overall outline..."
```

### Edge Added Event Summary

```
EDGE ADDED | 1.2 → 1.3 | Owner: ROOT_NODE
Context: Building graph for "Write introduction" task
```

### LLM Call Detail View

```
Agent: SimpleExecutor | Model: gpt-4o-mini | Duration: 11.12s

Tokens: 1,234 prompt + 567 completion = 1,801 total

[Prompt]
The collaborative report-writing requirement...
[expanded view with syntax highlighting]

[Response]
<think>
To design a comprehensive outline...
</think>
<result>
1. Introduction...
</result>
```

By implementing these improvements, we'll create a much more user-friendly and informative event visualization system that helps users understand the agent's execution process more clearly.
