import json
import random
from typing import Any, Optional

from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.registry import agent_register
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode
from recursive.common.context import ExecutionContext


@agent_register.register_module()
class DummyRandomPlanningAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        # layer_cnt = random.randint(1, 3)
        layer = node.node_graph_info["layer"]
        result: dict[str, Any] = {}
        if layer == 2:
            result = {"original": "", "result": [], "thought": ""}
            return result

        # layer_cnt = random.randint(1, 2)
        layer_cnt = 3 if layer == 1 else 1
        plans: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        cnt = 0
        for layer_idx in range(layer_cnt):
            parent = current
            current = []
            # node_cnt = random.randint(1, 3)
            node_cnt = random.randint(1, 2) if layer_idx < 2 else 1
            for nidx in range(node_cnt):
                if layer_idx == 0:
                    depend_cnt = 0
                    dependency = []
                else:
                    dependency = random.sample(parent, random.randint(1, len(parent)))
                    dependency = sorted([node["id"] for node in dependency])
                task = {"goal": "random_dummy", "id": cnt, "dependency": dependency}
                cnt += 1
                current.append(task)
            plans.extend(current)

        result = {"original": "", "result": plans, "thought": ""}
        return result

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return agent_output


@agent_register.register_module()
class DummyRandomExecutorAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        result = {
            "original": "",
            "process": [],
            "thought": "",
            "result": "Random Fake Result",
        }
        return result

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return agent_output


@agent_register.register_module()
class DummyRandomUpdateAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        return None

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(agent_output)


@agent_register.register_module()
class DummyRandomPriorReflectionAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        return None

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(agent_output)


@agent_register.register_module()
class DummyRandomPlanningPostReflectionAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        return None

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(agent_output)


@agent_register.register_module()
class DummyRandomExecutorPostReflectionAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        result: dict[str, Any] = {}
        result = {
            "thought": "",
            "original": "",
            "status": "success",
            "result": node.raw_plan,
        }
        return result

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(agent_output)


@agent_register.register_module()
class DummyRandomFinalAggregateAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        result: dict[str, Any] = {}
        result = {
            "thought": "",
            "original": "",
            "status": "success",
            "result": node.topological_task_queue[-1].get_node_final_result(),
        }
        return result

    @overrides
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(agent_output)
