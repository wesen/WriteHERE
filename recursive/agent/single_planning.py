from typing import Any

from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.registry import agent_register
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode


@agent_register.register_module()
class SinglePlanningAgent(Agent):
    @overrides
    def forward(
        self, node: AbstractNode, memory: Memory, *args: Any, **kwargs: Any
    ) -> str:
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
