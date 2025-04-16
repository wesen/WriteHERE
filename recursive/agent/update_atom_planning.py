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
    """
    An agent responsible for deciding if a task node is atomic or needs further planning,
    and potentially updating the task goal.

    This agent performs two main functions based on the node's configuration and context:
    1.  **Atomicity Check**: Determines if the task represented by the node is simple enough
        (atomic) to be executed directly or if it needs to be broken down (planned) into subtasks.
    2.  **Goal Update**: Optionally updates the node's task goal based on context or LLM feedback.
    3.  **Planning**: If the task is not atomic, it invokes the planning process to generate subtasks.
    """

    @overrides
    def forward(self, node, memory, *args, **kwargs) -> Dict:
        """
        Execute the atomicity check and potential planning for a node.

        The behavior depends heavily on the node's configuration (`node.config[task_type]`):
        - If `all_atom` is True: Assumes the task is atomic. Optionally updates the goal if dependencies exist or `only_on_depend` is False.
        - If `use_candidate_plan` is True: Uses the pre-defined `candidate_plan` from the node's task info.
        - If `force_atom_layer` is set and the node's layer meets the threshold: Forces atomicity.
        - Otherwise: Calls an LLM to determine atomicity ("atom" action). If not atomic, calls another LLM for planning ("planning" action).

        Args:
            node (AbstractNode): The task node to process.
            memory (Memory): The current memory context.
            *args: Additional positional arguments (passed to LLM calls).
            **kwargs: Additional keyword arguments (passed to LLM calls).

        Returns:
            dict: A dictionary containing results from the atomicity check and/or planning.
                  Includes keys like `atom_result`, `atom_think`, `update_result`, `plan_result`,
                  and `result` (which holds the list of subtasks if planning occurred, or an empty list if atomic).
        """
        # Configuration structure expected in node.config[task_type]:
        # {
        #     "atom": {
        #         "prompt_version": xxx,            # Prompt for atomicity check LLM
        #         "llm_args": {xxx},                 # LLM args for atomicity check
        #         "parse_arg_dict": {},            # Args for parsing atomicity result
        #         "atom_result_flag": "atomic",      # Expected string indicating atomicity
        #         "all_atom": False,               # Force all tasks of this type to be atomic
        #         "only_on_depend": False,         # Update goal only if node has dependencies
        #         "use_candidate_plan": False,     # Use pre-defined plan
        #         "force_atom_layer": N            # Force atomicity at or beyond layer N
        #     },
        #     "planning": {
        #         "prompt_version": xxx,            # Prompt for planning LLM
        #         "llm_args": {xxx},                 # LLM args for planning
        #         "parse_arg_dict": {}             # Args for parsing planning result
        #     }
        # }

        return_result = {}
        # Check Atom
        task_type = node.task_info.get("task_type", "")
        if (
            task_type == ""
        ):  # Handle potential missing task_type - assumes a default/global config?
            # TODO: Clarify behavior when task_type is missing. Assuming it uses a global default config key.
            # inner_kwargs = node.config.get(task_type, {}).get("atom", {}) # Safer approach
            inner_kwargs = node.config[task_type][
                "atom"
            ]  # Original code, might raise KeyError

        else:
            task_type_tag = node.task_type_tag
            inner_kwargs = node.config[task_type_tag]["atom"]

        if inner_kwargs.get("all_atom", False):
            # --- Case 1: Forced Atomicity ---
            if not "prompt_version" in inner_kwargs:
                # No update prompt defined, simply return empty plan
                plan_result = []
                return_result["result"] = plan_result
            else:
                # Update goal potentially, but still atomic
                # Check if update should happen based on dependencies
                if (not inner_kwargs.get("only_on_depend", False)) or (
                    len(node.node_graph_info["parent_nodes"]) > 0
                ):
                    # Call LLM for potential goal update
                    atom_llm_result = get_llm_output(
                        node, self, memory, "atom", *args, **kwargs
                    )
                    atom_llm_result["atom_original"] = atom_llm_result.pop("original")
                    # Update goal if provided by LLM
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
                # Task is atomic, so plan result is empty
                plan_result = []
                return_result["result"] = plan_result

        elif inner_kwargs.get("use_candidate_plan", False):
            # --- Case 2: Use Pre-defined Candidate Plan ---
            candidate_plan = node.task_info.get("candidate_plan", "Missing")
            plan_result = []
            if not isinstance(candidate_plan, list):
                logger.warning(
                    "Candidate Plan Missing or not a list: {}".format(candidate_plan)
                )
            else:
                plan_result = candidate_plan
            return_result["result"] = plan_result
            logger.info(
                "Using Candidate Plan for: {}, Plan: \n{}".format(
                    node.task_info["goal"], return_result["result"]
                )
            )
        elif (
            "force_atom_layer" in inner_kwargs
            and node.node_graph_info["layer"] >= inner_kwargs["force_atom_layer"]
        ):
            # --- Case 3: Force Atomicity by Layer Depth ---
            plan_result = []
            return_result["result"] = plan_result
            logger.info(
                "Node: {}, Layer={}, >= force_atom_layer ({}), forcing atomicity.".format(
                    node,  # Consider using node.nid or task_str() for brevity
                    node.node_graph_info["layer"],
                    inner_kwargs["force_atom_layer"],
                )
            )
        else:
            # --- Case 4: LLM-based Atomicity Check and Planning ---
            succ = False
            retry_cnt = 0
            MAX_RETRIES = 10  # Define as constant
            atom_llm_result = {}  # Initialize
            # Atomicity Check Loop
            while not succ and retry_cnt < MAX_RETRIES:
                atom_llm_result = get_llm_output(
                    node, self, memory, "atom", retry_cnt > 0, *args, **kwargs
                )
                # Determine if the LLM response indicates a clear decision
                # TODO: Make ("atomic", "complex") configurable? Seems hardcoded relation to atom_result_flag.
                succ = atom_llm_result.get("atom_result", "").strip() in (
                    "atomic",
                    "complex",
                )
                if not succ:
                    logger.error(
                        "ATOM Judgement for {} failed. Response: {}, Retry: {}/{}".format(
                            node.nid,
                            atom_llm_result.get("original", "N/A"),
                            retry_cnt + 1,
                            MAX_RETRIES,
                        )
                    )
                    retry_cnt += 1
                else:
                    logger.info(
                        "Atom check successful for {} after {} retries.".format(
                            node.nid, retry_cnt
                        )
                    )

            if not succ:
                logger.error(
                    "Atom check failed for {} after {} retries. Proceeding might yield unexpected results.".format(
                        node.nid, MAX_RETRIES
                    )
                )
                # Decide on fallback behavior: assume atomic? Assume complex? Raise error? Currently implicitly assumes complex if check fails.

            atom_llm_result["atom_original"] = atom_llm_result.pop("original", "N/A")
            return_result.update(atom_llm_result)
            # Use atom's thinking process as candidate context for potential planning step
            node.task_info["candidate_think"] = atom_llm_result.get("atom_think", "")
            # Update goal if LLM provided one
            if atom_llm_result.get("update_result", ""):
                ori_goal = node.task_info["goal"]
                node.task_info["goal"] = atom_llm_result.get(
                    "update_result", ""
                ).replace("\n", "; ")
                logger.info(
                    "Update goal for {} from '{}' to '{}'".format(
                        node.nid, ori_goal, node.task_info["goal"]
                    )
                )

            # Check if LLM decided the task is atomic
            # Assumes config `atom_result_flag` holds the string indicating atomicity (e.g., "atomic")
            if atom_llm_result.get("atom_result", "").strip() == inner_kwargs.get(
                "atom_result_flag", "atomic"
            ):
                plan_result = []
                return_result["result"] = plan_result
                logger.info("Node {} determined to be atomic.".format(node.nid))
            else:  # Task is complex, requires planning
                logger.info(
                    "Node {} determined to be complex, initiating planning.".format(
                        node.nid
                    )
                )
                succ = False
                retry_cnt = 0
                plan_result = []
                plan_llm_result = {}  # Initialize
                # Planning Loop
                while not succ and retry_cnt < MAX_RETRIES:
                    plan_llm_result = get_llm_output(
                        node, self, memory, "planning", retry_cnt > 0, *args, **kwargs
                    )
                    try:
                        # Attempt to parse the direct "plan_result" field
                        plan_result = self.parse_result(
                            plan_llm_result.get("plan_result", "")
                        )
                        succ = True
                    except Exception as e_direct:
                        logger.warning(
                            "Direct parsing of 'plan_result' failed for {}: {}. Trying extraction from 'original'...".format(
                                node.nid, e_direct
                            )
                        )
                        # If direct parsing fails, try extracting JSON from the raw response
                        source = plan_llm_result.get("original", "")
                        extracted_json_str = extract_json_content(source)
                        if extracted_json_str:
                            try:
                                plan_result = self.parse_result(extracted_json_str)
                                succ = True
                                logger.info(
                                    "Successfully parsed plan from extracted JSON for {}.".format(
                                        node.nid
                                    )
                                )
                            except Exception as e_extracted:
                                logger.error(
                                    "Planning parsing failed for {} even after extraction. Error: {}, Original: {}, Retry: {}/{}".format(
                                        node.nid,
                                        e_extracted,
                                        source,
                                        retry_cnt + 1,
                                        MAX_RETRIES,
                                    )
                                )
                                retry_cnt += 1
                        else:
                            logger.error(
                                "Planning failed for {}. Could not extract JSON from original response. Original: {}, Retry: {}/{}".format(
                                    node.nid, source, retry_cnt + 1, MAX_RETRIES
                                )
                            )
                            retry_cnt += 1

                if not succ:
                    logger.error(
                        "Planning failed for {} after {} retries. Returning empty plan.".format(
                            node.nid, MAX_RETRIES
                        )
                    )
                    plan_result = []  # Ensure plan_result is empty on failure

                plan_llm_result["result"] = plan_result
                return_result.update(plan_llm_result)

        return return_result

    @overrides
    def parse_result(self, agent_output, *args, **kwargs) -> list:
        """
        Parse the LLM output string containing the plan into a list of subtasks.

        Expects the `agent_output` to be a JSON string representing an object
        with a "sub_tasks" key, where the value is a list of subtask dictionaries.
        Cleans potential markdown code fences or "json" labels before parsing.

        Args:
            agent_output: The raw string output from the planning LLM.
            *args: Additional positional arguments (unused).
            **kwargs: Additional keyword arguments (unused).

        Returns:
            list: A list of dictionaries, where each dictionary represents a subtask.
                  Returns an empty list if parsing fails or input is invalid.

        Raises:
            json.JSONDecodeError: If the input string is not valid JSON after cleaning.
            KeyError: If the parsed JSON does not contain the "sub_tasks" key.
            TypeError: If the input is not a string or cannot be parsed.
        """
        if not isinstance(agent_output, str) or not agent_output.strip():
            logger.warning(
                "parse_result received invalid input: {}".format(agent_output)
            )
            return []  # Return empty list for invalid input
        try:
            # Clean potential markdown fences and language identifiers
            cleaned_output = agent_output.strip().strip("`").replace("json", "").strip()
            # Handle potential leading/trailing non-JSON content if necessary
            if not cleaned_output.startswith("{"):
                start_index = cleaned_output.find("{")
                if start_index != -1:
                    cleaned_output = cleaned_output[start_index:]
            if not cleaned_output.endswith("}"):
                end_index = cleaned_output.rfind("}")
                if end_index != -1:
                    cleaned_output = cleaned_output[: end_index + 1]

            parsed_json = json.loads(cleaned_output)
            if "sub_tasks" not in parsed_json:
                logger.error(
                    "'sub_tasks' key not found in parsed planning JSON: {}".format(
                        cleaned_output
                    )
                )
                return []
            if not isinstance(parsed_json["sub_tasks"], list):
                logger.error(
                    "'sub_tasks' value is not a list in parsed planning JSON: {}".format(
                        cleaned_output
                    )
                )
                return []
            return parsed_json["sub_tasks"]
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to decode planning JSON: {}. Input: {}".format(e, agent_output)
            )
            # Optionally re-raise or return empty list depending on desired error handling
            # raise # Re-raise the exception
            return []  # Return empty list on error
        except Exception as e:
            logger.error(
                "Unexpected error parsing planning result: {}. Input: {}".format(
                    e, agent_output
                )
            )
            return []
