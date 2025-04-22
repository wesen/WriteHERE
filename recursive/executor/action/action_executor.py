from typing import Dict, List, Union, Optional
import time  # For timing
import json  # For args summary
from loguru import logger  # Added logger

from recursive.common.context import ExecutionContext
from recursive.executor.schema import (
    ActionReturn,
    ActionValidCode,
    ActionStatusCode,
)  # Added ActionStatusCode
from .base import BaseAction
from .builtin_actions import FinishAction, InvalidAction, NoAction
from recursive.utils.event_bus import emit_tool_invoked, emit_tool_returned


class ActionExecutor:
    """The action executor class.

    Args:
        actions (Union[BaseAction, List[BaseAction]]): The action or actions.
        invalid_action (BaseAction, optional): The invalid action. Defaults to
            InvalidAction().
        no_action (BaseAction, optional): The no action.
            Defaults to NoAction().
        finish_action (BaseAction, optional): The finish action. Defaults to
            FinishAction().
        finish_in_action (bool, optional): Whether the finish action is in the
            action list. Defaults to False.
    """

    def __init__(
        self,
        actions: Union[BaseAction, List[BaseAction]],
        invalid_action: BaseAction = InvalidAction(),
        no_action: BaseAction = NoAction(),
        finish_action: BaseAction = FinishAction(),
        finish_in_action: bool = False,
    ):
        if isinstance(actions, BaseAction):
            actions = [actions]

        for action in actions:
            assert isinstance(
                action, BaseAction
            ), f"action must be BaseAction, but got {type(action)}"
        if finish_in_action:
            actions.append(finish_action)
        self.actions = {action.name: action for action in actions}
        self.invalid_action = invalid_action
        self.no_action = no_action
        self.finish_action = finish_action

    def get_actions_info(self) -> List[Dict]:
        actions = []
        for action_name, action in self.actions.items():
            if not action.enable:
                continue
            if action.is_toolkit:
                for api in action.description["api_list"]:
                    api_desc = api.copy()
                    api_desc["name"] = f"{action_name}.{api_desc['name']}"
                    actions.append(api_desc)
            else:
                action_desc = action.description.copy()
                actions.append(action_desc)
        return actions

    def is_valid(self, name: str):
        return name in self.actions and self.actions[name].enable

    def action_names(self, only_enable: bool = True):
        if only_enable:
            return [k for k, v in self.actions.items() if v.enable]
        else:
            return list(self.actions.keys())

    def add_action(self, action: BaseAction):
        assert isinstance(
            action, BaseAction
        ), f"action must be BaseAction, but got {type(action)}"
        self.actions[action.name] = action

    def del_action(self, name: str):
        if name in self.actions:
            del self.actions[name]

    def __call__(
        self, name: str, command: str, ctx: Optional[ExecutionContext] = None
    ) -> ActionReturn:
        action_name, api_name = name.split(".") if "." in name else (name, "run")
        tool_start_time = time.monotonic()
        action_return = None
        error_msg = None

        if not self.is_valid(action_name):
            if name == self.no_action.name:
                action_return = self.no_action(command)
            elif name == self.finish_action.name:
                action_return = self.finish_action(command)
            else:
                action_return = self.invalid_action(command)
        else:
            # --- Emit ToolInvoked ---
            try:
                # Attempt to parse command for better summary, fallback to raw string
                args_summary = json.dumps(json.loads(command))
            except:
                args_summary = str(command)

            emit_tool_invoked(
                tool_name=action_name,
                api_name=api_name,
                args_summary=args_summary,
                ctx=ctx,
            )

            try:
                action_return = self.actions[action_name](command, api_name)
                action_return.valid = ActionValidCode.OPEN
            except Exception as e:
                logger.error(f"Tool execution failed for {action_name}.{api_name}: {e}")
                error_msg = str(e)
                # Create a minimal ActionReturn on error
                action_return = ActionReturn(
                    args={},
                    type=action_name,
                    errmsg=error_msg,
                    state=ActionStatusCode.API_ERROR,
                )

        tool_duration = time.monotonic() - tool_start_time

        # --- Emit ToolReturned ---
        result_summary = (
            str(action_return.result) if hasattr(action_return, "result") else "N/A"
        )

        # Handle potential AttributeError if action_return doesn't have 'state'
        # Also handle case where state might be an int instead of enum
        if hasattr(action_return, "state"):
            if action_return.state is None:
                state_name = ActionStatusCode.API_ERROR.name
            elif isinstance(action_return.state, int):
                # Handle case where state is an int, not an enum
                try:
                    # Try to convert int to enum
                    state_name = ActionStatusCode(action_return.state).name
                except ValueError:
                    # If int doesn't match any enum value, fallback to API_ERROR
                    state_name = ActionStatusCode.API_ERROR.name
            else:
                # Normal case where state is an enum
                state_name = action_return.state.name
        else:
            state_name = ActionStatusCode.API_ERROR.name

        emit_tool_returned(
            tool_name=action_name,
            api_name=api_name,
            state=state_name,
            duration=tool_duration,
            result_summary=result_summary,
            error=error_msg
            or getattr(action_return, "errmsg", None),  # Prioritize direct exception
            ctx=ctx,
        )

        return action_return
