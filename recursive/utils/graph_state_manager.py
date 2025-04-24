from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import asyncio
import json


@dataclass
class NodeState:
    id: str  # node_id from DB
    nid: str  # node_nid from DB
    type: str  # node_type from DB
    goal: str  # task_goal from DB
    layer: int  # layer from DB
    taskType: str  # task_type from DB
    status: Optional[str] = None  # status from DB
    # Add other fields mirrored from DB if needed by UI state
    # e.g., outer_node_id, root_node_id? For now, keep it minimal.


@dataclass
class EdgeState:
    id: str  # Computed as f"{parent_node_id}-{child_node_id}"
    parent: str  # parent_node_id from DB
    child: str  # child_node_id from DB
    # Add other fields mirrored from DB if needed
    # e.g., parent_nid, child_nid?


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
    Can also load initial state directly from database records.
    Includes tracking of inner node relationships.
    """

    def __init__(self):
        self.state = GraphState()
        self._inner_nodes: Dict[str, List[str]] = {}  # outer_node_id -> [inner_node_id]
        self._lock = asyncio.Lock()

    async def load_state_from_db(self, nodes_data: List[Dict], edges_data: List[Dict]):
        """Loads the initial graph state directly from database node/edge records."""
        async with self._lock:
            # Clear existing state
            self.state = GraphState()
            self._inner_nodes = {}

            # Process nodes
            for node_record in nodes_data:
                node_id = node_record.get("node_id")
                if not node_id:
                    continue

                node = NodeState(
                    id=node_id,
                    nid=node_record.get("node_nid", ""),
                    type=node_record.get("node_type", ""),
                    goal=node_record.get("task_goal", ""),
                    layer=node_record.get("layer", 0),
                    taskType=node_record.get("task_type", ""),
                    status=node_record.get("status"),  # Status should be present
                )
                self.state.nodes.ids.append(node.id)
                self.state.nodes.entities[node.id] = node

                # Track inner node relationships during load
                outer_node_id = node_record.get("outer_node_id")
                if outer_node_id:
                    if outer_node_id not in self._inner_nodes:
                        self._inner_nodes[outer_node_id] = []
                    if (
                        node_id not in self._inner_nodes[outer_node_id]
                    ):  # Avoid duplicates if loaded multiple times
                        self._inner_nodes[outer_node_id].append(node_id)

            # Process edges
            for edge_record in edges_data:
                parent_id = edge_record.get("parent_node_id")
                child_id = edge_record.get("child_node_id")
                if not parent_id or not child_id:
                    continue

                edge_id = f"{parent_id}-{child_id}"
                edge = EdgeState(
                    id=edge_id,
                    parent=parent_id,
                    child=child_id,
                )
                self.state.edges.ids.append(edge.id)
                self.state.edges.entities[edge.id] = edge

    async def process_event(self, event: dict):
        """
        Process an event to update the graph state.
        Only processes events that affect the graph structure or node status *after* initial load.
        """
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        async with self._lock:
            # run_started should still clear state if a new run begins *live*
            if event_type == "run_started":
                self.state = GraphState()  # Clear the graph state
            elif event_type == "node_created":
                await self._handle_node_created(payload)
            elif event_type == "node_status_changed":
                await self._handle_node_status_changed(payload)
            elif event_type == "edge_added":
                await self._handle_edge_added(payload)
            # No need to handle plan_received, node_added for state
            # inner_graph_built needs to update the _inner_nodes mapping
            elif event_type == "inner_graph_built":
                await self._handle_inner_graph_built(payload)

    async def _handle_node_created(self, payload: dict):
        """Handle a node_created event by adding a new node to the state (idempotent)."""
        node_id = payload.get("node_id")
        # Only add if it doesn't exist (might happen if events arrive out of order slightly)
        if not node_id or node_id in self.state.nodes.entities:
            return

        node = NodeState(
            id=node_id,
            nid=payload.get("node_nid", ""),
            type=payload.get("node_type", ""),
            goal=payload.get("task_goal", ""),
            layer=payload.get("layer", 0),
            taskType=payload.get("task_type", ""),
            status=payload.get(
                "initial_status", "READY"
            ),  # Use initial status from event if available
        )
        await self._add_node(node)

    async def _handle_node_status_changed(self, payload: dict):
        """Handle a node_status_changed event by updating a node's status."""
        node_id = payload.get("node_id")
        # Check if node exists; it should if created event was processed or loaded
        if not node_id or node_id not in self.state.nodes.entities:
            # Log a warning? Could happen if status change arrives before creation event
            return

        new_status = payload.get("new_status")
        if new_status:
            node = self.state.nodes.entities[node_id]
            node.status = new_status

    async def _handle_edge_added(self, payload: dict):
        """Handle an edge_added event by adding a new edge to the state (idempotent)."""
        parent_id = payload.get("parent_node_id")
        child_id = payload.get("child_node_id")
        if not parent_id or not child_id:
            return

        edge_id = f"{parent_id}-{child_id}"
        # Only add if it doesn't exist
        if edge_id in self.state.edges.entities:
            return

        edge = EdgeState(
            id=edge_id,
            parent=parent_id,
            child=child_id,
        )
        await self._add_edge(edge)

    async def _add_node(self, node: NodeState):
        """Add a node to the graph state if not present."""
        if node.id not in self.state.nodes.ids:
            self.state.nodes.ids.append(node.id)
            self.state.nodes.entities[node.id] = node

    async def _add_edge(self, edge: EdgeState):
        """Add an edge to the graph state if not present."""
        if edge.id not in self.state.edges.ids:
            self.state.edges.ids.append(edge.id)
            self.state.edges.entities[edge.id] = edge

    async def _handle_inner_graph_built(self, payload: dict):
        """Handle inner_graph_built event by updating the inner node mapping."""
        outer_node_id = payload.get("node_id")
        inner_node_ids = payload.get("node_ids", [])

        if not outer_node_id or not inner_node_ids:
            return

        # Idempotently update the inner node mapping
        if outer_node_id not in self._inner_nodes:
            self._inner_nodes[outer_node_id] = []
        for inner_id in inner_node_ids:
            if inner_id not in self._inner_nodes[outer_node_id]:
                self._inner_nodes[outer_node_id].append(inner_id)

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

    def get_inner_node_relationships(self) -> Dict[str, List[str]]:
        """Get the mapping of outer node IDs to their inner node IDs."""
        # Return a copy to prevent external modification
        return dict(self._inner_nodes)

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

    def _node_to_dict(self, node: NodeState) -> Dict[str, Any]:
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

    def _edge_to_dict(self, edge: EdgeState) -> Dict[str, Any]:
        """Convert an EdgeState to a dictionary."""
        return {
            "id": edge.id,
            "parent": edge.parent,
            "child": edge.child,
        }
