# coding: utf8
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from recursive.utils.event_bus import emit_node_added, emit_edge_added
from recursive.common.context import ExecutionContext
from recursive.utils.registry import Register

if TYPE_CHECKING:
    from recursive.node.abstract import AbstractNode

task_register = Register("task_register")


class Graph:
    def __init__(self, outer_node: "AbstractNode"):
        # Create a dict to store relationships between points in the graph {v: [u, i]} (v,u,i are all points, representing edges <v, u>, <v, i>): edge collection
        # parent.nid -> child1, child2
        self.graph_edges: dict[str, list["AbstractNode"]] = {}
        self.nid_list: list[str] = []
        self.node_list: list["AbstractNode"] = []
        self.topological_task_queue: list["AbstractNode"] = []
        self.outer_node: "AbstractNode" = outer_node

    def clear(self):
        self.graph_edges = {}
        self.nid_list = []
        self.node_list = []
        self.topological_task_queue = []

    def add_edge(
        self,
        parent: "AbstractNode",
        cur: "AbstractNode",
        ctx: Optional[ExecutionContext] = None,
    ):
        # Add edge <parent, cur>
        assert parent.nid in self.graph_edges
        self.graph_edges[parent.nid].append(cur)

        # --- Emit Event ---
        if self.outer_node and self.outer_node.hashkey:
            emit_edge_added(
                graph_owner_node_id=self.outer_node.hashkey,
                parent_node_id=parent.hashkey,
                child_node_id=cur.hashkey,
                parent_node_nid=str(parent.nid),
                child_node_nid=str(cur.nid),
                ctx=ctx,
            )

    def add_node(self, node: "AbstractNode", ctx: Optional[ExecutionContext] = None):
        if node.nid in self.nid_list:
            raise Exception("Duplicate Node")
        self.nid_list.append(node.nid)
        self.node_list.append(node)
        self.graph_edges[node.nid] = []

        # --- Emit Event ---
        # Ensure outer_node exists and has a hashkey
        owner_id = self.outer_node.hashkey if self.outer_node else None
        if owner_id:
            emit_node_added(
                graph_owner_node_id=owner_id,
                added_node_id=node.hashkey,
                added_node_nid=str(node.nid),
                ctx=ctx,
            )

    def topological_sort(self, mode="bfs"):
        # mode is bfs or dfs
        # Return topologically sorted node order
        queue = []
        visited_nids = set()
        # In-degree count
        in_degree_recorder = defaultdict(int)
        # Traverse outgoing edges
        for par_idx, childs in self.graph_edges.items():
            for child in childs:
                in_degree_recorder[child.nid] += 1
        if mode == "bfs":
            while len(queue) != len(self.node_list):
                # Get all nodes with in-degree of 0, add to topological sequence
                current_batch_nids = []
                for node in self.node_list:
                    if (
                        in_degree_recorder.get(node.nid, 0) == 0
                        and node.nid not in visited_nids
                    ):
                        queue.append(node)
                        visited_nids.add(node.nid)
                        current_batch_nids.append(node.nid)
                # Recalculate in-degree of child nodes
                for nid in current_batch_nids:
                    for child in self.graph_edges[nid]:
                        in_degree_recorder[child.nid] -= 1
                # If no nodes were traversed, and some nodes haven't been selected, there is an error
                if len(current_batch_nids) == 0 and len(queue) != len(self.node_list):
                    raise Exception("Error, some node is not reachable")
        elif mode == "dfs":
            raise Exception(
                "Error! the topological_sort mode ({}) is invalid".format(mode)
            )
        else:
            raise Exception(
                "Error! the topological_sort mode ({}) is invalid".format(mode)
            )
        self.topological_task_queue = queue
        return queue

    def to_json(self):
        json_ret = {
            "task_list": [node.task_str() for node in self.topological_task_queue],
            "topological_task_queue": [
                node.to_json() for node in self.topological_task_queue
            ],
        }
        return json_ret
