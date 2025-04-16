# coding:utf8

from abc import ABC, abstractmethod

from recursive.llm.base import OpenAIApiProxy
from recursive.utils.parsing import parse_hierarchy_tags_result
from loguru import logger
from datetime import datetime
import os
import yaml
from typing import Any

from recursive.node.abstract import AbstractNode
from recursive.memory import Memory


class Agent(ABC):
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.args = args
        # Create debug/logs/llm directory if it doesn't exist
        os.makedirs("debug/logs/llm", exist_ok=True)

    @abstractmethod
    def forward(self, node: AbstractNode, memory: Memory, *args: Any, **kwargs: Any):
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
        logger.info(message[-1]["content"])

        model = other_inner_args.pop("model", "gpt-4o")

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

        resp = llm.call(messages=message, model=model, **other_inner_args)[0]
        if "r1" in model:
            reason = resp["message"]["reasoning_content"]
        else:
            reason = ""
        content = resp["message"]["content"]
        logger.info("Get REASONING: {}\n\nResult: {}".format(reason, content))

        # Update log data with response
        log_data.update(
            {"response": {"content": content, "reason": reason, "raw_response": resp}}
        )

        assert isinstance(parse_arg_dict, dict)
        result = {"original": content, "result": content, "reason": reason}

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

        return result
