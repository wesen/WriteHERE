import json
import re
from copy import deepcopy

from recursive.agent.prompts.base import prompt_register


def get_llm_output(
    node, agent, memory, agent_type, overwrite_cache=False, *args, **kwargs
):
    memory_info = memory.collect_node_run_info(node)
    task_type = node.task_info.get("task_type", "")

    if task_type == "":
        inner_kwargs = node.config[task_type]
    else:
        task_type = node.task_type_tag
        inner_kwargs = node.config[task_type][agent_type]

    if agent_type == "planning":
        if not inner_kwargs.get("depth_diff", False):
            prompt_version = inner_kwargs["prompt_version"]
        else:
            if node.node_graph_info["outer_node"] is None:
                prompt_version = inner_kwargs["depth_1_prompt_version"]
            else:
                prompt_version = inner_kwargs["depth_N_prompt_version"]
    elif agent_type == "atom":
        if inner_kwargs.get("update_diff", False):
            if len(node.node_graph_info["parent_nodes"]) > 0:
                prompt_version = inner_kwargs["with_update_prompt_version"]
            else:
                prompt_version = inner_kwargs["without_update_prompt_version"]
        else:
            prompt_version = inner_kwargs["prompt_version"]
    else:
        prompt_version = inner_kwargs["prompt_version"]

    to_run_check_str = kwargs.get("to_run_check_str", None)

    system_message = prompt_register.module_dict[
        prompt_version
    ]().construct_system_message(to_run_check_str=to_run_check_str)
    to_run_task = deepcopy(node.task_info)
    for k in ("candidate_plan", "candidate_think"):
        if k in to_run_task:
            del to_run_task[k]

    if kwargs.get("nl", False) and agent_type in ("execute", "final_aggregate"):
        to_run_task = node.task_info["goal"]
        if "length" in node.task_info:
            if node.config.get("language", "") == "en":
                to_run_task += " Word count requirement: approximately {}".format(
                    node.task_info["length"]
                )
            else:
                to_run_task += " 要求字数：约{}".format(node.task_info["length"])
        to_run_outer_graph_dependent = []
        for layer_tasks in memory_info["upper_graph_precedents"]:
            for t in layer_tasks:
                to_run_outer_graph_dependent.append(
                    "【{}】:\n {}".format(t["goal"], t["result"])
                )
        to_run_outer_graph_dependent = "\n\n".join(to_run_outer_graph_dependent)
        to_run_same_graph_dependent = "\n\n".join(
            [
                "【{}】: \n{}".format(t["goal"], t["result"])
                for t in memory_info["same_graph_precedents"]
            ]
        )
    else:
        to_run_task = json.dumps(to_run_task, ensure_ascii=False)
        to_run_outer_graph_dependent = []
        for layer_tasks in memory_info["upper_graph_precedents"]:
            for t in layer_tasks:
                to_run_outer_graph_dependent.append(
                    "【{}】:\n {}".format(t["goal"], t["result"])
                )
        to_run_outer_graph_dependent = "\n\n".join(to_run_outer_graph_dependent)
        to_run_same_graph_dependent = "\n\n".join(
            [
                "【{}】: \n{}".format(t["goal"], t["result"])
                for t in memory_info["same_graph_precedents"]
            ]
        )

    to_run_target_write_tasks = ""
    if task_type == "RETRIEVAL":
        depend_write_task = node.get_direct_depend_write_task()
        if node.config["language"] == "zh":
            to_run_target_write_tasks = (
                "\n".join(
                    "COMPOSITION任务{}，字数：{}".format(idx, node.task_info["length"])
                    for idx, node in enumerate(depend_write_task, start=1)
                )
                if (depend_write_task is not None and len(depend_write_task) > 0)
                else "Not Provided"
            )
        else:
            to_run_target_write_tasks = (
                "\n".join(
                    "Write Task{}，word count requirements：{}".format(
                        idx, node.task_info["length"]
                    )
                    for idx, node in enumerate(depend_write_task, start=1)
                )
                if (depend_write_task is not None and len(depend_write_task) > 0)
                else "Not Provided"
            )

    # Prepare prompt arguments
    prompt_args = {
        "to_run_root_question": memory.root_node.task_info["goal"],
        "to_run_article": memory.article,
        "to_run_full_plan": node.get_all_layer_plan(),
        "to_run_outer_graph_dependent": to_run_outer_graph_dependent,
        "to_run_same_graph_dependent": to_run_same_graph_dependent,
        "to_run_task": to_run_task,
        "to_run_candidate_plan": node.task_info.get("candidate_plan", "Missing"),
        "to_run_candidate_think": node.task_info.get("candidate_think", "Missing"),
        "to_run_final_aggregate": kwargs.get("to_run_final_aggregate", ""),
        "to_run_target_write_tasks": to_run_target_write_tasks,
        "to_run_global_writing_task": node.get_all_previous_writing_plan(),
        "today_date": node.config.get(
            "today_date", "Mar 26, 2025"
        ),  # Add today_date from config
    }

    prompt = prompt_register.module_dict[prompt_version]().construct_prompt(
        **prompt_args
    )
    llm_result = agent.call_llm(
        system_message=system_message,
        prompt=prompt,
        parse_arg_dict=inner_kwargs["parse_arg_dict"],
        overwrite_cache=overwrite_cache,
        **inner_kwargs.get("llm_args", {})
    )
    return llm_result


def extract_json_content(text):
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
