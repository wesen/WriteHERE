import json
import traceback
from datetime import datetime, timezone
import time
from typing import Optional

from loguru import logger

from recursive.cache import Cache
from recursive.common.enums import NodeType
from recursive.engine import GraphRunEngine
from recursive.utils.read_jsonl import read_jsonl
from recursive.memory import caches
from recursive.node.regular_dummy import RegularDummyNode
from recursive.utils.get_index import get_report_with_ref
from recursive.utils.event_bus import (
    emit_run_started,
    emit_run_finished,
    emit_run_error,
)
from recursive.common.context import ExecutionContext


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
    ctx: Optional[ExecutionContext] = None,
):
    # Statistics for run_finished event
    stats = {
        "total_steps": 0,
        "total_nodes": 0,
        "total_llm_calls": 0,
        "total_tool_calls": 0,
        "token_usage": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
        },
        "node_statistics": {
            "total_created": 0,
            "total_completed": 0,
            "by_type": {},
        },
        "search_statistics": {
            "total_searches": 0,
            "total_pages_processed": 0,
            "total_search_tokens": 0,
        },
    }
    start_time = time.time()

    try:
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

        # Emit run_started event with enhanced config
        start_time_utc = datetime.now(timezone.utc)
        event_config = {
            "model": global_use_model,
            "engine_backend": engine_backend,
            "start": start,
            "end": end,
            "today_date": today_date,
            "planning_config": {
                "language": config["language"],
                "task_types": list(config["task_type2tag"].keys()),
                "agents": {k: v[0] for k, v in config["action_mapping"].items()},
                "offer_global_writing_plan": config["offer_global_writing_plan"],
                "composition_settings": {
                    "prompt_versions": {
                        "execute": config["COMPOSITION"]["execute"]["prompt_version"],
                        "atom": {
                            "without_update": config["COMPOSITION"]["atom"][
                                "without_update_prompt_version"
                            ],
                            "with_update": config["COMPOSITION"]["atom"][
                                "with_update_prompt_version"
                            ],
                        },
                        "planning": config["COMPOSITION"]["planning"]["prompt_version"],
                    },
                    "force_atom_layer": config["COMPOSITION"]["atom"][
                        "force_atom_layer"
                    ],
                },
                "retrieval_settings": {
                    "search_config": {
                        "backend": engine_backend,
                        "region": config["RETRIEVAL"]["execute"]["cc"],
                        "max_turn": config["RETRIEVAL"]["execute"]["max_turn"],
                        "topk": config["RETRIEVAL"]["execute"]["topk"],
                        "quota": config["RETRIEVAL"]["execute"]["pk_quota"],
                    },
                    "prompt_versions": {
                        "search_agent": config["RETRIEVAL"]["execute"][
                            "prompt_version"
                        ],
                        "merge": config["RETRIEVAL"]["search_merge"]["prompt_version"],
                    },
                },
            },
        }

        # Add input data summary
        input_data_summary = {
            "filename": input_filename,
            "data": data,
        }

        emit_run_started(
            input_data=input_data_summary,
            config=event_config,
            run_mode="report",
            timestamp_utc=start_time_utc,
            ctx=ctx,
        )

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
            engine = GraphRunEngine(root_node, "xml", config, initial_ctx=ctx)
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

                # Update statistics after each successful item
                stats["total_steps"] += engine.step
                stats["total_nodes"] += len(engine.root_node.to_json()["nodes"])
                # Note: LLM and tool calls would need to be tracked in the respective agents/executors

            except Exception as e:
                logger.error(
                    "Encounter exception: {}\nWhen Process {}".format(
                        traceback.format_exc(), question
                    )
                )
                continue
            finally:
                logger.remove(log_id)
                rf.close()

            result = get_report_with_ref(engine.root_node.to_json(), result)
            item["result"] = result
            output_f.write(json.dumps(item, ensure_ascii=False) + "\n")
            output_f.flush()
            rf.write(item["result"])
            rf.flush()

        if done_flag_file is not None:
            with open(done_flag_file, "w") as f:
                f.write("done")

        # Emit run_finished event
        duration = time.time() - start_time
        emit_run_finished(
            total_steps=stats["total_steps"],
            duration_seconds=duration,
            total_nodes=stats["total_nodes"],
            total_llm_calls=stats["total_llm_calls"],
            total_tool_calls=stats["total_tool_calls"],
            token_usage_summary=stats["token_usage"],
            node_statistics=stats["node_statistics"],
            search_statistics=stats[
                "search_statistics"
            ],  # Additional report-specific stats
            ctx=ctx,
        )

    except Exception as e:
        # Emit run_error event for any unhandled exceptions
        error_context = {
            "last_successful_step": stats["total_steps"],
            "total_processed_items": len(items) if "items" in locals() else 0,
            "last_item_id": qstr if "qstr" in locals() else None,
            "engine_backend": engine_backend,  # Additional report-specific context
        }

        emit_run_error(
            error_type=e.__class__.__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            context=error_context,
            ctx=ctx,
        )
        raise  # Re-raise the exception after logging
