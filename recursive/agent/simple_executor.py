from typing import Dict

from loguru import logger
from overrides import overrides

from recursive.agent.base import Agent
from recursive.agent.helpers import get_llm_output
from recursive.agent.prompts.base import prompt_register
from recursive.agent.registry import agent_register
from recursive.executor.action import ActionExecutor, BingBrowser
from recursive.executor.agent import SearchAgent


@agent_register.register_module()
class SimpleExecutor(Agent):
    @overrides
    def forward(self, node, memory, *args, **kwargs) -> str:
        """
        {
            executor: {
                prompt_version: xxx,
                llm_args: {xxx},
                parse_arg_dict: {},
            }
        }
        """
        task_type = node.task_type_tag
        inner_kwargs = node.config[task_type]["execute"]
        if task_type == "RETRIEVAL" and inner_kwargs.get("react_agent", False):
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

            react_agent_result = react_agent.chat(
                message=node.task_info["goal"],
                global_start_index=memory.global_start_index,
                to_run_target_write_tasks=to_run_target_write_tasks,
                to_run_root_question=to_run_root_question,
                to_run_outer_write_task=to_run_outer_write_task,
                today_date=node.config.get("today_date", "Mar 26, 2025"),
                temperature=inner_kwargs.get("temperature", None),
            )

            execute_result = []
            for turn_result in react_agent_result["result"]:
                for page in turn_result["web_pages"]:
                    memory.add_search_result(page)
                    if not inner_kwargs.get("only_use_react_summary", False):
                        execute_result.append(
                            FORMAT_STRING_TEMPLATE.format(
                                index=page["global_index"],
                                title=page["title"],
                                url=page["url"],
                                publish_time=page["publish_time"],
                                content=page["summary"],
                            )
                        )
                execute_result.append(
                    "<web_pages_short_summary>\n{}\n</web_pages_short_summary>".format(
                        turn_result["observation"]
                    )
                )
            execute_result = "\n\n".join(execute_result)

            if inner_kwargs.get("llm_merge", False):
                merge_result = self.search_merge(
                    node, memory, execute_result, to_run_outer_write_task
                )
                llm_result = {
                    "ori": react_agent_result["ori"],
                    "agent_result": execute_result,
                    "merge_result": merge_result,
                    "result": merge_result["result"],
                }
            else:
                llm_result = {
                    "ori": react_agent_result["ori"],
                    "result": execute_result,
                }
        else:
            succ = False
            retry_cnt = 0
            while not succ and retry_cnt < 50:
                llm_result = get_llm_output(
                    node, self, memory, "execute", retry_cnt > 0, *args, **kwargs
                )
                # 判定是否失败，如果result不为空则为成功
                succ = llm_result["result"].strip() != ""
                if not succ:
                    logger.error(
                        "Execute for {} is failed, Get Response: {}, retry_cnt={}".format(
                            node, llm_result["original"], retry_cnt
                        )
                    )
                    retry_cnt += 1

            # for write
            if node.task_type_tag == "COMPOSITION":
                memory.article += "\n\n" + llm_result["result"]

        return llm_result

    @overrides
    def parse_result(self, agent_output, *args, **kwargs) -> Dict:
        return agent_output

    def search_merge(
        self, node, memory, search_results, to_run_outer_write_task, *args, **kwargs
    ):
        inner_kwargs = node.config["RETRIEVAL"]["search_merge"]
        prompt_version = inner_kwargs["prompt_version"]

        system_message = prompt_register.module_dict[
            prompt_version
        ]().construct_system_message()

        to_run_search_task = node.task_info["goal"]
        to_run_search_results = search_results

        to_run_root_question = memory.root_node.task_info["goal"]

        # to_run_target_write_tasks
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
        # Prepare prompt arguments
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

        prompt = prompt_register.module_dict[prompt_version]().construct_prompt(
            **prompt_args
        )

        succ = False
        retry_cnt = 0
        while not succ and retry_cnt < 50:
            llm_result = self.call_llm(
                system_message=system_message,
                prompt=prompt,
                parse_arg_dict=inner_kwargs["parse_arg_dict"],
                overwrite_cache=True if retry_cnt > 0 else False,
                **inner_kwargs.get("llm_args", {})
            )
            # 判定是否失败，如果result不为空则为成功
            succ = llm_result["result"].strip() != ""
            if not succ:
                logger.error(
                    "Search Merge for {} is failed, Get Response: {}, retry_cnt={}".format(
                        node, llm_result["original"], retry_cnt
                    )
                )
                retry_cnt += 1
        if not succ:
            logger.error(
                "Search Merge for {} after retry fail, return the original as result".format(
                    node
                )
            )
            llm_result = {"result": search_results}

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
