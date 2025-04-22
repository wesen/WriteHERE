# coding:utf8

from abc import ABC, abstractmethod

from recursive.llm.base import OpenAIApiProxy
from recursive.utils.parsing import parse_hierarchy_tags_result
from loguru import logger
from datetime import datetime
import os
import time  # For timing
import yaml
from typing import Any, Optional  # Added Optional
import hashlib  # For hashing prompt (optional)

from recursive.node.abstract import AbstractNode
from recursive.memory import Memory
from recursive.utils.event_bus import emit_llm_call_started, emit_llm_call_completed
from recursive.common.context import ExecutionContext  # Added import


class Agent(ABC):
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.args = args
        # Create debug/logs/llm directory if it doesn't exist
        os.makedirs("debug/logs/llm", exist_ok=True)

    @abstractmethod
    def forward(
        self, node: AbstractNode, memory: Memory, *args: Any, **kwargs: Any
    ) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def parse_result(self, agent_output: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError()

    def call_llm(
        self,
        system_message,
        prompt,
        parse_arg_dict,
        history_message=None,
        ctx: Optional[ExecutionContext] = None,  # Added ctx argument
        node: Optional[AbstractNode] = None,
        **other_inner_args,
    ):
        llm = OpenAIApiProxy()

        if system_message.strip() == "":
            message = []
        else:
            message = [
                {"role": "system", "content": system_message},
            ]
        if history_message is not None:
            message.append(history_message)
        message.append({"role": "user", "content": prompt})
        logger.debug(message[-1]["content"])

        model = other_inner_args.pop("model", "gpt-4o")
        # step = ctx.step if ctx else None  # Get step from context - No longer needed here

        llm_call_start_time = time.monotonic()
        node_id = node.hashkey if node else None

        # Log the request before making the call
        timestamp = datetime.now().strftime("%Y-%m-%d--%H-%M-%S-%f")
        agent_name = self.__class__.__name__
        log_file = f"debug/logs/llm/{timestamp}--{agent_name}.yaml"

        log_data = {
            "timestamp": timestamp,
            "agent": agent_name,
            "model": model,
            "messages": message,
            "other_args": other_inner_args,
        }

        # Create context with agent_class
        agent_ctx = (
            ctx.with_(agent_class=agent_name)
            if ctx
            else ExecutionContext(agent_class=agent_name)
        )

        # --- Emit LLMCallStarted ---
        # Use a truncated prompt or a hash for the event payload
        # prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        emit_llm_call_started(
            agent_class=agent_name,  # Keep explicit agent_class for direct access if needed
            model=model,
            prompt_messages=message,  # Pass full message list
            prompt_preview=prompt[:200] + "...",
            ctx=agent_ctx,  # Pass the enhanced context object
        )

        error_msg = None
        token_usage = None
        # Initialize result and response data structure
        resp_data = {}  # Store raw response for logging
        content = ""  # Initialize content
        reason = ""  # Initialize reason
        result = {}  # Initialize result dict

        try:
            resp = llm.call(messages=message, model=model, **other_inner_args)[0]
            resp_data = resp  # Store raw response
            reason = (
                resp["message"].get("reasoning_content", "") if "r1" in model else ""
            )
            content = resp["message"].get("content", "")
            logger.info("Get REASONING: {}\n\nResult: {}".format(reason, content))
            token_usage = resp.get("usage")  # Assuming usage info is in the response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            error_msg = str(e)
            content = f"ERROR: {error_msg}"  # Include error in content for clarity
            reason = ""

        llm_call_duration = time.monotonic() - llm_call_start_time

        # Update log data with response
        log_data.update(
            {
                "response": {
                    "content": content,
                    "reason": reason,
                    "raw_response": resp_data,
                }
            }
        )

        assert isinstance(parse_arg_dict, dict)
        result = {"original": content, "result": content, "reason": reason}

        # --- Emit LLMCallCompleted ---
        emit_llm_call_completed(
            agent_class=agent_name,  # Keep explicit agent_class for direct access if needed
            model=model,
            duration=llm_call_duration,
            response_content=content,  # Pass full content
            error=error_msg,
            ctx=agent_ctx,  # Pass the enhanced context object
            token_usage=token_usage,
        )

        """  
        The following code extracts structured information from an LLM's textual response by looking for content within specific XML-like tags. It works by:

        1. Iterating through each key-value pair in parse_arg_dict which maps output keys to tag patterns
        2. For each pair, it calls parse_hierarchy_tags_result() which extracts text enclosed in those specific XML-like tags
        3. The extracted content is stripped of whitespace and stored in the result dictionary under the corresponding key

        For example, if the LLM response contains <reasoning>Some analysis here</reasoning> and parse_arg_dict has {"thought": "reasoning"}, the function would extract "Some
        analysis here" and store it under result["thought"].
        """
        log_data["structured_output"] = {}
        for key, value in parse_arg_dict.items():
            result[key] = parse_hierarchy_tags_result(content, value).strip()
            log_data["structured_output"][key] = result[key]

        # Write log to file
        with open(log_file, "w") as f:
            yaml.safe_dump(log_data, f, default_flow_style=False, allow_unicode=True)

        # Add status based on error
        result["status"] = "success" if error_msg is None else "error"
        return result
