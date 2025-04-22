from dataclasses import dataclass, field
from typing import Dict, List, Optional
import asyncio
import json


@dataclass
class NodeState:
    id: str
    nid: str
    type: str  # PLAN_NODE or EXECUTE_NODE
    goal: str
    layer: int
    taskType: str  # COMPOSITION, REASONING, or RETRIEVAL
    status: Optional[str] = None


@dataclass
class EdgeState:
    id: str  # Computed as f"{parent}-{child}"
    parent: str
    child: str


@dataclass
class NodesState:
    ids: List[str] = field(default_factory=list)
    entities: Dict[str, NodeState] = field(default_factory=dict)


@dataclass
class EdgesState:
    ids: List[str] = field(default_factory=list)
    entities: Dict[str, EdgeState] = field(default_factory=dict)


@dataclass
class GraphState:
    nodes: NodesState = field(default_factory=NodesState)
    edges: EdgesState = field(default_factory=EdgesState)


class GraphStateManager:
    """
    Manages server-side graph state that mirrors the Redux store structure in the UI.
    Processes events to maintain state and provides methods to query the state.
    """

    def __init__(self):
        self.state = GraphState()
        self._lock = asyncio.Lock()

    async def process_event(self, event: dict):
        """
        Process an event to update the graph state.
        Only processes events that affect the graph structure.
        """
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        async with self._lock:
            if event_type == "run_started":
                self.state = GraphState()  # Clear the graph state
            elif event_type == "node_created":
                await self._handle_node_created(payload)
            elif event_type == "node_status_changed":
                await self._handle_node_status_changed(payload)
            elif event_type == "edge_added":
                await self._handle_edge_added(payload)

    async def _handle_node_created(self, payload: dict):
        """Handle a node_created event by adding a new node to the state."""
        node_id = payload.get("node_id")
        if not node_id or node_id in self.state.nodes.entities:
            return

        node = NodeState(
            id=node_id,
            nid=payload.get("node_nid", ""),
            type=payload.get("node_type", ""),
            goal=payload.get("task_goal", ""),
            layer=payload.get("layer", 0),
            taskType=payload.get("task_type", ""),
        )
        await self._add_node(node)

    async def _handle_node_status_changed(self, payload: dict):
        """Handle a node_status_changed event by updating a node's status."""
        node_id = payload.get("node_id")
        if not node_id or node_id not in self.state.nodes.entities:
            return

        new_status = payload.get("new_status")
        if new_status:
            node = self.state.nodes.entities[node_id]
            node.status = new_status

    async def _handle_edge_added(self, payload: dict):
        """Handle an edge_added event by adding a new edge to the state."""
        parent_id = payload.get("parent_node_id")
        child_id = payload.get("child_node_id")
        if not parent_id or not child_id:
            return

        edge_id = f"{parent_id}-{child_id}"
        if edge_id in self.state.edges.entities:
            return

        edge = EdgeState(
            id=edge_id,
            parent=parent_id,
            child=child_id,
        )
        await self._add_edge(edge)

    async def _add_node(self, node: NodeState):
        """Add a node to the graph state."""
        if node.id not in self.state.nodes.ids:
            self.state.nodes.ids.append(node.id)
            self.state.nodes.entities[node.id] = node

    async def _add_edge(self, edge: EdgeState):
        """Add an edge to the graph state."""
        if edge.id not in self.state.edges.ids:
            self.state.edges.ids.append(edge.id)
            self.state.edges.entities[edge.id] = edge

    def get_graph_state(self):
        """
        Get the full graph state as a dictionary that matches the Redux store structure.
        This dictionary structure exactly matches what the React UI expects.
        """
        return {
            "graph": {
                "nodes": {
                    "ids": self.state.nodes.ids,
                    "entities": {
                        node_id: self._node_to_dict(node)
                        for node_id, node in self.state.nodes.entities.items()
                    },
                },
                "edges": {
                    "ids": self.state.edges.ids,
                    "entities": {
                        edge_id: self._edge_to_dict(edge)
                        for edge_id, edge in self.state.edges.entities.items()
                    },
                },
            }
        }

    def get_node(self, node_id: str):
        """Get a specific node by ID."""
        if node_id in self.state.nodes.entities:
            return self._node_to_dict(self.state.nodes.entities[node_id])
        return None

    def get_edge(self, edge_id: str):
        """Get a specific edge by ID."""
        if edge_id in self.state.edges.entities:
            return self._edge_to_dict(self.state.edges.entities[edge_id])
        return None

    def get_nodes(self):
        """Get all nodes as a dictionary."""
        return {
            node_id: self._node_to_dict(node)
            for node_id, node in self.state.nodes.entities.items()
        }

    def get_edges(self):
        """Get all edges as a dictionary."""
        return {
            edge_id: self._edge_to_dict(edge)
            for edge_id, edge in self.state.edges.entities.items()
        }

    def _node_to_dict(self, node: NodeState):
        """Convert a NodeState to a dictionary."""
        node_dict = {
            "id": node.id,
            "nid": node.nid,
            "type": node.type,
            "goal": node.goal,
            "layer": node.layer,
            "taskType": node.taskType,
        }
        if node.status:
            node_dict["status"] = node.status
        return node_dict

    def _edge_to_dict(self, edge: EdgeState):
        """Convert an EdgeState to a dictionary."""
        return {
            "id": edge.id,
            "parent": edge.parent,
            "child": edge.child,
        }
