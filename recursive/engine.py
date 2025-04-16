# coding:utf8

from collections import deque
from recursive.common.enums import TaskStatus
from recursive.utils.display import display_plan
from recursive.memory import Memory
import dill as pickle
import json
from loguru import logger


class GraphRunEngine:
    """ """

    def __init__(self, root_node, memory_format, config):
        self.root_node = root_node
        self.memory = Memory(root_node, format=memory_format, config=config)

    def find_need_next_step_nodes(self, single=False):
        nodes = []
        queue = deque([self.root_node])
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

    def save(self, folder):
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

    def load(self, folder):
        root_node_file = "{}/nodes.pkl".format(folder)
        with open(root_node_file, "rb") as f:
            self.root_node = pickle.load(f)

        self.memory = self.memory.load(folder)

    def forward_exam(self, node, verbose):
        # The exam order is bottom-up hierarchically, and top-down based on dependencies.
        # not_ready -> ready: Need to check the execution status of dependent nodes, and whether upper-level nodes have entered the doing state
        # doing -> final_to_finish: Need to check if all lower-level nodes have finished
        # plan_reflection_done -> doing:
        if node.is_suspend:
            for inner_node in node.topological_task_queue:
                self.forward_exam(inner_node, verbose)
            node.do_exam(verbose)

    def forward_one_step_not_parallel(
        self,
        full_step=False,
        select_node_hashkey=None,
        log_fn=None,
        nodes_json_file=None,
        *action_args,
        **action_kwargs
    ):
        # Find tasks that need to enter the next step
        if select_node_hashkey is not None:
            need_next_step_node = self.find_need_next_step_nodes(single=False)
            for node in need_next_step_node:
                if node.hashkey == select_node_hashkey:
                    break
            else:
                raise Exception(
                    "Error, the select node {} can not be executed".format(
                        select_node_hashkey
                    )
                )
            need_next_step_node = node
        else:
            need_next_step_node = self.find_need_next_step_nodes(single=True)
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
        # Execute the next step for this node
        # Update Memory
        self.memory.update_infos([need_next_step_node])

        # Update nodes.json after each step if path provided
        if nodes_json_file:
            with open(nodes_json_file, "w") as f:
                json.dump(self.root_node.to_json(), f, indent=4, ensure_ascii=False)

        if not full_step:
            action_name, action_result = need_next_step_node.next_action_step(
                self.memory, *action_args, **action_kwargs
            )
        else:
            action_name = need_next_step_node.next_full_action_step(self.memory)

        verbose = action_name not in (
            "update",
            "prior_reflect",
            "planning_post_reflect",
            "execute_post_reflect",
        )

        # After the action ends, update the entire graph status. When in parallel, should wait for all parallel tasks to complete before executing uniformly
        self.forward_exam(self.root_node, verbose)

        if verbose:
            display_plan(self.root_node.inner_graph)

    def forward_one_step_untill_done(
        self,
        full_step=False,
        parallel=False,
        save_folder=None,
        nl=False,
        nodes_json_file=None,
        *action_args,
        **action_kwargs
    ):
        self.root_node.status = TaskStatus.READY
        for step in range(10000):
            logger.info("Step {}".format(step))
            ret = self.forward_one_step_not_parallel(
                full_step=False,
                log_fn="logs/temp/{}".format(step),
                nodes_json_file=nodes_json_file,
                *action_args,
                **action_kwargs
            )
            self.save(save_folder)
            if ret == "done":
                break

            if step > 3000:
                logger.error("Step > 3000, break")
                break

        if step <= 3000:
            final_answer = self.root_node.get_node_final_result()["result"]
        else:
            final_answer = "Out of Step"
        logger.info("Final Result: \n{}".format(final_answer))
        return final_answer
