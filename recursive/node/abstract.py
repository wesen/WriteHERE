import json
import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple

from loguru import logger

from recursive.agent.proxy import AgentProxy
from recursive.common.enums import TaskStatus, NodeType
from recursive.graph import Graph
from recursive.utils.event_bus import (
    emit_node_status_changed,
    emit_node_created,
    emit_plan_received,
    emit_inner_graph_built,
    emit_node_result_available,
)
from recursive.common.context import ExecutionContext
from recursive.memory import Memory


class AbstractNode(ABC):
    @staticmethod
    def process_all_node_to_node_str(obj):
        """
        Recursively converts all node objects in a nested structure to their string representations.

        This method traverses dictionaries, lists, and node objects, converting each node to its string
        representation while preserving the structure of the data.

        Args:
            obj: The object to process. Can be a dictionary, list, AbstractNode, or any other type.

        Returns:
            The processed object with all nodes converted to strings.
        """
        if isinstance(obj, dict):
            str_obj = {}
            for k, v in obj.items():
                str_obj[k] = AbstractNode.process_all_node_to_node_str(v)
        elif isinstance(obj, list):
            str_obj = []
            for v in obj:
                str_obj.append(AbstractNode.process_all_node_to_node_str(v))
        elif isinstance(obj, AbstractNode):
            str_obj = str(obj)
        else:
            str_obj = str(obj)
        return str_obj

    def __init__(
        self,
        config,
        nid,
        node_graph_info,
        task_info,
        node_type=None,
        ctx: Optional[ExecutionContext] = None,
    ):
        """
        Initialize a new AbstractNode instance.

        Args:
            config (dict): Configuration dictionary containing system settings and parameters.
            nid: Node identifier.
            node_graph_info (dict): Information about the node's position and relationships in the graph:
                - outer_node: The outer layer node to which it belongs
                - root_node: The root node of the entire nested task
                - parent_nodes: Dependent nodes of this node in the current Graph (initially just NIDs/strs)
                - layer: The layer number where this node is located, root is 0
            task_info (dict): Information about the task this node represents:
                - goal: Task objective
                - inclusion: What to include
                - exclusion: What to exclude
                - verify_standard: Verification criteria
                - task_type: Type of task (COMPOSITION, REASONING, RETRIEVAL)
            node_type (NodeType, optional): Type of the node (PLAN_NODE or EXECUTE_NODE).
            ctx (ExecutionContext, optional): Execution context, primarily for step tracking.
        """
        self.config = config
        self.nid = nid
        self.hashkey = str(uuid.uuid4())
        # Store original parent NIDs before they get replaced by node objects in plan2graph
        # This requires node_graph_info["parent_nodes"] to initially be the list of NIDs/strings
        self._initial_parent_nids = [
            str(p_nid) for p_nid in node_graph_info.get("parent_nodes", [])
        ]
        self.node_graph_info = node_graph_info
        self.task_info = task_info
        self.inner_graph = Graph(self)  # Internal Planning Graph
        self.raw_plan = None  # raw plan returned by planner, represented in JSON format
        self.node_type = node_type  # Node type
        self.status = TaskStatus.NOT_READY  # Execution status, default is NOT_READY
        self.agent_proxy = AgentProxy(config)

        # Result
        self.result: Dict[str, Any] = {}

        # -------- States -------
        self.status_list: Dict[str, List[TaskStatus]] = {
            "silence": [],
            "suspend": [],
            "activate": [],
        }

        # Status-Condtion-Action-NextStatus mapping
        self.status_action_mapping: Dict[Any, Any] = {}
        # Status-Condtion-NextStatus mapping
        self.status_exam_mapping: Dict[Any, Any] = {}

        self.define_status()
        self.check_status_valid()

        # --- Emit Event: node_created ---
        outer_node = self.node_graph_info.get("outer_node")
        root_node = self.node_graph_info.get("root_node")
        emit_node_created(
            node_id=self.hashkey,
            node_nid=str(self.nid),
            node_type=self.node_type.name if self.node_type else "UNKNOWN",
            task_type=self.task_type_tag,
            task_goal=self.task_info.get("goal", "N/A"),
            layer=self.node_graph_info.get("layer", -1),
            outer_node_id=outer_node.hashkey if outer_node else None,
            root_node_id=root_node.hashkey if root_node else "UNKNOWN",
            initial_parent_nids=self._initial_parent_nids,
            ctx=ctx,
        )

    @property
    def required_task_info_keys(self):
        """
        Get the required keys for the task info based on the task type.

        Returns:
            list: List of required keys for the task info dictionary.
        """
        require_keys = self.config["require_keys"][self.task_type_tag]
        return require_keys

    @property
    def task_type_tag(self):
        """
        Get the task type tag for this node.

        Returns:
            str: The task type tag (e.g., "COMPOSITION", "REASONING", "RETRIEVAL").
                Returns "GENERAL" if no_type is set in config.
        """
        if self.config.get("no_type", False):
            return "GENERAL"
        return self.config["tag2task_type"][self.task_info["task_type"]]

    @abstractmethod
    def define_status(self):
        """
        Define the possible states and transitions for this node.

        This method should be implemented by concrete classes to define:
        - Which states are silence, suspend, or activate states
        - The status-condition-action-next_status mappings
        - The status-condition-next_status mappings
        """
        return

    @abstractmethod
    def get_node_final_info(self):
        """
        Get the final information about this node after execution.

        This method should be implemented by concrete classes to return
        relevant information about the node's execution results.
        """
        pass

    @abstractmethod
    def get_node_final_result(self):
        """
        Get the final result of this node's execution.

        This method should be implemented by concrete classes to return
        the actual output/result produced by this node.
        """
        pass

    def get_outer_write_task(self):
        """
        Get the outer writing task that contains this node.

        Returns:
            AbstractNode: The outer COMPOSITION node that contains this node.
                Returns None if this is a root node.
        """
        cur_node = (
            self.node_graph_info["outer_node"]
            if self.node_type == NodeType.EXECUTE_NODE
            else self
        )
        outer_node = cur_node.node_graph_info["outer_node"]
        return outer_node

    @property
    def is_atom(self):
        """
        Check if this node represents an atomic task.

        A task is atomic if it's an EXECUTE_NODE and its outer node's task queue
        contains only one task.

        Returns:
            bool: True if this is an atomic task, False otherwise.
        """
        return (self.node_type == NodeType.EXECUTE_NODE) and (
            len(self.node_graph_info["outer_node"].topological_task_queue) == 1
        )

    def get_direct_depend_write_task(self):
        """
        Get all COMPOSITION tasks that directly depend on this node.

        Returns:
            list: List of COMPOSITION nodes that have this node as a parent.
        """
        cur_node = (
            self.node_graph_info["outer_node"]
            if self.node_type == NodeType.EXECUTE_NODE
            else self
        )
        outer_node = cur_node.node_graph_info["outer_node"]
        if outer_node is None:
            return None
        graph = outer_node.inner_graph.topological_task_queue
        depend_write_tasks = []
        for node in graph:
            if node.task_type_tag == "COMPOSITION":
                for par_node in node.node_graph_info["parent_nodes"]:
                    if par_node.nid == cur_node.nid:
                        depend_write_tasks.append(node)
        return depend_write_tasks

    def get_all_previous_writing_plan(self):
        """
        Get a hierarchical representation of all writing tasks in the graph.

        This method traverses the task graph and builds a string representation of all
        COMPOSITION tasks, showing their relationships, status, and progress.

        Returns:
            str: A formatted string showing the hierarchical writing plan with status indicators.
        """
        all_tasks = []

        def inner(cur_node, prefix_tab, cur_write_id_list):
            layer = cur_node.node_graph_info["layer"]
            if (cur_node.node_type == NodeType.EXECUTE_NODE) and (
                len(cur_node.node_graph_info["outer_node"].topological_task_queue) == 1
            ):
                return None
            if cur_node.task_type_tag != "COMPOSITION":
                return None

            if not self.config.get("offer_global_writing_plan", False):
                if (cur_node.status not in (TaskStatus.FINISH, TaskStatus.DOING)) and (
                    cur_node.hashkey != self.hashkey
                ):
                    return None

            content = "{}【{}】.{}: {}".format(
                prefix_tab,
                ".".join(map(str, cur_write_id_list)),
                cur_node.task_info["length"],
                cur_node.task_info["goal"],
            )
            all_tasks.append(content)

            if cur_node.status == TaskStatus.FINISH:
                all_tasks[-1] += " :**FINISHED**"
            elif cur_node.status == TaskStatus.DOING:
                all_tasks[-1] += " :**DOING**"
                widx = 1
                for next_node in cur_node.topological_task_queue:
                    if next_node.task_type_tag != "COMPOSITION":
                        continue
                    inner(
                        next_node,
                        prefix_tab + "\t",
                        deepcopy(cur_write_id_list) + [widx],
                    )
                    widx += 1
            else:
                if cur_node.hashkey == self.hashkey:
                    all_tasks[-1] += " :**You Need To Write**"
                else:
                    all_tasks[
                        -1
                    ] += " :**Not Started Yet, You should avoid content related to this part**"

        inner(self.node_graph_info["root_node"], "", [])
        if len(all_tasks) > 0:
            all_tasks = all_tasks[1:]
        return "\n".join(all_tasks)

    def get_all_layer_plan(self):
        """
        Get a JSON representation of the task plan up to a specific layer.

        This method builds a JSON structure representing the task hierarchy up to
        the layer after this node's layer, including task types, goals, dependencies,
        and completion status.

        Returns:
            dict: A JSON structure representing the task plan.
        """
        target_layer = self.node_graph_info["layer"] + 1

        def inner(cur_node):
            layer = cur_node.node_graph_info["layer"]
            if (cur_node.node_type == NodeType.EXECUTE_NODE) and (
                len(cur_node.node_graph_info["outer_node"].topological_task_queue) == 1
            ):
                return None
            if layer <= target_layer:
                plan_node = {
                    "id": cur_node.nid,
                    "task_type": cur_node.task_info["task_type"],
                    "goal": cur_node.task_info["goal"],
                    "dependency": [
                        n.nid
                        for n in cur_node.node_graph_info["parent_nodes"]
                        if n.task_type_tag != "COMPOSITION"
                    ],
                    "finish": cur_node.status == TaskStatus.FINISH,
                    "is_current_to_plan_task": cur_node.hashkey == self.hashkey,
                    "sub_tasks": [],
                }
                if layer < target_layer:
                    sub_tasks = [
                        inner(child) for child in cur_node.topological_task_queue
                    ]
                    sub_tasks = [st for st in sub_tasks if st is not None]
                    plan_node["sub_tasks"] = sub_tasks
                return plan_node

        plan_json = inner(self.node_graph_info["root_node"])
        return plan_json

    def get_all_lt_layer_plan(self):
        """
        Get a string representation of all tasks up to this node's layer.

        This method creates a formatted string showing all tasks up to and including
        the current node's layer, with proper indentation to show hierarchy.

        Returns:
            str: A formatted string showing the task plan with proper indentation.
        """
        plan_string = []
        target_layer = self.node_graph_info["layer"]

        def inner(cur_node, prefix_tab):
            layer = cur_node.node_graph_info["layer"]
            if (cur_node.node_type == NodeType.EXECUTE_NODE) and (
                len(cur_node.node_graph_info["outer_node"].topological_task_queue) == 1
            ):
                return
            if layer <= target_layer:
                if cur_node.hashkey == self.hashkey:
                    content = "{}**{}.{} {}**".format(
                        prefix_tab,
                        cur_node.nid,
                        (
                            "【{}】".format(cur_node.task_info["task_type"])
                            if cur_node.task_info["task_type"] != ""
                            else ""
                        ),
                        cur_node.task_info["goal"],
                    )
                else:
                    content = "{}{}.{} {}".format(
                        prefix_tab,
                        cur_node.nid,
                        (
                            "【{}】".format(cur_node.task_info["task_type"])
                            if cur_node.task_info["task_type"] != ""
                            else ""
                        ),
                        cur_node.task_info["goal"],
                    )
                plan_string.append(content)
                for next_node in cur_node.topological_task_queue:
                    inner(next_node, prefix_tab + "\t")

        inner(self.node_graph_info["root_node"], "")
        return "\n".join(plan_string)

    def check_status_valid(self):
        """
        Validate that the node's status definitions are complete and consistent.

        This method checks that:
        1. All required status categories (silence, suspend, activate) are defined
        2. All activate states have corresponding action mappings
        3. All suspend states have corresponding exam mappings

        Raises:
            Exception: If any validation check fails.

        Returns:
            bool: True if all validations pass.
        """
        assert "silence" in self.status_list
        assert "suspend" in self.status_list
        assert "activate" in self.status_list

        # Only when status registration of the activation type can execute actions, and all are required to register
        for status in self.status_list["activate"]:
            if status not in self.status_action_mapping:
                raise Exception(
                    "status {} is activate status but not register action".format(
                        status
                    )
                )
        for status in self.status_action_mapping.keys():
            if status not in self.status_list["activate"]:
                raise Exception(
                    "status {} register action but is not activate category".format(
                        status
                    )
                )

        # Only when pending type (and not ready) status must register check conditions, and all must be registered
        for status in self.status_list["suspend"]:
            if status not in self.status_exam_mapping:
                raise Exception(
                    "status {} is activate status but not register exam condition".format(
                        status
                    )
                )
        for status in self.status_exam_mapping.keys():
            if status not in self.status_list["suspend"]:
                raise Exception(
                    "status {} register action but is not suspend category".format(
                        status
                    )
                )

        return True

    def next_action_step(
        self,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """
        Execute the next action for this node based on its current status.

        This method:
        1. Checks that the node is in an activate state
        2. Evaluates conditions to determine the next action
        3. Executes the action and updates the node's status, passing context.

        Args:
            memory: The memory context for the action
            ctx: The execution context (optional)
            *args: Additional positional arguments for the action
            **kwargs: Additional keyword arguments for the action

        Returns:
            tuple: (action_name, result) - The name of the action executed and its result

        Raises:
            NotImplementedError: If the node is not in an activate state
            Exception: If no condition matches for the current status
        """
        # --- RUN ---
        if not self.is_activate:
            raise NotImplementedError(
                "Error Status process, status ({}) is not actiavate category".format(
                    self.status
                )
            )

        for condition_func, action_name, next_status in self.status_action_mapping[
            self.status
        ]:
            if condition_func(self, memory, ctx, *args, **kwargs):
                logger.info(
                    "Do Action: {}, make {} -> {}".format(
                        action_name, self.status, next_status
                    )
                )
                result = self.do_action(action_name, memory, ctx, *args, **kwargs)
                self.status = next_status
                break
        else:
            raise Exception("No Condition Matched for status action, Error!")

        return action_name, result

    def do_exam(self, verbose, ctx: Optional[ExecutionContext] = None):
        """
        Examine the node's status and update it based on defined conditions, emitting an event on change.

        This method:
        1. Checks that the node is in a suspend state
        2. Evaluates conditions to determine if the status should change
        3. Updates the status if conditions are met

        Args:
            verbose (bool): Whether to log status changes
            ctx (ExecutionContext, optional): Execution context, primarily for step tracking

        Raises:
            NotImplementedError: If the node is not in a suspend state
        """
        if not self.is_suspend:
            raise NotImplementedError(
                "Error Status process, status ({}) is not suspend category".format(
                    self.status
                )
            )
        for condition_func, next_status in self.status_exam_mapping[self.status]:
            if condition_func(self):
                old_status = self.status
                # --- Emit NodeStatusChanged ---
                if old_status != next_status:
                    emit_node_status_changed(
                        node_id=self.hashkey,
                        node_goal=self.task_info.get("goal", "?"),
                        old_status=old_status.name,
                        new_status=next_status.name,
                        ctx=ctx,
                    )
                if verbose:
                    logger.info(
                        "Do Exam, {}:{} make {} -> {}".format(
                            self.nid, self.task_info["goal"], self.status, next_status
                        )
                    )
                self.status = (
                    next_status  # Status change happens *after* event emission
                )
                break

    def task_str(self):
        """
        Get a string representation of this task node.

        The string includes:
        - Node ID
        - Node type indicator (* for EXECUTE_NODE)
        - Task type and length (for COMPOSITION tasks)
        - Task goal
        - Parent node IDs (excluding COMPOSITION parents)
        - Current status

        Returns:
            str: A formatted string representing this task node.
        """
        if self.task_type_tag == "COMPOSITION":
            tag = "【{}.{}】".format(
                self.task_info["task_type"], self.task_info["length"]
            )
        elif self.task_type_tag != "":
            tag = "【{}】".format(self.task_info["task_type"])
        else:
            tag = ""

        return "{}{}{}.({}).{:10s}: {}".format(
            self.nid,
            "" if self.node_type == NodeType.PLAN_NODE else "*",
            tag,
            self.task_info["goal"],
            ",".join(
                str(x.nid)
                for x in self.node_graph_info["parent_nodes"]
                if x.task_type_tag != "COMPOSITION"
            ),
            self.status.name,
        )

    def __str__(self):
        """
        Get a string representation of this node.

        Returns:
            str: The task string representation of this node.
        """
        return self.task_str()

    def __repr__(self):
        """
        Get a string representation of this node for debugging.

        Returns:
            str: The task string representation of this node.
        """
        return self.__str__()

    def to_json(self):
        """
        Convert this node to a JSON-serializable dictionary.

        The dictionary includes:
        - Node ID
        - Task information
        - Graph information
        - Raw plan
        - Node type
        - Status
        - Results
        - Inner graph

        Returns:
            dict: A JSON-serializable dictionary representing this node.
        """
        obj = {
            "nid": self.nid,
            "task_info": AbstractNode.process_all_node_to_node_str(self.task_info),
            "node_graph_info": AbstractNode.process_all_node_to_node_str(
                self.node_graph_info
            ),
            "raw_plan": self.raw_plan,
            "node_type": self.node_type.name,
            "status": self.status.name,
            "result": self.result,
            "inner_graph": self.inner_graph.to_json(),
        }
        return obj

    @property
    def topological_task_queue(self):
        """
        Get the topologically sorted queue of tasks in this node's inner graph.

        Returns:
            list: A list of nodes in topological order.
        """
        return self.inner_graph.topological_task_queue

    @property
    def is_silence(self):
        """
        Check if this node is in a silence state.

        Returns:
            bool: True if the node's status is in the silence category.
        """
        return self.status in self.status_list["silence"]

    @property
    def is_suspend(self):
        """
        Check if this node is in a suspend state.

        Returns:
            bool: True if the node's status is in the suspend category.
        """
        return self.status in self.status_list["suspend"]

    @property
    def is_activate(self):
        """
        Check if this node is in an activate state.

        Returns:
            bool: True if the node's status is in the activate category.
        """
        return self.status in self.status_list["activate"]

    def plan2graph(self, raw_plan: List[Dict], ctx: Optional[ExecutionContext] = None):
        """
        Convert a raw planning result into a task graph.

        This method:
        1. Emits plan_received event
        2. Processes the raw plan JSON
        3. Creates nodes for each task, passing context
        4. Establishes dependencies between nodes
        5. Builds the inner graph structure (emitting node_added/edge_added events via Graph methods)
        6. Emits inner_graph_built event

        Args:
            raw_plan (list): List of task dictionaries from the planner
            ctx (ExecutionContext, optional): Execution context
        """
        # --- Emit Event: plan_received ---
        emit_plan_received(
            node_id=self.hashkey,
            raw_plan=raw_plan,
            ctx=ctx,
        )

        if (
            len(raw_plan) == 0
        ):  # Atomic task, still create an execution graph, but the execution graph has only one execute node, iterating through required_task_info_keys and retrieving them.
            raw_plan.append(
                {
                    "id": 0,
                    "dependency": [],
                    "atom": True,
                }
            )
            for key in self.required_task_info_keys:
                if key not in raw_plan[-1]:
                    raw_plan[-1][key] = self.task_info[key]
        # raw plan is a jsonlist
        nodes = []
        id2node = {}
        for task in raw_plan:
            task["goal"] = task["goal"].replace("\n", ";")
            if task["task_type"] == "analyze" or task["task_type"] == "analysis":
                task["task_type"] = "think"
            node_graph_info = {
                "outer_node": self,
                "root_node": self.node_graph_info["root_node"],
                "parent_nodes": task["dependency"],
                "layer": self.node_graph_info["layer"] + 1,
            }
            if self.config["tag2task_type"][task["task_type"]] == "COMPOSITION":
                # If it is the only COMPOSITION task, the length can be assigned through rules
                if (
                    len(
                        [
                            st
                            for st in raw_plan
                            if self.config["tag2task_type"][st["task_type"]]
                            == "COMPOSITION"
                        ]
                    )
                    == 1
                ):
                    if "length" not in task:
                        task["length"] = self.task_info["length"]

            task_info = {
                key: task[key]
                for key in self.config["require_keys"][
                    self.config["tag2task_type"][task["task_type"]]
                ]
            }

            if "sub_tasks" in task:
                task_info["candidate_plan"] = task["sub_tasks"]
                for st in task["sub_tasks"]:
                    st["goal"] = st["goal"].replace("\n", ";")
            else:
                task_info["candidate_plan"] = "Missing"

            node = self.__class__(
                config=self.config,
                nid=task["id"],
                node_graph_info=node_graph_info,
                task_info=task_info,
                node_type=(
                    NodeType.PLAN_NODE
                    if not task.get("atom")
                    else NodeType.EXECUTE_NODE
                ),
                ctx=ctx,
            )
            nodes.append(node)
            id2node[task["id"]] = node

        # Modify dependency for reasoning tasks, all reasoning tasks must dependent all previous reasoning tasks
        sorted_nodes = sorted(nodes, key=lambda x: int(str(x.nid).split(".")[-1]))
        for i in range(len(sorted_nodes)):
            cur = sorted_nodes[i]
            parent_nodes = cur.node_graph_info["parent_nodes"]
            if cur.task_type_tag == "REASONING":
                for j in range(i):
                    if (
                        sorted_nodes[j].task_type_tag == "REASONING"
                        and sorted_nodes[j].nid not in parent_nodes
                    ):
                        parent_nodes.append(sorted_nodes[j].nid)
                cur.node_graph_info["parent_nodes"] = sorted(
                    parent_nodes, key=lambda x: int(str(x).split(".")[-1])
                )

        # Process implicit dependencies (sequential order) between COMPOSITION tasks
        prev_action_node: List[AbstractNode] = []
        for node in sorted(nodes, key=lambda x: int(str(x.nid).split(".")[-1])):
            if node.task_type_tag == "COMPOSITION":
                for prev in prev_action_node:
                    if prev.nid not in node.node_graph_info["parent_nodes"]:
                        node.node_graph_info["parent_nodes"].append(prev.nid)
                node.node_graph_info["parent_nodes"] = node.node_graph_info[
                    "parent_nodes"
                ]
                prev_action_node.append(node)
        # Replace parent node ids with actual node objects
        for node in nodes:
            # Filter out invalid dependencies
            node.node_graph_info["parent_nodes"] = [
                id2node[str(nid)]
                for nid in node.node_graph_info["parent_nodes"]
                if str(nid) in id2node
            ]
        # Build Graph
        self.inner_graph.clear()
        # Add nodes
        for node in nodes:
            self.inner_graph.add_node(node, ctx=ctx)
        # Add edges
        for node in nodes:
            for parent_node in node.node_graph_info["parent_nodes"]:
                self.inner_graph.add_edge(parent_node, node, ctx=ctx)
        self.inner_graph.topological_sort()

        # --- Emit Event: inner_graph_built ---
        edge_count = sum(
            len(children) for children in self.inner_graph.graph_edges.values()
        )
        emit_inner_graph_built(
            node_id=self.hashkey,
            node_count=len(self.inner_graph.node_list),
            edge_count=edge_count,
            node_ids=[n.hashkey for n in self.inner_graph.node_list],
            ctx=ctx,
        )

        return

    def do_action(
        self,
        action_name: str,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """
        Execute an action on this node, passing execution context.

        This method:
        1. Gets the appropriate agent function for the action via proxy
        2. Executes the action by calling the node's method named `action_name`,
           passing memory, context, and other args.
        3. Records the result and timestamp
        4. Logs the result (except for certain actions)

        Args:
            action_name (str): Name of the action to execute (must match a method name)
            memory: Memory context for the action
            ctx: Execution context (optional)
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            The result of the action execution.
        """
        # Note: Action execution itself (LLM calls, Tool calls within agents)
        # should emit their own specific events.
        agent = self.agent_proxy.proxy(action_name)
        result = getattr(self, action_name)(agent, memory, ctx=ctx, *args, **kwargs)
        # Saving information
        self.result[action_name] = {
            "result": result,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent": self.config["action_mapping"][action_name],
        }

        if action_name not in (
            "update",
            "prior_reflect",
            "planning_post_reflect",
            "execute_post_reflect",
        ):
            if not (
                action_name in ("execute", "final_aggregate")
                and self.task_type_tag == "RETRIEVAL"
            ):
                logger.info(
                    "{} Action: {} Result: \n{}".format(
                        self.task_str(),
                        action_name,
                        json.dumps(
                            self.result[action_name], ensure_ascii=False, indent=4
                        ),
                    )
                )

        # --- Emit Event: node_result_available ---
        # Check if the action is one that produces a final-ish result
        # (e.g., 'execute', 'final_aggregate')
        # We might need a more robust way to identify final result actions
        if action_name in ("execute", "final_aggregate", "plan") and result:
            # Create a summary; handling different result types might be needed
            if isinstance(result, (str, bytes)):
                summary = str(result)[:500]
            elif isinstance(result, dict):
                try:
                    summary = json.dumps(result)[:500]
                except TypeError:
                    summary = str(result)[:500]
            elif isinstance(result, list):
                try:
                    summary = json.dumps(result)[:500]
                except TypeError:
                    summary = str(result)[:500]
            else:
                summary = str(result)[:500]

            emit_node_result_available(
                node_id=self.hashkey,
                action_name=action_name,
                result_summary=summary,
                ctx=ctx,
            )

        return result
