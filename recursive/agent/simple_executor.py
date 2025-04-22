from typing import Dict, Any, Optional

from loguru import logger
from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.helpers import get_llm_output
from recursive.agent.prompts.base import prompt_register
from recursive.agent.registry import agent_register
from recursive.executor.action import ActionExecutor, BingBrowser
from recursive.executor.agent import SearchAgent
from recursive.common.log_typing import log_typing
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode
from recursive.common.context import ExecutionContext


@agent_register.register_module()
class SimpleExecutor(Agent):
    """
    An agent responsible for executing atomic tasks based on their type.

    This agent handles the direct execution of tasks that have been deemed atomic
    (i.e., do not require further planning/decomposition). It routes the execution
    based on the task type (RETRIEVAL, COMPOSITION, REASONING).

    For RETRIEVAL tasks, it can use either a ReAct-based SearchAgent or a standard
    LLM call, potentially followed by an LLM-based merge step.
    For COMPOSITION tasks, it calls an LLM and appends the result to the main article.
    For other tasks (like REASONING), it calls an LLM to get the result.
    """

    @log_typing
    @overrides
    def forward(
        self,
        node: AbstractNode,
        memory: Memory,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Dict:
        """
        Execute the task represented by the node.

        Determines the execution strategy based on the node's task type tag
        and configuration. Passes ExecutionContext down to LLM calls.

        - For RETRIEVAL tasks with `react_agent` enabled in config:
            - Initializes and runs a `SearchAgent` (ReAct style).
            - Adds individual search results to memory.
            - Formats search results and observations into a string.
            - Optionally calls `search_merge` to further process results with an LLM.
        - For other tasks (or RETRIEVAL without `react_agent`):
            - Calls the LLM using `get_llm_output` with the 'execute' action type.
            - Retries until a non-empty result is obtained.
            - For COMPOSITION tasks, appends the LLM result to `memory.article`.

        Args:
            node (AbstractNode): The node representing the task to execute.
            memory (Memory): The shared memory object providing context.
            ctx (Optional[ExecutionContext]): The execution context for the task.
            *args: Additional positional arguments (unused by default, potentially passed to LLM calls).
            **kwargs: Additional keyword arguments (unused by default, potentially passed to LLM calls).

        Returns:
            Dict: A dictionary containing the execution results. Structure varies:
                  - For ReAct RETRIEVAL: Includes 'ori' (original ReAct trace), 'result' (formatted/merged search results), potentially 'agent_result' (raw formatted results before merge) and 'merge_result' (raw merge LLM output).
                  - For other tasks: Includes 'result' (direct LLM output), 'original' (raw LLM response).
        """
        # Expected configuration structure in node.config[task_type]["execute"]
        # {
        #     "prompt_version": xxx,            # Prompt for standard execution LLM call
        #     "llm_args": {xxx},                 # LLM args for standard execution
        #     "parse_arg_dict": {},            # Args for parsing standard execution result (often unused here)
        #
        #     # --- Specific to RETRIEVAL with react_agent=True ---
        #     "react_agent": True,             # Flag to enable ReAct agent
        #     "searcher_type": "bing",         # Type of search engine action
        #     "search_max_thread": N,          # Max threads for search action
        #     "selector_max_workers": N,       # Workers for search result selection
        #     "summarizier_max_workers": N,    # Workers for search result summarization
        #     "selector_model": "xxx",         # Model for selection
        #     "summarizer_model": "xxx",       # Model for summarization
        #     "webpage_helper_max_threads": N, # Threads for webpage fetching
        #     "backend_engine": "xxx",         # Backend engine (e.g., OpenAI model name)
        #     "cc": "xxx",                     # Country code for search
        #     "max_turn": N,                   # Max ReAct turns
        #     "react_parse_arg_dict": {},      # Parsing args for ReAct output
        #     "only_use_react_summary": False, # If True, only use the <web_pages_short_summary>
        #     "llm_merge": False,              # If True, call search_merge after ReAct
        #     "temperature": T                 # Optional temperature override for ReAct LLM
        # }
        llm_result: Dict = {}  # Initialize llm_result
        task_type = node.task_type_tag
        inner_kwargs = node.config[task_type]["execute"]

        if task_type == "RETRIEVAL" and inner_kwargs.get("react_agent", False):
            # --- Execute RETRIEVAL using ReAct SearchAgent ---
            react_agent = SearchAgent(
                prompt_version=inner_kwargs["prompt_version"],
                action_executor=ActionExecutor(
                    actions=[
                        BingBrowser(
                            searcher_type=inner_kwargs["searcher_type"],
                            language=node.config["language"],
                            search_max_thread=inner_kwargs["search_max_thread"],
                            selector_max_workers=inner_kwargs["selector_max_workers"],
                            summarizier_max_workers=inner_kwargs[
                                "summarizier_max_workers"
                            ],
                            selector_model=inner_kwargs["selector_model"],
                            summarizer_model=inner_kwargs["summarizer_model"],
                            webpage_helper_max_threads=inner_kwargs[
                                "webpage_helper_max_threads"
                            ],
                            backend_engine=inner_kwargs["backend_engine"],
                            cc=inner_kwargs["cc"],
                        )
                    ]
                ),
                model=inner_kwargs["llm_args"]["model"],
                max_turn=inner_kwargs["max_turn"],
                action_memory=True,
                remove_history=True,
                parse_arg_dict=inner_kwargs["react_parse_arg_dict"],
            )

            # Gather context for the ReAct agent prompt
            depend_write_task = node.get_direct_depend_write_task()
            to_run_root_question = memory.root_node.task_info["goal"]
            if node.config["language"] == "zh":
                to_run_target_write_tasks = (
                    "\n".join(
                        "COMPOSITION任务{}，字数：{}".format(
                            idx, node.task_info["length"]
                        )
                        for idx, node in enumerate(depend_write_task, start=1)
                    )
                    if (depend_write_task is not None and len(depend_write_task) > 0)
                    else "Not Provided"
                )
                outer_write_task = node.get_outer_write_task()
                to_run_outer_write_task = "COMPOSITION任务{}，字数：{}".format(
                    outer_write_task["goal"], outer_write_task["length"]
                )
            else:
                to_run_target_write_tasks = (
                    "\n".join(
                        "Write Task{}, word count requirements: {}".format(
                            idx, node.task_info["length"]
                        )
                        for idx, node in enumerate(depend_write_task, start=1)
                    )
                    if (depend_write_task is not None and len(depend_write_task) > 0)
                    else "Not Provided"
                )
                outer_write_task = node.get_outer_write_task()
                to_run_outer_write_task = (
                    "Write Task {}, word count requirements: {}".format(
                        outer_write_task.task_info["goal"],
                        outer_write_task.task_info["length"],
                    )
                )

            # Run the ReAct agent
            react_agent_result = react_agent.chat(
                message=node.task_info["goal"],
                global_start_index=memory.global_start_index,
                to_run_target_write_tasks=to_run_target_write_tasks,
                to_run_root_question=to_run_root_question,
                to_run_outer_write_task=to_run_outer_write_task,
                today_date=node.config.get("today_date", "Mar 26, 2025"),
                temperature=inner_kwargs.get("temperature", None),
                ctx=ctx,
            )

            # Process ReAct agent results
            execute_result = []
            if "result" in react_agent_result:  # Check if result exists
                for turn_result in react_agent_result["result"]:
                    if "web_pages" in turn_result:  # Check if web_pages exists
                        for page in turn_result["web_pages"]:
                            memory.add_search_result(
                                page
                            )  # Add results to global memory
                            if not inner_kwargs.get("only_use_react_summary", False):
                                # Include formatted individual page summaries if not configured otherwise
                                execute_result.append(
                                    FORMAT_STRING_TEMPLATE.format(
                                        index=page.get(
                                            "global_index", "N/A"
                                        ),  # Use .get for safety
                                        title=page.get("title", "N/A"),
                                        url=page.get("url", "N/A"),
                                        publish_time=page.get("publish_time", "N/A"),
                                        content=page.get("summary", "N/A"),
                                    )
                                )
                    # Always include the agent's turn observation (summary of pages in that turn)
                    if "observation" in turn_result:  # Check if observation exists
                        execute_result.append(
                            "<web_pages_short_summary>\n{}\n</web_pages_short_summary>".format(
                                turn_result["observation"]
                            )
                        )
            execute_result_str = "\n\n".join(execute_result)

            # Optionally merge results using another LLM call
            if inner_kwargs.get("llm_merge", False):
                merge_result = self.search_merge(
                    node, memory, execute_result_str, to_run_outer_write_task, ctx=ctx
                )
                llm_result = {
                    "ori": react_agent_result.get(
                        "ori", "N/A"
                    ),  # Keep original ReAct trace
                    "agent_result": execute_result_str,  # Keep formatted pre-merge results
                    "merge_result": merge_result,  # Keep raw merge LLM output
                    "result": merge_result.get(
                        "result",
                        execute_result_str,  # Fallback to pre-merge if merge fails
                    ),  # Final result is the merged content
                }
            else:
                # If no merge, the formatted search results are the final result
                llm_result = {
                    "ori": react_agent_result.get("ori", "N/A"),
                    "result": execute_result_str,
                }
        else:
            # --- Execute other task types (COMPOSITION, REASONING) or non-ReAct RETRIEVAL ---
            succ = False
            retry_cnt = 0
            MAX_RETRIES = 50  # Consider making this configurable
            llm_result = {}  # Initialize
            while not succ and retry_cnt < MAX_RETRIES:
                llm_result = get_llm_output(
                    node,
                    self,
                    memory,
                    "execute",
                    retry_cnt > 0,
                    ctx=ctx,
                    *args,
                    **kwargs
                )
                # Check if the execution produced a non-empty result
                succ = llm_result.get("result", "").strip() != ""
                if not succ:
                    logger.error(
                        "Execute for {} failed. Response: {}, Retry: {}/{}".format(
                            node.nid,
                            llm_result.get("original", "N/A"),
                            retry_cnt + 1,
                            MAX_RETRIES,
                        )
                    )
                    retry_cnt += 1

            if not succ:
                logger.error(
                    "Execute for {} failed after {} retries. Result might be empty.".format(
                        node.nid, MAX_RETRIES
                    )
                )
                # Ensure result field exists even on failure
                if "result" not in llm_result:
                    llm_result["result"] = ""

            # Special handling for COMPOSITION tasks: append result to article
            if node.task_type_tag == "COMPOSITION":
                if llm_result.get(
                    "result", ""
                ).strip():  # Only append if result is not empty
                    memory.article += "\n\n" + llm_result["result"]
                else:
                    logger.warning(
                        "COMPOSITION task {} produced empty result, not appending to article.".format(
                            node.nid
                        )
                    )

        return llm_result

    @log_typing
    @overrides
    def parse_result(self, agent_output: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Parse the raw output from the agent's execution step.

        For SimpleExecutor, the standard LLM calls (via `get_llm_output`)
        already return a dictionary. This method acts as a pass-through
        for those cases. The ReAct path constructs its dictionary directly.

        Args:
            agent_output (Dict): The output dictionary from `get_llm_output`.
            *args: Additional positional arguments (unused).
            **kwargs: Additional keyword arguments (unused).

        Returns:
            Dict: The input dictionary, unchanged.
        """
        # Assumes get_llm_output returns a Dict. If it could return str,
        # more complex parsing might be needed here based on context.
        return agent_output

    @log_typing
    def search_merge(
        self,
        node: AbstractNode,
        memory: Memory,
        search_results: str,
        to_run_outer_write_task: str,
        ctx: Optional[ExecutionContext] = None,
        *args: Any,
        **kwargs: Any
    ) -> Dict:
        """
        Merge and summarize search results using an LLM call.

        This helper method is called specifically for RETRIEVAL tasks when
        the configuration enables `llm_merge` after a ReAct search.
        It takes the formatted search results, constructs a specific prompt
        (likely using `MergeSearchResultVFinal` or similar), and calls the LLM
        to produce a final, merged summary relevant to the writing tasks.

        Args:
            node (AbstractNode): The RETRIEVAL node being processed.
            memory (Memory): The shared memory object.
            search_results (str): The formatted string of search results from the ReAct agent.
            to_run_outer_write_task (str): Context string describing the outer writing task.
            ctx (Optional[ExecutionContext]): The execution context for the task.
            *args: Additional positional arguments (unused).
            **kwargs: Additional keyword arguments (unused).

        Returns:
            Dict: A dictionary containing the LLM's merge result under the 'result' key,
                  along with the original raw response ('original'). Returns the raw
                  `search_results` if the LLM call fails after retries.
        """
        # Retrieve configuration specific to the search merge step
        inner_kwargs = node.config["RETRIEVAL"]["search_merge"]
        prompt_version = inner_kwargs["prompt_version"]

        # Instantiate the prompt template
        prompt_template = prompt_register.module_dict[prompt_version]()
        system_message = prompt_template.construct_system_message()

        # Gather context for the merge prompt
        to_run_search_task = node.task_info["goal"]
        to_run_search_results = search_results
        to_run_root_question = memory.root_node.task_info["goal"]

        # Context: Dependent writing tasks
        depend_write_task = node.get_direct_depend_write_task()
        if node.config["language"] == "zh":
            to_run_target_write_tasks = (
                "\n".join(
                    "写作任务{}，字数：{}".format(idx, node.task_info["length"])
                    for idx, node in enumerate(depend_write_task, start=1)
                )
                if (depend_write_task is not None and len(depend_write_task) > 0)
                else "Not Provided"
            )
        else:
            to_run_target_write_tasks = (
                "\n".join(
                    "Write Task{}, word count requirements：{}".format(
                        idx, node.task_info["length"]
                    )
                    for idx, node in enumerate(depend_write_task, start=1)
                )
                if (depend_write_task is not None and len(depend_write_task) > 0)
                else "Not Provided"
            )

        # Prepare prompt arguments dictionary
        prompt_args = {
            "to_run_search_task": to_run_search_task,
            "to_run_search_results": to_run_search_results,
            "to_run_target_write_tasks": to_run_target_write_tasks,
            "to_run_outer_write_task": to_run_outer_write_task,
            "to_run_root_question": to_run_root_question,
            "today_date": node.config.get(
                "today_date", "Mar 26, 2025"
            ),  # Add today_date from config
        }

        # Construct the final prompt
        prompt = prompt_template.construct_prompt(**prompt_args)

        # Call LLM with retry logic
        succ = False
        retry_cnt = 0
        MAX_RETRIES = 50  # Consider making this configurable
        llm_result: Dict = {}  # Initialize
        while not succ and retry_cnt < MAX_RETRIES:
            llm_result = self.call_llm(
                system_message=system_message,
                prompt=prompt,
                parse_arg_dict=inner_kwargs["parse_arg_dict"],
                overwrite_cache=True if retry_cnt > 0 else False,
                ctx=ctx,
                **inner_kwargs.get("llm_args", {})
            )
            # Check if the merge produced a non-empty result
            succ = llm_result.get("result", "").strip() != ""
            if not succ:
                logger.error(
                    "Search Merge for {} failed. Response: {}, Retry: {}/{}".format(
                        node.nid,
                        llm_result.get("original", "N/A"),
                        retry_cnt + 1,
                        MAX_RETRIES,
                    )
                )
                retry_cnt += 1

        if not succ:
            # Fallback to using the original search_results if merge fails
            logger.error(
                "Search Merge for {} failed after {} retries. Falling back to pre-merge results.".format(
                    node.nid, MAX_RETRIES
                )
            )
            # Ensure structure is consistent on failure, providing original results
            llm_result = {
                "result": search_results,
                "original": "LLM merge failed after retries.",  # Add note about failure
            }

        return llm_result


FORMAT_STRING_TEMPLATE = """
<web_page index={index}>
<title>
{title}
</title>
<url>
{url}
</url>
<page_time>
{publish_time}
</page_time>
<summary>
{content}
</summary>
</web_page>
"""
