from dataclasses import dataclass, field, replace
from typing import Optional, Any, Dict


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
    # Add other fields as needed, e.g., run_id

    def with_(self, **changes: Any) -> "ExecutionContext":
        """
        Creates a new ExecutionContext instance with updated fields.

        Args:
            **changes: Keyword arguments mapping field names to new values.

        Returns:
            A new ExecutionContext instance with the specified changes.
        """
        return replace(self, **changes)

    # Optional: Method to convert to dict for logging/serialization if needed
    def to_dict(self) -> Dict[str, Any]:
        return {
            f.name: getattr(self, f.name)
            for f in field(self)  # type: ignore
            if getattr(self, f.name) is not None
        }
