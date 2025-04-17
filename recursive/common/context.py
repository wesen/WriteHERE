from typing import Optional
from pydantic import BaseModel


class ExecutionContext(BaseModel):
    """Holds contextual information about the current execution state."""

    step: Optional[int] = None
    # Add other relevant context here in the future if needed
