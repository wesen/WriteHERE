from typing import Any, Optional

from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.registry import agent_register
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode
from recursive.common.context import ExecutionContext


@agent_register.register_module()
class SinglePlanningAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        layer = node.node_graph_info["layer"]
        if layer == 1:
            result = {"original": "", "result": [], "thought": ""}
            return result

        plans = [{"id": 0, "dependency": [], "goal": node.task_info["goal"]}]

        result = {"original": "", "result": plans, "thought": ""}
        return result

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return agent_output
