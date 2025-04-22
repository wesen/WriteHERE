# coding:utf8

from collections import deque
from typing import Dict, List, Optional, Union, Any

from recursive.common.enums import TaskStatus
from recursive.utils.display import display_plan
from recursive.memory import Memory
from recursive.node.abstract import AbstractNode
import dill as pickle  # type: ignore
import json
from loguru import logger
from recursive.common.log_typing import log_typing
import time  # For timing steps
from recursive.utils.event_bus import emit_step_started, emit_step_finished
from recursive.common.context import ExecutionContext


class GraphRunEngine:
    """
    Orchestrates the execution of a task graph.

    This engine manages the lifecycle of tasks represented by nodes in a graph,
    driving the execution process step by step based on node statuses and dependencies.
    It handles finding executable nodes, triggering actions, updating node statuses,
    and managing memory context.
    """

    @log_typing
    def __init__(
        self, root_node: AbstractNode, memory_format: str, config: Dict
    ) -> None:
        """
        Initialize the GraphRunEngine.

        Args:
            root_node (AbstractNode): The root node of the task graph.
            memory_format (str): The format string for the memory representation.
            config (dict): The configuration dictionary for the engine and agents.
        """
        self.root_node: AbstractNode = root_node
        self.memory: Memory = Memory(root_node, format=memory_format, config=config)

    @log_typing
    def find_need_next_step_nodes(
        self, single: bool = False
    ) -> Optional[Union[List[AbstractNode], AbstractNode]]:
        """
        Find nodes in the graph that are ready for the next action step.

        Traverses the graph breadth-first, identifying nodes in an 'activate' state.
        If a node is in a 'suspend' state, its inner graph is traversed.

        Args:
            single (bool, optional): If True, returns the first activate node found.
                                     If False, returns all activate nodes. Defaults to False.

        Returns:
            list | AbstractNode | None: A list of activate nodes if single=False.
                                       The first activate node found if single=True.
                                       None if no activate nodes are found and single=True.
        """
        nodes: List[AbstractNode] = []
        queue: deque[AbstractNode] = deque([self.root_node])
        # Root node, starts in READY state
        while len(queue) > 0:
            # logger.info("in find_need_next_step_nodes, queue: {}".format(queue))
            node = queue.popleft()
            # logger.info("in find_need_next_step_nodes, select node: {}".format(node))
            if node.is_activate:
                nodes.append(node)
            if (
                node.is_suspend
            ):  # If the node is in a suspended state internally, traverse the topological_task_queue of internal nodes
                queue.extend(node.topological_task_queue)
            if single and len(nodes) > 0:
                return nodes[0]
        if not single:
            return nodes
        else:
            return None

    @log_typing
    def save(self, folder: str) -> None:
        """
        Save the current state of the engine and task graph.

        Persists the root node (both pickled and JSON), memory, and the
        current article content to the specified folder.

        Args:
            folder (str): The directory path to save the state files.
        """
        # save root_node
        # save memory
        # save article while running
        root_node_file = "{}/nodes.pkl".format(folder)
        root_node_json_file = "{}/nodes.json".format(folder)
        article_file = "{}/article.txt".format(folder)
        with open(root_node_file, "wb") as f:
            pickle.dump(self.root_node, f)

        with open(root_node_json_file, "w") as f:
            json.dump(self.root_node.to_json(), f, indent=4, ensure_ascii=False)

        self.memory.save(folder)

        with open(article_file, "w", encoding="utf-8") as file:
            file.write(self.memory.article)

    @log_typing
    def load(self, folder: str) -> None:
        """
        Load the engine and task graph state from a saved folder.

        Restores the root node and memory from persisted files.

        Args:
            folder (str): The directory path containing the saved state files.
        """
        root_node_file = "{}/nodes.pkl".format(folder)
        with open(root_node_file, "rb") as f:
            self.root_node = pickle.load(f)

        self.memory = self.memory.load(folder)

    @log_typing
    def forward_exam(
        self, node: AbstractNode, verbose: bool, ctx: Optional[ExecutionContext] = None
    ) -> None:
        """
        Recursively examine and update the status of a node and its descendants.

        This performs a bottom-up hierarchical and top-down dependency-based status update.
        It checks conditions for transitions like NOT_READY -> READY or DOING -> FINISH.
        The actual status update logic is within the node's `do_exam` method.

        Args:
            node (AbstractNode): The node to start the examination from.
            verbose (bool): Whether to log status changes during examination.
            ctx (ExecutionContext, optional): Execution context, primarily for step tracking.
        """
        # The exam order is bottom-up hierarchically, and top-down based on dependencies.
        # not_ready -> ready: Need to check the execution status of dependent nodes, and whether upper-level nodes have entered the doing state
        # doing -> final_to_finish: Need to check if all lower-level nodes have finished
        # plan_reflection_done -> doing:
        if node.is_suspend:
            for inner_node in node.topological_task_queue:
                self.forward_exam(inner_node, verbose, ctx)
            node.do_exam(verbose, ctx)

    @log_typing
    def forward_one_step_not_parallel(
        self,
        step: int,
        full_step: bool = False,
        select_node_hashkey: Optional[str] = None,
        log_fn: Optional[str] = None,
        nodes_json_file: Optional[str] = None,
        *action_args: Any,
        **action_kwargs: Any,
    ) -> Optional[str]:
        """
        Execute a single step in the graph execution process (sequentially).

        1. Finds the next node ready for an action.
        2. Updates the memory context for that node.
        3. Executes the node's next action step, passing ExecutionContext.
        4. Triggers a graph-wide status examination (`forward_exam`).
        5. Optionally logs the graph state and saves the node structure.

        Args:
            step (int): The step number in the execution process.
            full_step (bool, optional): Whether to execute the node's full action step. Defaults to False.
            select_node_hashkey (str, optional): If provided, forces execution of the node with this hashkey. Defaults to None.
            log_fn (str, optional): Path for logging graph visualization (not currently used effectively). Defaults to None.
            nodes_json_file (str, optional): Path to save the updated node structure as JSON after the step. Defaults to None.
            *action_args: Positional arguments passed to the node's action method.
            **action_kwargs: Keyword arguments passed to the node's action method.

        Returns:
            str | None: "done" if all nodes are finished, otherwise None.

        Raises:
            Exception: If `select_node_hashkey` is provided but the specified node cannot be executed.
        """
        # Find tasks that need to enter the next step
        need_next_step_node: Optional[AbstractNode] = None
        if select_node_hashkey is not None:
            found_nodes = self.find_need_next_step_nodes(single=False)
            if found_nodes:
                for node in found_nodes:
                    if node.hashkey == select_node_hashkey:
                        need_next_step_node = node
                        break
                else:
                    raise Exception(
                        "Error, the select node {} can not be executed".format(
                            select_node_hashkey
                        )
                    )
            else:
                raise Exception(
                    "Error, the select node {} can not be executed".format(
                        select_node_hashkey
                    )
                )
        else:
            need_next_step_node = self.find_need_next_step_nodes(single=True)

        step_start_time = time.monotonic()
        if need_next_step_node is None:
            logger.info("All Done")
            # display_graph(self.root_node.inner_graph, fn=log_fn)
            display_plan(self.root_node.inner_graph)

            # Save final nodes.json if path provided
            if nodes_json_file:
                with open(nodes_json_file, "w") as f:
                    json.dump(self.root_node.to_json(), f, indent=4, ensure_ascii=False)

            return "done"
        logger.info("select node: {}".format(need_next_step_node.task_str()))

        # --- Emit StepStarted ---
        emit_step_started(
            step=step,
            node_id=need_next_step_node.hashkey,
            node_goal=need_next_step_node.task_info.get("goal", "?"),
            root_id=self.root_node.hashkey,
            ctx=None,  # Initial step start doesn't have prior context
        )

        # Create ExecutionContext with initial step and node info
        ctx = ExecutionContext(
            step=step,
            node_id=need_next_step_node.hashkey,
            task_type=need_next_step_node.task_type_tag,  # Add task_type here
            task_goal=need_next_step_node.task_info.get("goal"),  # Add task_goal here
        )

        # Execute the next step for this node
        # Update Memory
        self.memory.update_infos([need_next_step_node])

        # Update nodes.json after each step if path provided
        if nodes_json_file:
            with open(nodes_json_file, "w") as f:
                json.dump(self.root_node.to_json(), f, indent=4, ensure_ascii=False)

        action_name: str = ""
        action_result: Any = None
        if not full_step:
            action_name, action_result = need_next_step_node.next_action_step(
                self.memory, ctx, *action_args, **action_kwargs
            )
        else:
            # TODO: Implement or remove next_full_action_step
            action_name, action_result = need_next_step_node.next_action_step(
                self.memory, ctx, *action_args, **action_kwargs
            )
            # action_name = need_next_step_node.next_full_action_step(self.memory) # Original code, method seems missing

        verbose: bool = action_name not in (
            "update",
            "prior_reflect",
            "planning_post_reflect",
            "execute_post_reflect",
        )

        # After the action ends, update the entire graph status. When in parallel, should wait for all parallel tasks to complete before executing uniformly
        self.forward_exam(self.root_node, verbose, ctx)

        # --- Emit StepFinished ---
        step_duration = time.monotonic() - step_start_time
        emit_step_finished(
            step=step,
            node_id=need_next_step_node.hashkey,
            action_name=action_name,
            status_after=need_next_step_node.status.name,
            duration=step_duration,
            ctx=ctx,  # Pass the context used in this step
        )
        if verbose:
            display_plan(self.root_node.inner_graph)
        return None  # Explicitly return None if not done

    @log_typing
    def forward_one_step_untill_done(
        self,
        full_step: bool = False,
        parallel: bool = False,
        save_folder: Optional[str] = None,
        nl: bool = False,
        nodes_json_file: Optional[str] = None,
        *action_args: Any,
        **action_kwargs: Any,
    ) -> str:
        """
        Run the graph execution process until all nodes are finished or a step limit is reached.

        Repeatedly calls `forward_one_step_not_parallel` until the graph is complete
        or the maximum number of steps (10000) is exceeded. Saves the state
        after each step if `save_folder` is provided.

        Args:
            full_step (bool, optional): Passed to `forward_one_step_not_parallel`. Defaults to False.
            parallel (bool, optional): Currently unused. Defaults to False.
            save_folder (str, optional): Folder to save state after each step. Defaults to None.
            nl (bool, optional): Currently unused. Defaults to False.
            nodes_json_file (str, optional): Path to save the final node structure as JSON. Defaults to None.
            *action_args: Positional arguments passed to the node's action method.
            **action_kwargs: Keyword arguments passed to the node's action method.

        Returns:
            str: The final result from the root node's execution, or "Out of Step" if the step limit was reached.
        """
        self.root_node.status = TaskStatus.READY
        step: int = 0
        final_answer: str = ""
        for step in range(10000):
            logger.info("Step {}".format(step))
            ret = self.forward_one_step_not_parallel(
                step=step,
                full_step=False,  # Note: full_step arg passed from here seems ignored in the call above
                log_fn="logs/temp/{}".format(step),
                nodes_json_file=nodes_json_file,  # Pass directly, internal method handles logic
                *action_args,
                **action_kwargs,
            )
            if save_folder:
                self.save(save_folder)

            if ret == "done":
                # Final save is handled inside forward_one_step_not_parallel when ret == "done"
                # and also after the loop completes, so no extra save needed here.
                break

            if (
                step >= 3000
            ):  # Changed from > 3000 to >= 3000 for consistency with log message
                logger.error("Step >= 3000, break")
                break

        if step < 3000:  # Changed from <= 3000 to < 3000 for consistency
            # Assuming get_node_final_result returns a Dict with a 'result' key
            final_result_data: Optional[Dict[str, Any]] = (
                self.root_node.get_node_final_result()
            )
            if final_result_data and isinstance(final_result_data.get("result"), str):
                final_answer = final_result_data["result"]
            else:
                final_answer = "Error: Could not retrieve final result."
                logger.error(f"Unexpected final result format: {final_result_data}")
        else:
            final_answer = "Out of Step"
        logger.info("Final Result: \n{}".format(final_answer))
        return final_answer
