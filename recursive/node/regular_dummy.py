from overrides import overrides
from typing import Any, Optional, Dict

from recursive.common.enums import NodeType, TaskStatus
from recursive.graph import task_register
from recursive.node.abstract import AbstractNode


@task_register.register_module()
class RegularDummyNode(AbstractNode):
    @overrides
    def get_node_final_info(self) -> Optional[Dict[str, Any]]:
        if self.node_type is NodeType.PLAN_NODE:
            if self.status == TaskStatus.FINISH:
                return self.result["final_aggregate"]
            else:
                return None
        elif self.node_type is NodeType.EXECUTE_NODE:
            if self.status == TaskStatus.FINISH:
                return self.result[
                    "execute"
                ]  # {"result": {"original": "xxx", "result": "xxx"}}
            else:
                return None
        else:
            raise NotImplementedError()

    @overrides
    def get_node_final_result(self) -> Any:
        final_info = self.get_node_final_info()
        if final_info is None:
            return None
        return final_info["result"]

    @overrides
    def define_status(self) -> None:
        self.status_list = {
            "silence": [TaskStatus.FINISH, TaskStatus.FAILED],
            "suspend": [TaskStatus.NOT_READY, TaskStatus.DOING],
            "activate": [
                TaskStatus.READY,
                TaskStatus.NEED_UPDATE,
                TaskStatus.PLAN_DONE,
                TaskStatus.FINAL_TO_FINISH,
                TaskStatus.NEED_POST_REFLECT,
            ],
        }
        self.status_action_mapping = {
            # key is status, value is (condition, action_name, next_status)
            # Execute the plan when the plan node is ready, execute the execute function when the execute node is ready
            TaskStatus.READY: [
                (
                    lambda node, *args, **kwargs: node.node_type == NodeType.PLAN_NODE,
                    "plan",
                    TaskStatus.PLAN_DONE,
                ),
                (
                    lambda node, *args, **kwargs: node.node_type
                    == NodeType.EXECUTE_NODE,
                    "execute",
                    TaskStatus.NEED_POST_REFLECT,
                ),
            ],
            TaskStatus.NEED_UPDATE: [
                (lambda node, *args, **kwargs: True, "update", TaskStatus.READY),
            ],
            # When plan_done occurs, complete the plan reflection and directly enter the doing state without setting the plan_reflect_done status
            TaskStatus.PLAN_DONE: [
                (lambda node, *args, **kwargs: True, "prior_reflect", TaskStatus.DOING),
            ],
            TaskStatus.FINAL_TO_FINISH: [
                (
                    lambda node, *args, **kwargs: True,
                    "final_aggregate",
                    TaskStatus.NEED_POST_REFLECT,
                ),
            ],
            TaskStatus.NEED_POST_REFLECT: [
                (
                    lambda node, *args, **kwargs: node.node_type == NodeType.PLAN_NODE,
                    "planning_post_reflect",
                    TaskStatus.FINISH,
                ),
                (
                    lambda node, *args, **kwargs: node.node_type
                    == NodeType.EXECUTE_NODE,
                    "execute_post_reflect",
                    TaskStatus.FINISH,
                ),
            ],
        }
        # key is status, value is (condition, next_status)
        self.status_exam_mapping = {
            TaskStatus.NOT_READY: [
                # When an external node enters the doing state, if there are no dependent nodes, it directly enters the ready state.
                (
                    lambda node, *args, **kwargs: node.node_graph_info[
                        "outer_node"
                    ].status
                    == TaskStatus.DOING
                    and len(node.node_graph_info["parent_nodes"]) == 0,
                    TaskStatus.READY,
                ),
                # When the external node enters the doing state, if it has dependent nodes and all dependent nodes are finished, it enters the need_update state.
                (
                    lambda node, *args, **kwargs: node.node_graph_info[
                        "outer_node"
                    ].status
                    == TaskStatus.DOING
                    and all(
                        [
                            parent.status == TaskStatus.FINISH
                            for parent in node.node_graph_info["parent_nodes"]
                        ]
                    ),
                    TaskStatus.NEED_UPDATE,
                ),
            ],
            # When all internal nodes are finished, it changes to final_to_finish and begins to gather information
            TaskStatus.DOING: [
                (
                    lambda node, *args, **kwargs: all(
                        [
                            inner_node.status == TaskStatus.FINISH
                            for inner_node in node.topological_task_queue
                        ]
                    ),
                    TaskStatus.FINAL_TO_FINISH,
                )
            ],
        }

    def plan(self, agent, memory, *args, **kwargs) -> Any:
        # Assemble data
        # Agent's plan
        result = agent.forward(self, memory, *args, **kwargs)
        self.raw_plan = result["result"]
        # Parse the plan generated by the agent
        if self.raw_plan is not None:
            self.plan2graph(self.raw_plan)
        else:
            raise Exception("No plan found")
        return result

    def update(self, agent, memory, *args, **kwargs) -> Any:
        result = agent.forward(self, memory, *args, **kwargs)
        return result

    def execute(self, agent, memory, *args, **kwargs) -> Any:
        result = agent.forward(self, memory, *args, **kwargs)
        return result

    def prior_reflect(self, agent, memory, *args, **kwargs) -> Any:
        result = agent.forward(self, memory, *args, **kwargs)
        return result

    def planning_post_reflect(self, agent, memory, *args, **kwargs) -> Any:
        result = agent.forward(self, memory, *args, **kwargs)
        return result

    def execute_post_reflect(self, agent, memory, *args, **kwargs) -> Any:
        result = agent.forward(self, memory, *args, **kwargs)
        return result

    def final_aggregate(self, agent, memory, *args, **kwargs) -> Any:
        if (
            len(self.topological_task_queue) == 1
            and self.topological_task_queue[0].node_type == NodeType.EXECUTE_NODE
        ):
            return self.topological_task_queue[0].get_node_final_result()
        else:
            result = agent.forward(self, memory, *args, **kwargs)
        return result
