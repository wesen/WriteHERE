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
from recursive.utils.event_bus import (
    emit_run_started,
    emit_run_finished,
    emit_run_error,
)
from recursive.common.context import ExecutionContext


def story_writing(
    input_filename,
    output_filename,
    start,
    end,
    done_flag_file,
    global_use_model,
    nodes_json_file=None,
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
    }
    start_time = time.time()

    try:
        config = {
            "language": "en",
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
            "COMPOSITION": {
                "execute": {
                    "prompt_version": "StoryWrtingNLWriterEN",
                    "llm_args": {"model": global_use_model, "temperature": 0.3},
                    "parse_arg_dict": {
                        "result": ["article"],
                    },
                },
                "atom": {
                    "update_diff": True,
                    "without_update_prompt_version": "StoryWritingNLWriteAtomEN",
                    "with_update_prompt_version": "StoryWritingNLWriteAtomWithUpdateEN",
                    "llm_args": {"model": global_use_model, "temperature": 0.1},
                    "parse_arg_dict": {
                        "atom_think": ["think"],
                        "atom_result": ["atomic_task_determination"],
                        "update_result": ["goal_updating"],
                    },
                    "atom_result_flag": "atomic",
                },
                "planning": {
                    "prompt_version": "StoryWritingNLPlanningEN",
                    "llm_args": {"model": global_use_model, "temperature": 0.1},
                    "parse_arg_dict": {
                        "plan_think": ["think"],
                        "plan_result": ["result"],
                    },
                },
                "update": {},
                "final_aggregate": {},
            },
            "RETRIEVAL": {"all_atom": True},
            "REASONING": {
                "execute": {
                    "prompt_version": "StoryWrtingNLReasonerEN",
                    "llm_args": {"model": global_use_model, "temperature": 0.3},
                    "parse_arg_dict": {
                        "result": ["result"],
                    },
                },
                "atom": {"use_candidate_plan": True},
                "planning": {},
                "update": {},
                "final_aggregate": {
                    "prompt_version": "StoryWritingReasonerFinalAggregate",
                    "mode": "llm",
                    "parse_arg_dict": {
                        "result": ["result"],
                    },
                },
            },
        }
        config["tag2task_type"] = {v: k for k, v in config["task_type2tag"].items()}

        data = read_jsonl(input_filename)
        items = data[start:end]

        # Emit run_started event with enhanced config
        start_time_utc = datetime.now(timezone.utc)
        event_config = {
            "model": global_use_model,
            "start": start,
            "end": end,
            "planning_config": {
                "language": config["language"],
                "task_types": list(config["task_type2tag"].keys()),
                "agents": {k: v[0] for k, v in config["action_mapping"].items()},
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
            run_mode="story",
            timestamp_utc=start_time_utc,
            ctx=ctx,
        )

        import pathlib

        root_folder = "{}/{}".format(
            str(pathlib.Path(output_filename).parent.parent), "records"
        )
        caches["search"] = Cache(
            "{}/../cache/{}-{}-search".format(root_folder, start, end)
        )
        caches["llm"] = Cache("{}/../cache/{}-{}-llm".format(root_folder, start, end))

        import os

        if os.path.exists(output_filename):
            done_ques = [item["ori"]["inputs"] for item in read_jsonl(output_filename)]
            filtered_items = [
                item for item in items if item["ori"]["inputs"] not in done_ques
            ]
            print(
                "Has Done {} item, left {} items to run".format(
                    len(done_ques), len(filtered_items)
                )
            )
            items = filtered_items

        output_f = open(output_filename, "w", encoding="utf8")
        print("Need Run {} items".format(len(items)), flush=True)

        for item in items:
            question = item["ori"]["inputs"]
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
                    "length": "determine based on the task requirements:",
                    "dependency": [],
                },
                node_type=NodeType.PLAN_NODE,
                ctx=ctx,
            )
            root_node.node_graph_info["root_node"] = root_node
            engine = GraphRunEngine(root_node, "xml", config, initial_ctx=ctx)
            import os

            qstr = item["id"]
            folder = "{}/{}".format(root_folder, qstr)
            os.makedirs(folder, exist_ok=True)
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

            item["result"] = result
            output_f.write(json.dumps(item, ensure_ascii=False) + "\n")
            output_f.flush()

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
            ctx=ctx,
        )

    except Exception as e:
        # Emit run_error event for any unhandled exceptions
        error_context = {
            "last_successful_step": stats["total_steps"],
            "total_processed_items": len(items) if "items" in locals() else 0,
            "last_item_id": qstr if "qstr" in locals() else None,
        }

        emit_run_error(
            error_type=e.__class__.__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            context=error_context,
            ctx=ctx,
        )
        raise  # Re-raise the exception after logging
