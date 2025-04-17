from typing import Dict, Any, Optional

from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.helpers import get_llm_output
from recursive.agent.registry import agent_register
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode
from recursive.common.context import ExecutionContext


@agent_register.register_module()
class FinalAggregateAgent(Agent):
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Dict:
        return_result = {}
        task_type = node.task_type_tag
        if task_type == "RETRIEVAL":
            # Aggregate All Child Result
            results = []
            for child in node.topological_task_queue:
                results.append(
                    "【{}】:\n {}".format(
                        child.task_info["goal"], child.get_node_final_result()["result"]
                    )
                )
            results = "\n\n".join(results)
            return_result["result"] = results

        elif task_type == "REASONING":
            inner_kwargs = node.config[task_type]["final_aggregate"]
            results = []
            for child in node.topological_task_queue:
                results.append(
                    "【{}】:\n {}".format(
                        child.task_info["goal"], child.get_node_final_result()["result"]
                    )
                )
            results = "\n\n".join(results)
            if inner_kwargs.get("mode", "concat") == "concat":
                return_result["result"] = results
            else:
                assert inner_kwargs.get("mode", "concat") == "llm"
                fa_llm_result = get_llm_output(
                    node,
                    self,
                    memory,
                    "final_aggregate",
                    ctx=ctx,
                    to_run_final_aggregate=results,
                    *args,
                    **kwargs
                )
                return_result = fa_llm_result

        elif task_type == "COMPOSITION":
            return_result["result"] = memory.article
        return return_result

    @overrides
    def parse_result(self, agent_output, *args, **kwargs) -> Dict:
        return agent_output
