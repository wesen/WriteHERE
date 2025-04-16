# coding:utf8

from typing import Dict
from overrides import overrides
import json

from recursive.agent.helpers import get_llm_output, extract_json_content
from recursive.executor.action import ActionExecutor
from loguru import logger
from recursive.agent.base import agent_register, Agent
from recursive.agent.prompts.base import prompt_register
from recursive.executor.agent.claude_fc_react import SearchAgent
from recursive.executor.action.bing_browser import BingBrowser


@agent_register.register_module()
class UpdateAtomPlanningAgent(Agent):
    @overrides
    def forward(self, node, memory, *args, **kwargs) -> str:
        """
        {
            atom: {
                prompt_version: xxx,
                llm_args: {xxx},
                parse_arg_dict: {},
                "atom_result_flag": "原子任务"
            }
            planning: {
                prompt_version: xxx,
                llm_args: {xxx},
                parse_arg_dict: {}
            }
        }
        """
        return_result = {}
        # Check Atom
        task_type = node.task_info.get("task_type", "")
        if task_type == "":
            inner_kwargs = node.config[task_type]
        else:
            task_type = node.task_type_tag
            inner_kwargs = node.config[task_type]["atom"]

        if inner_kwargs.get("all_atom", False):
            if not "prompt_version" in inner_kwargs:
                plan_result = []
                return_result["result"] = plan_result
            else:
                # update, but is atom task
                # judge only_on_depend
                if (not inner_kwargs.get("only_on_depend", False)) or (
                    len(node.node_graph_info["parent_nodes"]) > 0
                ):
                    atom_llm_result = get_llm_output(
                        node, self, memory, "atom", *args, **kwargs
                    )
                    atom_llm_result["atom_original"] = atom_llm_result.pop("original")
                    if atom_llm_result.get("update_result", ""):
                        ori_goal = node.task_info["goal"]
                        node.task_info["goal"] = atom_llm_result.get(
                            "update_result", ""
                        ).replace("\n", "; ")
                        logger.info(
                            "Update goal from {} to {}".format(
                                ori_goal, node.task_info["goal"]
                            )
                        )
                    return_result.update(atom_llm_result)
                plan_result = []
                return_result["result"] = plan_result

        elif inner_kwargs.get("use_candidate_plan", False):
            candidate_plan = node.task_info["candidate_plan"]
            plan_result = []
            if not isinstance(candidate_plan, list):
                logger.info("Candidate Plan Missing: {}".format(candidate_plan))
            else:
                plan_result = candidate_plan
            return_result["result"] = plan_result
            logger.info(
                "Use Candidate Plan for: {}, the candidate plan is \n{}".format(
                    node.task_info["goal"], return_result["result"]
                )
            )
        elif (
            "force_atom_layer" in inner_kwargs
            and node.node_graph_info["layer"] >= inner_kwargs["force_atom_layer"]
        ):
            plan_result = []
            return_result["result"] = plan_result
            logger.info(
                "Current Node: {}, Layer = {}, >= force atom layer(), force to atom".format(
                    node,
                    node.node_graph_info["layer"],
                    inner_kwargs["force_atom_layer"],
                )
            )
        else:
            succ = False
            retry_cnt = 0
            while not succ and retry_cnt < 10:
                atom_llm_result = get_llm_output(
                    node, self, memory, "atom", retry_cnt > 0, *args, **kwargs
                )
                # Determine if it failed. If atom_result is not one of "atomic" or "complex" then it's a failure, otherwise it's successful
                succ = atom_llm_result["atom_result"].strip() in ("atomic", "complex")
                if not succ:
                    logger.error(
                        "ATOM Judgement for {} is failed, Get Response: {}, retry_cnt={}".format(
                            node, atom_llm_result["original"], retry_cnt
                        )
                    )
                    retry_cnt += 1

            atom_llm_result["atom_original"] = atom_llm_result.pop("original")
            return_result.update(atom_llm_result)
            # Use atom's thinking as candidate_think for recursive planning
            node.task_info["candidate_think"] = atom_llm_result["atom_think"]
            if atom_llm_result.get("update_result", ""):
                node.task_info["goal"] = atom_llm_result.get(
                    "update_result", ""
                ).replace("\n", "; ")

            if atom_llm_result["atom_result"] == inner_kwargs["atom_result_flag"]:
                plan_result = []
                return_result["result"] = plan_result
            else:  # Need Recursive Planning
                succ = False
                retry_cnt = 0
                plan_result = []
                while not succ and retry_cnt < 10:
                    plan_llm_result = get_llm_output(
                        node, self, memory, "planning", retry_cnt > 0, *args, **kwargs
                    )
                    try:
                        plan_result = self.parse_result(plan_llm_result["plan_result"])
                    except Exception as e:
                        # Incorrect format, cannot get plan_result, first check if planning can be extracted directly from the response
                        source = (
                            plan_llm_result["plan_result"].strip()
                            if plan_llm_result["plan_result"].strip() != ""
                            else plan_llm_result["original"]
                        )
                        plan_llm_result["plan_result"] = extract_json_content(
                            source
                        )  # If fail to fetch, return None
                        try:
                            plan_result = self.parse_result(
                                plan_llm_result["plan_result"]
                            )
                        except Exception as e:
                            logger.error(
                                "Planning for {} failed, original is {}, retry {}".format(
                                    node, plan_llm_result["original"], retry_cnt
                                )
                            )
                            retry_cnt += 1
                            continue
                    succ = True

                plan_llm_result["result"] = plan_result
                return_result.update(plan_llm_result)

        return return_result

    @overrides
    def parse_result(self, agent_output, *args, **kwargs) -> Dict:
        return json.loads(agent_output.strip().strip("`").replace("json", "").strip())[
            "sub_tasks"
        ]
