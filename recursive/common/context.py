import contextvars
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T", bound="ExecutionContext")


@dataclass(frozen=True)
class ExecutionContext:
    """
    Immutable context object to track execution state like step number,
    current node ID, and task type.

    Use the `with_` method to create a new context with updated fields.
    """

    step: Optional[int] = None
    node_id: Optional[str] = None
    task_type: Optional[str] = None
    action_name: Optional[str] = None
    node_status: Optional[str] = None
    node_next_status: Optional[str] = None
    task_goal: Optional[str] = None
    agent_class: Optional[str] = None
    parent_node_ids: Optional[List[str]] = None
    # Add other fields as needed, e.g., run_id

    def with_(self: T, **kwargs: Any) -> T:
        """
        Create a new ExecutionContext instance with updated attributes.

        Example:
            ctx = ExecutionContext(step=1)
            new_ctx = ctx.with_(node_id="node123")
            # new_ctx has step=1 and node_id="node123"
            # ctx still only has step=1
        """
        current_values = self.to_dict()
        current_values.update(kwargs)
        return self.__class__(**current_values)

    # Optional: Method to convert to dict for logging/serialization if needed
    def to_dict(self) -> Dict[str, Any]:
        """Convert the context to a dictionary, excluding None values."""
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if getattr(self, f.name) is not None
        }
