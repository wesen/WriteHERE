import json
import traceback
from datetime import datetime

from loguru import logger

from recursive.cache import Cache
from recursive.common.enums import NodeType
from recursive.engine import GraphRunEngine
from recursive.utils.read_jsonl import read_jsonl
from recursive.memory import caches
from recursive.node.regular_dummy import RegularDummyNode
from recursive.utils.get_index import get_report_with_ref


def report_writing(
    input_filename,
    output_filename,
    start,
    end,
    done_flag_file,
    global_use_model,
    engine_backend,
    nodes_json_file=None,
    today_date=None,
):
    # Use current date if not provided
    if today_date is None:
        today_date = datetime.now().strftime("%b %d, %Y")
    config = {
        "language": "en",
        # Agent is Defined in recursive.agent.agent.regular
        # update, prior_reflect, planning_post_reflect and execute_post_reflect is skipped, by using Dummy Agent
        # prompt is Defined in recursive.agent.prompts
        "today_date": today_date,  # Add the today_date parameter to config
        "action_mapping": {
            "plan": ["UpdateAtomPlanningAgent", {}],
            "update": ["DummyRandomUpdateAgent", {}],
            "execute": ["SimpleExecutor", {}],
            "final_aggregate": ["FinalAggregateAgent", {}],
            "prior_reflect": ["DummyRandomPriorReflectionAgent", {}],
            "planning_post_reflect": ["DummyRandomPlanningPostReflectionAgent", {}],
            "execute_post_reflect": ["DummyRandomExecutorPostReflectionAgent", {}],
        },
        "task_type2tag": {
            "COMPOSITION": "write",
            "REASONING": "think",
            "RETRIEVAL": "search",
        },
        "require_keys": {
            "COMPOSITION": ["id", "dependency", "goal", "task_type", "length"],
            "RETRIEVAL": ["id", "dependency", "goal", "task_type"],
            "REASONING": ["id", "dependency", "goal", "task_type"],
        },
        "offer_global_writing_plan": True,
        "COMPOSITION": {
            "execute": {
                "prompt_version": "ReportWriter",
                "llm_args": {"model": global_use_model, "temperature": 0.3},
                "parse_arg_dict": {
                    "result": ["article"],
                },
            },
            "atom": {
                "update_diff": True,  # Combine Atom and Update, see agent.agents.regular.get_llm_output
                "without_update_prompt_version": "ReportAtom",
                "with_update_prompt_version": "ReportAtomWithUpdate",
                "llm_args": {"model": global_use_model, "temperature": 0.1},
                "parse_arg_dict": {  # parse args from llm output in xml format
                    "atom_think": ["think"],
                    "atom_result": ["atomic_task_determination"],
                    "update_result": ["goal_updating"],
                },
                "atom_result_flag": "atomic",
                "force_atom_layer": 3,  # >= 3, force to atom and skip atom judgement
            },
            "planning": {
                "prompt_version": "ReportPlanning",
                "llm_args": {"model": global_use_model, "temperature": 0.1},
                "parse_arg_dict": {
                    "plan_think": ["think"],
                    "plan_result": ["result"],
                },
            },
            "update": {},
            "final_aggregate": {},
        },
        "RETRIEVAL": {
            "execute": {
                "react_agent": True,  # use Search Agent
                "prompt_version": "SearchAgentENPrompt",  # see recursive.agent.prompts.search_agent.main
                "searcher_type": "SerpApiSearch",  # see recursive.executor.action.bing_browser
                "llm_args": {
                    "model": global_use_model,  # set the llm
                },
                "parse_arg_dict": {
                    "result": ["result"],
                },
                "react_parse_arg_dict": {  # for search agent, parse result from xml format llm response
                    "observation": ["observation"],
                    "missing_info": ["missing_info"],
                    "think": ["planning_and_think"],
                    "action_think": ["current_turn_query_think"],
                    "search_querys": ["current_turn_search_querys"],
                },
                "temperature": 0.2,  # search agent
                "max_turn": 4,  # search agent max turn
                "llm_merge": True,  # use llm to merge search agent result, see recursive.agent.agent.regular.SimpleExcutor.search_merge, the prompt is set in config
                "only_use_react_summary": False,
                "webpage_helper_max_threads": 10,  # use requests to download web page
                "search_max_thread": 4,  # serpapi parallel
                "backend_engine": engine_backend,  # google or bing, defined in serpapi
                "cc": "US",  # search region
                "topk": 20,
                "pk_quota": 20,  # search agent, pk quota, see __search
                "select_quota": 20,  # search agent select quota
                "selector_max_workers": 8,  # selector parallel
                "summarizier_max_workers": 8,  # summarizer parallel
                "selector_model": "gpt-4o-mini",
                "summarizer_model": "gpt-4o-mini",
            },
            "search_merge": {
                "prompt_version": "MergeSearchResultVFinal",  # search merge prompt
                "llm_args": {
                    "model": global_use_model,
                },
                "parse_arg_dict": {
                    "result": ["result"],
                },
            },
            "atom": {
                "prompt_version": "ReportSearchOnlyUpdate",
                "llm_args": {
                    "model": global_use_model,
                },
                "parse_arg_dict": {
                    "atom_think": ["think"],
                    "update_result": ["goal_updating"],
                },
                "all_atom": True,
                "only_on_depend": True,
            },
            "planning": {},
            "update": {},
            "final_aggregate": {},
        },
        "REASONING": {
            "execute": {
                "prompt_version": "ReportReasoner",
                "llm_args": {"model": global_use_model, "temperature": 0.3},
                "parse_arg_dict": {
                    "think": ["think"],
                    "result": ["result"],
                },
            },
            "atom": {
                # "use_candidate_plan": True
                "all_atom": True  # force to atom
            },
            "planning": {},
            "update": {},
            "final_aggregate": {},
        },
    }
    config["tag2task_type"] = {v: k for k, v in config["task_type2tag"].items()}

    data = read_jsonl(input_filename)
    items = data[start:end]

    import pathlib

    root_folder = "{}/{}".format(
        str(pathlib.Path(output_filename).parent.parent), "records"
    )
    caches["search"] = Cache(
        "{}/../cache/{}-{}-search".format(root_folder, start, end)
    )  # cache search and llm result
    caches["llm"] = Cache("{}/../cache/{}-{}-llm".format(root_folder, start, end))

    import os

    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    if os.path.exists(output_filename):
        done_ques = [item["prompt"] for item in read_jsonl(output_filename)]
        filtered_items = [item for item in items if item["prompt"] not in done_ques]
        print(
            "Has Done {} item, left {} items to run".format(
                len(done_ques), len(filtered_items)
            )
        )
        items = filtered_items

    output_f = open(output_filename, "a", encoding="utf8")
    for item in items:
        question = item["prompt"]
        root_node = RegularDummyNode(
            config=config,
            nid="",
            node_graph_info={
                "outer_node": None,
                "root_node": None,
                "parent_nodes": [],
                "layer": 0,
            },
            task_info={
                "goal": question,
                "task_type": "write",
                "length": "You should determine itself, according to the question",
                "dependency": [],
            },
            node_type=NodeType.PLAN_NODE,
        )
        root_node.node_graph_info["root_node"] = root_node
        engine = GraphRunEngine(root_node, "xml", config)
        import os

        qstr = item["id"]
        folder = "{}/{}".format(root_folder, qstr)
        os.makedirs(folder, exist_ok=True)
        rf = open("{}/report.md".format(folder), "w")

        custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        log_id = logger.add("{}/engine.log".format(folder), format=custom_format)
        try:
            result = engine.forward_one_step_untill_done(
                save_folder=folder, nl=True, nodes_json_file=nodes_json_file
            )
        except Exception as e:
            logger.error(
                "Encounter exception: {}\nWhen Process {}".format(
                    traceback.format_exc(), question
                )
            )
            continue

        result = get_report_with_ref(engine.root_node.to_json(), result)
        item["result"] = result
        output_f.write(json.dumps(item, ensure_ascii=False) + "\n")
        output_f.flush()
        rf.write(item["result"])
        rf.flush()
        rf.close()

        logger.remove(log_id)

    if done_flag_file is not None:
        with open(done_flag_file, "w") as f:
            f.write("done")
